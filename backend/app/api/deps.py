from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import verify_csrf_token, verify_session_token_payload
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

    verified = verify_session_token_payload(
        session_token,
        settings.secret_key,
        settings.session_max_age_seconds,
    )
    if verified is None:
        raise UnauthorizedError("Invalid or expired session.", code="INVALID_SESSION")
    user_id, token_version = verified

    with open_db_session(request.app) as db:
        user = auth_service.get_active_user_by_id(db, user_id)
        if user is None or user.token_version != token_version:
            raise UnauthorizedError(
                "Account is inactive or session was revoked.",
                code="INVALID_SESSION",
            )
        db.expunge(user)

    return user


def is_request_session_valid(
    request: Request,
    db: Session,
    settings: Settings,
    expected_user_id: str,
) -> bool:
    session_token = request.cookies.get(settings.session_cookie_name)
    if not session_token:
        return False
    verified = verify_session_token_payload(
        session_token,
        settings.secret_key,
        settings.session_max_age_seconds,
    )
    if verified is None:
        return False
    user_id, token_version = verified
    if user_id != expected_user_id:
        return False
    user = auth_service.get_active_user_by_id(db, user_id)
    return bool(user is not None and user.token_version == token_version)


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
