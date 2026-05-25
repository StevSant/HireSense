"""create application artifact tables and backfill snapshots

Revision ID: 005
Revises: 004
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_job_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("tracked_applications.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("required_skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "application_matches",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("tracked_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("semantic_score", sa.Float(), nullable=False),
        sa.Column("skill_score", sa.Float(), nullable=False),
        sa.Column("experience_score", sa.Float(), nullable=False),
        sa.Column("language_score", sa.Float(), nullable=False),
        sa.Column("matched_skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("missing_skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("pros", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("cons", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("recommendations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("cv_language", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_application_matches_app_created",
        "application_matches",
        ["application_id", "created_at"],
    )

    op.create_table(
        "application_cv_optimizations",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("tracked_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "match_id",
            sa.Uuid(),
            sa.ForeignKey("application_matches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("cv_language", sa.String(10), nullable=False),
        sa.Column("original_tex", sa.Text(), nullable=False),
        sa.Column("optimized_tex", sa.Text(), nullable=False),
        sa.Column("improvement_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("changes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_application_cv_opts_app_created",
        "application_cv_optimizations",
        ["application_id", "created_at"],
    )

    op.create_table(
        "application_interview_preps",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("tracked_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("competencies_to_probe", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("technical_topics", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("negotiation_points", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("matched_stories", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_application_interview_preps_app_created",
        "application_interview_preps",
        ["application_id", "created_at"],
    )

    # Backfill: each existing tracked_application gets an empty job snapshot.
    # Source is 'manual' because we cannot reliably reconstruct ingested-job
    # description/skills here (the normalized_jobs table may have changed).
    op.execute(
        """
        INSERT INTO application_job_snapshots (id, application_id, description, required_skills, source)
        SELECT gen_random_uuid(), ta.id, '', '[]'::json, 'manual'
        FROM tracked_applications ta
        LEFT JOIN application_job_snapshots ajs ON ajs.application_id = ta.id
        WHERE ajs.id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_application_interview_preps_app_created", table_name="application_interview_preps")
    op.drop_table("application_interview_preps")
    op.drop_index("ix_application_cv_opts_app_created", table_name="application_cv_optimizations")
    op.drop_table("application_cv_optimizations")
    op.drop_index("ix_application_matches_app_created", table_name="application_matches")
    op.drop_table("application_matches")
    op.drop_table("application_job_snapshots")
