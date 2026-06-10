from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from hiresense.infrastructure import SqlRepository
from hiresense.ingestion.infrastructure.models import IngestedJob


@dataclasses.dataclass(frozen=True)
class CorpusJobRow:
    """A read-only projection of an ingested job for analytics enrichment."""

    id: str
    title: str
    company: str
    location: str
    source: str
    salary_range: str | None
    posted_date: datetime | None
    remote_modality: str | None
    status: str
    quality: str


class CorpusAnalyticsRepository(SqlRepository):
    """Read-only aggregation over the ingested-job corpus (status='open').

    The full-corpus scans (`open_skill_lists`, `posting_dates`,
    `open_salary_strings`) read every open posting into memory. To keep that
    bounded as the corpus grows, each scan is capped at `sample_cap` rows — the
    resulting aggregates are computed over a SAMPLE of up to that many open
    postings rather than the entire corpus.
    """

    def __init__(self, session_factory: Any, sample_cap: int) -> None:
        super().__init__(session_factory)
        self._sample_cap = sample_cap

    def open_skill_lists(self) -> list[list[str]]:
        with self._session_factory() as session:
            stmt = (
                select(IngestedJob.skills)
                .where(IngestedJob.status == "open")
                .limit(self._sample_cap)
            )
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
            stmt = (
                select(IngestedJob.posted_date)
                .where(IngestedJob.status == "open", IngestedJob.posted_date.is_not(None))
                .limit(self._sample_cap)
            )
            return [d for d in session.scalars(stmt).all() if d is not None]

    def open_salary_strings(self) -> tuple[list[str], int]:
        with self._session_factory() as session:
            # Cap the denominator at the same sample size so disclosed_pct stays
            # a valid sample estimate (share of sampled open postings with a
            # salary string) rather than mixing a full-corpus count with a
            # capped numerator.
            open_count = session.scalar(
                select(func.count()).select_from(IngestedJob).where(IngestedJob.status == "open")
            ) or 0
            total = min(int(open_count), self._sample_cap)
            stmt = (
                select(IngestedJob.salary_range)
                .where(IngestedJob.status == "open", IngestedJob.salary_range.is_not(None))
                .limit(self._sample_cap)
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

    def descriptions_for_ids(self, job_ids: list[str]) -> dict[str, str]:
        """Job descriptions keyed by id (for seniority detection on matched jobs)."""
        if not job_ids:
            return {}
        with self._session_factory() as session:
            stmt = select(IngestedJob.id, IngestedJob.description).where(
                IngestedJob.id.in_(job_ids)
            )
            return {row[0]: (row[1] or "") for row in session.execute(stmt).all()}

    def rows_for_ids(self, job_ids: list[str]) -> dict[str, CorpusJobRow]:
        """Full projections keyed by id — enrichment for comp / focus / by-source.

        Returns only the ids that exist; callers filter on status/quality.
        """
        if not job_ids:
            return {}
        with self._session_factory() as session:
            stmt = select(
                IngestedJob.id, IngestedJob.title, IngestedJob.company, IngestedJob.location,
                IngestedJob.source, IngestedJob.salary_range, IngestedJob.posted_date,
                IngestedJob.remote_modality, IngestedJob.status, IngestedJob.quality,
            ).where(IngestedJob.id.in_(job_ids))
            return {
                r[0]: CorpusJobRow(
                    id=r[0], title=r[1] or "", company=r[2] or "", location=r[3] or "",
                    source=r[4] or "", salary_range=r[5], posted_date=r[6],
                    remote_modality=r[7], status=r[8] or "open", quality=r[9] or "ok",
                )
                for r in session.execute(stmt).all()
            }
