"""widen profile URL columns from VARCHAR(500) to VARCHAR(2048)

The ``profiles`` table stores ``linkedin_url``, ``github_url`` and
``portfolio_url`` as ``VARCHAR(500)`` (from an earlier migration), but the ORM
declares them as ``String(2048)``. This resolves that model/schema drift by
widening the DB columns to match the ORM. Widening a varchar is a metadata-only
change in Postgres (no table rewrite) and is fully reversible.

Revision ID: 022
Revises: 021
Create Date: 2026-06-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = ("linkedin_url", "github_url", "portfolio_url")


def upgrade() -> None:
    for column in _COLUMNS:
        op.alter_column(
            "profiles",
            column,
            existing_type=sa.String(length=500),
            type_=sa.String(length=2048),
            existing_nullable=True,
        )


def downgrade() -> None:
    for column in _COLUMNS:
        op.alter_column(
            "profiles",
            column,
            existing_type=sa.String(length=2048),
            type_=sa.String(length=500),
            existing_nullable=True,
        )
