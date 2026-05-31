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


class FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.8, 0.6] for _ in texts]


@pytest.mark.asyncio
async def test_orchestrator_produces_match_result() -> None:
    bus = InMemoryEventBus()
    events: list[DomainEvent] = []

    async def capture(event: DomainEvent) -> None:
        events.append(event)

    bus.subscribe("match.completed", capture)

    orchestrator = MatchingOrchestrator(llm=FakeLLM(), event_bus=bus, embedding=FakeEmbedder())
    result = await orchestrator.analyze(
        job_id="job-1",
        cv_id="cv-1",
        job_description="Backend engineer with Python, FastAPI, and Kubernetes experience",
        job_skills=["python", "fastapi", "kubernetes"],
        cv_summary="Experienced Python developer with FastAPI projects",
        cv_skills=["python", "fastapi", "django"],
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
async def test_orchestrator_matches_skill_from_cv_text_evidence() -> None:
    # "kubernetes" is absent from the explicit skills list but demonstrated in
    # the full CV text, so it should be matched rather than reported missing.
    bus = InMemoryEventBus()
    orchestrator = MatchingOrchestrator(llm=FakeLLM(), event_bus=bus)
    result = await orchestrator.analyze(
        job_id="job-3",
        cv_id="cv-3",
        job_description="Backend engineer",
        job_skills=["python", "kubernetes"],
        cv_summary="Backend developer",
        cv_skills=["python"],
        cv_text="Deployed services to a Kubernetes cluster with Helm.",
    )
    assert "kubernetes" in result.matched_skills
    assert "kubernetes" not in result.missing_skills


class FakeLLMWithPresentSkills:
    def __init__(self) -> None:
        self.last_prompt = ""

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.last_prompt = prompt
        return """{
            "experience_score": 0.6,
            "language_score": 1.0,
            "present_skills": ["backend development"],
            "pros": [],
            "cons": [],
            "recommendations": []
        }"""


@pytest.mark.asyncio
async def test_orchestrator_uses_llm_present_skills_verdict() -> None:
    # "backend development" is not in the skills list nor a literal phrase in
    # the CV text, but the LLM judges it present from the experience.
    bus = InMemoryEventBus()
    llm = FakeLLMWithPresentSkills()
    orchestrator = MatchingOrchestrator(llm=llm, event_bus=bus)
    result = await orchestrator.analyze(
        job_id="job-4",
        cv_id="cv-4",
        job_description="Backend engineer",
        job_skills=["python", "backend development"],
        cv_summary="Engineer",
        cv_skills=["python"],
        cv_text="Designed and shipped microservices and REST endpoints.",
    )
    assert "backend development" in result.matched_skills
    assert "backend development" not in result.missing_skills
    # full CV text is handed to the LLM, not just the summary
    assert "microservices" in llm.last_prompt


@pytest.mark.asyncio
async def test_orchestrator_without_embedding_port() -> None:
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
