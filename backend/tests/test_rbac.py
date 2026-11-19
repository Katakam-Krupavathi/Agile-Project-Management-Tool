from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.rate_limit import login_rate_limiter
from app.db.session import get_db
from app.main import create_app


@contextmanager
def _user_client(
    db_session_factory: sessionmaker[Session],
    email: str,
    name: str,
) -> Generator[tuple[TestClient, dict, dict[str, str]], None, None]:
    login_rate_limiter.reset()
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": email, "name": name, "password": "StrongPassword123"},
        )
        assert reg.status_code == 201
        user = reg.json()

        login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "StrongPassword123"},
        )
        assert login.status_code == 200
        csrf = login.json()["csrf_token"]
        yield client, user, {"X-CSRF-Token": csrf}


def test_permission_matrix_for_owner_member_viewer_and_non_member(
    db_session_factory: sessionmaker[Session],
) -> None:
    with (
        _user_client(db_session_factory, "owner@example.com", "Owner") as (
            owner_client,
            _owner_user,
            owner_headers,
        ),
        _user_client(db_session_factory, "member@example.com", "Member") as (
            member_client,
            member_user,
            member_headers,
        ),
        _user_client(db_session_factory, "viewer@example.com", "Viewer") as (
            viewer_client,
            viewer_user,
            viewer_headers,
        ),
        _user_client(db_session_factory, "outsider@example.com", "Outsider") as (
            outsider_client,
            _outsider_user,
            outsider_headers,
        ),
        _user_client(db_session_factory, "extra@example.com", "Extra") as (
            _extra_client,
            extra_user,
            _extra_headers,
        ),
    ):
        # Owner creates project and adds member + viewer
        create_res = owner_client.post(
            "/api/v1/projects",
            json={"key": "RBAC", "name": "RBAC Matrix Project"},
            headers=owner_headers,
        )
        assert create_res.status_code == 201
        project_id = create_res.json()["id"]

        assert (
            owner_client.post(
                f"/api/v1/projects/{project_id}/members",
                json={"email": "member@example.com", "role": "member"},
                headers=owner_headers,
            ).status_code
            == 201
        )
        assert (
            owner_client.post(
                f"/api/v1/projects/{project_id}/members",
                json={"email": "viewer@example.com", "role": "viewer"},
                headers=owner_headers,
            ).status_code
            == 201
        )

        # GET /projects: only members see the project
        assert [p["id"] for p in owner_client.get("/api/v1/projects").json()["items"]] == [
            project_id
        ]
        assert [p["id"] for p in member_client.get("/api/v1/projects").json()["items"]] == [
            project_id
        ]
        assert [p["id"] for p in viewer_client.get("/api/v1/projects").json()["items"]] == [
            project_id
        ]
        assert outsider_client.get("/api/v1/projects").json()["items"] == []

        # GET /projects/{id}: owner/member/viewer -> 200; non-member -> 404
        assert owner_client.get(f"/api/v1/projects/{project_id}").status_code == 200
        assert member_client.get(f"/api/v1/projects/{project_id}").status_code == 200
        assert viewer_client.get(f"/api/v1/projects/{project_id}").status_code == 200
        assert outsider_client.get(f"/api/v1/projects/{project_id}").status_code == 404

        # GET /projects/{id}/members: owner/member/viewer -> 200; non-member -> 404
        assert owner_client.get(f"/api/v1/projects/{project_id}/members").status_code == 200
        assert member_client.get(f"/api/v1/projects/{project_id}/members").status_code == 200
        assert viewer_client.get(f"/api/v1/projects/{project_id}/members").status_code == 200
        assert outsider_client.get(f"/api/v1/projects/{project_id}/members").status_code == 404

        # PATCH /projects/{id}: owner -> 200; member/viewer -> 403; non-member -> 404
        assert (
            member_client.patch(
                f"/api/v1/projects/{project_id}",
                json={"name": "Member Edit", "version": 1},
                headers=member_headers,
            ).status_code
            == 403
        )
        assert (
            viewer_client.patch(
                f"/api/v1/projects/{project_id}",
                json={"name": "Viewer Edit", "version": 1},
                headers=viewer_headers,
            ).status_code
            == 403
        )
        assert (
            outsider_client.patch(
                f"/api/v1/projects/{project_id}",
                json={"name": "Outsider Edit", "version": 1},
                headers=outsider_headers,
            ).status_code
            == 404
        )
        assert (
            owner_client.patch(
                f"/api/v1/projects/{project_id}",
                json={"name": "Owner Edit", "version": 1},
                headers=owner_headers,
            ).status_code
            == 200
        )

        # POST /projects/{id}/members: owner -> 201; member/viewer -> 403; non-member -> 404
        add_payload = {"email": "extra@example.com", "role": "viewer"}
        assert (
            member_client.post(
                f"/api/v1/projects/{project_id}/members",
                json=add_payload,
                headers=member_headers,
            ).status_code
            == 403
        )
        assert (
            viewer_client.post(
                f"/api/v1/projects/{project_id}/members",
                json=add_payload,
                headers=viewer_headers,
            ).status_code
            == 403
        )
        assert (
            outsider_client.post(
                f"/api/v1/projects/{project_id}/members",
                json=add_payload,
                headers=outsider_headers,
            ).status_code
            == 404
        )
        assert (
            owner_client.post(
                f"/api/v1/projects/{project_id}/members",
                json=add_payload,
                headers=owner_headers,
            ).status_code
            == 201
        )

        # DELETE /projects/{id}/members/{uid}: owner -> 204; member/viewer -> 403; non-member -> 404
        assert (
            member_client.delete(
                f"/api/v1/projects/{project_id}/members/{viewer_user['id']}",
                headers=member_headers,
            ).status_code
            == 403
        )
        assert (
            viewer_client.delete(
                f"/api/v1/projects/{project_id}/members/{member_user['id']}",
                headers=viewer_headers,
            ).status_code
            == 403
        )
        assert (
            outsider_client.delete(
                f"/api/v1/projects/{project_id}/members/{viewer_user['id']}",
                headers=outsider_headers,
            ).status_code
            == 404
        )
        assert (
            owner_client.delete(
                f"/api/v1/projects/{project_id}/members/{extra_user['id']}",
                headers=owner_headers,
            ).status_code
            == 204
        )

        # DELETE /projects/{id} (archive): member/viewer -> 403; non-member -> 404; owner -> 204
        assert (
            member_client.delete(
                f"/api/v1/projects/{project_id}",
                headers=member_headers,
            ).status_code
            == 403
        )
        assert (
            viewer_client.delete(
                f"/api/v1/projects/{project_id}",
                headers=viewer_headers,
            ).status_code
            == 403
        )
        assert (
            outsider_client.delete(
                f"/api/v1/projects/{project_id}",
                headers=outsider_headers,
            ).status_code
            == 404
        )
        assert (
            owner_client.delete(
                f"/api/v1/projects/{project_id}",
                headers=owner_headers,
            ).status_code
            == 204
        )


