from contextlib import suppress

from starlette.datastructures import MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import problem_response

_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


class _PayloadTooLargeError(Exception):
    pass


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "/")

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
                headers.setdefault(
                    "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
                )
                if not path.startswith(_DOCS_PATHS):
                    headers.setdefault(
                        "Content-Security-Policy",
                        "default-src 'none'; frame-ancestors 'none'",
                    )
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


class RequestSizeLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    def _payload_too_large_response(self, path: str) -> Response:
        return problem_response(
            status_code=413,
            title="Payload Too Large",
            detail=f"Request body exceeds limit of {self.max_body_bytes} bytes.",
            instance=path,
            error_slug="payload-too-large",
            code="PAYLOAD_TOO_LARGE",
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "/")
        for raw_name, raw_value in scope.get("headers", []):
            if raw_name.lower() == b"content-length":
                try:
                    declared_size = int(raw_value.decode("latin-1"))
                except ValueError:
                    declared_size = 0
                if declared_size > self.max_body_bytes:
                    response = self._payload_too_large_response(path)
                    await response(scope, receive, send)
                    return

        bytes_seen = 0
        exceeded = False
        response_started = False

        async def counting_receive() -> Message:
            nonlocal bytes_seen, exceeded
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                bytes_seen += len(chunk)
                if bytes_seen > self.max_body_bytes:
                    exceeded = True
                    raise _PayloadTooLargeError()
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if exceeded:
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        with suppress(_PayloadTooLargeError):
            await self.app(scope, counting_receive, tracking_send)

        if exceeded and not response_started:
            response = self._payload_too_large_response(path)
            await response(scope, receive, send)
