from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, update

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.infrastructure.models import IngestedJob
from hiresense.ingestion.ports.jobs_repository import ScoreUpdate


def _to_orm(job: NormalizedJob, bucket: str, dedup_key: str) -> IngestedJob:
    return IngestedJob(
        id=job.id,
        bucket=bucket,
        dedup_key=dedup_key,
        source=job.source,
        source_type=job.source_type,
        platform=job.platform,
        title=job.title,
        company=job.company,
        description=job.description,
        location=job.location,
        salary_range=job.salary_range,
        language=job.language,
        url=job.url,
        posted_date=job.posted_date,
        department=job.department,
        skills=list(job.skills),
        categories=list(job.categories),
        countries=list(job.countries),
        remote_modality=job.remote_modality,
        match_score=job.match_score,
        semantic_score=job.semantic_score,
    )


def _to_domain(row: IngestedJob) -> NormalizedJob:
    return NormalizedJob(
        id=row.id,
        title=row.title,
        company=row.company,
        description=row.description,
        skills=list(row.skills or []),
        location=row.location,
        salary_range=row.salary_range,
        source=row.source,
        source_type=row.source_type,
        language=row.language,
        url=row.url,
        posted_date=row.posted_date,
        department=row.department,
        platform=row.platform,
        categories=list(row.categories or []),
        countries=list(row.countries or []),
        remote_modality=row.remote_modality,
        match_score=row.match_score,
        semantic_score=row.semantic_score,
    )


class JobsRepository:
    """Bucket-scoped persistent store for normalized jobs.

    Two buckets coexist in the same table: 'boards' (board-style aggregators
    via IngestionOrchestrator) and 'portals' (company ATS portals via
    PortalScanner). Each instance is scoped to a single bucket; the API tabs
    rely on this isolation to render boards-vs-portals as distinct lists.
    """

    def __init__(self, session_factory: Any, *, bucket: str) -> None:
        self._session_factory = session_factory
        self._bucket = bucket

    def add_if_absent(self, job: NormalizedJob) -> bool:
        dedup_key = job.dedup_key()
        with self._session_factory() as session:
            stmt = select(IngestedJob.id).where(
                IngestedJob.bucket == self._bucket,
                IngestedJob.dedup_key == dedup_key,
            )
            if session.scalars(stmt).first() is not None:
                return False
            session.add(_to_orm(job, self._bucket, dedup_key))
            session.commit()
            return True

    def list_all(self) -> list[NormalizedJob]:
        with self._session_factory() as session:
            stmt = select(IngestedJob).where(IngestedJob.bucket == self._bucket)
            return [_to_domain(r) for r in session.scalars(stmt).all()]

    def get_by_id(self, job_id: str) -> NormalizedJob | None:
        with self._session_factory() as session:
            row = session.get(IngestedJob, job_id)
            if row is None or row.bucket != self._bucket:
                return None
            return _to_domain(row)

    def update_scores(
        self,
        job_id: str,
        match_score: float | None,
        semantic_score: float | None,
    ) -> None:
        with self._session_factory() as session:
            row = session.get(IngestedJob, job_id)
            if row is None or row.bucket != self._bucket:
                return
            row.match_score = match_score
            row.semantic_score = semantic_score
            session.commit()

    def bulk_update_scores(self, updates: list[ScoreUpdate]) -> None:
        """Persist score updates for multiple jobs in a single DB round-trip.

        Issues one UPDATE … WHERE id IN (…) statement per non-empty batch.
        Bucket-scoped: only rows belonging to this instance's bucket are
        touched. Unknown IDs produce no rows in the WHERE clause and are
        silently ignored. An empty list is a no-op (no DB call at all).
        """
        if not updates:
            return
        with self._session_factory() as session:
            for su in updates:
                stmt = (
                    update(IngestedJob)
                    .where(
                        IngestedJob.id == su.job_id,
                        IngestedJob.bucket == self._bucket,
                    )
                    .values(
                        match_score=su.match_score,
                        semantic_score=su.semantic_score,
                    )
                )
                session.execute(stmt)
            session.commit()

    def prune_older_than(self, cutoff: datetime) -> int:
        with self._session_factory() as session:
            result = session.execute(
                delete(IngestedJob).where(
                    IngestedJob.bucket == self._bucket,
                    IngestedJob.fetched_at < cutoff,
                )
            )
            session.commit()
            return int(result.rowcount or 0)
