import threading
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.main import create_app


def _setup_story_and_task(client: TestClient) -> tuple[dict[str, str], dict, dict, dict]:
    client.post(
        "/api/v1/auth/register",
        json={"email": "occ@example.com", "name": "OCC User", "password": "StrongPassword123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "occ@example.com", "password": "StrongPassword123"},
    )
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    project = client.post(
        "/api/v1/projects",
        json={"key": "OCC", "name": "Concurrency Project"},
        headers=headers,
    ).json()
    story = client.post(
        f"/api/v1/projects/{project['id']}/stories",
        json={"title": "Original Story"},
        headers=headers,
    ).json()
    task = client.post(
        f"/api/v1/stories/{story['id']}/tasks",
        json={"title": "Original Task"},
        headers=headers,
    ).json()
    return headers, project, story, task


def _run_parallel_patches(
    db_session_factory: sessionmaker[Session],
    cookies: dict[str, str],
    headers: dict[str, str],
    path: str,
    payload_factory,
    num_threads: int,
) -> list[int]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    barrier = threading.Barrier(num_threads)
    statuses: list[int] = []
    lock = threading.Lock()

    def worker(idx: int) -> None:
        with TestClient(app) as tc:
            for k, v in cookies.items():
                tc.cookies.set(k, v)
            barrier.wait()
            res = tc.patch(path, json=payload_factory(idx), headers=headers)
            with lock:
                statuses.append(res.status_code)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return statuses


def test_story_and_task_optimistic_concurrency_returns_409(client: TestClient) -> None:
    headers, _project, story, task = _setup_story_and_task(client)

    # Missing version rejected with 422
    assert (
        client.patch(
            f"/api/v1/stories/{story['id']}",
            json={"title": "No Version"},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/v1/tasks/{task['id']}",
            json={"title": "No Version"},
            headers=headers,
        ).status_code
        == 422
    )

    # First editor updates story (v1 -> v2)
    s_ok = client.patch(
        f"/api/v1/stories/{story['id']}",
        json={"title": "Updated Story", "version": 1},
        headers=headers,
    )
    assert s_ok.status_code == 200
    assert s_ok.json()["version"] == 2

    # Second editor with stale v1 gets 409 Conflict
    s_conflict = client.patch(
        f"/api/v1/stories/{story['id']}",
        json={"title": "Stale Story Edit", "version": 1},
        headers=headers,
    )
    assert s_conflict.status_code == 409
    assert s_conflict.headers["content-type"].startswith("application/problem+json")
    assert s_conflict.json()["code"] == "VERSION_CONFLICT"

    # Stale move also gets 409
    s_move_conflict = client.post(
        f"/api/v1/stories/{story['id']}/move",
        json={"status": "in_progress", "version": 1},
        headers=headers,
    )
    assert s_move_conflict.status_code == 409
    assert s_move_conflict.json()["code"] == "VERSION_CONFLICT"

    # First editor updates task (v1 -> v2)
    t_ok = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"status": "doing", "version": 1},
        headers=headers,
    )
    assert t_ok.status_code == 200
    assert t_ok.json()["version"] == 2

    # Second editor with stale v1 gets 409 Conflict
    t_conflict = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"status": "done", "version": 1},
        headers=headers,
    )
    assert t_conflict.status_code == 409
    assert t_conflict.json()["code"] == "VERSION_CONFLICT"

    # Stale task move also gets 409
    t_move_conflict = client.post(
        f"/api/v1/tasks/{task['id']}/move",
        json={"status": "blocked", "version": 1},
        headers=headers,
    )
    assert t_move_conflict.status_code == 409
    assert t_move_conflict.json()["code"] == "VERSION_CONFLICT"


def test_parallel_story_patches_allow_exactly_one_winner(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    headers, _project, story, _task = _setup_story_and_task(client)
    cookies = dict(client.cookies)

    statuses = _run_parallel_patches(
        db_session_factory,
        cookies,
        headers,
        f"/api/v1/stories/{story['id']}",
        lambda i: {"title": f"Race Story {i}", "version": 1},
        num_threads=20,
    )
    assert statuses.count(200) == 1
    assert statuses.count(409) == 19


def test_parallel_task_patches_allow_exactly_one_winner(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    headers, _project, _story, task = _setup_story_and_task(client)
    cookies = dict(client.cookies)

    statuses = _run_parallel_patches(
        db_session_factory,
        cookies,
        headers,
        f"/api/v1/tasks/{task['id']}",
        lambda i: {"title": f"Race Task {i}", "version": 1},
        num_threads=12,
    )
    assert statuses.count(200) == 1
    assert statuses.count(409) == 11


def test_parallel_project_patches_allow_exactly_one_winner(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    headers, project, _story, _task = _setup_story_and_task(client)
    cookies = dict(client.cookies)

    statuses = _run_parallel_patches(
        db_session_factory,
        cookies,
        headers,
        f"/api/v1/projects/{project['id']}",
        lambda i: {"name": f"Race Project {i}", "version": 1},
        num_threads=12,
    )
    assert statuses.count(200) == 1
    assert statuses.count(409) == 11


def test_move_endpoints_require_version(client: TestClient) -> None:
    headers, _project, story, task = _setup_story_and_task(client)

    assert (
        client.post(
            f"/api/v1/stories/{story['id']}/move",
            json={"status": "in_progress"},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/tasks/{task['id']}/move",
            json={"status": "doing"},
            headers=headers,
        ).status_code
        == 422
    )
