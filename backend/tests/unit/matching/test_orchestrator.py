import asyncio

import pytest

from hiresense.adapters.event_bus.in_memory_bus import InMemoryEventBus
from hiresense.kernel.events import DomainEvent
from hiresense.matching.domain.services import MatchingOrchestrator


class FakeLLM:
    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        return """{
            "experience_score": 0.7,
            "language_score": 1.0,
            "pros": ["Strong Python background"],
            "cons": ["No Kubernetes experience"],
            "recommendations": ["Learn container orchestration"]
        }"""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.8, 0.6] for _ in texts]


@pytest.mark.asyncio
async def test_orchestrator_produces_match_result() -> None:
    bus = InMemoryEventBus()
    events: list[DomainEvent] = []

    async def capture(event: DomainEvent) -> None:
        events.append(event)

    bus.subscribe("match.completed", capture)

    orchestrator = MatchingOrchestrator(llm=FakeLLM(), event_bus=bus)
    result = await orchestrator.analyze(
        job_id="job-1",
        cv_id="cv-1",
        job_description="Backend engineer with Python, FastAPI, and Kubernetes experience",
        job_skills=["python", "fastapi", "kubernetes"],
        cv_summary="Experienced Python developer with FastAPI projects",
        cv_skills=["python", "fastapi", "django"],
        cv_embedding=[1.0, 0.8, 0.6],
        job_embedding=[0.9, 0.85, 0.55],
    )
    assert result.job_id == "job-1"
    assert result.cv_id == "cv-1"
    assert 0.0 <= result.overall_score <= 1.0
    assert result.breakdown.semantic_score > 0
    assert result.breakdown.skill_score > 0
    assert "python" in result.matched_skills
    assert "kubernetes" in result.missing_skills
    assert len(result.pros) > 0

    await asyncio.sleep(0.05)
    assert len(events) == 1
    assert events[0].event_type == "match.completed"


@pytest.mark.asyncio
async def test_orchestrator_without_embeddings() -> None:
    bus = InMemoryEventBus()
    orchestrator = MatchingOrchestrator(llm=FakeLLM(), event_bus=bus)
    result = await orchestrator.analyze(
        job_id="job-2",
        cv_id="cv-2",
        job_description="Frontend developer",
        job_skills=["react", "typescript"],
        cv_summary="Backend developer",
        cv_skills=["python", "django"],
    )
    assert result.breakdown.semantic_score == 0.0
    assert result.breakdown.skill_score == 0.0
    assert 0.0 <= result.overall_score <= 1.0
