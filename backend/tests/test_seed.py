from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.seed import seed_demo_data
from app.models import Project, Report, Story, Task, User


def test_seed_demo_data_is_idempotent_and_creates_expected_counts(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as db:
        assert seed_demo_data(db) is True
        assert seed_demo_data(db) is False

        assert db.scalar(select(func.count(User.id))) == 3
        assert db.scalar(select(func.count(Project.id))) == 2
        assert db.scalar(select(func.count(Story.id))) == 8
        assert db.scalar(select(func.count(Task.id))) == 25
        assert db.scalar(select(func.count(Report.id))) == 1
