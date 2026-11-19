from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, email: str, name: str) -> str:
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
    return login.json()["csrf_token"]


def test_project_crud_pagination_version_and_archive(client: TestClient) -> None:
    csrf = _register_and_login(client, "owner@example.com", "Owner User")
    headers = {"X-CSRF-Token": csrf}

    # Key validation: must be 2-5 uppercase letters
    for bad_key in ["A", "ABCDEF", "ab", "A1", "A-B"]:
        bad_res = client.post(
            "/api/v1/projects",
            json={"key": bad_key, "name": "Bad Key"},
            headers=headers,
        )
        assert bad_res.status_code == 422

    # Create two projects
    p1_res = client.post(
        "/api/v1/projects",
        json={"key": "APM", "name": "Agile PM", "description": "Core board"},
        headers=headers,
    )
    assert p1_res.status_code == 201
    p1 = p1_res.json()
    assert p1["key"] == "APM"
    assert p1["role"] == "owner"
    assert p1["version"] == 1
    assert p1["next_story_number"] == 1

    # Duplicate key returns 409
    dup_res = client.post(
        "/api/v1/projects",
        json={"key": "APM", "name": "Duplicate Key"},
        headers=headers,
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["code"] == "PROJECT_KEY_EXISTS"

    p2_res = client.post(
        "/api/v1/projects",
        json={"key": "OPS", "name": "Operations"},
        headers=headers,
    )
    assert p2_res.status_code == 201
    p2 = p2_res.json()

    # Cursor pagination with limit=1
    page1 = client.get("/api/v1/projects?limit=1")
    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["items"]) == 1
    assert body1["has_more"] is True
    assert body1["next_cursor"]

    page2 = client.get(f"/api/v1/projects?limit=1&cursor={body1['next_cursor']}")
    assert page2.status_code == 200
    body2 = page2.json()
    assert len(body2["items"]) == 1
    assert body2["has_more"] is False
    assert {body1["items"][0]["id"], body2["items"][0]["id"]} == {p1["id"], p2["id"]}

    # Get by ID
    get_res = client.get(f"/api/v1/projects/{p1['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Agile PM"

    # Update with correct version
    patch_res = client.patch(
        f"/api/v1/projects/{p1['id']}",
        json={"name": "Agile PM v2", "version": 1},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Agile PM v2"
    assert patch_res.json()["version"] == 2

    # Stale version returns 409
    stale_res = client.patch(
        f"/api/v1/projects/{p1['id']}",
        json={"name": "Stale Update", "version": 1},
        headers=headers,
    )
    assert stale_res.status_code == 409
    assert stale_res.json()["code"] == "VERSION_CONFLICT"

    # Archive project
    del_res = client.delete(f"/api/v1/projects/{p1['id']}", headers=headers)
    assert del_res.status_code == 204

    # Archived project returns 404 and disappears from list
    assert client.get(f"/api/v1/projects/{p1['id']}").status_code == 404
    remaining = client.get("/api/v1/projects").json()["items"]
    assert [item["id"] for item in remaining] == [p2["id"]]
