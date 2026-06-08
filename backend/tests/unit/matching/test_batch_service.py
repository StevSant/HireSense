from __future__ import annotations

import asyncio

import pytest

from hiresense.matching.domain.batch_service import BatchEvaluationService
from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.services import EvaluationResult


class FakeOrchestrator:
    def __init__(self, score: float = 0.75) -> None:
        self._score = score
        self.call_count = 0

    async def evaluate(self, job, profile=None, dimension_scorers=None):
        self.call_count += 1
        return EvaluationResult(
            composite_score=self._score,
            job_title=job.get("title", ""),
            company=job.get("company", ""),
            dimensions=[
                DimensionResult(dimension="seniority_fit", score=self._score, rationale="Test", weight=10),
            ],
        )


class FailingOrchestrator:
    async def evaluate(self, job, profile=None, dimension_scorers=None):
        raise RuntimeError("LLM exploded")


class SlowOrchestrator:
    def __init__(self) -> None:
        self.max_concurrent = 0
        self._current = 0
        self._lock = asyncio.Lock()

    async def evaluate(self, job, profile=None, dimension_scorers=None):
        async with self._lock:
            self._current += 1
            if self._current > self.max_concurrent:
                self.max_concurrent = self._current
        await asyncio.sleep(0.05)
        async with self._lock:
            self._current -= 1
        return EvaluationResult(
            composite_score=0.5,
            job_title=job.get("title", ""),
            company=job.get("company", ""),
            dimensions=[],
        )


@pytest.mark.asyncio
async def test_batch_evaluate_returns_sorted_results() -> None:
    orchestrator = FakeOrchestrator(score=0.75)
    service = BatchEvaluationService(orchestrator=orchestrator, concurrency=3)
    jobs = [
        {"title": "SWE", "company": "Acme", "description": "", "source": "tracked", "source_id": "id-1"},
        {"title": "ML Eng", "company": "Beta", "description": "", "source": "tracked", "source_id": "id-2"},
    ]
    results = await service.evaluate_batch(jobs)
    assert len(results) == 2
    assert results[0].source == "tracked"
    assert results[0].composite_score == 0.75
    assert len(results[0].dimensions) == 1
    assert orchestrator.call_count == 2


@pytest.mark.asyncio
async def test_batch_evaluate_sorts_by_composite_desc() -> None:
    class VaryingOrchestrator:
        def __init__(self):
            self._scores = iter([0.3, 0.9, 0.6])
        async def evaluate(self, job, profile=None, dimension_scorers=None):
            score = next(self._scores)
            return EvaluationResult(composite_score=score, job_title=job.get("title", ""), company=job.get("company", ""), dimensions=[])

    service = BatchEvaluationService(orchestrator=VaryingOrchestrator(), concurrency=3)
    jobs = [
        {"title": "Low", "company": "A", "description": "", "source": "tracked", "source_id": "1"},
        {"title": "High", "company": "B", "description": "", "source": "tracked", "source_id": "2"},
        {"title": "Mid", "company": "C", "description": "", "source": "ingested", "source_id": "3"},
    ]
    results = await service.evaluate_batch(jobs)
    assert results[0].composite_score == 0.9
    assert results[1].composite_score == 0.6
    assert results[2].composite_score == 0.3


@pytest.mark.asyncio
async def test_batch_evaluate_empty_list() -> None:
    service = BatchEvaluationService(orchestrator=FakeOrchestrator(), concurrency=3)
    results = await service.evaluate_batch([])
    assert results == []


@pytest.mark.asyncio
async def test_batch_evaluate_handles_single_job_failure() -> None:
    service = BatchEvaluationService(orchestrator=FailingOrchestrator(), concurrency=3)
    jobs = [{"title": "SWE", "company": "Acme", "description": "", "source": "tracked", "source_id": "id-1"}]
    results = await service.evaluate_batch(jobs)
    assert len(results) == 1
    assert results[0].composite_score == 0.0
    assert results[0].dimensions == []
    assert results[0].failed is True


@pytest.mark.asyncio
async def test_batch_evaluate_respects_concurrency() -> None:
    orchestrator = SlowOrchestrator()
    service = BatchEvaluationService(orchestrator=orchestrator, concurrency=2)
    jobs = [
        {"title": f"Job {i}", "company": "X", "description": "", "source": "tracked", "source_id": str(i)}
        for i in range(6)
    ]
    results = await service.evaluate_batch(jobs)
    assert len(results) == 6
    assert orchestrator.max_concurrent <= 2
