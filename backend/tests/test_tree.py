from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker


def _auth(client: TestClient) -> dict[str, str]:
    client.post(
        "/api/v1/auth/register",
        json={"email": "tree@example.com", "name": "Tree User", "password": "StrongPassword123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "tree@example.com", "password": "StrongPassword123"},
    )
    return {"X-CSRF-Token": login.json()["csrf_token"]}


def test_tree_endpoint_reflects_live_task_rollups_and_suggestions(client: TestClient) -> None:
    headers = _auth(client)
    project_id = client.post(
        "/api/v1/projects",
        json={"key": "TRE", "name": "Tree Project"},
        headers=headers,
    ).json()["id"]
    story_id = client.post(
        f"/api/v1/projects/{project_id}/stories",
        json={"title": "Build tree"},
        headers=headers,
    ).json()["id"]

    t1 = client.post(
        f"/api/v1/stories/{story_id}/tasks",
        json={"title": "Step 1", "estimate_hours": 2.0},
        headers=headers,
    ).json()
    t2 = client.post(
        f"/api/v1/stories/{story_id}/tasks",
        json={"title": "Step 2", "estimate_hours": 6.0},
        headers=headers,
    ).json()

    # Initially 0% progress, on_track
    tree1 = client.get(f"/api/v1/projects/{project_id}/tree").json()
    assert tree1["rollup"]["health"] == "on_track"
    assert tree1["stories"][0]["rollup"]["progress_pct"] == 0.0
    assert tree1["stories"][0]["rollup"]["suggested_status"] is None

    # Complete task 1 (2h / 8h = 25%) and start task 2 (doing -> suggests in_progress)
    client.patch(
        f"/api/v1/tasks/{t1['id']}",
        json={"status": "done", "version": 1},
        headers=headers,
    )
    client.patch(
        f"/api/v1/tasks/{t2['id']}",
        json={"status": "doing", "version": 1},
        headers=headers,
    )
    tree2 = client.get(f"/api/v1/projects/{project_id}/tree").json()
    assert tree2["stories"][0]["rollup"]["progress_pct"] == 25.0
    assert tree2["stories"][0]["rollup"]["suggested_status"] == "in_progress"

    # Complete task 2 -> 100% progress, suggests in_review
    client.patch(
        f"/api/v1/tasks/{t2['id']}",
        json={"status": "done", "version": 2},
        headers=headers,
    )
    tree3 = client.get(f"/api/v1/projects/{project_id}/tree").json()
    assert tree3["stories"][0]["rollup"]["progress_pct"] == 100.0
    assert tree3["stories"][0]["rollup"]["suggested_status"] == "in_review"
    assert tree3["rollup"]["done_tasks"] == 2
    assert tree3["rollup"]["total_tasks"] == 2


def test_tree_endpoint_avoids_n_plus_one_queries(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    headers = _auth(client)
    project_id = client.post(
        "/api/v1/projects",
        json={"key": "NPO", "name": "N Plus One Guard"},
        headers=headers,
    ).json()["id"]

    # Create 10 stories with 3 tasks each (30 tasks)
    for s_idx in range(10):
        story_id = client.post(
            f"/api/v1/projects/{project_id}/stories",
            json={"title": f"Story {s_idx}"},
            headers=headers,
        ).json()["id"]
        for t_idx in range(3):
            client.post(
                f"/api/v1/stories/{story_id}/tasks",
                json={"title": f"Task {s_idx}-{t_idx}"},
                headers=headers,
            )

    engine = db_session_factory.kw["bind"]
    executed_sql: list[str] = []

    def count_queries(
        _conn: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        executed_sql.append(statement)

    event.listen(engine, "before_cursor_execute", count_queries)
    try:
        res = client.get(f"/api/v1/projects/{project_id}/tree")
    finally:
        event.remove(engine, "before_cursor_execute", count_queries)

    assert res.status_code == 200
    body = res.json()
    assert len(body["stories"]) == 10
    assert body["rollup"]["total_tasks"] == 30
    # 1 (user) + 1 (project+member) + 1 (stories) + 1 (tasks) = 4 queries regardless of N
    assert len(executed_sql) <= 5
