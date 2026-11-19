from fastapi.testclient import TestClient


def _setup_story_and_task(client: TestClient) -> tuple[dict[str, str], dict, dict]:
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
    return headers, story, task


def test_story_and_task_optimistic_concurrency_returns_409(client: TestClient) -> None:
    headers, story, task = _setup_story_and_task(client)

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
