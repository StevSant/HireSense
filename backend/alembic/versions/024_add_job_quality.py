"""add quality + quality_reason to ingested_jobs

Intrinsic, profile-independent job-quality classification (see JobQuality):
"ok" | "low_quality" | "spam". Defaults to "ok" with a server_default so every
existing row backfills to "ok" and nothing is hidden retroactively. The
ingestion orchestrator (re)classifies jobs on insert/update going forward.

Revision ID: 024
Revises: 023
Create Date: 2026-06-08
"""

from typing import Sequence, Union

from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ingested_jobs "
        "ADD COLUMN IF NOT EXISTS quality VARCHAR(20) NOT NULL DEFAULT 'ok'"
    )
    op.execute("ALTER TABLE ingested_jobs ADD COLUMN IF NOT EXISTS quality_reason TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE ingested_jobs DROP COLUMN IF EXISTS quality_reason")
    op.execute("ALTER TABLE ingested_jobs DROP COLUMN IF EXISTS quality")
