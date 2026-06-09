"""index vector_embeddings metadata bucket

PgVectorStore.search() always filters by metadata->>'bucket' ("boards" /
"portals") before the HNSW ANN ordering. Without an index that filter is a
sequential scan over every vector row; an expression index keeps the filtered
ANN search cheap as the corpus grows.

Revision ID: 025
Revises: 024
Create Date: 2026-06-09
"""

from typing import Sequence, Union

from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vector_embeddings_bucket "
        "ON vector_embeddings ((metadata->>'bucket'))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_vector_embeddings_bucket")
