from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from hiresense.autohunt.domain.digest import Digest
from hiresense.autohunt.domain.digest_entry import DigestEntry

logger = logging.getLogger(__name__)


class AutoHuntService:
    """Orchestrates one auto-hunt run: new-since jobs → taste-rank → floor →
    top-N → persist a Digest. Pure orchestration over injected ports."""

    def __init__(
        self,
        *,
        jobs_repo: Any,
        pre_ranker: Any,
        profile_service: Any,
        digest_repo: Any,
        top_n: int,
        min_score: float,
        initial_lookback_days: int,
        retention_days: int,
        language: str,
    ) -> None:
        self._jobs_repo = jobs_repo
        self._pre_ranker = pre_ranker
        self._profile = profile_service
        self._digest_repo = digest_repo
        self._top_n = top_n
        self._min_score = min_score
        self._initial_lookback_days = initial_lookback_days
        self._retention_days = retention_days
        self._language = language

    async def run(self) -> Digest:
        now = datetime.now(timezone.utc)
        latest = self._digest_repo.latest()
        cutoff = (
            latest.created_at
            if latest is not None and latest.created_at is not None
            else now - timedelta(days=self._initial_lookback_days)
        )

        view = self._profile.get_for_language(self._language)
        if view is None:
            return self._persist([], cutoff, now)

        new_jobs = self._jobs_repo.list_since(cutoff, status="open")
        candidate_skills = list(view.skills or [])
        candidate_summary = view.summary or ""
        try:
            ranked = await self._pre_ranker.rerank(
                new_jobs, {}, candidate_skills, candidate_summary, "boards"
            )
        except Exception:
            logger.exception("autohunt: rerank failed — persisting empty digest")
            return self._persist([], cutoff, now)

        qualified = [
            j for j in ranked
            if getattr(j, "match_score", None) is not None and j.match_score >= self._min_score
        ][: self._top_n]
        entries = [
            DigestEntry(
                job_id=j.id, title=j.title, company=j.company,
                url=getattr(j, "url", None), score=j.match_score,
            )
            for j in qualified
        ]
        return self._persist(entries, cutoff, now)

    def _persist(self, entries: list[DigestEntry], cutoff: datetime, now: datetime) -> Digest:
        digest = self._digest_repo.add(
            Digest(cutoff_at=cutoff, entries=entries, job_count=len(entries))
        )
        try:
            self._digest_repo.prune_older_than(now - timedelta(days=self._retention_days))
        except Exception:
            logger.exception("autohunt: digest prune failed (non-fatal)")
        return digest
