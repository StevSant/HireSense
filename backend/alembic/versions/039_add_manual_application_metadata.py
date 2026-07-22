"""add manual application listing metadata

Revision ID: 039
Revises: 038
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tracked_applications", sa.Column("location", sa.Text(), nullable=True))
    op.add_column(
        "tracked_applications", sa.Column("remote_modality", sa.String(length=20), nullable=True)
    )
    op.add_column("tracked_applications", sa.Column("salary_range", sa.Text(), nullable=True))
    op.add_column("tracked_applications", sa.Column("source", sa.String(length=100), nullable=True))
    op.add_column(
        "tracked_applications", sa.Column("posted_date", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("tracked_applications", "posted_date")
    op.drop_column("tracked_applications", "source")
    op.drop_column("tracked_applications", "salary_range")
    op.drop_column("tracked_applications", "remote_modality")
    op.drop_column("tracked_applications", "location")
