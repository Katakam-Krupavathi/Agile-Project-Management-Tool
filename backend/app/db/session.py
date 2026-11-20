from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    raw_path = database_url.removeprefix("sqlite:///")
    if raw_path in ("", ":memory:"):
        return
    Path(raw_path).parent.mkdir(parents=True, exist_ok=True)


def _configure_sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA busy_timeout=5000;")
    finally:
        cursor.close()


def create_db_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    _ensure_sqlite_parent_dir(url)
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(url, connect_args=connect_args, future=True)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _configure_sqlite_pragmas)
    return engine


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def begin_immediate_if_sqlite(db: Session) -> None:
    """Release any read-only snapshot and acquire SQLite's write lock cleanly.

    In SQLite WAL mode, upgrading a deferred read transaction to a write
    transaction fails immediately with SQLITE_BUSY if another writer committed
    after the snapshot began. Rolling back the read-only transaction and
    issuing ``BEGIN IMMEDIATE`` honors ``busy_timeout`` and serializes writers
    without spurious 500s.
    """
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "sqlite":
        db.rollback()
        db.execute(text("BEGIN IMMEDIATE"))
