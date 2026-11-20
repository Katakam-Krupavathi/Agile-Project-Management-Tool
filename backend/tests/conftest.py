from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.rate_limit import login_rate_limiter
from app.db.session import create_db_engine, get_db
from app.main import create_app
from app.services.notification_service import reset_user_stream_slots


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    db_path = tmp_path / "test.db"
    url = f"sqlite:///{db_path.as_posix()}"
    alembic_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return url


@pytest.fixture
def db_session_factory(db_url: str) -> Generator[sessionmaker[Session], None, None]:
    engine = create_db_engine(db_url)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture
def client(db_session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    login_rate_limiter.reset()
    reset_user_stream_slots()
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    reset_user_stream_slots()
    login_rate_limiter.reset()
