from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import hash_password, verify_dummy_password, verify_password
from app.models.user import User, utc_now
from app.schemas.auth import RegisterRequest


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register_user(db: Session, payload: RegisterRequest) -> User:
    normalized_email = normalize_email(str(payload.email))
    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        verify_dummy_password(payload.password)
        raise ConflictError(
            "An account with this email already exists.",
            code="EMAIL_ALREADY_REGISTERED",
        )

    user = User(
        email=normalized_email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    normalized_email = normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        verify_dummy_password(password)
        raise UnauthorizedError(
            "Invalid email or password.",
            code="INVALID_CREDENTIALS",
        )
    password_valid = verify_password(password, user.password_hash)
    if not user.is_active or not password_valid:
        raise UnauthorizedError(
            "Invalid email or password.",
            code="INVALID_CREDENTIALS",
        )
    return user


def get_active_user_by_id(db: Session, user_id: str) -> User | None:
    return db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))


def revoke_user_sessions(db: Session, user_id: str) -> None:
    db.execute(
        update(User)
        .where(User.id == user_id)
        .values(token_version=User.token_version + 1, updated_at=utc_now())
    )
    db.commit()
