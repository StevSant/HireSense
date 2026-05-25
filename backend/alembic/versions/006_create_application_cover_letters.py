"""create application_cover_letters table

Revision ID: 006
Revises: 005
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_cover_letters",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("tracked_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "match_id",
            sa.Uuid(),
            sa.ForeignKey("application_matches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("tone", sa.String(20), nullable=False, server_default="professional"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_application_cover_letters_app_created",
        "application_cover_letters",
        ["application_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_application_cover_letters_app_created", table_name="application_cover_letters")
    op.drop_table("application_cover_letters")
