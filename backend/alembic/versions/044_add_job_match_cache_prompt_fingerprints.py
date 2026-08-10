"""add prompt fingerprints to job_match_cache

Records which prompt produced each cached tier of a match result. A read whose
current prompt fingerprint differs is treated as a miss, so editing a scoring
prompt invalidates its own cached results instead of silently serving scores
from two different rubrics side by side in one list.

Both columns are nullable and backfilled to NULL on purpose: every existing row
predates fingerprinting, cannot be attributed to a prompt, and so must miss.
job_match_cache is explicitly derived and disposable — it repopulates lazily.

Revision ID: 044
Revises: 043
Create Date: 2026-08-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "044"
down_revision: Union[str, None] = "043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "job_match_cache",
        sa.Column("quick_prompt_fingerprint", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "job_match_cache",
        sa.Column("deep_prompt_fingerprint", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("job_match_cache", "deep_prompt_fingerprint")
    op.drop_column("job_match_cache", "quick_prompt_fingerprint")
