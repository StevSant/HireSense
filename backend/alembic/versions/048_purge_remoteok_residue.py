"""purge RemoteOK residue after source retirement

Revision ID: 048
Revises: 047
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "048"
down_revision: Union[str, None] = "047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove rows that survived the initial source-retirement migration."""
    source_jobs = """
        SELECT id FROM ingested_jobs
        WHERE lower(coalesce(source, '')) = 'remoteok'
    """

    op.execute(f"DELETE FROM job_match_cache WHERE job_id IN ({source_jobs})")
    op.execute(f"DELETE FROM vector_embeddings WHERE id IN ({source_jobs})")
    op.execute(f"DELETE FROM feedback_signals WHERE job_id::text IN ({source_jobs})")
    op.execute(f"DELETE FROM autopilot_drafts WHERE job_id IN ({source_jobs})")
    op.execute("DELETE FROM tracked_applications WHERE lower(coalesce(source, '')) = 'remoteok'")
    op.execute(f"DELETE FROM job_history_events WHERE job_id IN ({source_jobs})")
    op.execute("DELETE FROM ingested_jobs WHERE lower(coalesce(source, '')) = 'remoteok'")


def downgrade() -> None:
    # Deleted source data cannot be reconstructed.
    pass
