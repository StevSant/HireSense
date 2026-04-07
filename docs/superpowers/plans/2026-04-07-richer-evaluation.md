# Richer Evaluation (10-Dimension Scoring) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 6 new LLM-powered evaluation dimensions to the matching module, wire the Anthropic LLM adapter, and display a 10-dimension breakdown on the frontend.

**Architecture:** Each dimension is an independent scorer class implementing a `DimensionScorer` protocol. A new `evaluate()` method on the `MatchingOrchestrator` runs all 10 scorers in parallel via `asyncio.gather`, produces a weighted composite. A new `POST /matching/evaluate` endpoint exposes this alongside the existing `POST /matching/analyze`. The existing endpoint is untouched for backward compatibility.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, asyncio, Anthropic SDK (via existing adapter), Angular 21, pytest-asyncio

---

## File Map

### New Files

| File | Responsibility |
|---|---|
| `backend/src/hiresense/matching/domain/scorers/__init__.py` | Package marker |
| `backend/src/hiresense/matching/domain/scorers/base.py` | DimensionScorer protocol + DimensionResult model |
| `backend/src/hiresense/matching/domain/scorers/llm_scorer.py` | Base class for LLM-powered scorers (shared prompt/parse logic) |
| `backend/src/hiresense/matching/domain/scorers/seniority_scorer.py` | Seniority fit dimension |
| `backend/src/hiresense/matching/domain/scorers/compensation_scorer.py` | Compensation dimension |
| `backend/src/hiresense/matching/domain/scorers/growth_scorer.py` | Growth potential dimension |
| `backend/src/hiresense/matching/domain/scorers/culture_scorer.py` | Culture fit dimension |
| `backend/src/hiresense/matching/domain/scorers/application_strength_scorer.py` | Application strength (needs CV) |
| `backend/src/hiresense/matching/domain/scorers/interview_readiness_scorer.py` | Interview readiness (needs CV) |
| `backend/src/hiresense/matching/domain/scorers/semantic_dimension.py` | Wraps existing SemanticScorer as DimensionScorer |
| `backend/src/hiresense/matching/domain/scorers/skill_dimension.py` | Wraps existing SkillMatcher as DimensionScorer |
| `backend/src/hiresense/matching/domain/scorers/experience_dimension.py` | Wraps existing LLM experience analysis as DimensionScorer |
| `backend/src/hiresense/matching/domain/scorers/language_dimension.py` | Wraps existing LLM language analysis as DimensionScorer |
| `backend/src/hiresense/matching/api/schemas.py` | EvaluateRequest + EvaluationResponse |
| `backend/tests/unit/matching/test_dimension_result.py` | Tests for base models |
| `backend/tests/unit/matching/test_llm_scorer.py` | Tests for LLM base scorer |
| `backend/tests/unit/matching/test_seniority_scorer.py` | Tests for seniority scorer |
| `backend/tests/unit/matching/test_compensation_scorer.py` | Tests for compensation scorer |
| `backend/tests/unit/matching/test_growth_scorer.py` | Tests for growth scorer |
| `backend/tests/unit/matching/test_culture_scorer.py` | Tests for culture scorer |
| `backend/tests/unit/matching/test_application_strength_scorer.py` | Tests for application strength scorer |
| `backend/tests/unit/matching/test_interview_readiness_scorer.py` | Tests for interview readiness scorer |
| `backend/tests/unit/matching/test_evaluate.py` | Tests for evaluate orchestration + route |
| `frontend/src/app/core/models/dimension-result.model.ts` | DimensionResult TS interface |
| `frontend/src/app/core/models/evaluation-result.model.ts` | EvaluationResult TS interface |
| `frontend/src/app/core/models/evaluate-request.model.ts` | EvaluateRequest TS interface |

### Modified Files

| File | Change |
|---|---|
| `backend/src/hiresense/config.py` | Add 6 new weight env vars, update existing defaults |
| `backend/src/hiresense/matching/domain/services.py` | Add `evaluate()` method |
| `backend/src/hiresense/matching/api/routes.py` | Add `POST /matching/evaluate` endpoint |
| `backend/src/hiresense/main.py` | Wire LLM adapter + scorers |
| `.env.example` | Add new weight env vars |
| `frontend/src/app/pages/matching/matching.component.ts` | Add evaluate UI |
| `frontend/src/app/pages/matching/matching.component.html` | Add dimension breakdown display |

---

## Task 1: DimensionResult model and DimensionScorer protocol

**Files:**
- Create: `backend/src/hiresense/matching/domain/scorers/__init__.py`
- Create: `backend/src/hiresense/matching/domain/scorers/base.py`
- Create: `backend/tests/unit/matching/test_dimension_result.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/matching/test_dimension_result.py`:

```python
from hiresense.matching.domain.scorers.base import DimensionResult


def test_dimension_result_creation() -> None:
    result = DimensionResult(
        dimension="seniority_fit",
        score=0.8,
        rationale="Good seniority match",
        weight=10,
    )
    assert result.dimension == "seniority_fit"
    assert result.score == 0.8
    assert result.rationale == "Good seniority match"
    assert result.weight == 10


def test_dimension_result_score_clamped() -> None:
    result = DimensionResult(dimension="test", score=1.5, rationale="x", weight=10)
    assert result.score == 1.0

    result2 = DimensionResult(dimension="test", score=-0.5, rationale="x", weight=10)
    assert result2.score == 0.0


def test_dimension_result_default_score() -> None:
    result = DimensionResult.default("seniority_fit", weight=10, rationale="LLM not configured")
    assert result.score == 0.5
    assert result.dimension == "seniority_fit"
    assert result.rationale == "LLM not configured"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/matching/test_dimension_result.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create empty `backend/src/hiresense/matching/domain/scorers/__init__.py`.

Create `backend/src/hiresense/matching/domain/scorers/base.py`:

```python
from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, field_validator


