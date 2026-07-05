"""create application_status_history (+ backfill one seed row per existing app)

Backs the funnel analytics. Each tracked-application status change appends a
row (written transactionally by the tracking repository). Existing applications
are seeded with a single NULL->current_status row timestamped at applied_at or
created_at.

Revision ID: 017
Revises: 016
Create Date: 2026-05-31
"""

import uuid
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS application_status_history (
            id UUID PRIMARY KEY,
            application_id UUID NOT NULL,
            from_status VARCHAR(20),
            to_status VARCHAR(20) NOT NULL,
            changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_application_status_history_application_id "
        "ON application_status_history (application_id)"
    )
    conn = op.get_bind()
    rows = conn.execute(
        text("SELECT id, status, applied_at, created_at FROM tracked_applications")
    ).fetchall()
    for r in rows:
        conn.execute(
            text(
                "INSERT INTO application_status_history "
                "(id, application_id, from_status, to_status, changed_at) "
                "VALUES (:id, :app_id, NULL, :to_status, :changed_at)"
            ),
            {
                "id": str(uuid.uuid4()),
                "app_id": r.id,
                "to_status": r.status,
                "changed_at": r.applied_at or r.created_at,
            },
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_application_status_history_application_id")
    op.execute("DROP TABLE IF EXISTS application_status_history")
