"""SemanticPreRanker — domain service for global ANN-based pre-ranking.

Reorders the ENTIRE job list by pgvector ANN similarity to the profile
embedding BEFORE pagination.  Depends ONLY on ports (VectorStorePort +
embedding port) — no infrastructure imports; hexagonal layering.

Fallback contract (REQ-04):
  Any of these conditions → return jobs UNCHANGED (skill-only passthrough):
    - vector_store is None
    - embedding port is None
    - candidate profile is empty (no skills and no summary)
    - embedding call raises
    - vector store search() raises
    - preference.query_vector() raises or returns None (baseline is used)
    - search returns empty results

Unindexed jobs (not present in ANN results) are appended to the TAIL
preserving their prior relative order — they are never dropped (REQ-01/02).

Profile embeddings are cached in-process by content hash (same strategy as
SemanticScoringService) so repeated requests with the same profile only pay
for one embed call.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from hiresense.ingestion.domain.embedding_text import embed_profile_cached
from hiresense.ingestion.domain.job_scorer import combine_fit_score
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.kernel import LRUCache

logger = logging.getLogger(__name__)


class SemanticPreRanker:
    """Domain service: reorder a job list by ANN similarity before pagination.

    Parameters
    ----------
    vector_store:
        Implements VectorStorePort (or None → always passthrough).
    embedding:
        Async embedding port with ``embed(texts) -> list[list[float]]``
        (or None → always passthrough).
    top_k_cap:
        Maximum ``top_k`` passed to ``vector_store.search()``.
    skill_weight:
        Weight for the skill-overlap component in ``combine_fit_score``.
    semantic_weight:
        Weight for the semantic similarity component in ``combine_fit_score``.
    """

    def __init__(
        self,
        vector_store: Any,
        embedding: Any,
        *,
        top_k_cap: int,
        skill_weight: float,
        semantic_weight: float,
        preference: Any = None,
        profile_cache_size: int = 8,
    ) -> None:
        self._vector_store = vector_store
        self._embedding = embedding
        self._top_k_cap = top_k_cap
        self._skill_weight = skill_weight
        self._semantic_weight = semantic_weight
        self._preference = preference
        # In-process profile embedding cache: sha256(profile_text) → vector.
        # Bounded — distinct profile texts would otherwise accumulate forever.
        self._profile_cache: LRUCache[str, list[float]] = LRUCache(profile_cache_size)
        self._lock = asyncio.Lock()

    async def rerank(
        self,
        jobs: list[NormalizedJob],
        skill_by_id: dict[str, float | None],
        candidate_skills: list[str],
        candidate_summary: str,
        bucket: str,
    ) -> list[NormalizedJob]:
        """Reorder ``jobs`` by ANN similarity to the candidate profile.

        Returns the same list unchanged (passthrough) when any fallback
        condition is met.  No jobs are ever dropped.

        Parameters
        ----------
        jobs:
            Full corpus for the current tab (all jobs, pre-pagination).
        skill_by_id:
            Mapping of job_id → skill-overlap score (may be None).
        candidate_skills:
            Profile skills used to compute/cache the profile embedding.
        candidate_summary:
            Profile summary text used together with skills.
        bucket:
            Tab name ("boards" or "portals") forwarded as vector-store filter.
        """
        if not jobs:
            return jobs

        # Fallback: no vector store or embedding port
        if self._vector_store is None or self._embedding is None:
            return jobs

        # Fallback: empty profile → nothing to embed
        if not candidate_skills and not candidate_summary.strip():
            return jobs

        # Obtain profile embedding (cached or cold-start)
        profile_vec = await self._get_profile_embedding(candidate_skills, candidate_summary)
        if profile_vec is None:
            return jobs

        # Apply the learned taste vector (preference loop). Passthrough when no
        # preference port is wired or no model exists — baseline is returned.
        if self._preference is not None:
            try:
                profile_vec = self._preference.query_vector(profile_vec)
            except Exception:
                logger.exception(
                    "SemanticPreRanker: preference.query_vector failed — using baseline"
                )

        # A rogue preference port could return None; never pass None to search().
        if profile_vec is None:
            return jobs

        # Call ANN search; any exception → passthrough
        try:
            results = await self._vector_store.search(
                profile_vec,
                top_k=self._top_k_cap,
                filters={"bucket": bucket},
            )
        except Exception:
            logger.exception("SemanticPreRanker: vector store search failed — passthrough")
            return jobs

        if not results:
            return jobs

        # Build id → score map from ANN results (already sorted best-first by pgvector)
        score_by_id: dict[str, float] = {r.id: r.score for r in results}

        # Partition into indexed and unindexed sets preserving original order
        indexed: list[NormalizedJob] = []
        unindexed: list[NormalizedJob] = []
        for job in jobs:
            if job.id in score_by_id:
                indexed.append(job)
            else:
                unindexed.append(job)

        # Re-score indexed jobs with the ANN semantic score and combine_fit_score
        rescored: list[NormalizedJob] = []
        for job in indexed:
            sem_score = score_by_id[job.id]
            sk_score = skill_by_id.get(job.id)
            match = combine_fit_score(
                sk_score,
                sem_score,
                skill_weight=self._skill_weight,
                semantic_weight=self._semantic_weight,
            )
            rescored.append(
                job.model_copy(update={"semantic_score": sem_score, "match_score": match})
            )

        # Sort indexed jobs by combined match_score descending
        rescored.sort(key=lambda j: (j.match_score is None, -(j.match_score or 0.0)))

        return rescored + unindexed

    async def _get_profile_embedding(self, skills: list[str], summary: str) -> list[float] | None:
        async with self._lock:
            return await embed_profile_cached(
                self._embedding,
                self._profile_cache,
                skills,
                summary,
                log_label="SemanticPreRanker: profile embedding failed — passthrough",
            )