def test_last_owner_protection_and_member_edge_cases(
    db_session_factory: sessionmaker[Session],
) -> None:
    with (
        _user_client(db_session_factory, "owner1@example.com", "Owner 1") as (
            owner1_client,
            owner1_user,
            owner1_headers,
        ),
        _user_client(db_session_factory, "owner2@example.com", "Owner 2") as (
            owner2_client,
            owner2_user,
            owner2_headers,
        ),
    ):
        project_id = owner1_client.post(
            "/api/v1/projects",
            json={"key": "OWN", "name": "Owner Protection"},
            headers=owner1_headers,
        ).json()["id"]

        # Missing CSRF header rejected
        no_csrf = owner1_client.post(
            f"/api/v1/projects/{project_id}/members",
            json={"email": "owner2@example.com", "role": "owner"},
        )
        assert no_csrf.status_code == 403
        assert no_csrf.json()["code"] == "CSRF_INVALID"

        # Sole owner cannot be removed
        sole_remove = owner1_client.delete(
            f"/api/v1/projects/{project_id}/members/{owner1_user['id']}",
            headers=owner1_headers,
        )
        assert sole_remove.status_code == 409
        assert sole_remove.json()["code"] == "LAST_OWNER_CANNOT_BE_REMOVED"

        # Unknown email returns 404
        unknown_email = owner1_client.post(
            f"/api/v1/projects/{project_id}/members",
            json={"email": "missing@example.com", "role": "member"},
            headers=owner1_headers,
        )
        assert unknown_email.status_code == 404
        assert unknown_email.json()["code"] == "USER_NOT_FOUND"

        # Add second owner
        add_owner2 = owner1_client.post(
            f"/api/v1/projects/{project_id}/members",
            json={"email": "owner2@example.com", "role": "owner"},
            headers=owner1_headers,
        )
        assert add_owner2.status_code == 201

        # Duplicate add returns 409
        dup_add = owner1_client.post(
            f"/api/v1/projects/{project_id}/members",
            json={"email": "owner2@example.com", "role": "member"},
            headers=owner1_headers,
        )
        assert dup_add.status_code == 409
        assert dup_add.json()["code"] == "MEMBER_ALREADY_EXISTS"

        # Now owner1 can be removed since owner2 remains
        remove_owner1 = owner2_client.delete(
            f"/api/v1/projects/{project_id}/members/{owner1_user['id']}",
            headers=owner2_headers,
        )
        assert remove_owner1.status_code == 204

        # Owner2 is now the last owner and cannot be removed
        sole_remove2 = owner2_client.delete(
            f"/api/v1/projects/{project_id}/members/{owner2_user['id']}",
            headers=owner2_headers,
        )
        assert sole_remove2.status_code == 409
        assert sole_remove2.json()["code"] == "LAST_OWNER_CANNOT_BE_REMOVED"
