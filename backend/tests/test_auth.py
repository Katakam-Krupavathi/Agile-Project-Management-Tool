from fastapi.testclient import TestClient


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
