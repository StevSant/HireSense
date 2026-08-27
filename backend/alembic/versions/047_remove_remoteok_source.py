"""remove RemoteOK listings and derived data

RemoteOK's apply flow requires a paid subscription and never exposes the
employer application URL. The source was removed from the product, so discard
its persisted listings and data derived exclusively from those listings.

Revision ID: 047
Revises: 046
Create Date: 2026-08-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "047"
down_revision: Union[str, None] = "046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # These tables are derived from an ingested job and have no FK in older
    # migrations, so remove them explicitly before removing the source rows.
    op.execute(
        """
        DELETE FROM job_match_cache
        WHERE job_id IN (SELECT id FROM ingested_jobs WHERE source = 'remoteok')
        """
    )
    op.execute(
        """
        DELETE FROM vector_embeddings
        WHERE id IN (SELECT id FROM ingested_jobs WHERE source = 'remoteok')
        """
    )
    op.execute(
        """
        DELETE FROM feedback_signals
        WHERE job_id::text IN (SELECT id FROM ingested_jobs WHERE source = 'remoteok')
        """
    )
    op.execute(
        """
        DELETE FROM autopilot_drafts
        WHERE job_id IN (SELECT id FROM ingested_jobs WHERE source = 'remoteok')
        """
    )
    # A tracked application is a user-visible copy of a job; remove it too so
    # the deleted source cannot remain in the application pipeline. Its
    # artifact rows cascade from tracked_applications.
    op.execute("DELETE FROM tracked_applications WHERE lower(coalesce(source, '')) = 'remoteok'")
    # job_history_events has ON DELETE CASCADE, but explicit deletion keeps the
    # cleanup correct on databases created before that FK was added.
    op.execute(
        """
        DELETE FROM job_history_events
        WHERE job_id IN (SELECT id FROM ingested_jobs WHERE source = 'remoteok')
        """
    )
    op.execute("DELETE FROM ingested_jobs WHERE source = 'remoteok'")


def downgrade() -> None:
    # Deleted source data cannot be reconstructed.
    pass
