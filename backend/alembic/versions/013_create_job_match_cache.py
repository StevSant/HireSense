"""create job_match_cache

Per-(job_id, profile_hash) cache for LLM match scoring. Holds the Tier-1 quick
score (shown on the job list) and the Tier-2 deep analysis (loaded on demand
in the detail panel). Keyed by a content hash of the candidate profile so the
cache self-invalidates when the CV changes. Purely derived/disposable data.

Revision ID: 013
Revises: 012
Create Date: 2026-05-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_match_cache",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("profile_hash", sa.String(length=64), nullable=False),
        sa.Column("quick_score", sa.Float(), nullable=True),
        sa.Column("quick_verdict", sa.String(length=16), nullable=True),
        sa.Column("quick_payload", sa.JSON(), nullable=True),
        sa.Column("quick_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deep_payload", sa.JSON(), nullable=True),
        sa.Column("deep_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "profile_hash", name="ux_job_match_cache_job_profile"),
    )
    op.create_index(
        "ix_job_match_cache_profile", "job_match_cache", ["profile_hash"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_job_match_cache_profile", table_name="job_match_cache")
    op.drop_table("job_match_cache")
