from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from hiresense.ingestion.infrastructure.models import IngestedJob


class CorpusAnalyticsRepository:
    """Read-only aggregation over the ingested-job corpus (status='open')."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def open_skill_lists(self) -> list[list[str]]:
        with self._session_factory() as session:
            stmt = select(IngestedJob.skills).where(IngestedJob.status == "open")
            return [list(row or []) for row in session.scalars(stmt).all()]

    def remote_modality_counts(self) -> dict[str, int]:
        with self._session_factory() as session:
            stmt = (
                select(IngestedJob.remote_modality, func.count())
                .where(IngestedJob.status == "open", IngestedJob.remote_modality.is_not(None))
                .group_by(IngestedJob.remote_modality)
            )
            return {row[0]: row[1] for row in session.execute(stmt).all()}

    def posting_dates(self) -> list[datetime]:
        with self._session_factory() as session:
            stmt = select(IngestedJob.posted_date).where(
                IngestedJob.status == "open", IngestedJob.posted_date.is_not(None)
            )
            return [d for d in session.scalars(stmt).all() if d is not None]

    def open_salary_strings(self) -> tuple[list[str], int]:
        with self._session_factory() as session:
            total = session.scalar(
                select(func.count()).select_from(IngestedJob).where(IngestedJob.status == "open")
            ) or 0
            stmt = select(IngestedJob.salary_range).where(
                IngestedJob.status == "open", IngestedJob.salary_range.is_not(None)
            )
            return [s for s in session.scalars(stmt).all() if s], int(total)

    def salary_strings_for_ids(self, job_ids: list[str]) -> dict[str, str | None]:
        if not job_ids:
            return {}
        with self._session_factory() as session:
            stmt = select(IngestedJob.id, IngestedJob.salary_range).where(
                IngestedJob.id.in_(job_ids)
            )
            return {row[0]: row[1] for row in session.execute(stmt).all()}
