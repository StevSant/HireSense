"""add portfolio_projects table

Revision ID: 026
Revises: 025
Create Date: 2026-06-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_projects",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_key", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("demo_url", sa.String(length=2048), nullable=True),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column(
            "tech",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "translations",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_key", name="ux_portfolio_projects_source_key"),
    )
    op.create_index("ix_portfolio_projects_source", "portfolio_projects", ["source"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_portfolio_projects_source", table_name="portfolio_projects")
    op.drop_table("portfolio_projects")
