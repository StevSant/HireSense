"""widen ingested_jobs text-ish columns to TEXT

Some adapters (Himalayas) emit comma-separated multi-country location strings
that exceed 500 chars. Title/salary_range/department can also exceed their
caps for niche postings. Promote them to TEXT; URL stays bounded because
HTTP URLs rarely exceed 2KB.

Revision ID: 011
Revises: 010
Create Date: 2026-05-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_WIDEN = ("title", "location", "salary_range", "department")


def upgrade() -> None:
    for column in _WIDEN:
        op.alter_column(
            "ingested_jobs",
            column,
            type_=sa.Text(),
            existing_type=sa.String(length=500),
            existing_nullable=column in ("salary_range", "department"),
        )


def downgrade() -> None:
    for column in _WIDEN:
        op.alter_column(
            "ingested_jobs",
            column,
            type_=sa.String(length=500),
            existing_type=sa.Text(),
            existing_nullable=column in ("salary_range", "department"),
            postgresql_using=f"substr({column}, 1, 500)",
        )
