from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from hiresense.infrastructure import SqlRepository
from hiresense.ingestion.domain.quick_match_result import QuickMatchResult
from hiresense.ingestion.domain.quick_match_verdict import QuickMatchVerdict
from hiresense.ingestion.infrastructure.job_match_cache_model import JobMatchCache


def _row_to_quick(row: JobMatchCache) -> QuickMatchResult | None:
    if row.quick_score is None or row.quick_verdict is None:
        return None
    payload = row.quick_payload or {}
    try:
        verdict = QuickMatchVerdict(row.quick_verdict)
    except ValueError:
        verdict = QuickMatchVerdict.MODERATE
    return QuickMatchResult(
        job_id=row.job_id,
        score=row.quick_score,
        verdict=verdict,
        reasons=list(payload.get("reasons", [])),
        dealbreakers=list(payload.get("dealbreakers", [])),
    )


class JobMatchCacheRepository(SqlRepository):
    """Per-(job_id, profile_hash) persistence for LLM match scoring.

    Sync sessions (mirrors JobsRepository) since the API resolves these from a
    threadpool-friendly sessionmaker. Quick and deep results live on the same
    row; each is written independently as it's computed.
    """

    # ---- Quick (Tier-1) ----------------------------------------------

    def get_quick_bulk(self, job_ids: list[str], profile_hash: str) -> dict[str, QuickMatchResult]:
        if not job_ids:
            return {}
        with self._session_factory() as session:
            stmt = select(JobMatchCache).where(
                JobMatchCache.profile_hash == profile_hash,
                JobMatchCache.job_id.in_(job_ids),
            )
            results: dict[str, QuickMatchResult] = {}
            for row in session.scalars(stmt).all():
                quick = _row_to_quick(row)
                if quick is not None:
                    results[row.job_id] = quick
            return results

    def upsert_quick(self, result: QuickMatchResult, profile_hash: str) -> None:
        with self._session_factory() as session:
            row = self._get_row(session, result.job_id, profile_hash)
            if row is None:
                row = JobMatchCache(job_id=result.job_id, profile_hash=profile_hash)
                session.add(row)
            row.quick_score = result.score
            row.quick_verdict = result.verdict.value
            row.quick_payload = {
                "reasons": list(result.reasons),
                "dealbreakers": list(result.dealbreakers),
            }
            row.quick_updated_at = datetime.now(timezone.utc)
            session.commit()

    # ---- Deep (Tier-2) -----------------------------------------------

    def get_deep(self, job_id: str, profile_hash: str) -> dict | None:
        with self._session_factory() as session:
            row = self._get_row(session, job_id, profile_hash)
            if row is None or row.deep_payload is None:
                return None
            return dict(row.deep_payload)

    def upsert_deep(self, job_id: str, profile_hash: str, payload: dict) -> None:
        with self._session_factory() as session:
            row = self._get_row(session, job_id, profile_hash)
            if row is None:
                row = JobMatchCache(job_id=job_id, profile_hash=profile_hash)
                session.add(row)
            row.deep_payload = payload
            row.deep_updated_at = datetime.now(timezone.utc)
            session.commit()

    # ---- Internal -----------------------------------------------------

    @staticmethod
    def _get_row(session: Any, job_id: str, profile_hash: str) -> JobMatchCache | None:
        stmt = select(JobMatchCache).where(
            JobMatchCache.job_id == job_id,
            JobMatchCache.profile_hash == profile_hash,
        )
        return session.scalars(stmt).first()
