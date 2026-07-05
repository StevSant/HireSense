"""add weight_overrides to preference_models (Phase 2 dimension-weight nudging)

Adds a JSONB column holding ``{dimension_name: integer_delta}`` applied on top
of each scorer's base weight in the matching composite. Nullable with no
backfill: existing rows read back as NULL and the repository maps that to "no
overrides", so scoring is unchanged until the nudge gate is met.

Revision ID: 020
Revises: 019
Create Date: 2026-06-07
"""

from typing import Sequence, Union

from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE preference_models ADD COLUMN IF NOT EXISTS weight_overrides JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE preference_models DROP COLUMN IF EXISTS weight_overrides")
