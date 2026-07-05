from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select, update

from hiresense.infrastructure import SqlRepository
from hiresense.ingestion.domain.closure_detector import OpenJob, detect_closures
from hiresense.ingestion.domain.content_hash import content_hash
from hiresense.ingestion.domain.identity import identity_key
from hiresense.ingestion.domain.job_list_criteria import JobListCriteria
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.upsert_result import UpsertResult
from hiresense.ingestion.infrastructure.models import IngestedJob
from hiresense.ingestion.ports.jobs_repository import QualityUpdate, ScoreUpdate, UpsertOutcome


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
        apply_url=job.apply_url,
        application_method=job.application_method.value,
        ats_type=job.ats_type,
        posted_date=job.posted_date,
        expiry_date=job.expiry_date,
        department=job.department,
        skills=list(job.skills),
        categories=list(job.categories),
        countries=list(job.countries),
        remote_modality=job.remote_modality,
        match_score=job.match_score,
        semantic_score=job.semantic_score,
        quality=job.quality,
        quality_reason=job.quality_reason,
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
        apply_url=row.apply_url,
        application_method=row.application_method,
        ats_type=row.ats_type,
        posted_date=row.posted_date,
        expiry_date=row.expiry_date,
        department=row.department,
        platform=row.platform,
        categories=list(row.categories or []),
        countries=list(row.countries or []),
        remote_modality=row.remote_modality,
        match_score=row.match_score,
        semantic_score=row.semantic_score,
        quality=row.quality,
        quality_reason=row.quality_reason,
    )


