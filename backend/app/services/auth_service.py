from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import RegisterRequest


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register_user(db: Session, payload: RegisterRequest) -> User:
    normalized_email = normalize_email(str(payload.email))
    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
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
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise UnauthorizedError(
            "Invalid email or password.",
            code="INVALID_CREDENTIALS",
        )
    return user


def get_active_user_by_id(db: Session, user_id: str) -> User | None:
    return db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
