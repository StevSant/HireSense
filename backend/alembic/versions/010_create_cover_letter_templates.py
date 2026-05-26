"""create cover_letter_templates table

Revision ID: 010
Revises: 009
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cover_letter_templates",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("tone", sa.String(20), nullable=False, server_default="professional"),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("opening", sa.Text(), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("signature", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_cover_letter_templates_updated_at",
        "cover_letter_templates",
        ["updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cover_letter_templates_updated_at", table_name="cover_letter_templates"
    )
    op.drop_table("cover_letter_templates")