class DimensionResult(BaseModel):
    dimension: str
    score: float
    rationale: str
    weight: int

    @field_validator("score")
    @classmethod
    def clamp_score(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @classmethod
    def default(cls, dimension: str, weight: int, rationale: str = "Not evaluated") -> DimensionResult:
        return cls(dimension=dimension, score=0.5, rationale=rationale, weight=weight)


class DimensionScorer(Protocol):
    @property
    def dimension_name(self) -> str: ...

    @property
    def weight(self) -> int: ...

    async def score(self, job: Any, profile: Any | None = None) -> DimensionResult: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/matching/test_dimension_result.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/matching/domain/scorers/ backend/tests/unit/matching/test_dimension_result.py
git commit -m "feat(matching): add DimensionResult model and DimensionScorer protocol"
```

---

## Task 2: LLM base scorer with JSON parsing

**Files:**
- Create: `backend/src/hiresense/matching/domain/scorers/llm_scorer.py`
- Create: `backend/tests/unit/matching/test_llm_scorer.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/matching/test_llm_scorer.py`:

```python
import pytest

from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer
from hiresense.matching.domain.scorers.base import DimensionResult


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        return self._response


class ConcreteLLMScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "test_dimension"

    @property
    def weight(self) -> int:
        return 10

    def _build_prompt(self, job, profile=None) -> str:
        return f"Evaluate: {job.get('title', '')}"

    def _build_system(self) -> str:
        return "You are a test scorer."


@pytest.mark.asyncio
async def test_llm_scorer_parses_json_response() -> None:
    llm = FakeLLM('{"score": 0.85, "rationale": "Great fit"}')
    scorer = ConcreteLLMScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 0.85
    assert result.rationale == "Great fit"
    assert result.dimension == "test_dimension"
    assert result.weight == 10


@pytest.mark.asyncio
async def test_llm_scorer_handles_malformed_json() -> None:
    llm = FakeLLM("This is not JSON but score is 0.7 probably")
    scorer = ConcreteLLMScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 0.7


@pytest.mark.asyncio
async def test_llm_scorer_handles_complete_garbage() -> None:
    llm = FakeLLM("I cannot evaluate this")
    scorer = ConcreteLLMScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 0.5
    assert "failed" in result.rationale.lower() or "parse" in result.rationale.lower()


@pytest.mark.asyncio
async def test_llm_scorer_handles_llm_exception() -> None:
    class FailingLLM:
        async def complete(self, prompt, *, system="", model=""):
            raise RuntimeError("API timeout")

    scorer = ConcreteLLMScorer(llm=FailingLLM(), weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 0.5
    assert "API timeout" in result.rationale


@pytest.mark.asyncio
async def test_llm_scorer_handles_none_llm() -> None:
    scorer = ConcreteLLMScorer(llm=None, weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 0.5
    assert "not configured" in result.rationale.lower()


@pytest.mark.asyncio
async def test_llm_scorer_clamps_score_above_one() -> None:
    llm = FakeLLM('{"score": 1.5, "rationale": "Off the charts"}')
    scorer = ConcreteLLMScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 1.0


@pytest.mark.asyncio
async def test_llm_scorer_extracts_json_from_markdown() -> None:
    llm = FakeLLM('Here is my analysis:\n```json\n{"score": 0.6, "rationale": "Decent"}\n```')
    scorer = ConcreteLLMScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 0.6
    assert result.rationale == "Decent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/matching/test_llm_scorer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/hiresense/matching/domain/scorers/llm_scorer.py`:

```python
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from hiresense.matching.domain.scorers.base import DimensionResult

logger = logging.getLogger(__name__)


class BaseLLMScorer(ABC):
    def __init__(self, llm: Any, weight: int) -> None:
        self._llm = llm
        self._weight = weight

    @property
    @abstractmethod
    def dimension_name(self) -> str: ...

    @property
    def weight(self) -> int:
        return self._weight

    @abstractmethod
    def _build_prompt(self, job: Any, profile: Any | None = None) -> str: ...

    @abstractmethod
    def _build_system(self) -> str: ...

    async def score(self, job: Any, profile: Any | None = None) -> DimensionResult:
        if self._llm is None:
            return DimensionResult.default(
                self.dimension_name, weight=self._weight, rationale="LLM not configured"
            )

        try:
            prompt = self._build_prompt(job, profile)
            system = self._build_system()
            response = await self._llm.complete(prompt, system=system)
            return self._parse_response(response)
        except Exception as exc:
            logger.warning("Scorer %s failed: %s", self.dimension_name, exc)
            return DimensionResult(
                dimension=self.dimension_name,
                score=0.5,
                rationale=f"Evaluation failed: {exc}",
                weight=self._weight,
            )

    def _parse_response(self, response: str) -> DimensionResult:
        # Try direct JSON parse
        try:
            data = json.loads(response)
            return DimensionResult(
                dimension=self.dimension_name,
                score=float(data["score"]),
                rationale=str(data.get("rationale", "")),
                weight=self._weight,
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

        # Try extracting JSON from markdown code block
        md_match = re.search(r"```(?:json)?\s*\n?({.*?})\s*\n?```", response, re.DOTALL)
        if md_match:
            try:
                data = json.loads(md_match.group(1))
                return DimensionResult(
                    dimension=self.dimension_name,
                    score=float(data["score"]),
                    rationale=str(data.get("rationale", "")),
                    weight=self._weight,
                )
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        # Try regex extraction of a float
        float_match = re.search(r"\b(0\.\d+|1\.0|0|1)\b", response)
        if float_match:
            return DimensionResult(
                dimension=self.dimension_name,
                score=float(float_match.group(1)),
                rationale=response[:200],
                weight=self._weight,
            )

        # Complete fallback
        return DimensionResult(
            dimension=self.dimension_name,
            score=0.5,
            rationale=f"Failed to parse LLM response: {response[:200]}",
            weight=self._weight,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/matching/test_llm_scorer.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/matching/domain/scorers/llm_scorer.py backend/tests/unit/matching/test_llm_scorer.py
git commit -m "feat(matching): add BaseLLMScorer with JSON parsing and error handling"
```

---

## Task 3: Seniority scorer

**Files:**
- Create: `backend/src/hiresense/matching/domain/scorers/seniority_scorer.py`
- Create: `backend/tests/unit/matching/test_seniority_scorer.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/matching/test_seniority_scorer.py`:

```python
import pytest

from hiresense.matching.domain.scorers.seniority_scorer import SeniorityScorer


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str = ""

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.last_prompt = prompt
        return self._response


@pytest.mark.asyncio
async def test_seniority_scorer_returns_result() -> None:
    llm = FakeLLM('{"score": 0.8, "rationale": "Good seniority match for mid-senior"}')
    scorer = SeniorityScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "Senior Backend Engineer", "company": "Anthropic", "description": "Build APIs"})
    assert result.dimension == "seniority_fit"
    assert result.score == 0.8
    assert result.weight == 10


@pytest.mark.asyncio
async def test_seniority_scorer_includes_job_info_in_prompt() -> None:
    llm = FakeLLM('{"score": 0.5, "rationale": "Average fit"}')
    scorer = SeniorityScorer(llm=llm, weight=10)
    await scorer.score({"title": "Staff Engineer", "company": "Google", "description": "Lead distributed systems"})
    assert "Staff Engineer" in llm.last_prompt
    assert "Google" in llm.last_prompt


@pytest.mark.asyncio
async def test_seniority_scorer_no_llm() -> None:
    scorer = SeniorityScorer(llm=None, weight=10)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 0.5
    assert "not configured" in result.rationale.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/matching/test_seniority_scorer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/hiresense/matching/domain/scorers/seniority_scorer.py`:

```python
from __future__ import annotations

from typing import Any

from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer


class SeniorityScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "seniority_fit"

    def _build_system(self) -> str:
        return "You are a career level analyst. Return only valid JSON."

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")
        description = job.get("description", "") if isinstance(job, dict) else getattr(job, "description", "")

        return (
            "Analyze this job posting for seniority level. Rate how well it fits "
            "a mid-senior backend/AI engineer (3-5 years experience).\n"
            "Score 0.0 (terrible fit) to 1.0 (perfect fit).\n"
            'Return JSON: {"score": <float>, "rationale": "<1-2 sentences>"}\n\n'
            f"Title: {title}\n"
            f"Company: {company}\n"
            f"Description: {description[:2000]}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/matching/test_seniority_scorer.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/matching/domain/scorers/seniority_scorer.py backend/tests/unit/matching/test_seniority_scorer.py
git commit -m "feat(matching): add seniority fit scorer"
```

---

## Task 4: Compensation scorer

**Files:**
- Create: `backend/src/hiresense/matching/domain/scorers/compensation_scorer.py`
- Create: `backend/tests/unit/matching/test_compensation_scorer.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/matching/test_compensation_scorer.py`:

```python
import pytest

from hiresense.matching.domain.scorers.compensation_scorer import CompensationScorer


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str = ""

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.last_prompt = prompt
        return self._response


@pytest.mark.asyncio
async def test_compensation_scorer_returns_result() -> None:
    llm = FakeLLM('{"score": 0.7, "rationale": "Competitive for the market"}')
    scorer = CompensationScorer(llm=llm, weight=10)
    result = await scorer.score({
        "title": "Backend Engineer", "company": "Startup",
        "location": "Remote", "salary_range": "$120k-$160k", "description": "Build APIs",
    })
    assert result.dimension == "compensation"
    assert result.score == 0.7


@pytest.mark.asyncio
async def test_compensation_scorer_includes_salary_in_prompt() -> None:
    llm = FakeLLM('{"score": 0.5, "rationale": "Average"}')
    scorer = CompensationScorer(llm=llm, weight=10)
    await scorer.score({"title": "SWE", "company": "X", "salary_range": "$150k", "location": "NYC", "description": ""})
    assert "$150k" in llm.last_prompt
    assert "NYC" in llm.last_prompt


@pytest.mark.asyncio
async def test_compensation_scorer_handles_no_salary() -> None:
    llm = FakeLLM('{"score": 0.5, "rationale": "No salary info"}')
    scorer = CompensationScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "SWE", "company": "X", "description": ""})
    assert "Not specified" in llm.last_prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/matching/test_compensation_scorer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/hiresense/matching/domain/scorers/compensation_scorer.py`:

```python
from __future__ import annotations

from typing import Any

from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer


class CompensationScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "compensation"

    def _build_system(self) -> str:
        return "You are a compensation analyst. Return only valid JSON."

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")
        location = job.get("location", "") if isinstance(job, dict) else getattr(job, "location", "")
        salary = job.get("salary_range", None) if isinstance(job, dict) else getattr(job, "salary_range", None)
        description = job.get("description", "") if isinstance(job, dict) else getattr(job, "description", "")

        return (
            "Evaluate the compensation competitiveness of this role based on the job posting.\n"
            "Consider: salary info if present, role level, company type, location.\n"
            "Score 0.0 (likely underpaid) to 1.0 (likely well-compensated).\n"
            'Return JSON: {"score": <float>, "rationale": "<1-2 sentences>"}\n\n'
            f"Title: {title}\n"
            f"Company: {company}\n"
            f"Location: {location}\n"
            f"Salary: {salary or 'Not specified'}\n"
            f"Description: {description[:2000]}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/matching/test_compensation_scorer.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/matching/domain/scorers/compensation_scorer.py backend/tests/unit/matching/test_compensation_scorer.py
git commit -m "feat(matching): add compensation scorer"
```

---

## Task 5: Growth, culture, application strength, and interview readiness scorers

Since all 4 remaining scorers follow the identical pattern (subclass `BaseLLMScorer`, override `dimension_name`, `_build_system`, `_build_prompt`), this task creates all 4 together.

**Files:**
- Create: `backend/src/hiresense/matching/domain/scorers/growth_scorer.py`
- Create: `backend/src/hiresense/matching/domain/scorers/culture_scorer.py`
- Create: `backend/src/hiresense/matching/domain/scorers/application_strength_scorer.py`
- Create: `backend/src/hiresense/matching/domain/scorers/interview_readiness_scorer.py`
- Create: `backend/tests/unit/matching/test_growth_scorer.py`
- Create: `backend/tests/unit/matching/test_culture_scorer.py`
- Create: `backend/tests/unit/matching/test_application_strength_scorer.py`
- Create: `backend/tests/unit/matching/test_interview_readiness_scorer.py`

- [ ] **Step 1: Write all 4 test files**

Create `backend/tests/unit/matching/test_growth_scorer.py`:

```python
import pytest
from hiresense.matching.domain.scorers.growth_scorer import GrowthScorer


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str = ""
    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.last_prompt = prompt
        return self._response


@pytest.mark.asyncio
async def test_growth_scorer_returns_result() -> None:
    llm = FakeLLM('{"score": 0.9, "rationale": "Excellent growth opportunities"}')
    scorer = GrowthScorer(llm=llm, weight=5)
    result = await scorer.score({"title": "ML Engineer", "company": "Startup", "description": "Build new AI products"})
    assert result.dimension == "growth_potential"
    assert result.score == 0.9
    assert result.weight == 5

@pytest.mark.asyncio
async def test_growth_scorer_no_llm() -> None:
    scorer = GrowthScorer(llm=None, weight=5)
    result = await scorer.score({"title": "SWE"})
    assert result.score == 0.5
```

Create `backend/tests/unit/matching/test_culture_scorer.py`:

```python
import pytest
from hiresense.matching.domain.scorers.culture_scorer import CultureScorer


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str = ""
    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.last_prompt = prompt
        return self._response


@pytest.mark.asyncio
async def test_culture_scorer_returns_result() -> None:
    llm = FakeLLM('{"score": 0.75, "rationale": "Good remote culture signals"}')
    scorer = CultureScorer(llm=llm, weight=5)
    result = await scorer.score({"title": "SWE", "company": "Remote Co", "location": "Remote", "description": "Flexible hours"})
    assert result.dimension == "culture_fit"
    assert result.score == 0.75

@pytest.mark.asyncio
async def test_culture_scorer_includes_location() -> None:
    llm = FakeLLM('{"score": 0.5, "rationale": "Average"}')
    scorer = CultureScorer(llm=llm, weight=5)
    await scorer.score({"title": "SWE", "company": "X", "location": "San Francisco", "description": ""})
    assert "San Francisco" in llm.last_prompt
```

Create `backend/tests/unit/matching/test_application_strength_scorer.py`:

```python
import pytest
from hiresense.matching.domain.scorers.application_strength_scorer import ApplicationStrengthScorer


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
        self.sections = [type("S", (), {"name": "EXPERIENCE", "content": "Built APIs at Acme Corp"})()]


@pytest.mark.asyncio
async def test_application_strength_with_profile() -> None:
    llm = FakeLLM('{"score": 0.85, "rationale": "Strong alignment with role requirements"}')
    scorer = ApplicationStrengthScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "Backend Eng", "company": "X", "description": "Build APIs"}, profile=FakeProfile())
    assert result.dimension == "application_strength"
    assert result.score == 0.85
    assert "Python" in llm.last_prompt
    assert "Built APIs" in llm.last_prompt

@pytest.mark.asyncio
async def test_application_strength_no_profile() -> None:
    llm = FakeLLM('{"score": 0.5, "rationale": "No CV"}')
    scorer = ApplicationStrengthScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "SWE"}, profile=None)
    assert result.score == 0.5
    assert "no cv" in result.rationale.lower()
```

Create `backend/tests/unit/matching/test_interview_readiness_scorer.py`:

```python
import pytest
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
        self.skills = ["Python", "System Design"]
        self.sections = [type("S", (), {"name": "EXPERIENCE", "content": "Led migration of monolith to microservices"})()]


@pytest.mark.asyncio
async def test_interview_readiness_with_profile() -> None:
    llm = FakeLLM('{"score": 0.7, "rationale": "Has relevant STAR stories"}')
    scorer = InterviewReadinessScorer(llm=llm, weight=10)
    result = await scorer.score({"title": "SWE", "company": "X", "description": "Microservices"}, profile=FakeProfile())
    assert result.dimension == "interview_readiness"
    assert result.score == 0.7
    assert "Led migration" in llm.last_prompt

@pytest.mark.asyncio
async def test_interview_readiness_no_profile() -> None:
    scorer = InterviewReadinessScorer(llm=FakeLLM(""), weight=10)
    result = await scorer.score({"title": "SWE"}, profile=None)
    assert result.score == 0.5
    assert "no cv" in result.rationale.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/matching/test_growth_scorer.py tests/unit/matching/test_culture_scorer.py tests/unit/matching/test_application_strength_scorer.py tests/unit/matching/test_interview_readiness_scorer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write all 4 scorer implementations**

Create `backend/src/hiresense/matching/domain/scorers/growth_scorer.py`:

```python
from __future__ import annotations
from typing import Any
from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer


class GrowthScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "growth_potential"

    def _build_system(self) -> str:
        return "You are a career growth analyst. Return only valid JSON."

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")
        description = job.get("description", "") if isinstance(job, dict) else getattr(job, "description", "")
        return (
            "Evaluate career growth potential in this role. Consider: learning opportunities, "
            "technology stack, team size, mentorship signals, promotion trajectory.\n"
            "Score 0.0 (dead-end) to 1.0 (excellent growth).\n"
            'Return JSON: {"score": <float>, "rationale": "<1-2 sentences>"}\n\n'
            f"Title: {title}\nCompany: {company}\nDescription: {description[:2000]}"
        )
```

Create `backend/src/hiresense/matching/domain/scorers/culture_scorer.py`:

```python
from __future__ import annotations
from typing import Any
from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer


class CultureScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "culture_fit"

    def _build_system(self) -> str:
        return "You are a workplace culture analyst. Return only valid JSON."

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")
        location = job.get("location", "") if isinstance(job, dict) else getattr(job, "location", "")
        description = job.get("description", "") if isinstance(job, dict) else getattr(job, "description", "")
        return (
            "Evaluate work culture fit based on job posting signals. Consider: remote/hybrid/office, "
            "work-life balance cues, team collaboration style, company values mentioned.\n"
            "Score 0.0 (poor cultural fit) to 1.0 (excellent cultural fit).\n"
            'Return JSON: {"score": <float>, "rationale": "<1-2 sentences>"}\n\n'
            f"Title: {title}\nCompany: {company}\nLocation: {location}\n"
            f"Description: {description[:2000]}"
        )
```

Create `backend/src/hiresense/matching/domain/scorers/application_strength_scorer.py`:

```python
from __future__ import annotations
from typing import Any
from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer


class ApplicationStrengthScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "application_strength"

    def _build_system(self) -> str:
        return "You are a recruitment analyst. Return only valid JSON."

    async def score(self, job: Any, profile: Any | None = None) -> DimensionResult:
        if profile is None:
            return DimensionResult.default(
                self.dimension_name, weight=self.weight, rationale="No CV provided for evaluation"
            )
        return await super().score(job, profile)

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")
        description = job.get("description", "") if isinstance(job, dict) else getattr(job, "description", "")

        skills = ", ".join(getattr(profile, "skills", [])) if profile else ""
        experience = ""
        if profile:
            for section in getattr(profile, "sections", []):
                if hasattr(section, "name") and "experience" in section.name.lower():
                    experience = section.content[:1500]
                    break

        return (
            "Evaluate how strongly this candidate's CV positions them for this role. "
            "Consider: relevant experience, skill overlap, project relevance, education fit.\n"
            "Score 0.0 (weak application) to 1.0 (very strong application).\n"
            'Return JSON: {"score": <float>, "rationale": "<1-2 sentences>"}\n\n'
            f"Job Title: {title}\nCompany: {company}\nJob Description: {description[:2000]}\n\n"
            f"Candidate Skills: {skills}\nCandidate Experience: {experience}"
        )
```

Create `backend/src/hiresense/matching/domain/scorers/interview_readiness_scorer.py`:

```python
from __future__ import annotations
from typing import Any
from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer


class InterviewReadinessScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "interview_readiness"

    def _build_system(self) -> str:
        return "You are an interview preparation coach. Return only valid JSON."

    async def score(self, job: Any, profile: Any | None = None) -> DimensionResult:
        if profile is None:
            return DimensionResult.default(
                self.dimension_name, weight=self.weight, rationale="No CV provided for evaluation"
            )
        return await super().score(job, profile)

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")
        description = job.get("description", "") if isinstance(job, dict) else getattr(job, "description", "")

        skills = ", ".join(getattr(profile, "skills", [])) if profile else ""
        experience = ""
        if profile:
            for section in getattr(profile, "sections", []):
                if hasattr(section, "name") and "experience" in section.name.lower():
                    experience = section.content[:1500]
                    break

        return (
            "Evaluate how ready this candidate would be to interview for this role. "
            "Consider: STAR stories they could tell from their experience, technical depth "
            "in required areas, potential weak spots.\n"
            "Score 0.0 (not ready) to 1.0 (very well prepared).\n"
            'Return JSON: {"score": <float>, "rationale": "<1-2 sentences>"}\n\n'
            f"Job Title: {title}\nCompany: {company}\nJob Description: {description[:2000]}\n\n"
            f"Candidate Skills: {skills}\nCandidate Experience: {experience}"
        )
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/matching/test_growth_scorer.py tests/unit/matching/test_culture_scorer.py tests/unit/matching/test_application_strength_scorer.py tests/unit/matching/test_interview_readiness_scorer.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/matching/domain/scorers/growth_scorer.py backend/src/hiresense/matching/domain/scorers/culture_scorer.py backend/src/hiresense/matching/domain/scorers/application_strength_scorer.py backend/src/hiresense/matching/domain/scorers/interview_readiness_scorer.py backend/tests/unit/matching/test_growth_scorer.py backend/tests/unit/matching/test_culture_scorer.py backend/tests/unit/matching/test_application_strength_scorer.py backend/tests/unit/matching/test_interview_readiness_scorer.py
git commit -m "feat(matching): add growth, culture, application strength, and interview readiness scorers"
```

---

## Task 6: Config weights and API schemas

**Files:**
- Modify: `backend/src/hiresense/config.py`
- Modify: `.env.example`
- Create: `backend/src/hiresense/matching/api/schemas.py`

- [ ] **Step 1: Update Settings with new weights**

Add to `backend/src/hiresense/config.py` Settings class, replacing existing weight defaults and adding new ones:

```python
    # Matching weights (must sum to 100)
    weight_semantic: int = 15
    weight_skill_match: int = 20
    weight_experience: int = 10
    weight_language: int = 5
    weight_seniority: int = 10
    weight_compensation: int = 10
    weight_growth: int = 5
    weight_culture: int = 5
    weight_application: int = 10
    weight_interview: int = 10
```

- [ ] **Step 2: Update .env.example**

Add to `.env.example`:

```env
# === Matching Weights (must sum to 100) ===
WEIGHT_SEMANTIC=15
WEIGHT_SKILL_MATCH=20
WEIGHT_EXPERIENCE=10
WEIGHT_LANGUAGE=5
WEIGHT_SENIORITY=10
WEIGHT_COMPENSATION=10
WEIGHT_GROWTH=5
WEIGHT_CULTURE=5
WEIGHT_APPLICATION=10
WEIGHT_INTERVIEW=10
```

- [ ] **Step 3: Create API schemas**

Create `backend/src/hiresense/matching/api/schemas.py`:

```python
from __future__ import annotations

from pydantic import BaseModel


class EvaluateRequest(BaseModel):
    job_id: str | None = None
    profile_id: str | None = None
    job_title: str | None = None
    company: str | None = None
    description: str | None = None
    skills: list[str] = []
    location: str | None = None


class DimensionResultResponse(BaseModel):
    dimension: str
    score: float
    rationale: str
    weight: int


class EvaluationResponse(BaseModel):
    composite_score: float
    job_title: str
    company: str
    dimensions: list[DimensionResultResponse]
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/config.py .env.example backend/src/hiresense/matching/api/schemas.py
git commit -m "feat(matching): add evaluation weights config and API schemas"
```

---

## Task 7: Evaluate method on MatchingOrchestrator

**Files:**
- Modify: `backend/src/hiresense/matching/domain/services.py`
- Create: `backend/tests/unit/matching/test_evaluate.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/matching/test_evaluate.py`:

```python
import asyncio

import pytest

from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.services import MatchingOrchestrator


class FakeScorer:
    def __init__(self, dimension: str, score: float, weight: int) -> None:
        self._dimension = dimension
        self._score = score
        self._weight = weight

    @property
    def dimension_name(self) -> str:
        return self._dimension

    @property
    def weight(self) -> int:
        return self._weight

    async def score(self, job, profile=None) -> DimensionResult:
        return DimensionResult(
            dimension=self._dimension,
            score=self._score,
            rationale=f"Score for {self._dimension}",
            weight=self._weight,
        )


class FakeEventBus:
    async def publish(self, event) -> None:
        pass


@pytest.mark.asyncio
async def test_evaluate_returns_composite_score() -> None:
    scorers = [
        FakeScorer("dim_a", 0.8, 60),
        FakeScorer("dim_b", 0.4, 40),
    ]
    orchestrator = MatchingOrchestrator(llm=None, event_bus=FakeEventBus())
    result = await orchestrator.evaluate(
        job={"title": "SWE", "company": "Acme", "description": "Build stuff"},
        profile=None,
        dimension_scorers=scorers,
    )
    # Weighted: (0.8 * 60 + 0.4 * 40) / 100 = (48 + 16) / 100 = 0.64
    assert abs(result.composite_score - 0.64) < 0.01
    assert result.job_title == "SWE"
    assert result.company == "Acme"
    assert len(result.dimensions) == 2


@pytest.mark.asyncio
async def test_evaluate_handles_scorer_exception() -> None:
    class FailingScorer:
        dimension_name = "failing"
        weight = 50

        async def score(self, job, profile=None):
            raise RuntimeError("boom")

    scorers = [
        FakeScorer("good", 0.8, 50),
        FailingScorer(),
    ]
    orchestrator = MatchingOrchestrator(llm=None, event_bus=FakeEventBus())
    result = await orchestrator.evaluate(
        job={"title": "SWE", "company": "Acme", "description": ""},
        profile=None,
        dimension_scorers=scorers,
    )
    assert len(result.dimensions) == 2
    failing = [d for d in result.dimensions if d.dimension == "failing"][0]
    assert failing.score == 0.5


@pytest.mark.asyncio
async def test_evaluate_all_dimensions_present() -> None:
    scorers = [FakeScorer(f"dim_{i}", 0.5, 10) for i in range(10)]
    orchestrator = MatchingOrchestrator(llm=None, event_bus=FakeEventBus())
    result = await orchestrator.evaluate(
        job={"title": "SWE", "company": "Acme", "description": ""},
        profile=None,
        dimension_scorers=scorers,
    )
    assert len(result.dimensions) == 10
    assert result.composite_score == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/matching/test_evaluate.py -v`
Expected: FAIL — `AttributeError: 'MatchingOrchestrator' has no attribute 'evaluate'`

- [ ] **Step 3: Add evaluate method**

Add these imports to `backend/src/hiresense/matching/domain/services.py`:

```python
import asyncio
from hiresense.matching.domain.scorers.base import DimensionResult
```

Add a new Pydantic model at module level:

```python
from pydantic import BaseModel

class EvaluationResult(BaseModel):
    composite_score: float
    job_title: str
    company: str
    dimensions: list[DimensionResult]
```

Add this method to `MatchingOrchestrator`:

```python
    async def evaluate(
        self,
        job: dict[str, Any] | Any,
        profile: Any | None = None,
        dimension_scorers: list[Any] | None = None,
    ) -> EvaluationResult:
        scorers = dimension_scorers or []
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")

        async def safe_score(scorer):
            try:
                return await scorer.score(job, profile)
            except Exception as exc:
                logger.warning("Scorer %s failed: %s", scorer.dimension_name, exc)
                return DimensionResult(
                    dimension=scorer.dimension_name,
                    score=0.5,
                    rationale=f"Evaluation failed: {exc}",
                    weight=scorer.weight,
                )

        results = await asyncio.gather(*[safe_score(s) for s in scorers])
        dimensions = list(results)

        total_weight = sum(d.weight for d in dimensions)
        if total_weight > 0:
            composite = sum(d.score * d.weight for d in dimensions) / total_weight
        else:
            composite = 0.5

        return EvaluationResult(
            composite_score=round(composite, 4),
            job_title=title,
            company=company,
            dimensions=dimensions,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/matching/test_evaluate.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Run all matching tests for regressions**

Run: `cd backend && uv run pytest tests/unit/matching/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/matching/domain/services.py backend/tests/unit/matching/test_evaluate.py
git commit -m "feat(matching): add evaluate method with parallel dimension scoring"
```

---

## Task 8: Evaluate API endpoint

**Files:**
- Modify: `backend/src/hiresense/matching/api/routes.py`
- Create: `backend/tests/unit/matching/test_evaluate_route.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/matching/test_evaluate_route.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.matching.api.dependencies import get_matching_orchestrator
from hiresense.matching.api.routes import router
from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.services import EvaluationResult


class FakeOrchestrator:
    async def evaluate(self, job, profile=None, dimension_scorers=None):
        return EvaluationResult(
            composite_score=0.75,
            job_title=job.get("title", "Unknown"),
            company=job.get("company", "Unknown"),
            dimensions=[
                DimensionResult(dimension="seniority_fit", score=0.8, rationale="Good fit", weight=10),
                DimensionResult(dimension="compensation", score=0.7, rationale="Competitive", weight=10),
            ],
        )

    async def analyze(self, **kwargs):
        pass


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_matching_orchestrator] = lambda: FakeOrchestrator()
    return app


def test_evaluate_endpoint_returns_result() -> None:
    client = TestClient(_make_app())
    response = client.post("/matching/evaluate", json={
        "job_title": "Backend Engineer",
        "company": "Anthropic",
        "description": "Build APIs",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["composite_score"] == 0.75
    assert data["job_title"] == "Backend Engineer"
    assert data["company"] == "Anthropic"
    assert len(data["dimensions"]) == 2


def test_evaluate_endpoint_empty_request() -> None:
    client = TestClient(_make_app())
    response = client.post("/matching/evaluate", json={})
    assert response.status_code == 200


def test_evaluate_endpoint_with_job_id() -> None:
    client = TestClient(_make_app())
    response = client.post("/matching/evaluate", json={"job_id": "some-uuid"})
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/matching/test_evaluate_route.py -v`
Expected: FAIL

- [ ] **Step 3: Add evaluate endpoint to routes.py**

Add these imports to `backend/src/hiresense/matching/api/routes.py`:

```python
from hiresense.matching.api.schemas import (
    EvaluateRequest,
    EvaluationResponse,
    DimensionResultResponse,
)
```

Add this endpoint:

```python
@router.post("/matching/evaluate", response_model=EvaluationResponse)
async def evaluate_job(
    body: EvaluateRequest,
    orchestrator: Annotated[object, Depends(get_matching_orchestrator)],
) -> EvaluationResponse:
    job = {
        "title": body.job_title or "",
        "company": body.company or "",
        "description": body.description or "",
        "skills": body.skills,
        "location": body.location or "",
    }
    result = await orchestrator.evaluate(job=job, profile=None)
    return EvaluationResponse(
        composite_score=result.composite_score,
        job_title=result.job_title,
        company=result.company,
        dimensions=[
            DimensionResultResponse(
                dimension=d.dimension,
                score=d.score,
                rationale=d.rationale,
                weight=d.weight,
            )
            for d in result.dimensions
        ],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/matching/test_evaluate_route.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/matching/api/routes.py backend/src/hiresense/matching/api/schemas.py backend/tests/unit/matching/test_evaluate_route.py
git commit -m "feat(matching): add POST /matching/evaluate API endpoint"
```

---

## Task 9: Wire LLM adapter and scorers into app factory

**Files:**
- Modify: `backend/src/hiresense/main.py`

- [ ] **Step 1: Add imports**

Add to `backend/src/hiresense/main.py`:

```python
from hiresense.matching.domain.scorers.seniority_scorer import SeniorityScorer
from hiresense.matching.domain.scorers.compensation_scorer import CompensationScorer
from hiresense.matching.domain.scorers.growth_scorer import GrowthScorer
from hiresense.matching.domain.scorers.culture_scorer import CultureScorer
from hiresense.matching.domain.scorers.application_strength_scorer import ApplicationStrengthScorer
from hiresense.matching.domain.scorers.interview_readiness_scorer import InterviewReadinessScorer
```

- [ ] **Step 2: Wire LLM and scorers**

Replace the matching module section in `create_app()`:

```python
    # --- Matching module ---
    llm = None
    if settings.llm_api_key:
        try:
            from anthropic import AsyncAnthropic
            from hiresense.adapters.llm.anthropic_adapter import AnthropicLLMAdapter
            anthropic_client = AsyncAnthropic(api_key=settings.llm_api_key)
            llm = AnthropicLLMAdapter(client=anthropic_client, model=settings.llm_model)
        except ImportError:
            pass

    dimension_scorers = [
        SeniorityScorer(llm=llm, weight=settings.weight_seniority),
        CompensationScorer(llm=llm, weight=settings.weight_compensation),
        GrowthScorer(llm=llm, weight=settings.weight_growth),
        CultureScorer(llm=llm, weight=settings.weight_culture),
        ApplicationStrengthScorer(llm=llm, weight=settings.weight_application),
        InterviewReadinessScorer(llm=llm, weight=settings.weight_interview),
    ]

    matching_orchestrator = MatchingOrchestrator(llm=llm, event_bus=event_bus)
    matching_orchestrator._dimension_scorers = dimension_scorers
    app.dependency_overrides[get_matching_orchestrator] = lambda: matching_orchestrator
    app.include_router(matching_router)
```

Also update the `evaluate()` method call in routes.py to pass the scorers:

In `backend/src/hiresense/matching/api/routes.py`, update the evaluate endpoint:

```python
    result = await orchestrator.evaluate(
        job=job,
        profile=None,
        dimension_scorers=getattr(orchestrator, '_dimension_scorers', []),
    )
```

- [ ] **Step 3: Run all tests**

Run: `cd backend && uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/main.py backend/src/hiresense/matching/api/routes.py
git commit -m "feat(app): wire LLM adapter and dimension scorers into matching module"
```

---

## Task 10: Frontend models and evaluation UI

**Files:**
- Create: `frontend/src/app/core/models/dimension-result.model.ts`
- Create: `frontend/src/app/core/models/evaluation-result.model.ts`
- Create: `frontend/src/app/core/models/evaluate-request.model.ts`
- Modify: `frontend/src/app/pages/matching/matching.component.ts`
- Modify: `frontend/src/app/pages/matching/matching.component.html`

- [ ] **Step 1: Create TypeScript models**

Create `frontend/src/app/core/models/dimension-result.model.ts`:

```typescript
export interface DimensionResult {
  dimension: string;
  score: number;
  rationale: string;
  weight: number;
}
```

Create `frontend/src/app/core/models/evaluation-result.model.ts`:

```typescript
import { DimensionResult } from './dimension-result.model';

export interface EvaluationResult {
  composite_score: number;
  job_title: string;
  company: string;
  dimensions: DimensionResult[];
}
```

Create `frontend/src/app/core/models/evaluate-request.model.ts`:

```typescript
export interface EvaluateRequest {
  job_id?: string;
  profile_id?: string;
  job_title?: string;
  company?: string;
  description?: string;
  skills?: string[];
  location?: string;
}
```

- [ ] **Step 2: Add evaluation state and methods to matching component**

Read the existing matching component first. Then add:

Import:
```typescript
import { EvaluationResult } from '../../core/models/evaluation-result.model';
import { EvaluateRequest } from '../../core/models/evaluate-request.model';
```

Add signals:
```typescript
  evaluationResult = signal<EvaluationResult | null>(null);
  evaluating = signal(false);
```

Add method:
```typescript
  evaluate(): void {
    this.evaluating.set(true);
    const req: EvaluateRequest = {
      job_title: this.jobDescription().split('\n')[0] || 'Unknown',
      company: 'Unknown',
      description: this.jobDescription(),
      skills: this.jobSkills().split(',').map(s => s.trim()).filter(Boolean),
    };
    this.http.post<EvaluationResult>(`${environment.apiUrl}/matching/evaluate`, req).subscribe({
      next: (res) => {
        this.evaluationResult.set(res);
        this.evaluating.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Evaluation failed');
        this.evaluating.set(false);
      },
    });
  }

  dimensionLabel(dimension: string): string {
    const labels: Record<string, string> = {
      seniority_fit: 'Seniority Fit',
      compensation: 'Compensation',
      growth_potential: 'Growth Potential',
      culture_fit: 'Culture Fit',
      application_strength: 'Application Strength',
      interview_readiness: 'Interview Readiness',
    };
    return labels[dimension] || dimension.replace(/_/g, ' ');
  }
```

- [ ] **Step 3: Add evaluation section to template**

Add to `frontend/src/app/pages/matching/matching.component.html`, after the existing results section:

```html
<!-- Evaluation Section -->
<section class="evaluation-section">
  <button (click)="evaluate()" [disabled]="evaluating()">
    {{ evaluating() ? 'Evaluating...' : 'Run 10-Dimension Evaluation' }}
  </button>

  @if (evaluationResult()) {
    <div class="evaluation-results">
      <div class="composite-score">
        <span class="score-value">{{ (evaluationResult()!.composite_score * 100).toFixed(0) }}</span>
        <span class="score-label">Composite Score</span>
      </div>

      <div class="dimensions-grid">
        @for (dim of evaluationResult()!.dimensions; track dim.dimension) {
          <div class="dimension-card">
            <div class="dimension-header">
              <span class="dimension-name">{{ dimensionLabel(dim.dimension) }}</span>
              <span class="dimension-score">{{ (dim.score * 100).toFixed(0) }}%</span>
            </div>
            <div class="dimension-bar">
              <div class="dimension-bar-fill"
                   [style.width.%]="dim.score * 100"
                   [class]="scoreColor(dim.score)">
              </div>
            </div>
            <p class="dimension-rationale">{{ dim.rationale }}</p>
            <span class="dimension-weight">Weight: {{ dim.weight }}%</span>
          </div>
        }
      </div>
    </div>
  }
</section>
```

- [ ] **Step 4: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/core/models/dimension-result.model.ts frontend/src/app/core/models/evaluation-result.model.ts frontend/src/app/core/models/evaluate-request.model.ts frontend/src/app/pages/matching/matching.component.ts frontend/src/app/pages/matching/matching.component.html
git commit -m "feat(frontend): add 10-dimension evaluation UI to matching page"
```

---

## Task 11: Run full test suite and verify

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Run linter**

Run: `cd backend && uv run ruff check src/hiresense/matching/ tests/unit/matching/`
Expected: Clean

- [ ] **Step 4: Final commit if any lint fixes needed**

```bash
git add -A
git commit -m "fix: address lint issues from evaluation implementation"
```
