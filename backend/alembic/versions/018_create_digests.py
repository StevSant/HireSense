"""create digests (auto-hunt run log + top-N new-match snapshots)

Revision ID: 018
Revises: 017
Create Date: 2026-05-31
"""
from typing import Sequence, Union

from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS digests (
            id UUID PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            cutoff_at TIMESTAMPTZ NOT NULL,
            entries JSONB NOT NULL DEFAULT '[]'::jsonb,
            job_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_digests_created_at ON digests (created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_digests_created_at")
    op.execute("DROP TABLE IF EXISTS digests")
