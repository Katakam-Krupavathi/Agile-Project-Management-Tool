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


def test_story_crud_numbering_filtering_move_and_delete(client: TestClient) -> None:
    user, headers = _auth(client, "storyowner@example.com", "Story Owner")
    project = client.post(
        "/api/v1/projects",
        json={"key": "APT", "name": "Agile Project Tool"},
        headers=headers,
    ).json()
    project_id = project["id"]

    # Create three stories and verify sequential numbering APT-1, APT-2, APT-3
    s1 = client.post(
        f"/api/v1/projects/{project_id}/stories",
        json={"title": "Auth flow", "priority": "high", "assignee_id": user["id"]},
        headers=headers,
    )
    assert s1.status_code == 201
    assert s1.json()["key"] == "APT-1"
    assert s1.json()["number"] == 1

    s2 = client.post(
        f"/api/v1/projects/{project_id}/stories",
        json={"title": "Kanban board", "description": "Drag and drop columns"},
        headers=headers,
    )
    assert s2.status_code == 201
    assert s2.json()["key"] == "APT-2"

    s3 = client.post(
        f"/api/v1/projects/{project_id}/stories",
        json={"title": "Audit log", "status": "in_progress"},
        headers=headers,
    )
    assert s3.status_code == 201
    assert s3.json()["key"] == "APT-3"

    # Filters: status, assignee, q
    in_progress = client.get(f"/api/v1/projects/{project_id}/stories?status=in_progress").json()
    assert [item["key"] for item in in_progress["items"]] == ["APT-3"]

    assigned = client.get(f"/api/v1/projects/{project_id}/stories?assignee={user['id']}").json()
    assert [item["key"] for item in assigned["items"]] == ["APT-1"]

    searched = client.get(f"/api/v1/projects/{project_id}/stories?q=drag").json()
    assert [item["key"] for item in searched["items"]] == ["APT-2"]

    # Move APT-3 into backlog between APT-1 and APT-2
    moved = client.post(
        f"/api/v1/stories/{s3.json()['id']}/move",
        json={
            "status": "backlog",
            "before_id": s1.json()["id"],
            "after_id": s2.json()["id"],
        },
        headers=headers,
    )
    assert moved.status_code == 200
    assert moved.json()["status"] == "backlog"
    assert s1.json()["position"] < moved.json()["position"] < s2.json()["position"]

    ordered = client.get(f"/api/v1/projects/{project_id}/stories?status=backlog").json()["items"]
    assert [item["key"] for item in ordered] == ["APT-1", "APT-3", "APT-2"]

    # Update story
    updated = client.patch(
        f"/api/v1/stories/{s1.json()['id']}",
        json={"title": "Auth flow v2", "story_points": 5, "version": s1.json()["version"]},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Auth flow v2"
    assert updated.json()["story_points"] == 5

    # Soft delete story
    deleted = client.delete(f"/api/v1/stories/{s2.json()['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/stories/{s2.json()['id']}").status_code == 404
