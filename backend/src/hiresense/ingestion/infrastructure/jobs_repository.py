from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select

from hiresense.ingestion.domain.closure_detector import OpenJob, detect_closures
from hiresense.ingestion.domain.content_hash import content_hash
from hiresense.ingestion.domain.identity import identity_key
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.upsert_result import UpsertResult
from hiresense.ingestion.infrastructure.models import IngestedJob


def _to_orm(job: NormalizedJob, bucket: str) -> IngestedJob:
    return IngestedJob(
        id=job.id,
        bucket=bucket,
        identity_key=identity_key(job),
        source=job.source,
        source_id=job.source_id,
        source_type=job.source_type,
        status=job.status,
        content_hash=content_hash(job),
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
        source_id=row.source_id,
        status=row.status,
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
        # Transitional shim until orchestrator/scanner migrate to upsert (T11/T12). Removed in T12.
        return self.upsert(job) == UpsertResult.INSERTED

    def upsert(self, job: NormalizedJob) -> UpsertResult:
        ident = identity_key(job)
        new_hash = content_hash(job)
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            row = session.scalars(
                select(IngestedJob).where(
                    IngestedJob.bucket == self._bucket,
                    IngestedJob.source == job.source,
                    IngestedJob.identity_key == ident,
                )
            ).first()
            if row is None:
                session.add(_to_orm(job, self._bucket))  # computes ident + hash internally
                session.commit()
                return UpsertResult.INSERTED

            row.last_seen_at = now
            row.missed_count = 0
            reopened = row.status == "closed"
            if reopened:
                row.status = "open"
                row.closed_at = None

            changed = row.content_hash != new_hash
            if changed:
                row.title = job.title
                row.company = job.company
                row.description = job.description
                row.location = job.location
                row.salary_range = job.salary_range
                row.skills = list(job.skills)
                row.categories = list(job.categories)
                row.countries = list(job.countries)
                row.remote_modality = job.remote_modality
                row.content_hash = new_hash
                row.updated_at = now

            if reopened:
                session.commit()
                return UpsertResult.REOPENED
            if changed:
                session.commit()
                return UpsertResult.UPDATED

            session.commit()
            return UpsertResult.UNCHANGED

    def get_id_by_identity(self, source: str, job: NormalizedJob) -> str | None:
        with self._session_factory() as session:
            row = session.scalars(
                select(IngestedJob).where(
                    IngestedJob.bucket == self._bucket,
                    IngestedJob.source == source,
                    IngestedJob.identity_key == identity_key(job),
                )
            ).first()
            return row.id if row else None

    def mark_closed(self, job_ids: list[str]) -> None:
        if not job_ids:
            return
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            for row in session.scalars(
                select(IngestedJob).where(
                    IngestedJob.bucket == self._bucket, IngestedJob.id.in_(job_ids)
                )
            ).all():
                row.status = "closed"
                row.closed_at = now
            session.commit()

    def bump_missed_and_close(
        self, source: str, seen_identity_keys: set[str], threshold: int
    ) -> list[str]:
        """Apply the disappearance rule to open jobs of `source`. Delegates the
        decision to the pure `detect_closures` (Task 9), then persists. Returns
        ids closed this run."""
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            rows = session.scalars(
                select(IngestedJob).where(
                    IngestedJob.bucket == self._bucket,
                    IngestedJob.source == source,
                    IngestedJob.status == "open",
                )
            ).all()
            updated, to_close = detect_closures(
                seen=seen_identity_keys,
                open_jobs=[OpenJob(r.id, r.identity_key, r.missed_count) for r in rows],
                threshold=threshold,
            )
            close_set = set(to_close)
            for row in rows:
                row.missed_count = updated[row.id]
                if row.id in close_set:
                    row.status = "closed"
                    row.closed_at = now
            session.commit()
        return to_close

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
