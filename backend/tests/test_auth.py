import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import create_app
from tests.test_async_features import _open_asgi_sse_stream


def _assert_problem_envelope(response_json: dict, expected_status: int, expected_code: str) -> None:
    assert response_json["status"] == expected_status
    assert response_json["code"] == expected_code
    assert response_json["type"].startswith("https://agile-pm.local/errors/")
    assert isinstance(response_json["title"], str) and response_json["title"]
    assert isinstance(response_json["detail"], str) and response_json["detail"]
    assert isinstance(response_json["instance"], str) and response_json["instance"].startswith("/")


def test_register_login_me_and_logout_flow(client: TestClient) -> None:
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "Dev@Example.com",
            "name": "Dev User",
            "password": "StrongPassword123",
        },
    )
    assert reg_res.status_code == 201
    user_data = reg_res.json()
    assert user_data["email"] == "dev@example.com"
    assert user_data["name"] == "Dev User"
    assert "password" not in user_data
    assert "password_hash" not in user_data

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "StrongPassword123"},
    )
    assert login_res.status_code == 200
    login_body = login_res.json()
    assert login_body["user"]["id"] == user_data["id"]
    csrf_token = login_body["csrf_token"]
    assert csrf_token

    set_cookie_headers = login_res.headers.get_list("set-cookie")
    session_cookie_header = next(h for h in set_cookie_headers if h.startswith("agile_pm_session="))
    assert "httponly" in session_cookie_header.lower()
    assert "samesite=lax" in session_cookie_header.lower()

    csrf_cookie_header = next(h for h in set_cookie_headers if h.startswith("agile_pm_csrf="))
    assert "httponly" not in csrf_cookie_header.lower()
    assert "samesite=lax" in csrf_cookie_header.lower()

    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["id"] == user_data["id"]

    # Logout without CSRF header must fail with 403
    bad_logout_res = client.post("/api/v1/auth/logout")
    assert bad_logout_res.status_code == 403
    assert bad_logout_res.headers["content-type"].startswith("application/problem+json")
    _assert_problem_envelope(bad_logout_res.json(), 403, "CSRF_INVALID")

    # Logout with matching CSRF header succeeds
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_res.status_code == 204

    # Subsequent /me must be rejected
    after_logout_res = client.get("/api/v1/auth/me")
    assert after_logout_res.status_code == 401
    _assert_problem_envelope(after_logout_res.json(), 401, "UNAUTHENTICATED")


def test_duplicate_register_and_validation_errors(client: TestClient) -> None:
    payload = {
        "email": "dup@example.com",
        "name": "First User",
        "password": "StrongPassword123",
    }
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    duplicate = client.post("/api/v1/auth/register", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.headers["content-type"].startswith("application/problem+json")
    _assert_problem_envelope(duplicate.json(), 409, "EMAIL_ALREADY_REGISTERED")

    invalid = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "name": "   ", "password": "short"},
    )
    assert invalid.status_code == 422
    assert invalid.headers["content-type"].startswith("application/problem+json")
    _assert_problem_envelope(invalid.json(), 422, "VALIDATION_ERROR")
    assert len(invalid.json()["errors"]) >= 1


def test_wrong_password_and_unknown_email_return_401_problem_envelope(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "name": "Real User",
            "password": "CorrectPassword123",
        },
    )

    wrong_pw = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "WrongPassword123"},
    )
    assert wrong_pw.status_code == 401
    assert wrong_pw.headers["content-type"].startswith("application/problem+json")
    _assert_problem_envelope(wrong_pw.json(), 401, "INVALID_CREDENTIALS")

    unknown = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "SomePassword123"},
    )
    assert unknown.status_code == 401
    _assert_problem_envelope(unknown.json(), 401, "INVALID_CREDENTIALS")


def test_me_rejects_missing_and_tampered_session_cookie(client: TestClient) -> None:
    missing = client.get("/api/v1/auth/me")
    assert missing.status_code == 401
    _assert_problem_envelope(missing.json(), 401, "UNAUTHENTICATED")

    client.cookies.set("agile_pm_session", "tampered.invalid.token")
    tampered = client.get("/api/v1/auth/me")
    assert tampered.status_code == 401
    _assert_problem_envelope(tampered.json(), 401, "INVALID_SESSION")


def test_login_rate_limiting_returns_429_with_retry_after(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "ratelimit@example.com",
            "name": "Rate Limited",
            "password": "CorrectPassword123",
        },
    )

    for _ in range(5):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "ratelimit@example.com", "password": "WrongPassword!"},
        )
        assert res.status_code == 401

    limited = client.post(
        "/api/v1/auth/login",
        json={"email": "ratelimit@example.com", "password": "CorrectPassword123"},
    )
    assert limited.status_code == 429
    assert limited.headers["content-type"].startswith("application/problem+json")
    assert int(limited.headers["retry-after"]) >= 1
    _assert_problem_envelope(limited.json(), 429, "LOGIN_RATE_LIMITED")


def test_logout_revokes_old_session_cookie_on_replay(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "replay@example.com",
            "name": "Replay User",
            "password": "StrongPassword123",
        },
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "replay@example.com", "password": "StrongPassword123"},
    )
    assert login_res.status_code == 200
    csrf_token = login_res.json()["csrf_token"]
    saved_session_cookie = client.cookies.get("agile_pm_session")
    assert saved_session_cookie

    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_res.status_code == 204

    # Replay the captured pre-logout session cookie
    client.cookies.set("agile_pm_session", saved_session_cookie)
    replayed = client.get("/api/v1/auth/me")
    assert replayed.status_code == 401
    _assert_problem_envelope(replayed.json(), 401, "INVALID_SESSION")


