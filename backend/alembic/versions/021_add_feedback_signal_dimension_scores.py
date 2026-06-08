"""add dimension_scores to feedback_signals (Phase 2 nudge activation)

Adds a JSONB column holding ``{dimension_name: score}`` snapshotted from the
matching dimension scorers at outcome time. Nullable with no backfill: existing
rows (and explicit signals) read back as NULL, which the repository maps to
domain ``None`` so those signals contribute nothing to weight nudging and
matching stays unchanged until enough outcome signals carry scores.

Revision ID: 021
Revises: 020
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE feedback_signals ADD COLUMN IF NOT EXISTS dimension_scores JSONB"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE feedback_signals DROP COLUMN IF EXISTS dimension_scores")
