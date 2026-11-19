from fastapi.testclient import TestClient


def _auth(client: TestClient, email: str, name: str) -> tuple[dict, dict[str, str]]:
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": name, "password": "StrongPassword123"},
    )
    assert reg.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123"},
    )
    assert login.status_code == 200
    return reg.json(), {"X-CSRF-Token": login.json()["csrf_token"]}


def test_task_crud_move_and_story_cascade_soft_delete(client: TestClient) -> None:
    user, headers = _auth(client, "taskowner@example.com", "Task Owner")
    project_id = client.post(
        "/api/v1/projects",
        json={"key": "TSK", "name": "Task Project"},
        headers=headers,
    ).json()["id"]
    story_id = client.post(
        f"/api/v1/projects/{project_id}/stories",
        json={"title": "Implement tasks"},
        headers=headers,
    ).json()["id"]

    t1 = client.post(
        f"/api/v1/stories/{story_id}/tasks",
        json={"title": "Task 1", "estimate_hours": 2.0, "assignee_id": user["id"]},
        headers=headers,
    )
    assert t1.status_code == 201
    t2 = client.post(
        f"/api/v1/stories/{story_id}/tasks",
        json={"title": "Task 2", "estimate_hours": 3.0},
        headers=headers,
    )
    assert t2.status_code == 201
    t3 = client.post(
        f"/api/v1/stories/{story_id}/tasks",
        json={"title": "Task 3", "due_date": "2026-12-01"},
        headers=headers,
    )
    assert t3.status_code == 201

    # Reorder Task 3 between Task 1 and Task 2
    moved = client.post(
        f"/api/v1/tasks/{t3.json()['id']}/move",
        json={"before_id": t1.json()["id"], "after_id": t2.json()["id"], "status": "doing"},
        headers=headers,
    )
    assert moved.status_code == 200
    assert moved.json()["status"] == "doing"

    ordered = client.get(f"/api/v1/stories/{story_id}/tasks").json()["items"]
    assert [item["title"] for item in ordered] == ["Task 1", "Task 3", "Task 2"]

    # Update Task 1
    updated = client.patch(
        f"/api/v1/tasks/{t1.json()['id']}",
        json={"status": "done", "version": t1.json()["version"]},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "done"

    # Delete Task 2
    assert client.delete(f"/api/v1/tasks/{t2.json()['id']}", headers=headers).status_code == 204
    remaining = client.get(f"/api/v1/stories/{story_id}/tasks").json()["items"]
    assert [item["title"] for item in remaining] == ["Task 1", "Task 3"]

    # Soft-deleting parent story cascades soft-delete to remaining tasks
    assert client.delete(f"/api/v1/stories/{story_id}", headers=headers).status_code == 204
    assert (
        client.patch(
            f"/api/v1/tasks/{t1.json()['id']}",
            json={"title": "Should fail", "version": 2},
            headers=headers,
        ).status_code
        == 404
    )
