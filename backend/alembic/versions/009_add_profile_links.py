"""add linkedin/github/portfolio URLs to profiles

Revision ID: 009
Revises: 008
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("linkedin_url", sa.String(2048), nullable=True))
    op.add_column("profiles", sa.Column("github_url", sa.String(2048), nullable=True))
    op.add_column("profiles", sa.Column("portfolio_url", sa.String(2048), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "portfolio_url")
    op.drop_column("profiles", "github_url")
    op.drop_column("profiles", "linkedin_url")
