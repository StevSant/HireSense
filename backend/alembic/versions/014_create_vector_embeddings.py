"""create vector_embeddings (pgvector)

Generic vector store for semantic search: (id, embedding, metadata). Backs the
VectorStorePort / PgVectorStore adapter and replaces the in-memory cosine cache
for job embeddings. Requires the Postgres `pgvector` extension.

Revision ID: 014
Revises: 013
Create Date: 2026-05-30
"""

import os
from typing import Sequence, Union

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Vector dimension tracks EMBEDDING_DIM in config (all-mpnet-base-v2 = 768).
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
    # Approximate-nearest-neighbour index for cosine distance (`<=>`).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vector_embeddings_embedding "
        "ON vector_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_vector_embeddings_embedding")
    op.execute("DROP TABLE IF EXISTS vector_embeddings")
    # Leave the `vector` extension installed — other objects may depend on it.
