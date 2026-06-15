"""add apply_profile JSON column to profiles

Revision ID: 031
Revises: 030
Create Date: 2026-06-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("apply_profile", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("profiles", "apply_profile")
