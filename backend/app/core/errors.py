import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

PROBLEM_BASE_URI = "https://agile-pm.local/errors"
HTTP_422_STATUS = getattr(
    status, "HTTP_422_UNPROCESSABLE_CONTENT", status.HTTP_422_UNPROCESSABLE_ENTITY
)


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    title: str = "Application Error"
    error_slug: str = "application-error"
    default_code: str = "APPLICATION_ERROR"

    def __init__(
        self,
        detail: str,
        *,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code or self.default_code
        self.headers = headers or {}


class BadRequestError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    title = "Bad Request"
    error_slug = "bad-request"
    default_code = "BAD_REQUEST"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    title = "Unauthorized"
    error_slug = "unauthorized"
    default_code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    title = "Forbidden"
    error_slug = "forbidden"
    default_code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    title = "Not Found"
    error_slug = "not-found"
    default_code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    title = "Conflict"
    error_slug = "conflict"
    default_code = "CONFLICT"


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    title = "Too Many Requests"
    error_slug = "rate-limit-exceeded"
    default_code = "RATE_LIMIT_EXCEEDED"


def problem_response(
    *,
    status_code: int,
    title: str,
    detail: str,
    instance: str,
    error_slug: str,
    code: str,
    errors: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{PROBLEM_BASE_URI}/{error_slug}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "code": code,
    }
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(
        status_code=status_code,
        content=body,
        media_type="application/problem+json",
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return problem_response(
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            instance=str(request.url.path),
            error_slug=exc.error_slug,
            code=exc.code,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        formatted = [
            {
                "field": ".".join(str(part) for part in err.get("loc", [])),
                "message": err.get("msg", "Invalid value"),
                "type": err.get("type", "value_error"),
            }
            for err in exc.errors()
        ]
        return problem_response(
            status_code=HTTP_422_STATUS,
            title="Unprocessable Content",
            detail="Request validation failed.",
            instance=str(request.url.path),
            error_slug="validation-error",
            code="VALIDATION_ERROR",
            errors=formatted,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return problem_response(
            status_code=exc.status_code,
            title="HTTP Error",
            detail=str(exc.detail),
            instance=str(request.url.path),
            error_slug=f"http-{exc.status_code}",
            code=f"HTTP_{exc.status_code}",
            headers=dict(exc.headers) if exc.headers else None,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return problem_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="An unexpected error occurred.",
            instance=str(request.url.path),
            error_slug="internal-server-error",
            code="INTERNAL_SERVER_ERROR",
        )
