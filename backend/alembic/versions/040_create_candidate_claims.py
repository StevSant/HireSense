"""create candidate claims ledger

Revision ID: 040
Revises: 039
Create Date: 2026-07-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidate_claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("provenance", sa.Text(), nullable=False),
        sa.Column("verification_status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_claims_verification_status",
        "candidate_claims",
        ["verification_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_claims_verification_status", table_name="candidate_claims")
    op.drop_table("candidate_claims")
