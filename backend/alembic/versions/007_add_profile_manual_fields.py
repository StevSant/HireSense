"""add manual override + URL fields to profiles

Revision ID: 007
Revises: 006
Create Date: 2026-05-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("name_override", sa.String(255), nullable=True))
    op.add_column("profiles", sa.Column("location_override", sa.String(255), nullable=True))
    op.add_column("profiles", sa.Column("linkedin_url", sa.String(500), nullable=True))
    op.add_column("profiles", sa.Column("github_url", sa.String(500), nullable=True))
    op.add_column("profiles", sa.Column("portfolio_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "portfolio_url")
    op.drop_column("profiles", "github_url")
    op.drop_column("profiles", "linkedin_url")
    op.drop_column("profiles", "location_override")
    op.drop_column("profiles", "name_override")
