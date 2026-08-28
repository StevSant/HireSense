"""add source evidence to inbox signals

Revision ID: 050
Revises: 049
Create Date: 2026-08-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "050"
down_revision: Union[str, None] = "049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inbox_detected_signals",
        sa.Column("evidence_excerpt", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "inbox_detected_signals",
        sa.Column("evidence_hash", sa.String(length=64), nullable=False, server_default=""),
    )
    op.alter_column("inbox_detected_signals", "evidence_excerpt", server_default=None)
    op.alter_column("inbox_detected_signals", "evidence_hash", server_default=None)


def downgrade() -> None:
    op.drop_column("inbox_detected_signals", "evidence_hash")
    op.drop_column("inbox_detected_signals", "evidence_excerpt")
