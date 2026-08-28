"""create immutable application packets

Revision ID: 049
Revises: 048
Create Date: 2026-08-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "049"
down_revision: Union[str, None] = "048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_packets",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("job_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("profile_hash", sa.String(length=64), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=True),
        sa.Column("optimization_id", sa.Uuid(), nullable=True),
        sa.Column("cover_letter_id", sa.Uuid(), nullable=True),
        sa.Column("verified_claim_ids", sa.JSON(), nullable=False),
        sa.Column("cv_content_hash", sa.String(length=64), nullable=True),
        sa.Column("cover_letter_content_hash", sa.String(length=64), nullable=True),
        sa.Column("quality_report", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["application_id"], ["tracked_applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_application_packets_application_created", "application_packets", ["application_id", "created_at"])
    op.create_index("ix_application_packets_state", "application_packets", ["state"])


def downgrade() -> None:
    op.drop_index("ix_application_packets_state", table_name="application_packets")
    op.drop_index("ix_application_packets_application_created", table_name="application_packets")
    op.drop_table("application_packets")
