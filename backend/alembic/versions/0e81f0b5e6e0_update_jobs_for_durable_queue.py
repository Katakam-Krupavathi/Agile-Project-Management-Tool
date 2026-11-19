"""update_jobs_for_durable_queue

Revision ID: 0e81f0b5e6e0
Revises: 75d5cd9b3dcc
Create Date: 2026-11-20 03:47:41
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0e81f0b5e6e0"
down_revision: str | Sequence[str] | None = "75d5cd9b3dcc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE jobs SET status = 'queued' WHERE status = 'pending'")
    with op.batch_alter_table("jobs", schema=None, recreate="always") as batch_op:
        batch_op.drop_constraint(op.f("ck_jobs_status_valid"), type_="check")
        batch_op.add_column(sa.Column("result", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("project_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("created_by", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_check_constraint(
            "status_valid",
            "status IN ('queued', 'running', 'succeeded', 'failed', 'dead')",
        )
        batch_op.create_foreign_key(
            op.f("fk_jobs_project_id_projects"),
            "projects",
            ["project_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            op.f("fk_jobs_created_by_users"),
            "users",
            ["created_by"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    op.execute("UPDATE jobs SET status = 'pending' WHERE status = 'queued'")
    with op.batch_alter_table("jobs", schema=None, recreate="always") as batch_op:
        batch_op.drop_constraint(op.f("fk_jobs_created_by_users"), type_="foreignkey")
        batch_op.drop_constraint(op.f("fk_jobs_project_id_projects"), type_="foreignkey")
        batch_op.drop_constraint(op.f("ck_jobs_status_valid"), type_="check")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("created_by")
        batch_op.drop_column("project_id")
        batch_op.drop_column("result")
        batch_op.create_check_constraint(
            "status_valid",
            "status IN ('pending', 'running', 'succeeded', 'failed', 'dead')",
        )
