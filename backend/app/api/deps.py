from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import verify_csrf_token, verify_session_token
from app.db.session import open_db_session
from app.models.user import User
from app.services import auth_service


def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    session_token = request.cookies.get(settings.session_cookie_name)
    if not session_token:
        raise UnauthorizedError("Authentication required.", code="UNAUTHENTICATED")

    user_id = verify_session_token(
        session_token,
        settings.secret_key,
        settings.session_max_age_seconds,
    )
    if not user_id:
        raise UnauthorizedError("Invalid or expired session.", code="INVALID_SESSION")

    with open_db_session(request.app) as db:
        user = auth_service.get_active_user_by_id(db, user_id)
        if user is None:
            raise UnauthorizedError("Account is inactive or not found.", code="INVALID_SESSION")
        db.expunge(user)

    return user


def require_csrf(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get(settings.csrf_header_name)
    if not verify_csrf_token(cookie_token, header_token):
        raise ForbiddenError(
            "Invalid or missing CSRF token.",
            code="CSRF_INVALID",
        )
