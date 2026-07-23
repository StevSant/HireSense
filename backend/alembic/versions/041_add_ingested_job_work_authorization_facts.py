"""add structured work-authorization facts to ingested jobs

Revision ID: 041
Revises: 040
Create Date: 2026-07-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ingested_jobs",
        sa.Column("requires_existing_work_authorization", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "ingested_jobs",
        sa.Column("visa_sponsorship_available", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingested_jobs", "visa_sponsorship_available")
    op.drop_column("ingested_jobs", "requires_existing_work_authorization")