def test_sse_stream_closes_after_logout_revokes_session(
    db_session_factory: sessionmaker[Session],
) -> None:
    app = create_app()

    def override_get_db() -> Any:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    base_settings = get_settings()
    fast_poll_settings = base_settings.model_copy(
        update={"sse_poll_interval_seconds": 0.05}
    )
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: fast_poll_settings

    with TestClient(app) as local_client:
        local_client.post(
            "/api/v1/auth/register",
            json={
                "email": "sse_logout@example.com",
                "name": "SSE Logout",
                "password": "StrongPassword123",
            },
        )
        login_res = local_client.post(
            "/api/v1/auth/login",
            json={"email": "sse_logout@example.com", "password": "StrongPassword123"},
        )
        assert login_res.status_code == 200
        csrf_token = login_res.json()["csrf_token"]
        session_cookie = local_client.cookies.get(base_settings.session_cookie_name)
        assert session_cookie

        async def _run() -> None:
            async with _open_asgi_sse_stream(app, session_cookie) as stream:
                assert stream["status"] == 200
                logout_res = local_client.post(
                    "/api/v1/auth/logout",
                    headers={"X-CSRF-Token": csrf_token},
                )
                assert logout_res.status_code == 204
                # Stream task should exit promptly on its next poll after token_version bump
                await asyncio.wait_for(stream["task"], timeout=0.6)

        asyncio.run(_run())


def test_unknown_user_and_wrong_password_both_call_argon2_hasher(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.core.security as security_mod

    client.post(
        "/api/v1/auth/register",
        json={
            "email": "known@example.com",
            "name": "Known User",
            "password": "StrongPassword123",
        },
    )

    verify_calls: list[str] = []
    original_hasher = security_mod._password_hasher

    class _SpyHasher:
        def hash(self, password: str) -> str:
            return original_hasher.hash(password)

        def verify(self, hash_val: str, password: str) -> bool:
            verify_calls.append(password)
            return original_hasher.verify(hash_val, password)

    monkeypatch.setattr(security_mod, "_password_hasher", _SpyHasher())

    unknown_res = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown_person@example.com", "password": "AttemptPassword1"},
    )
    assert unknown_res.status_code == 401
    assert len(verify_calls) == 1

    wrong_res = client.post(
        "/api/v1/auth/login",
        json={"email": "known@example.com", "password": "AttemptPassword2"},
    )
    assert wrong_res.status_code == 401
    assert len(verify_calls) == 2


@pytest.mark.xfail(
    strict=True,
    reason="Per-IP login limiter and register rate limiter not implemented yet",
)
def test_per_ip_login_limiter_across_emails_and_register_limiter(
    client: TestClient,
) -> None:
    # 1. Per-IP login limiter triggers across distinct emails (even with 1 attempt per email)
    triggered_ip_limit = False
    for idx in range(20):
        res = client.post(
            "/api/v1/auth/login",
            json={
                "email": f"spray_{idx}@example.com",
                "password": "WrongPassword123",
            },
        )
        if res.status_code == 429:
            triggered_ip_limit = True
            assert int(res.headers["retry-after"]) >= 1
            _assert_problem_envelope(res.json(), 429, "LOGIN_RATE_LIMITED")
            break
        assert res.status_code == 401
    assert triggered_ip_limit is True

    # 2. Register endpoint rate limiter triggers after max attempts from same IP
    triggered_register_limit = False
    for idx in range(15):
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"bulkreg_{idx}@example.com",
                "name": f"Bulk {idx}",
                "password": "StrongPassword123",
            },
        )
        if reg.status_code == 429:
            triggered_register_limit = True
            assert int(reg.headers["retry-after"]) >= 1
            _assert_problem_envelope(reg.json(), 429, "REGISTER_RATE_LIMITED")
            break
        assert reg.status_code == 201
    assert triggered_register_limit is True


@pytest.mark.xfail(
    strict=True,
    reason="Production secret validation and default Secure cookie flag not implemented yet",
)
def test_production_defaults_reject_weak_secret_and_enable_secure_cookie(
    db_session_factory: sessionmaker[Session],
) -> None:
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(app_env="production")

    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(app_env="production", secret_key="too-short-secret")

    prod_settings = Settings(
        app_env="production",
        secret_key="prod-secret-key-with-at-least-32-characters-long!",
    )
    assert prod_settings.session_cookie_secure is True
    assert prod_settings.enable_api_docs is False

    app = create_app(prod_settings)

    def override_get_db() -> Any:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: prod_settings

    with TestClient(app, base_url="https://testserver") as prod_client:
        assert prod_client.get("/docs").status_code == 404
        assert prod_client.get("/openapi.json").status_code == 404

        reg = prod_client.post(
            "/api/v1/auth/register",
            json={
                "email": "prod@example.com",
                "name": "Prod User",
                "password": "StrongPassword123",
            },
        )
        assert reg.status_code == 201

        login = prod_client.post(
            "/api/v1/auth/login",
            json={"email": "prod@example.com", "password": "StrongPassword123"},
        )
        assert login.status_code == 200
        set_cookies = login.headers.get_list("set-cookie")
        session_header = next(
            h for h in set_cookies if h.startswith(f"{prod_settings.session_cookie_name}=")
        )
        assert "secure" in session_header.lower()
