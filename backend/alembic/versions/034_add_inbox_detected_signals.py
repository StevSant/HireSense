"""add inbox_detected_signals

Revision ID: 034
Revises: 033
Create Date: 2026-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inbox_detected_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.String(length=512), nullable=False),
        sa.Column("from_address", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("company", sa.String(length=256), nullable=True),
        sa.Column("role", sa.String(length=256), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("matched_application_id", sa.Uuid(), nullable=True),
        sa.Column("proposed_status", sa.String(length=16), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inbox_detected_signals_message_id",
        "inbox_detected_signals",
        ["message_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_inbox_detected_signals_message_id", table_name="inbox_detected_signals")
    op.drop_table("inbox_detected_signals")
