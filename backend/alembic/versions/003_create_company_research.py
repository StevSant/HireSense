"""create company_research table

Revision ID: 003
Revises: 002
Create Date: 2026-04-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_research",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("funding_stage", sa.String(100), nullable=False),
        sa.Column("tech_stack", sa.Text(), nullable=False),
        sa.Column("culture_summary", sa.Text(), nullable=False),
        sa.Column("growth_trajectory", sa.Text(), nullable=False),
        sa.Column("red_flags", sa.Text(), nullable=True),
        sa.Column("pros", sa.Text(), nullable=False),
        sa.Column("cons", sa.Text(), nullable=False),
        sa.Column("raw_llm_response", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True
        ),
    )
    op.create_index(
        "ix_company_research_company_name", "company_research", ["company_name"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_company_research_company_name", table_name="company_research")
    op.drop_table("company_research")
