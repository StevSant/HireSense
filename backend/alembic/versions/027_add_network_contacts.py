"""add network_contacts table

Revision ID: 027
Revises: 026
Create Date: 2026-06-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "network_contacts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("first_name", sa.String(length=256), nullable=False),
        sa.Column("last_name", sa.String(length=256), nullable=False),
        sa.Column("company", sa.String(length=512), nullable=False),
        sa.Column("position", sa.String(length=512), nullable=False),
        sa.Column("company_normalized", sa.String(length=512), nullable=False),
        sa.Column("linkedin_url", sa.String(length=2048), nullable=True),
        sa.Column("email", sa.String(length=512), nullable=True),
        sa.Column("connected_on", sa.String(length=64), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_network_contacts_company_normalized",
        "network_contacts",
        ["company_normalized"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_network_contacts_company_normalized", table_name="network_contacts")
    op.drop_table("network_contacts")
