from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    raw_path = database_url.removeprefix("sqlite:///")
    if raw_path in ("", ":memory:"):
        return
    Path(raw_path).parent.mkdir(parents=True, exist_ok=True)


_SQLITE_WRITE_TOKENS = frozenset(
    {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP"}
)


def _configure_sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
    # Disable pysqlite's implicit DEFERRED BEGIN so the engine event hook can
    # issue BEGIN IMMEDIATE specifically when a write statement starts.
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA busy_timeout=5000;")
    finally:
        cursor.close()


def _sqlite_begin_immediate_on_write(
    _conn: Connection,
    cursor: Any,
    statement: str,
    _parameters: Any,
    _context: Any,
    _executemany: bool,
) -> None:
    if cursor.connection.in_transaction:
        return
    leading = statement.lstrip()
    if not leading:
        return
    first_token = leading.split(None, 1)[0].upper()
    if first_token in _SQLITE_WRITE_TOKENS or (
        first_token == "WITH"
        and any(kw in leading.upper() for kw in ("INSERT ", "UPDATE ", "DELETE "))
    ):
        cursor.execute("BEGIN IMMEDIATE")


def create_db_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    _ensure_sqlite_parent_dir(url)
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _configure_sqlite_pragmas)
        event.listen(engine, "before_cursor_execute", _sqlite_begin_immediate_on_write)
    return engine


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def open_db_session(app: Any = None) -> Generator[Session, None, None]:
    """Open a short-lived DB session (respecting dependency_overrides) and close it on exit."""
    provider = get_db
    if app is not None and hasattr(app, "dependency_overrides"):
        provider = app.dependency_overrides.get(get_db, get_db)
    gen = provider()
    try:
        yield next(gen)
    finally:
        gen.close()


def begin_immediate_if_sqlite(db: Session) -> None:
    """Reset any prior session transaction before a write transaction begins.

    The SQLite engine's ``before_cursor_execute`` event hook automatically
    issues ``BEGIN IMMEDIATE`` on the first write statement, acquiring the
    write lock up front and honoring ``busy_timeout=5000``.
    """
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "sqlite" and db.in_transaction():
        db.rollback()
