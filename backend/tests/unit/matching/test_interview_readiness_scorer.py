import pytest

from hiresense.claims.domain import CandidateClaim, ClaimVerificationStatus
from hiresense.matching.domain.scorers.interview_readiness_scorer import InterviewReadinessScorer


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str = ""

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.last_prompt = prompt
        return self._response


class FakeProfile:
    def __init__(self) -> None:
        self.skills = ["Python", "FastAPI", "PostgreSQL"]
        self.sections = [
            type("S", (), {"name": "EXPERIENCE", "content": "Built APIs at Acme Corp"})()
        ]


class FakeClaimService:
    def list_verified_for_readiness(self) -> list[CandidateClaim]:
        return [
            CandidateClaim(
                text="Reduced API latency by 40%.",
                source="portfolio",
                provenance="https://example.com/case-study",
                verification_status=ClaimVerificationStatus.VERIFIED,
            )
        ]


JOB = {
    "title": "Backend Engineer",
    "company": "Tech Co",
    "description": "Build scalable backend systems.",
    "location": "Remote",
    "salary_range": "$120k-$150k",
    "skills": ["Python", "FastAPI", "PostgreSQL"],
}


@pytest.mark.asyncio
async def test_interview_readiness_scorer_with_profile_returns_result() -> None:
    llm = FakeLLM('{"score": 0.78, "rationale": "Good STAR material"}')
    scorer = InterviewReadinessScorer(llm=llm, weight=20)
    profile = FakeProfile()
    result = await scorer.score(JOB, profile)
    assert result.score == 0.78
    assert result.rationale == "Good STAR material"
    assert result.dimension == "interview_readiness"
    assert result.weight == 20


@pytest.mark.asyncio
async def test_interview_readiness_scorer_includes_profile_in_prompt() -> None:
    llm = FakeLLM('{"score": 0.75, "rationale": "Prepared"}')
    scorer = InterviewReadinessScorer(llm=llm, weight=20)
    profile = FakeProfile()
    await scorer.score(JOB, profile)
    assert "Python" in llm.last_prompt
    assert "Built APIs at Acme Corp" in llm.last_prompt
    assert "EXPERIENCE" in llm.last_prompt


@pytest.mark.asyncio
async def test_interview_readiness_scorer_includes_verified_claim_provenance_in_prompt() -> None:
    llm = FakeLLM('{"score": 0.75, "rationale": "Prepared"}')
    scorer = InterviewReadinessScorer(llm=llm, weight=20, claim_service=FakeClaimService())

    await scorer.score(JOB, FakeProfile())

    assert "Verified candidate evidence:" in llm.last_prompt
    assert "Reduced API latency by 40%." in llm.last_prompt
    assert "portfolio: https://example.com/case-study" in llm.last_prompt


@pytest.mark.asyncio
async def test_interview_readiness_scorer_without_profile_returns_default() -> None:
    llm = FakeLLM('{"score": 0.9, "rationale": "Would be great"}')
    scorer = InterviewReadinessScorer(llm=llm, weight=20)
    result = await scorer.score(JOB, profile=None)
    assert result.score == 0.5
    assert result.rationale == "No CV provided for evaluation"
    assert result.dimension == "interview_readiness"


@pytest.mark.asyncio
async def test_interview_readiness_scorer_without_profile_does_not_call_llm() -> None:
    llm = FakeLLM('{"score": 0.9, "rationale": "Would be great"}')
    scorer = InterviewReadinessScorer(llm=llm, weight=20)
    await scorer.score(JOB, profile=None)
    assert llm.last_prompt == ""


@pytest.mark.asyncio
async def test_interview_readiness_scorer_dimension_name() -> None:
    scorer = InterviewReadinessScorer(llm=None, weight=20)
    assert scorer.dimension_name == "interview_readiness"


@pytest.mark.asyncio
async def test_interview_readiness_scorer_no_llm_fallback() -> None:
    profile = FakeProfile()
    scorer = InterviewReadinessScorer(llm=None, weight=20)
    result = await scorer.score(JOB, profile)
    assert result.score == 0.5
    assert "not configured" in result.rationale.lower()


@pytest.mark.asyncio
async def test_interview_readiness_scorer_truncates_long_description() -> None:
    llm = FakeLLM('{"score": 0.5, "rationale": "ok"}')
    scorer = InterviewReadinessScorer(llm=llm, weight=20)
    profile = FakeProfile()
    job = {**JOB, "description": "x" * 50_000}
    await scorer.score(job, profile)
    assert len(llm.last_prompt) < 10_000
