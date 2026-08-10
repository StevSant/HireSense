from __future__ import annotations

from hiresense.ingestion.domain.job_list_criteria import JobListCriteria
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.ports import JobsRepositoryPort, ScoreUpdate


class JobQueryService:
    """Read/write access to one bucket of the ingested job corpus.

    This is the seam every other bounded context (tracking, applications,
    matching, preference, …) uses when it just needs to *look up* a job or
    persist a recomputed score. It deliberately knows nothing about fetching,
    normalizing, closing, or indexing — that is ``IngestionOrchestrator``'s job.

    One instance per repository bucket, sharing the very same repository the
    orchestrator (``boards``) or the portal scanner (``portals``) writes
    through, so reads always see the latest ingested state.
    """

    def __init__(self, repository: JobsRepositoryPort) -> None:
        self._repository: JobsRepositoryPort = repository

    def store_job(self, job: NormalizedJob) -> None:
        self._repository.upsert(job)

    def get_job_by_id(self, job_id: str) -> NormalizedJob | None:
        return self._repository.get_by_id(job_id)

    def get_jobs_by_ids(self, job_ids: list[str]) -> dict[str, NormalizedJob]:
        """Batch job enrichment: resolve many ids in one query (avoids the
        per-row ``get_job_by_id`` N+1 when shaping list responses)."""
        return self._repository.get_by_ids(job_ids)

    def list_jobs(self, criteria: JobListCriteria | None = None) -> list[NormalizedJob]:
        """Full corpus, or — given criteria — only rows matching the cheap
        selective predicates (filtered DB-side by the SQL repository)."""
        if criteria is None:
            return self._repository.list_all()
        return self._repository.list_filtered(criteria)

    def persist_scores(
        self,
        job_id: str,
        match_score: float | None,
        semantic_score: float | None,
    ) -> None:
        self._repository.update_scores(job_id, match_score, semantic_score)

    def persist_scores_batch(self, updates: list[ScoreUpdate]) -> None:
        """Persist score updates for multiple jobs in a single batched write.

        Delegates directly to repo.bulk_update_scores so the call site
        executes one I/O round-trip regardless of corpus size.
        """
        self._repository.bulk_update_scores(updates)
