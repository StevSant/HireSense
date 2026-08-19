"""create job_history_events table

Revision ID: 046
Revises: 045
Create Date: 2026-08-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_history_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("event", sa.String(length=20), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("reason", sa.String(length=40), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["job_id"], ["ingested_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_runs.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_job_history_events_job_occurred", "job_history_events", ["job_id", "occurred_at"]
    )
    op.create_index("ix_job_history_events_run", "job_history_events", ["run_id"])
    op.create_index("ix_job_history_events_occurred", "job_history_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_job_history_events_occurred", table_name="job_history_events")
    op.drop_index("ix_job_history_events_run", table_name="job_history_events")
    op.drop_index("ix_job_history_events_job_occurred", table_name="job_history_events")
    op.drop_table("job_history_events")
