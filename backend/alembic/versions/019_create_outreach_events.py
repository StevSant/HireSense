"""create outreach_events (append-only outreach log per application)

Revision ID: 019
Revises: 018
Create Date: 2026-05-31
"""

from typing import Sequence, Union

from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_events (
            id UUID PRIMARY KEY,
            application_id UUID NOT NULL,
            kind VARCHAR(16) NOT NULL,
            contact_name VARCHAR(255),
            channel VARCHAR(32),
            message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_outreach_events_application_id "
        "ON outreach_events (application_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_outreach_events_application_id")
    op.execute("DROP TABLE IF EXISTS outreach_events")
