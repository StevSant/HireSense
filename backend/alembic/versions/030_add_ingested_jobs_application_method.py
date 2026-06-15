"""add apply_url, application_method, ats_type to ingested_jobs

Revision ID: 030
Revises: 029
Create Date: 2026-06-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ingested_jobs",
        sa.Column("apply_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "ingested_jobs",
        sa.Column(
            "application_method",
            sa.String(length=20),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "ingested_jobs",
        sa.Column("ats_type", sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingested_jobs", "ats_type")
    op.drop_column("ingested_jobs", "application_method")
    op.drop_column("ingested_jobs", "apply_url")
