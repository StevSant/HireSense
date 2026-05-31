"""create preference tables (feedback_signals, preference_models)

Backs the preference learning loop. Embeddings are stored as JSON float arrays
(the ANN query targets the separate vector_embeddings table; taste math is in
Python), so no pgvector column type is used here.

Revision ID: 016
Revises: 015
Create Date: 2026-05-31
"""
from typing import Sequence, Union

from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback_signals (
            id UUID PRIMARY KEY,
            job_id UUID NOT NULL,
            kind VARCHAR(32) NOT NULL,
            source VARCHAR(16) NOT NULL,
            job_embedding JSONB,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_feedback_signals_job_id ON feedback_signals (job_id)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS preference_models (
            id INTEGER PRIMARY KEY,
            delta_vector JSONB NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            updated_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS preference_models")
    op.execute("DROP INDEX IF EXISTS ix_feedback_signals_job_id")
    op.execute("DROP TABLE IF EXISTS feedback_signals")
