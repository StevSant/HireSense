"""Tests for SemanticPreRanker domain service (Work Unit D).

TDD: tests are written first (RED), then the implementation makes them pass (GREEN).
All dependencies are faked — no real DB, no real embeddings.
"""

from __future__ import annotations

import pytest

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.semantic_pre_ranker import SemanticPreRanker
from hiresense.ports.vector_store import ScoredResult


# ---------------------------------------------------------------------------
# Test helpers / fakes
# ---------------------------------------------------------------------------


def _job(
    id: str, skill_score: float | None = None, semantic_score: float | None = None
) -> NormalizedJob:
    return NormalizedJob(
        id=id,
        title=f"Job {id}",
        company="Co",
        description="desc",
        skills=["python"],
        source="test",
        source_type="api",
        language="en",
        url=f"https://example.com/{id}",
        match_score=skill_score,
        semantic_score=semantic_score,
    )


class FakeVectorStore:
    """Fake VectorStorePort that returns canned ScoredResults."""

    def __init__(
        self, results: list[ScoredResult] | None = None, raises: Exception | None = None
    ) -> None:
        self._results = results or []
        self._raises = raises
        self.last_call: dict | None = None

    async def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[ScoredResult]:
        self.last_call = {"query_embedding": query_embedding, "top_k": top_k, "filters": filters}
        if self._raises is not None:
            raise self._raises
        return self._results

    async def upsert(self, id: str, embedding: list[float], metadata: dict) -> None:
        pass

    async def delete(self, ids: list[str]) -> None:
        pass


class FakeEmbeddingPort:
    """Fake embedding port that returns canned vectors."""

    _SENTINEL: list[list[float]] = [[0.1, 0.2, 0.3]]

    def __init__(
        self, vectors: list[list[float]] | None = None, raises: Exception | None = None
    ) -> None:
        # Use sentinel to distinguish "not provided" from an explicit empty list
        self._vectors = self._SENTINEL if vectors is None else vectors
        self._raises = raises
        self.embed_call_count = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_call_count += 1
        if self._raises is not None:
            raise self._raises
        return self._vectors


# ---------------------------------------------------------------------------
# D1 — Tests (RED phase first)
# ---------------------------------------------------------------------------


PROFILE_SKILLS = ["python", "fastapi"]
PROFILE_SUMMARY = "Backend developer"
PROFILE_VEC = [0.1, 0.2, 0.3]


