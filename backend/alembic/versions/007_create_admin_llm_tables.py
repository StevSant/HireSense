"""create admin LLM tables (settings, feature_overrides, usage_log, audit_log)

Revision ID: 007
Revises: 006
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("extra_params", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name="llm_settings_single_row"),
    )

    op.create_table(
        "llm_feature_overrides",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("feature_key", sa.String(64), nullable=False, unique=True),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("extra_params", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "llm_usage_log",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("feature_key", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("user_id", sa.String(128), nullable=True),
    )
    op.create_index("ix_llm_usage_log_created_at", "llm_usage_log", ["created_at"])
    op.create_index("ix_llm_usage_log_feature_created", "llm_usage_log", ["feature_key", "created_at"])
    op.create_index("ix_llm_usage_log_provider_model", "llm_usage_log", ["provider", "model"])

    op.create_table(
        "llm_audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actor", sa.String(128), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target", sa.String(128), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_llm_audit_log_created_at", "llm_audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_llm_audit_log_created_at", table_name="llm_audit_log")
    op.drop_table("llm_audit_log")
    op.drop_index("ix_llm_usage_log_provider_model", table_name="llm_usage_log")
    op.drop_index("ix_llm_usage_log_feature_created", table_name="llm_usage_log")
    op.drop_index("ix_llm_usage_log_created_at", table_name="llm_usage_log")
    op.drop_table("llm_usage_log")
    op.drop_table("llm_feature_overrides")
    op.drop_table("llm_settings")
