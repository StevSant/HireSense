"""add autopilot_drafts

Revision ID: 035
Revises: 034
Create Date: 2026-06-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "autopilot_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=True),
        sa.Column("job_title", sa.String(length=512), nullable=True),
        sa.Column("company", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_autopilot_drafts_job_id", "autopilot_drafts", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_autopilot_drafts_job_id", table_name="autopilot_drafts")
    op.drop_table("autopilot_drafts")
