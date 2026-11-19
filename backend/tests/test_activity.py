from fastapi.testclient import TestClient


def _auth(client: TestClient) -> dict[str, str]:
    client.post(
        "/api/v1/auth/register",
        json={"email": "audit@example.com", "name": "Audit User", "password": "StrongPassword123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "audit@example.com", "password": "StrongPassword123"},
    )
    return {"X-CSRF-Token": login.json()["csrf_token"]}


def test_activity_log_records_all_mutations_with_diffs_and_pagination(client: TestClient) -> None:
    headers = _auth(client)
    project = client.post(
        "/api/v1/projects",
        json={"key": "AUD", "name": "Audit Project"},
        headers=headers,
    ).json()
    project_id = project["id"]

    story = client.post(
        f"/api/v1/projects/{project_id}/stories",
        json={"title": "Initial Story"},
        headers=headers,
    ).json()
    client.patch(
        f"/api/v1/stories/{story['id']}",
        json={"title": "Renamed Story", "version": 1},
        headers=headers,
    )
    client.post(
        f"/api/v1/stories/{story['id']}/move",
        json={"status": "in_progress"},
        headers=headers,
    )

    task = client.post(
        f"/api/v1/stories/{story['id']}/tasks",
        json={"title": "Initial Task"},
        headers=headers,
    ).json()
    client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"status": "done", "version": 1},
        headers=headers,
    )
    client.delete(f"/api/v1/tasks/{task['id']}", headers=headers)
    client.delete(f"/api/v1/stories/{story['id']}", headers=headers)

    # Fetch first page of activity (limit=4) and paginate to get all 8 events
    page1 = client.get(f"/api/v1/projects/{project_id}/activity?limit=4")
    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["items"]) == 4
    assert body1["has_more"] is True
    assert body1["next_cursor"]

    page2 = client.get(
        f"/api/v1/projects/{project_id}/activity?limit=10&cursor={body1['next_cursor']}"
    )
    assert page2.status_code == 200
    body2 = page2.json()
    assert body2["has_more"] is False

    all_events = body1["items"] + body2["items"]
    actions = [event["action"] for event in all_events]
    expected_actions = {
        "project.created",
        "story.created",
        "story.updated",
        "story.moved",
        "task.created",
        "task.updated",
        "task.deleted",
        "story.deleted",
    }
    assert expected_actions.issubset(set(actions))

    story_update_event = next(e for e in all_events if e["action"] == "story.updated")
    assert story_update_event["actor_name"] == "Audit User"
    assert story_update_event["details"]["title"] == {
        "from": "Initial Story",
        "to": "Renamed Story",
    }

    task_update_event = next(e for e in all_events if e["action"] == "task.updated")
    assert task_update_event["details"]["status"] == {"from": "todo", "to": "done"}
