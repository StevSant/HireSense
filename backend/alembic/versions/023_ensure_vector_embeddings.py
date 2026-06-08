"""ensure vector_embeddings exists (drift repair)

Reconciliation migration for environments whose `alembic_version` advanced past
revision 014 without its `vector_embeddings` table ever materializing on the
volume (observed on a long-lived dev DB stamped at a later revision; see the
2026-05/06 alembic-drift fixes). Migration 014 is correct and creates the table
on a fresh chain, but a drifted DB already records 014 as applied, so alembic
never re-runs it and the PgVectorStore queries fail with
`relation "vector_embeddings" does not exist` (the SemanticPreRanker then
degrades to passthrough — semantic ANN pre-ranking silently disabled).

This re-asserts 014's objects idempotently: a no-op on healthy databases
(`IF NOT EXISTS`), and the missing table/index get created on drifted ones.
Schema is kept byte-for-byte identical to migration 014.

Revision ID: 023
Revises: 022
Create Date: 2026-06-07
"""
import os
from typing import Sequence, Union

from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Vector dimension tracks EMBEDDING_DIM in config (all-mpnet-base-v2 = 768),
# mirroring migration 014 so a repaired table matches the original schema.
_DIM = int(os.environ.get("EMBEDDING_DIM", "768"))


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS vector_embeddings (
            id TEXT PRIMARY KEY,
            embedding vector({_DIM}) NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vector_embeddings_embedding "
        "ON vector_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    # No-op: the table's lifecycle is owned by migration 014's down path. This
    # repair migration must not drop an object it may not have created.
    pass
