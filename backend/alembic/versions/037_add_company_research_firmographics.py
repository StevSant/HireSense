"""add firmographics to company_research

Revision ID: 037
Revises: 036
Create Date: 2026-07-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company_research",
        sa.Column("industry", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "company_research",
        sa.Column("company_size", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "company_research",
        sa.Column("headquarters", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "company_research",
        sa.Column("website", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("company_research", "website")
    op.drop_column("company_research", "headquarters")
    op.drop_column("company_research", "company_size")
    op.drop_column("company_research", "industry")
