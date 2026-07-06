from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.kernel import LRUCache
from hiresense.matching.domain.semantic_scorer import SemanticScorer

logger = logging.getLogger(__name__)

_JOB_TEXT_CHAR_LIMIT = 4000
_PROFILE_TEXT_CHAR_LIMIT = 4000


def _job_text(job: NormalizedJob) -> str:
    parts = [job.title, " ".join(job.skills), job.description]
    return "\n".join(p for p in parts if p)[:_JOB_TEXT_CHAR_LIMIT]


def _profile_text(skills: list[str], summary: str) -> str:
    return f"{' '.join(skills)}\n{summary}"[:_PROFILE_TEXT_CHAR_LIMIT]


def _profile_key(skills: list[str], summary: str) -> str:
    raw = _profile_text(skills, summary).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class SemanticScoringService:
    """Computes semantic (cosine) similarity between a profile and each job.

    Caches job embeddings by job_id and profile embeddings by content hash so
    that subsequent requests are near-instant. Embedding work happens lazily
    on first use, batched per request.
    """

    def __init__(
        self,
        embedding_port: Any,
        scorer: SemanticScorer | None = None,
        *,
        job_cache_size: int = 2000,
        profile_cache_size: int = 8,
    ) -> None:
        self._embedding = embedding_port
        self._scorer = scorer or SemanticScorer()
        # Bounded: embeddings are ~3 KB each; unbounded dicts grow for the
        # lifetime of the process.
        self._job_cache: LRUCache[str, list[float]] = LRUCache(job_cache_size)
        self._profile_cache: LRUCache[str, list[float]] = LRUCache(profile_cache_size)
        self._lock = asyncio.Lock()

    async def score_jobs(
        self,
        jobs: list[NormalizedJob],
        candidate_skills: list[str],
        candidate_summary: str,
    ) -> list[NormalizedJob]:
        """Return new NormalizedJob instances with semantic_score populated.

        If no profile content is available, returns jobs unchanged.
        Falls back to leaving semantic_score=None for any job whose embedding
        cannot be computed.
        """
        if self._embedding is None or (not candidate_skills and not candidate_summary):
            return jobs

        async with self._lock:
            profile_vec = await self._get_profile_embedding(candidate_skills, candidate_summary)
            if profile_vec is None:
                return jobs

            await self._populate_job_cache(jobs)

        result: list[NormalizedJob] = []
        for job in jobs:
            vec = self._job_cache.get(job.id)
            score = self._scorer.score(profile_vec, vec) if vec else None
            result.append(job.model_copy(update={"semantic_score": score}))
        return result

    async def _get_profile_embedding(self, skills: list[str], summary: str) -> list[float] | None:
        key = _profile_key(skills, summary)
        cached = self._profile_cache.get(key)
        if cached is not None:
            return cached
        text = _profile_text(skills, summary)
        if not text.strip():
            return None
        try:
            vectors = await self._embedding.embed([text])
        except Exception:
            logger.exception("Profile embedding failed")
            return None
        if not vectors:
            return None
        self._profile_cache[key] = vectors[0]
        return vectors[0]

    async def _populate_job_cache(self, jobs: list[NormalizedJob]) -> None:
        missing = [j for j in jobs if j.id not in self._job_cache]
        if not missing:
            return
        texts = [_job_text(j) for j in missing]
        try:
            vectors = await self._embedding.embed(texts)
        except Exception:
            logger.exception("Job embedding batch failed (size=%d)", len(missing))
            return
        for job, vec in zip(missing, vectors):
            if vec:
                self._job_cache[job.id] = vec
