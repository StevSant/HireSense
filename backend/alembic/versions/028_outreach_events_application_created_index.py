"""replace outreach_events application_id index with composite (application_id, created_at)

Revision ID: 028
Revises: 027
Create Date: 2026-06-10
"""

from typing import Sequence, Union

from alembic import op

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_outreach_events_application_id", table_name="outreach_events")
    op.create_index(
        "ix_outreach_events_application_created",
        "outreach_events",
        ["application_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_outreach_events_application_created", table_name="outreach_events")
    op.create_index(
        "ix_outreach_events_application_id",
        "outreach_events",
        ["application_id"],
        unique=False,
    )
