import json

import pytest

from hiresense.matching.domain.scorers.combined_scorer import CombinedDimensionScorer

JOB = {
    "title": "Senior Backend Engineer",
    "company": "Acme Corp",
    "description": "We need a 4-6 year experienced backend engineer.",
    "location": "Remote",
    "salary_range": "$120k-$150k",
    "skills": ["Python", "FastAPI", "PostgreSQL"],
}

_WELL_FORMED = json.dumps(
    {
        "dimensions": [
            {"dimension": "seniority_fit", "score": 0.8, "rationale": "Good seniority match"},
            {"dimension": "compensation", "score": 0.7, "rationale": "Competitive"},
            {"dimension": "growth_potential", "score": 0.6, "rationale": "Solid growth"},
            {"dimension": "culture_fit", "score": 0.5, "rationale": "Neutral"},
            {"dimension": "application_strength", "score": 0.9, "rationale": "Strong CV match"},
            {"dimension": "interview_readiness", "score": 0.4, "rationale": "Needs prep"},
        ]
    }
)


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str = ""

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.last_prompt = prompt
        return self._response


@pytest.mark.asyncio
async def test_combined_scorer_parses_well_formed_response() -> None:
    llm = FakeLLM(_WELL_FORMED)
    scorer = CombinedDimensionScorer(llm=llm)
    results = await scorer.score_all(JOB)

    assert results is not None
    assert len(results) == 6
    by_dim = {r.dimension: r for r in results}
    assert by_dim["seniority_fit"].score == 0.8
    assert by_dim["seniority_fit"].rationale == "Good seniority match"
    assert by_dim["interview_readiness"].score == 0.4
    # weight is a caller-owned placeholder, not sourced from the LLM
    assert all(r.weight == 0 for r in results)


@pytest.mark.asyncio
async def test_combined_scorer_includes_job_info_in_prompt() -> None:
    llm = FakeLLM(_WELL_FORMED)
    scorer = CombinedDimensionScorer(llm=llm)
    await scorer.score_all(JOB)
    assert "Senior Backend Engineer" in llm.last_prompt
    assert "Acme Corp" in llm.last_prompt
    assert "$120k-$150k" in llm.last_prompt


@pytest.mark.asyncio
async def test_combined_scorer_no_profile_notes_missing_candidate() -> None:
    llm = FakeLLM(_WELL_FORMED)
    scorer = CombinedDimensionScorer(llm=llm)
    await scorer.score_all(JOB, profile=None)
    assert "No candidate profile provided" in llm.last_prompt


@pytest.mark.asyncio
async def test_combined_scorer_includes_profile_skills_and_sections() -> None:
    class Section:
        def __init__(self, name, content):
            self.name = name
            self.content = content

    class Profile:
        skills = ["Python", "Django"]
        sections = [Section("Experience", "5 years building APIs")]

    llm = FakeLLM(_WELL_FORMED)
    scorer = CombinedDimensionScorer(llm=llm)
    await scorer.score_all(JOB, profile=Profile())
    assert "Python, Django" in llm.last_prompt
    assert "5 years building APIs" in llm.last_prompt


@pytest.mark.asyncio
async def test_combined_scorer_truncates_long_description() -> None:
    llm = FakeLLM(_WELL_FORMED)
    scorer = CombinedDimensionScorer(llm=llm, job_char_limit=100)
    job = {**JOB, "description": "x" * 50_000}
    await scorer.score_all(job)
    assert len(llm.last_prompt) < 1000


@pytest.mark.asyncio
async def test_combined_scorer_malformed_json_returns_none() -> None:
    llm = FakeLLM("not json at all")
    scorer = CombinedDimensionScorer(llm=llm)
    result = await scorer.score_all(JOB)
    assert result is None


@pytest.mark.asyncio
async def test_combined_scorer_missing_dimension_returns_none() -> None:
    incomplete = json.dumps(
        {
            "dimensions": [
                {"dimension": "seniority_fit", "score": 0.8, "rationale": "ok"},
                {"dimension": "compensation", "score": 0.7, "rationale": "ok"},
                # missing the other 4 dimensions
            ]
        }
    )
    llm = FakeLLM(incomplete)
    scorer = CombinedDimensionScorer(llm=llm)
    result = await scorer.score_all(JOB)
    assert result is None


@pytest.mark.asyncio
async def test_combined_scorer_unknown_dimension_name_is_ignored() -> None:
    data = json.loads(_WELL_FORMED)
    data["dimensions"].append({"dimension": "made_up", "score": 0.9, "rationale": "n/a"})
    llm = FakeLLM(json.dumps(data))
    scorer = CombinedDimensionScorer(llm=llm)
    results = await scorer.score_all(JOB)
    assert results is not None
    assert len(results) == 6
    assert "made_up" not in {r.dimension for r in results}


@pytest.mark.asyncio
async def test_combined_scorer_no_llm_returns_none() -> None:
    scorer = CombinedDimensionScorer(llm=None)
    result = await scorer.score_all(JOB)
    assert result is None


@pytest.mark.asyncio
async def test_combined_scorer_llm_exception_returns_none() -> None:
    class BoomLLM:
        async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
            raise RuntimeError("provider down")

    scorer = CombinedDimensionScorer(llm=BoomLLM())
    result = await scorer.score_all(JOB)
    assert result is None


@pytest.mark.asyncio
async def test_combined_scorer_handles_markdown_fenced_response() -> None:
    fenced = f"```json\n{_WELL_FORMED}\n```"
    llm = FakeLLM(fenced)
    scorer = CombinedDimensionScorer(llm=llm)
    results = await scorer.score_all(JOB)
    assert results is not None
    assert len(results) == 6
