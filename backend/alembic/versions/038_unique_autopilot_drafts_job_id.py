"""unique constraint on autopilot_drafts.job_id

Makes a reserved draft the idempotency guard for the autopilot pipeline: two
concurrent runs racing on the same job can no longer both insert a draft row.

Pre-existing duplicate rows (from before this guard existed) are collapsed to a
single row per job_id — the earliest by created_at — before the unique index is
created, otherwise the CREATE UNIQUE INDEX would fail.

Revision ID: 038
Revises: 037
Create Date: 2026-07-20
"""

from typing import Sequence, Union

from alembic import op

revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Collapse any pre-existing duplicates, keeping the earliest row per job_id.
    op.execute(
        """
        DELETE FROM autopilot_drafts
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY job_id
                           ORDER BY created_at ASC, id ASC
                       ) AS rn
                FROM autopilot_drafts
            ) ranked
            WHERE ranked.rn > 1
        )
        """
    )
    op.drop_index("ix_autopilot_drafts_job_id", table_name="autopilot_drafts")
    op.create_index("ix_autopilot_drafts_job_id", "autopilot_drafts", ["job_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_autopilot_drafts_job_id", table_name="autopilot_drafts")
    op.create_index("ix_autopilot_drafts_job_id", "autopilot_drafts", ["job_id"])
