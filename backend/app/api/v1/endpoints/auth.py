import time
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.core.config import Settings, get_settings
from app.core.errors import RateLimitError, UnauthorizedError
from app.core.rate_limit import login_rate_limiter
from app.core.security import create_session_token, generate_csrf_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AuthSessionResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserResponse:
    client_ip = request.client.host if request.client else "unknown"
    reg_key = f"reg:{client_ip}"
    retry_after = login_rate_limiter.check(
        reg_key,
        settings.register_rate_limit_max_attempts,
        settings.register_rate_limit_window_seconds,
    )
    if retry_after is not None:
        raise RateLimitError(
            "Too many registration attempts. Please try again later.",
            code="REGISTER_RATE_LIMITED",
            headers={"Retry-After": str(retry_after)},
        )
    login_rate_limiter.record_attempt(reg_key, settings.register_rate_limit_window_seconds)
    user = auth_service.register_user(db, payload)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=AuthSessionResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthSessionResponse:
    client_ip = request.client.host if request.client else "unknown"
    normalized_email = auth_service.normalize_email(str(payload.email))
    rate_key = f"{client_ip}:{normalized_email}"
    ip_key = f"ip:{client_ip}"
    account_key = f"acct:{normalized_email}"

    pair_retry = login_rate_limiter.check(
        rate_key,
        settings.login_rate_limit_max_attempts,
        settings.login_rate_limit_window_seconds,
    )
    ip_retry = login_rate_limiter.check(
        ip_key,
        settings.login_ip_rate_limit_max_attempts,
        settings.login_ip_rate_limit_window_seconds,
    )
    if pair_retry is not None or ip_retry is not None:
        retry_after = max(pair_retry or 0, ip_retry or 0)
        raise RateLimitError(
            "Too many login attempts. Please try again later.",
            code="LOGIN_RATE_LIMITED",
            headers={"Retry-After": str(retry_after)},
        )

    backoff_delay = login_rate_limiter.compute_backoff_delay(
        account_key,
        settings.login_account_backoff_base_seconds,
        settings.login_account_backoff_max_seconds,
        settings.login_account_backoff_window_seconds,
    )
    if backoff_delay > 0:
        time.sleep(backoff_delay)

    try:
        user = auth_service.authenticate_user(db, str(payload.email), payload.password)
    except UnauthorizedError:
        login_rate_limiter.record_attempt(rate_key, settings.login_rate_limit_window_seconds)
        login_rate_limiter.record_attempt(ip_key, settings.login_ip_rate_limit_window_seconds)
        login_rate_limiter.record_attempt(
            account_key,
            settings.login_account_backoff_window_seconds,
        )
        raise

    login_rate_limiter.clear(rate_key)
    login_rate_limiter.clear(account_key)
    session_token = create_session_token(
        user.id,
        settings.secret_key,
        token_version=user.token_version,
    )
    csrf_token = generate_csrf_token()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        max_age=settings.session_max_age_seconds,
        path="/",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=settings.session_cookie_secure,
        max_age=settings.session_max_age_seconds,
        path="/",
    )
    return AuthSessionResponse(
        user=UserResponse.model_validate(user),
        csrf_token=csrf_token,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def logout(
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    auth_service.revoke_user_sessions(db, current_user.id)
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        samesite="lax",
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path="/",
        samesite="lax",
    )


@router.get("/me", response_model=UserResponse)
def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse.model_validate(current_user)
