"""create submission attempts and their audit events

Revision ID: 051
Revises: 050
Create Date: 2026-08-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "051"
down_revision: Union[str, None] = "050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "submission_attempts",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("packet_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("attempt_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
        sa.Column("escalated_fields", sa.JSON(), nullable=False),
        sa.Column("runner_id", sa.String(length=64), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["tracked_applications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_submission_attempts_status", "submission_attempts", ["status"])
    op.create_index(
        "ix_submission_attempts_status_created",
        "submission_attempts",
        ["status", "created_at"],
    )
    op.create_index("ix_submission_attempts_application", "submission_attempts", ["application_id"])

    op.create_table(
        "submission_events",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["attempt_id"], ["submission_attempts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_submission_events_attempt_seq", "submission_events", ["attempt_id", "seq"])


def downgrade() -> None:
    op.drop_index("ix_submission_events_attempt_seq", table_name="submission_events")
    op.drop_table("submission_events")
    op.drop_index("ix_submission_attempts_application", table_name="submission_attempts")
    op.drop_index("ix_submission_attempts_status_created", table_name="submission_attempts")
    op.drop_index("ix_submission_attempts_status", table_name="submission_attempts")
    op.drop_table("submission_attempts")
