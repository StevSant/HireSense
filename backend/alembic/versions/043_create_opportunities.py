"""create opportunities table

Revision ID: 043
Revises: 042
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "043"
down_revision: Union[str, None] = "042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("organization", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("apply_url", sa.String(length=2048), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("cfp_deadline", sa.Date(), nullable=True),
        sa.Column("application_deadline", sa.Date(), nullable=True),
        sa.Column("funding", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("identity_key", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "identity_key", name="ux_opportunities_source_identity"),
    )
    op.create_index("ix_opportunities_kind", "opportunities", ["kind"])
    op.create_index("ix_opportunities_status", "opportunities", ["status"])
    op.create_index("ix_opportunities_country", "opportunities", ["country"])
    op.create_index("ix_opportunities_cfp_deadline", "opportunities", ["cfp_deadline"])
    op.create_index(
        "ix_opportunities_application_deadline", "opportunities", ["application_deadline"]
    )


def downgrade() -> None:
    op.drop_index("ix_opportunities_application_deadline", table_name="opportunities")
    op.drop_index("ix_opportunities_cfp_deadline", table_name="opportunities")
    op.drop_index("ix_opportunities_country", table_name="opportunities")
    op.drop_index("ix_opportunities_status", table_name="opportunities")
    op.drop_index("ix_opportunities_kind", table_name="opportunities")
    op.drop_table("opportunities")
