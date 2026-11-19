from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.core.security import hash_password, verify_password
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