class TestSemanticPreRankerOrder:
    """REQ-01/02: Jobs are globally reordered by ANN distance ascending."""

    @pytest.mark.asyncio
    async def test_ranks_jobs_by_ann_distance_ascending(self) -> None:
        """Jobs with lower ANN distance (higher score from pgvector) come first."""
        jobs = [_job("a"), _job("b"), _job("c")]
        skill_by_id = {"a": 0.5, "b": 0.8, "c": 0.3}

        # pgvector returns score = 1 - cosine_distance, so higher score = closer.
        # We expect the returned order: b (0.9), a (0.7), c (0.4).
        scored_results = [
            ScoredResult(id="a", score=0.7, metadata={}),
            ScoredResult(id="b", score=0.9, metadata={}),
            ScoredResult(id="c", score=0.4, metadata={}),
        ]
        vs = FakeVectorStore(results=scored_results)
        emb = FakeEmbeddingPort(vectors=[PROFILE_VEC])
        ranker = SemanticPreRanker(vs, emb, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        result = await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        assert [j.id for j in result] == ["b", "a", "c"]

    @pytest.mark.asyncio
    async def test_rerank_updates_semantic_score_from_ann_results(self) -> None:
        """Each job's semantic_score is set from the ANN result score."""
        jobs = [_job("a"), _job("b")]
        skill_by_id = {"a": 0.5, "b": 0.5}
        scored_results = [
            ScoredResult(id="a", score=0.8, metadata={}),
            ScoredResult(id="b", score=0.6, metadata={}),
        ]
        vs = FakeVectorStore(results=scored_results)
        emb = FakeEmbeddingPort(vectors=[PROFILE_VEC])
        ranker = SemanticPreRanker(vs, emb, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        result = await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        assert result[0].semantic_score == pytest.approx(0.8)
        assert result[1].semantic_score == pytest.approx(0.6)


class TestSemanticPreRankerUnindexed:
    """Unindexed jobs (absent from ANN results) fall to the TAIL preserving order."""

    @pytest.mark.asyncio
    async def test_unindexed_jobs_go_to_tail_preserving_relative_order(self) -> None:
        jobs = [_job("a"), _job("unindexed-1"), _job("b"), _job("unindexed-2")]
        skill_by_id = {j.id: 0.5 for j in jobs}
        scored_results = [
            ScoredResult(id="b", score=0.9, metadata={}),
            ScoredResult(id="a", score=0.7, metadata={}),
        ]
        vs = FakeVectorStore(results=scored_results)
        emb = FakeEmbeddingPort(vectors=[PROFILE_VEC])
        ranker = SemanticPreRanker(vs, emb, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        result = await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        ranked_ids = [j.id for j in result]
        # Indexed jobs first in ANN order, then unindexed in their original order
        assert ranked_ids[:2] == ["b", "a"]
        assert ranked_ids[2:] == ["unindexed-1", "unindexed-2"]

    @pytest.mark.asyncio
    async def test_no_jobs_are_dropped(self) -> None:
        """The total count of jobs must be preserved — none are ever dropped."""
        jobs = [_job(f"job-{i}") for i in range(10)]
        skill_by_id = {j.id: 0.5 for j in jobs}
        # Only 3 are indexed
        scored_results = [
            ScoredResult(id=f"job-{i}", score=0.9 - i * 0.1, metadata={}) for i in range(3)
        ]
        vs = FakeVectorStore(results=scored_results)
        emb = FakeEmbeddingPort(vectors=[PROFILE_VEC])
        ranker = SemanticPreRanker(vs, emb, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        result = await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        assert len(result) == 10


class TestSemanticPreRankerTopK:
    """top_k cap is passed to vector store."""

    @pytest.mark.asyncio
    async def test_top_k_cap_passed_to_vector_store(self) -> None:
        jobs = [_job("a")]
        skill_by_id = {"a": 0.5}
        vs = FakeVectorStore(results=[ScoredResult(id="a", score=0.8, metadata={})])
        emb = FakeEmbeddingPort(vectors=[PROFILE_VEC])
        ranker = SemanticPreRanker(vs, emb, top_k_cap=500, skill_weight=0.4, semantic_weight=0.6)

        await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        assert vs.last_call is not None
        assert vs.last_call["top_k"] == 500

    @pytest.mark.asyncio
    async def test_bucket_filter_passed_to_vector_store(self) -> None:
        jobs = [_job("a")]
        skill_by_id = {"a": 0.5}
        vs = FakeVectorStore(results=[ScoredResult(id="a", score=0.8, metadata={})])
        emb = FakeEmbeddingPort(vectors=[PROFILE_VEC])
        ranker = SemanticPreRanker(vs, emb, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="portals",
        )

        assert vs.last_call is not None
        assert vs.last_call["filters"] == {"bucket": "portals"}


class TestSemanticPreRankerGracefulFallback:
    """REQ-04: Graceful passthrough when vector store unavailable / search raises / no profile."""

    @pytest.mark.asyncio
    async def test_passthrough_when_vector_store_is_none(self) -> None:
        jobs = [_job("a"), _job("b")]
        skill_by_id = {"a": 0.5, "b": 0.8}
        emb = FakeEmbeddingPort(vectors=[PROFILE_VEC])
        ranker = SemanticPreRanker(None, emb, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        result = await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        assert [j.id for j in result] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_passthrough_when_search_raises(self) -> None:
        jobs = [_job("a"), _job("b")]
        skill_by_id = {"a": 0.5, "b": 0.8}
        vs = FakeVectorStore(raises=RuntimeError("DB unavailable"))
        emb = FakeEmbeddingPort(vectors=[PROFILE_VEC])
        ranker = SemanticPreRanker(vs, emb, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        result = await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        assert [j.id for j in result] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_passthrough_when_search_returns_empty(self) -> None:
        jobs = [_job("a"), _job("b")]
        skill_by_id = {"a": 0.5, "b": 0.8}
        vs = FakeVectorStore(results=[])
        emb = FakeEmbeddingPort(vectors=[PROFILE_VEC])
        ranker = SemanticPreRanker(vs, emb, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        result = await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        assert [j.id for j in result] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_passthrough_when_no_profile(self) -> None:
        """No profile skills/summary → skip embedding + search, return unchanged."""
        jobs = [_job("a"), _job("b")]
        skill_by_id = {"a": 0.5, "b": 0.8}
        vs = FakeVectorStore(results=[ScoredResult(id="a", score=0.9, metadata={})])
        emb = FakeEmbeddingPort(vectors=[PROFILE_VEC])
        ranker = SemanticPreRanker(vs, emb, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        result = await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=[],
            candidate_summary="",
            bucket="boards",
        )

        assert [j.id for j in result] == ["a", "b"]
        # vector store must NOT have been called
        assert vs.last_call is None

    @pytest.mark.asyncio
    async def test_passthrough_when_embedding_port_is_none(self) -> None:
        jobs = [_job("a"), _job("b")]
        skill_by_id = {"a": 0.5, "b": 0.8}
        vs = FakeVectorStore(results=[ScoredResult(id="a", score=0.9, metadata={})])
        ranker = SemanticPreRanker(vs, None, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        result = await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        assert [j.id for j in result] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_passthrough_when_embedding_fails(self) -> None:
        jobs = [_job("a"), _job("b")]
        skill_by_id = {"a": 0.5, "b": 0.8}
        vs = FakeVectorStore(results=[ScoredResult(id="a", score=0.9, metadata={})])
        emb = FakeEmbeddingPort(raises=RuntimeError("model not loaded"))
        ranker = SemanticPreRanker(vs, emb, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        result = await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        assert [j.id for j in result] == ["a", "b"]


class TestSemanticPreRankerColdStart:
    """Cold-start: profile embedding obtained from embedding port (called exactly once)."""

    @pytest.mark.asyncio
    async def test_cold_start_embeds_profile_once(self) -> None:
        jobs = [_job("a")]
        skill_by_id = {"a": 0.5}
        vs = FakeVectorStore(results=[ScoredResult(id="a", score=0.8, metadata={})])
        emb = FakeEmbeddingPort(vectors=[PROFILE_VEC])
        ranker = SemanticPreRanker(vs, emb, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        assert emb.embed_call_count == 1

    @pytest.mark.asyncio
    async def test_warm_cache_skips_embedding_call(self) -> None:
        """Second call with the same profile reuses cached embedding (0 extra embeds)."""
        jobs = [_job("a")]
        skill_by_id = {"a": 0.5}
        vs = FakeVectorStore(results=[ScoredResult(id="a", score=0.8, metadata={})])
        emb = FakeEmbeddingPort(vectors=[PROFILE_VEC])
        ranker = SemanticPreRanker(vs, emb, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )
        # Reset FakeVectorStore to new results so we can call a second time
        vs._results = [ScoredResult(id="a", score=0.8, metadata={})]
        await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        # embed() should have been called only once total
        assert emb.embed_call_count == 1


class TestSemanticPreRankerWeights:
    """Injected weights change the combined score and thus the ordering."""

    @pytest.mark.asyncio
    async def test_injected_weights_change_order(self) -> None:
        """Skill-heavy weighting brings skill-dominant job first."""
        # job-a: skill=0.9, semantic=0.3  → skill-heavy: 0.8*0.9 + 0.2*0.3 = 0.78
        # job-b: skill=0.2, semantic=0.9  → skill-heavy: 0.8*0.2 + 0.2*0.9 = 0.34
        jobs = [_job("a", skill_score=0.9), _job("b", skill_score=0.2)]
        skill_by_id = {"a": 0.9, "b": 0.2}
        scored_results = [
            ScoredResult(id="b", score=0.9, metadata={}),  # b has better ANN score
            ScoredResult(id="a", score=0.3, metadata={}),
        ]
        vs = FakeVectorStore(results=scored_results)
        emb = FakeEmbeddingPort(vectors=[PROFILE_VEC])
        # Skill-heavy: skill_weight=0.8, semantic_weight=0.2 → a should win
        ranker = SemanticPreRanker(vs, emb, top_k_cap=100, skill_weight=0.8, semantic_weight=0.2)

        result = await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        assert result[0].id == "a"


class TestSemanticPreRankerEmptyEmbedding:
    """Guard: empty vector from embedding port → passthrough, no vector store call."""

    @pytest.mark.asyncio
    async def test_passthrough_when_embedding_returns_empty_vector(self) -> None:
        """Embedding port returns [[]] (list with one empty vector) → passthrough, no search."""
        jobs = [_job("a"), _job("b")]
        skill_by_id = {"a": 0.5, "b": 0.8}
        vs = FakeVectorStore(results=[ScoredResult(id="a", score=0.9, metadata={})])
        emb = FakeEmbeddingPort(vectors=[[]])  # returns a single empty vector
        ranker = SemanticPreRanker(vs, emb, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        result = await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        assert [j.id for j in result] == ["a", "b"]
        assert vs.last_call is None  # vector_store.search() must NOT have been called

    @pytest.mark.asyncio
    async def test_passthrough_when_embedding_returns_empty_list(self) -> None:
        """Embedding port returns [] (fully empty list) → passthrough, no search."""
        jobs = [_job("a"), _job("b")]
        skill_by_id = {"a": 0.5, "b": 0.8}
        vs = FakeVectorStore(results=[ScoredResult(id="a", score=0.9, metadata={})])
        emb = FakeEmbeddingPort(vectors=[])  # returns empty list (no vectors at all)
        ranker = SemanticPreRanker(vs, emb, top_k_cap=100, skill_weight=0.4, semantic_weight=0.6)

        result = await ranker.rerank(
            jobs=jobs,
            skill_by_id=skill_by_id,
            candidate_skills=PROFILE_SKILLS,
            candidate_summary=PROFILE_SUMMARY,
            bucket="boards",
        )

        assert [j.id for j in result] == ["a", "b"]
        assert vs.last_call is None
