from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import create_db_engine
from app.models import Project, ProjectMember, User


def _run_migrations(db_path: Path) -> str:
    url = f"sqlite:///{db_path.as_posix()}"
    alembic_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return url


def test_migrations_from_empty_db_and_sqlite_pragmas(tmp_path: Path) -> None:
    db_path = tmp_path / "test_agile.db"
    url = _run_migrations(db_path)

    engine = create_db_engine(url)
    try:
        with engine.connect() as conn:
            journal_mode = conn.execute(text("PRAGMA journal_mode;")).scalar_one()
            foreign_keys = conn.execute(text("PRAGMA foreign_keys;")).scalar_one()
            assert str(journal_mode).lower() == "wal"
            assert foreign_keys == 1

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        expected_tables = {
            "users",
            "projects",
            "project_members",
            "stories",
            "tasks",
            "activity_log",
            "notifications",
            "jobs",
            "alembic_version",
        }
        assert expected_tables.issubset(tables)

        story_indexes = {idx["name"] for idx in inspector.get_indexes("stories")}
        assert "ix_stories_project_id_status" in story_indexes
        assert "ix_stories_assignee_id" in story_indexes

        task_indexes = {idx["name"] for idx in inspector.get_indexes("tasks")}
        assert "ix_tasks_story_id_position" in task_indexes
        assert "ix_tasks_assignee_id" in task_indexes
        assert "ix_tasks_due_date" in task_indexes

        job_indexes = {idx["name"] for idx in inspector.get_indexes("jobs")}
        assert "ix_jobs_status_run_at" in job_indexes
    finally:
        engine.dispose()


def test_db_enforces_foreign_keys_and_check_constraints(tmp_path: Path) -> None:
    db_path = tmp_path / "test_constraints.db"
    url = _run_migrations(db_path)
    engine = create_db_engine(url)

    try:
        with Session(engine) as session:
            # Foreign key violation: created_by does not exist
            session.add(Project(key="BAD", name="Bad FK", created_by="nonexistent-user"))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

            # Valid user & project
            user = User(email="owner@example.com", name="Owner", password_hash="hash")
            session.add(user)
            session.flush()

            project = Project(key="APM", name="Agile PM", created_by=user.id)
            session.add(project)
            session.flush()

            # CHECK constraint violation on project_members.role
            session.add(ProjectMember(project_id=project.id, user_id=user.id, role="superadmin"))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        engine.dispose()