class JobsRepository(SqlRepository):
    """Bucket-scoped persistent store for normalized jobs.

    Two buckets coexist in the same table: 'boards' (board-style aggregators
    via IngestionOrchestrator) and 'portals' (company ATS portals via
    PortalScanner). Each instance is scoped to a single bucket; the API tabs
    rely on this isolation to render boards-vs-portals as distinct lists.
    """

    def __init__(self, session_factory: Any, *, bucket: str) -> None:
        super().__init__(session_factory)
        self._bucket = bucket

    @staticmethod
    def _apply_to_row(row: IngestedJob, job: NormalizedJob, new_hash: str, now: datetime) -> UpsertResult:
        """Apply one job's upsert semantics to an existing row (no commit)."""
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
            return UpsertResult.REOPENED
        if changed:
            return UpsertResult.UPDATED
        return UpsertResult.UNCHANGED

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

            result = self._apply_to_row(row, job, new_hash, now)
            session.commit()
            return result

    def bulk_upsert(self, jobs: list[NormalizedJob]) -> list[UpsertOutcome]:
        """One bulk identity SELECT + one commit for the whole batch.

        Preserves upsert()'s per-job semantics via _apply_to_row. In-batch
        duplicate identities resolve against the row created/updated earlier
        in the same batch.
        """
        if not jobs:
            return []
        now = datetime.now(timezone.utc)
        idents = [identity_key(j) for j in jobs]
        with self._session_factory() as session:
            rows = session.scalars(
                select(IngestedJob).where(
                    IngestedJob.bucket == self._bucket,
                    IngestedJob.source.in_({j.source for j in jobs}),
                    IngestedJob.identity_key.in_(idents),
                )
            ).all()
            by_key: dict[tuple[str, str], IngestedJob] = {
                (r.source, r.identity_key): r for r in rows
            }
            outcomes: list[UpsertOutcome] = []
            for job, ident in zip(jobs, idents):
                key = (job.source, ident)
                row = by_key.get(key)
                if row is None:
                    orm = _to_orm(job, self._bucket)
                    session.add(orm)
                    by_key[key] = orm
                    outcomes.append(UpsertOutcome(job=job, result=UpsertResult.INSERTED))
                    continue
                resolved = job.model_copy(update={"id": row.id})
                result = self._apply_to_row(row, resolved, content_hash(resolved), now)
                outcomes.append(UpsertOutcome(job=resolved, result=result))
            session.commit()
        return outcomes

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

    def close_expired(self, now: datetime) -> list[str]:
        """Close every open job whose source-declared expiry_date has passed.

        The closure path for sources whose public pages block URL probes (e.g.
        Himalayas): expiry_date is captured at ingest, and this closes the job
        once now overtakes it. Returns the ids closed so the caller can evict
        their vector-store entries."""
        with self._session_factory() as session:
            rows = session.scalars(
                select(IngestedJob).where(
                    IngestedJob.bucket == self._bucket,
                    IngestedJob.status == "open",
                    IngestedJob.expiry_date.is_not(None),
                    IngestedJob.expiry_date < now,
                )
            ).all()
            closed = [row.id for row in rows]
            for row in rows:
                row.status = "closed"
                row.closed_at = now
            session.commit()
        return closed

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

    def find_open_stale(self, sources: list[str], limit: int) -> list[NormalizedJob]:
        """Open jobs of the given sources, oldest-checked first (never-checked
        first), capped at `limit`. Used to pace the URL-probe sweep."""
        if not sources:
            return []
        stmt = (
            select(IngestedJob)
            .where(
                IngestedJob.bucket == self._bucket,
                IngestedJob.status == "open",
                IngestedJob.source.in_(sources),
            )
            .order_by(IngestedJob.last_checked_at.asc().nullsfirst())
            .limit(limit)
        )
        return self._select_all(stmt, _to_domain)

    def mark_checked(self, job_ids: list[str]) -> None:
        if not job_ids:
            return
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            for row in session.scalars(
                select(IngestedJob).where(
                    IngestedJob.bucket == self._bucket, IngestedJob.id.in_(job_ids)
                )
            ).all():
                row.last_checked_at = now
            session.commit()

    def list_all(self) -> list[NormalizedJob]:
        stmt = select(IngestedJob).where(IngestedJob.bucket == self._bucket)
        return self._select_all(stmt, _to_domain)

    def list_filtered(self, criteria: JobListCriteria) -> list[NormalizedJob]:
        """Selective predicates pushed into the WHERE clause (see port docstring)."""
        stmt = select(IngestedJob).where(IngestedJob.bucket == self._bucket)
        if not criteria.include_closed:
            stmt = stmt.where(IngestedJob.status != "closed")
        if not criteria.include_low_quality:
            stmt = stmt.where(
                (IngestedJob.quality.is_(None)) | (IngestedJob.quality == "ok")
            )
        if criteria.source:
            stmt = stmt.where(IngestedJob.source == criteria.source)
        if criteria.company:
            target = criteria.company.strip().lower()
            stmt = stmt.where(func.lower(func.trim(IngestedJob.company)) == target)
        if criteria.date_from:
            stmt = stmt.where(
                IngestedJob.posted_date.is_not(None),
                IngestedJob.posted_date >= criteria.date_from,
            )
        if criteria.date_to:
            stmt = stmt.where(
                IngestedJob.posted_date.is_not(None),
                IngestedJob.posted_date <= criteria.date_to,
            )
        return self._select_all(stmt, _to_domain)

    def list_since(self, cutoff: datetime, *, status: str = "open") -> list[NormalizedJob]:
        stmt = (
            select(IngestedJob)
            .where(
                IngestedJob.bucket == self._bucket,
                IngestedJob.status == status,
                IngestedJob.fetched_at >= cutoff,
            )
            .order_by(IngestedJob.fetched_at.desc())
        )
        return self._select_all(stmt, _to_domain)

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
        """Persist score updates for multiple jobs in a single executemany round-trip.

        Issues a single bulk UPDATE keyed by primary key via SQLAlchemy ORM
        executemany — one session, one commit. Both score fields (including
        None values) are written as supplied; partial-None updates are
        intentional and overwrite the stored value. Unknown IDs are silently
        ignored by the DB engine. An empty list is a no-op (no DB call at all).
        """
        if not updates:
            return
        # Order rows by primary key so concurrent bulk updates acquire row
        # locks in a single global order. The frontend fires several list_jobs
        # requests at once (e.g. with/without user_location, per-source), each
        # building its update list in a different sort/filter order over the
        # same corpus. Without a deterministic lock order Postgres deadlocks:
        # txn A locks row X then waits on Y while txn B holds Y and waits on X.
        # Sorting by id turns that cycle into a plain wait.
        ordered = sorted(updates, key=lambda su: su.job_id)
        with self._session_factory() as session:
            session.execute(
                update(IngestedJob),
                [
                    {
                        "id": su.job_id,
                        "match_score": su.match_score,
                        "semantic_score": su.semantic_score,
                    }
                    for su in ordered
                ],
            )
            session.commit()

    def bulk_update_quality(self, updates: list[QualityUpdate]) -> None:
        """Persist quality classifications in a single executemany round-trip."""
        if not updates:
            return
        # Same primary-key ordering as bulk_update_scores so concurrent batches
        # touching the same rows can't deadlock (see bulk_update_scores).
        ordered = sorted(updates, key=lambda qu: qu.job_id)
        with self._session_factory() as session:
            session.execute(
                update(IngestedJob),
                [
                    {
                        "id": qu.job_id,
                        "quality": qu.quality,
                        "quality_reason": qu.quality_reason,
                    }
                    for qu in ordered
                ],
            )
            session.commit()

    def prune_older_than(self, cutoff: datetime) -> list[str]:
        """Delete rows older than `cutoff`; return their ids so the caller can
        evict the matching vectors (no FK cascade to vector_embeddings)."""
        with self._session_factory() as session:
            ids = list(
                session.scalars(
                    select(IngestedJob.id).where(
                        IngestedJob.bucket == self._bucket,
                        IngestedJob.fetched_at < cutoff,
                    )
                ).all()
            )
            if ids:
                session.execute(delete(IngestedJob).where(IngestedJob.id.in_(ids)))
                session.commit()
            return ids
