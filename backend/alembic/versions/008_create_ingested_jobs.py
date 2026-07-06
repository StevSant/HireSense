"""create ingested_jobs table

Revision ID: 008
Revises: 007
Create Date: 2026-05-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingested_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bucket", sa.String(20), nullable=False, server_default="boards"),
        sa.Column("dedup_key", sa.String(64), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("company", sa.String(255), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("location", sa.Text(), nullable=False, server_default=""),
        sa.Column("salary_range", sa.Text(), nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("url", sa.String(2048), nullable=False, server_default=""),
        sa.Column("posted_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("department", sa.Text(), nullable=True),
        sa.Column("skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("categories", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("semantic_score", sa.Float(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ux_ingested_jobs_bucket_dedup",
        "ingested_jobs",
        ["bucket", "dedup_key"],
        unique=True,
    )
    op.create_index(
        "ix_ingested_jobs_bucket_fetched_at",
        "ingested_jobs",
        ["bucket", "fetched_at"],
    )
    op.create_index("ix_ingested_jobs_source", "ingested_jobs", ["source"])


def downgrade() -> None:
    op.drop_index("ix_ingested_jobs_source", table_name="ingested_jobs")
    op.drop_index("ix_ingested_jobs_bucket_fetched_at", table_name="ingested_jobs")
    op.drop_index("ux_ingested_jobs_bucket_dedup", table_name="ingested_jobs")
    op.drop_table("ingested_jobs")
