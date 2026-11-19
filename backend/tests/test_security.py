from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.core.security import (
    create_session_token,
    generate_csrf_token,
    hash_password,
    verify_csrf_token,
    verify_password,
    verify_session_token,
)
from app.db.base import Base
from app.db.session import create_db_engine
from app.schemas.auth import RegisterRequest
from app.services import auth_service


def test_argon2_password_hashing_and_verification() -> None:
    hashed = hash_password("StrongPass123!")
    assert hashed.startswith("$argon2")
    assert hashed != "StrongPass123!"
    assert verify_password("StrongPass123!", hashed) is True
    assert verify_password("WrongPass123!", hashed) is False
    assert verify_password("StrongPass123!", "not-a-valid-hash") is False


def test_register_user_normalizes_email_and_rejects_duplicates(tmp_path: Path) -> None:
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'reg.db').as_posix()}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            user = auth_service.register_user(
                db,
                RegisterRequest(
                    email="Alice@Example.COM",
                    name="  Alice Dev  ",
                    password="SecurePassword123",
                ),
            )
            assert user.email == "alice@example.com"
            assert user.name == "Alice Dev"
            assert user.password_hash.startswith("$argon2")
            assert verify_password("SecurePassword123", user.password_hash)

            with pytest.raises(ConflictError) as exc_info:
                auth_service.register_user(
                    db,
                    RegisterRequest(
                        email="alice@example.com",
                        name="Alice Duplicate",
                        password="AnotherPassword123",
                    ),
                )
            assert exc_info.value.code == "EMAIL_ALREADY_REGISTERED"
    finally:
        engine.dispose()


def test_session_token_roundtrip_and_tamper_rejection() -> None:
    token = create_session_token("user-123", "test-secret")
    assert verify_session_token(token, "test-secret", max_age_seconds=60) == "user-123"
    assert verify_session_token(token, "wrong-secret", max_age_seconds=60) is None
    assert verify_session_token(f"{token}tampered", "test-secret", max_age_seconds=60) is None


def test_csrf_token_verification() -> None:
    token = generate_csrf_token()
    assert len(token) >= 32
    assert verify_csrf_token(token, token) is True
    assert verify_csrf_token(token, "mismatch") is False
    assert verify_csrf_token(None, token) is False
    assert verify_csrf_token(token, None) is False
