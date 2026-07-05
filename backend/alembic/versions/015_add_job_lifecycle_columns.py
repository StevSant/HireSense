"""add job lifecycle columns to ingested_jobs

Replaces the content-derived dedup_key with a stable identity_key
(source_id or sha256(url)) and adds change/closure-tracking columns.

Revision ID: 015
Revises: 014
Create Date: 2026-05-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.add_column("ingested_jobs", sa.Column("identity_key", sa.String(length=64), nullable=True))
    op.add_column("ingested_jobs", sa.Column("source_id", sa.String(length=255), nullable=True))
    op.add_column(
        "ingested_jobs",
        sa.Column("status", sa.String(length=10), nullable=False, server_default="open"),
    )
    op.add_column(
        "ingested_jobs",
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column(
        "ingested_jobs", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "ingested_jobs", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "ingested_jobs", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "ingested_jobs", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "ingested_jobs", sa.Column("missed_count", sa.Integer(), nullable=False, server_default="0")
    )

    op.execute(
        "UPDATE ingested_jobs SET identity_key = encode(digest(url, 'sha256'), 'hex') WHERE identity_key IS NULL"
    )
    op.execute("UPDATE ingested_jobs SET last_seen_at = fetched_at WHERE last_seen_at IS NULL")

    op.alter_column("ingested_jobs", "identity_key", nullable=False)
    op.alter_column(
        "ingested_jobs", "last_seen_at", nullable=False, server_default=sa.text("now()")
    )

    op.drop_index("ux_ingested_jobs_bucket_dedup", table_name="ingested_jobs")
    op.drop_column("ingested_jobs", "dedup_key")

    op.create_unique_constraint(
        "ux_ingested_jobs_bucket_source_identity",
        "ingested_jobs",
        ["bucket", "source", "identity_key"],
    )
    op.create_index(
        "ix_ingested_jobs_bucket_status_checked",
        "ingested_jobs",
        ["bucket", "status", "last_checked_at"],
    )

    op.alter_column("ingested_jobs", "status", server_default=None)
    op.alter_column("ingested_jobs", "content_hash", server_default=None)
    op.alter_column("ingested_jobs", "missed_count", server_default=None)


def downgrade() -> None:
    op.add_column("ingested_jobs", sa.Column("dedup_key", sa.String(length=64), nullable=True))
    op.execute("UPDATE ingested_jobs SET dedup_key = identity_key WHERE dedup_key IS NULL")
    op.alter_column("ingested_jobs", "dedup_key", nullable=False)
    op.drop_index("ix_ingested_jobs_bucket_status_checked", "ingested_jobs")
    op.drop_constraint("ux_ingested_jobs_bucket_source_identity", "ingested_jobs", type_="unique")
    op.create_index(
        "ux_ingested_jobs_bucket_dedup", "ingested_jobs", ["bucket", "dedup_key"], unique=True
    )
    for col in (
        "missed_count",
        "updated_at",
        "closed_at",
        "last_checked_at",
        "last_seen_at",
        "content_hash",
        "status",
        "source_id",
        "identity_key",
    ):
        op.drop_column("ingested_jobs", col)
