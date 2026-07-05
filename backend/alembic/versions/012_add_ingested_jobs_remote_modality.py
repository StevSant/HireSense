"""add countries + remote_modality to ingested_jobs

Carries the source's hybrid/remote/on-site signal and country list through to
the API so the strict-location filter can reject hybrid/on-site postings in
mismatched countries instead of relying on naive substring matching.

Revision ID: 012
Revises: 011
Create Date: 2026-05-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ingested_jobs",
        sa.Column("countries", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "ingested_jobs",
        sa.Column("remote_modality", sa.String(length=20), nullable=True),
    )
    op.alter_column("ingested_jobs", "countries", server_default=None)


def downgrade() -> None:
    op.drop_column("ingested_jobs", "remote_modality")
    op.drop_column("ingested_jobs", "countries")
