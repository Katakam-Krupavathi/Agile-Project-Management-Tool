from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import ConflictError, register_exception_handlers


def test_unknown_route_returns_rfc7807_404(client: TestClient) -> None:
    res = client.get("/api/v1/does-not-exist")
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/problem+json")
    body = res.json()
    assert body["status"] == 404
    assert body["code"] == "HTTP_404"
    assert body["instance"] == "/api/v1/does-not-exist"
    assert body["type"].startswith("https://agile-pm.local/errors/")


def test_app_error_and_unhandled_exception_return_rfc7807() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/conflict")
    def trigger_conflict() -> None:
        raise ConflictError("Version mismatch.", code="VERSION_CONFLICT")

    @app.get("/boom")
    def trigger_boom() -> None:
        raise RuntimeError("sensitive internal detail")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        conflict_res = test_client.get("/conflict")
        assert conflict_res.status_code == 409
        assert conflict_res.headers["content-type"].startswith("application/problem+json")
        conflict_body = conflict_res.json()
        assert conflict_body["code"] == "VERSION_CONFLICT"
        assert conflict_body["detail"] == "Version mismatch."

        boom_res = test_client.get("/boom")
        assert boom_res.status_code == 500
        assert boom_res.headers["content-type"].startswith("application/problem+json")
        boom_body = boom_res.json()
        assert boom_body["code"] == "INTERNAL_SERVER_ERROR"
        assert "sensitive internal detail" not in boom_body["detail"]
