"""add employment_type, equity_range, source_metadata to ingested jobs

Revision ID: 042
Revises: 041
Create Date: 2026-07-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "042"
down_revision: Union[str, None] = "041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ingested_jobs",
        sa.Column("employment_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "ingested_jobs",
        sa.Column("equity_range", sa.Text(), nullable=True),
    )
    op.add_column(
        "ingested_jobs",
        sa.Column("source_metadata", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingested_jobs", "source_metadata")
    op.drop_column("ingested_jobs", "equity_range")
    op.drop_column("ingested_jobs", "employment_type")
