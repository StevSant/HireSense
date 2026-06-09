from __future__ import annotations

from datetime import datetime, timezone

from hiresense.ingestion.domain.closure_detector import OpenJob, detect_closures
from hiresense.ingestion.domain.content_hash import content_hash
from hiresense.ingestion.domain.identity import identity_key
from hiresense.ingestion.domain.job_list_criteria import JobListCriteria
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.upsert_result import UpsertResult
from hiresense.ingestion.ports.jobs_repository import QualityUpdate, ScoreUpdate, UpsertOutcome


class InMemoryJobsRepository:
    """In-process repository for tests and the legacy ephemeral default.

    Mirrors the SQL repository's identity-keyed upsert + closure semantics so
    the two implementations are behaviourally interchangeable. Identity is
    `(source, identity_key)`; change detection uses `content_hash`; closure
    delegates to the pure `detect_closures`. Pruning uses an internal
    fetched_at clock since there is no DB column to consult.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, NormalizedJob] = {}
        self._identity_to_id: dict[tuple[str, str], str] = {}
        self._content_hash: dict[str, str] = {}
        self._missed: dict[str, int] = {}
        self._fetched_at: dict[str, datetime] = {}
        self._last_checked: dict[str, datetime | None] = {}

    def upsert(self, job: NormalizedJob) -> UpsertResult:
        key = (job.source, identity_key(job))
        new_hash = content_hash(job)
        existing_id = self._identity_to_id.get(key)

        if existing_id is None:
            self._jobs[job.id] = job.model_copy(update={"status": "open"})
            self._identity_to_id[key] = job.id
            self._content_hash[job.id] = new_hash
            self._missed[job.id] = 0
            self._fetched_at[job.id] = datetime.now(timezone.utc)
            self._last_checked[job.id] = None
            return UpsertResult.INSERTED

        existing = self._jobs[existing_id]
        self._missed[existing_id] = 0
        reopened = existing.status == "closed"
        changed = self._content_hash.get(existing_id) != new_hash

        updates: dict = {}
        if reopened:
            updates["status"] = "open"
        if changed:
            updates.update(
                {
                    "title": job.title,
                    "company": job.company,
                    "description": job.description,
                    "location": job.location,
                    "salary_range": job.salary_range,
                    "skills": list(job.skills),
                    "categories": list(job.categories),
                    "countries": list(job.countries),
                    "remote_modality": job.remote_modality,
                }
            )
            self._content_hash[existing_id] = new_hash
        if updates:
            self._jobs[existing_id] = existing.model_copy(update=updates)

        if reopened:
            return UpsertResult.REOPENED
        if changed:
            return UpsertResult.UPDATED
        return UpsertResult.UNCHANGED

    def get_id_by_identity(self, source: str, job: NormalizedJob) -> str | None:
        return self._identity_to_id.get((source, identity_key(job)))

    def bulk_upsert(self, jobs: list[NormalizedJob]) -> list[UpsertOutcome]:
        """Batch wrapper over upsert(); resolves each job's stored id first."""
        outcomes: list[UpsertOutcome] = []
        for job in jobs:
            existing_id = self.get_id_by_identity(job.source, job)
            if existing_id:
                job = job.model_copy(update={"id": existing_id})
            outcomes.append(UpsertOutcome(job=job, result=self.upsert(job)))
        return outcomes

    def mark_closed(self, job_ids: list[str]) -> None:
        for jid in job_ids:
            job = self._jobs.get(jid)
            if job is not None:
                self._jobs[jid] = job.model_copy(update={"status": "closed"})

    def bump_missed_and_close(
        self, source: str, seen_identity_keys: set[str], threshold: int
    ) -> list[str]:
        open_jobs: list[OpenJob] = []
        for (src, ident), jid in self._identity_to_id.items():
            if src != source:
                continue
            job = self._jobs.get(jid)
            if job is None or job.status != "open":
                continue
            open_jobs.append(OpenJob(jid, ident, self._missed.get(jid, 0)))

        updated, to_close = detect_closures(
            seen=seen_identity_keys, open_jobs=open_jobs, threshold=threshold
        )
        for jid, missed in updated.items():
            self._missed[jid] = missed
        for jid in to_close:
            job = self._jobs.get(jid)
            if job is not None:
                self._jobs[jid] = job.model_copy(update={"status": "closed"})
        return to_close

    def find_open_stale(self, sources: list[str], limit: int) -> list[NormalizedJob]:
        if not sources:
            return []
        src = set(sources)
        open_jobs = [j for j in self._jobs.values() if j.status == "open" and j.source in src]
        _min = datetime.min.replace(tzinfo=timezone.utc)
        open_jobs.sort(key=lambda j: self._last_checked.get(j.id) or _min)
        return open_jobs[:limit]

    def mark_checked(self, job_ids: list[str]) -> None:
        now = datetime.now(timezone.utc)
        for jid in job_ids:
            if jid in self._jobs:
                self._last_checked[jid] = now

    def list_all(self) -> list[NormalizedJob]:
        return list(self._jobs.values())

    def list_filtered(self, criteria: JobListCriteria) -> list[NormalizedJob]:
        return [j for j in self._jobs.values() if criteria.matches(j)]

    def get_by_id(self, job_id: str) -> NormalizedJob | None:
        return self._jobs.get(job_id)

    def update_scores(
        self,
        job_id: str,
        match_score: float | None,
        semantic_score: float | None,
    ) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        self._jobs[job_id] = job.model_copy(
            update={"match_score": match_score, "semantic_score": semantic_score}
        )

    def bulk_update_scores(self, updates: list[ScoreUpdate]) -> None:
        """Update multiple jobs' scores in one pass over the in-memory dict.

        Unknown IDs are silently skipped; an empty list is a no-op.
        """
        for score_update in updates:
            job = self._jobs.get(score_update.job_id)
            if job is None:
                continue
            self._jobs[score_update.job_id] = job.model_copy(
                update={
                    "match_score": score_update.match_score,
                    "semantic_score": score_update.semantic_score,
                }
            )

    def bulk_update_quality(self, updates: list[QualityUpdate]) -> None:
        """Update multiple jobs' quality classifications in one pass."""
        for qu in updates:
            job = self._jobs.get(qu.job_id)
            if job is None:
                continue
            self._jobs[qu.job_id] = job.model_copy(
                update={"quality": qu.quality, "quality_reason": qu.quality_reason}
            )

    def prune_older_than(self, cutoff: datetime) -> list[str]:
        stale = [jid for jid, ts in self._fetched_at.items() if ts < cutoff]
        for jid in stale:
            job = self._jobs.pop(jid, None)
            self._fetched_at.pop(jid, None)
            self._content_hash.pop(jid, None)
            self._missed.pop(jid, None)
            self._last_checked.pop(jid, None)
            if job is not None:
                self._identity_to_id.pop((job.source, identity_key(job)), None)
        return stale
