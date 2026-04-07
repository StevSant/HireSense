# Richer Evaluation (10-Dimension Scoring) — Design Spec

**Date:** 2026-04-07
**Status:** Approved
**Phase:** 3 of 6 (career-ops feature adoption roadmap)

## Overview

Extend the matching module with 6 new LLM-powered evaluation dimensions, bringing the total from 4 to 10. Each dimension is an independent scorer class that produces a 0-1 score with a text rationale. The weighted composite gives a comprehensive job-fit assessment. The LLM adapter (Anthropic) is wired into main.py for the first time.

## Goals

- Add 6 new evaluation dimensions: seniority fit, compensation, growth potential, culture fit, application strength, interview readiness
- Wire the existing Anthropic LLM adapter into the app factory
- Run all dimension scorers in parallel via asyncio.gather
- Graceful degradation when LLM is unavailable or profile is missing
- Display 10-dimension breakdown on the frontend matching page

## Non-Goals

- Replacing the existing 4 scoring dimensions (they are extended, not replaced)
- Caching LLM evaluation results (future phase)
- Batch evaluation of multiple jobs at once (Phase 5)
- Custom prompt templates per user (future)

---

## Architecture

### File Structure

```
backend/src/hiresense/matching/
├── domain/
│   ├── models.py                          (extend with DimensionResult, EvaluationResult)
│   ├── services.py                        (extend orchestrator with evaluate method)
│   ├── skill_matcher.py                   (existing)
│   ├── semantic_scorer.py                 (existing)
│   └── scorers/
│       ├── __init__.py
│       ├── base.py                        (DimensionScorer protocol)
│       ├── seniority_scorer.py
│       ├── compensation_scorer.py
│       ├── growth_scorer.py
│       ├── culture_scorer.py
│       ├── application_strength_scorer.py
│       └── interview_readiness_scorer.py
├── api/
│   ├── routes.py                          (extend with evaluation endpoint)
│   └── schemas.py                         (new — evaluation request/response)
```

### Dependency Flow

```
routes.py (POST /matching/evaluate)
  → MatchingOrchestrator.evaluate(job, profile?)
    → asyncio.gather(
        semantic_scorer.score(job, profile),
        skill_matcher.score(job, profile),
        experience_scorer.score(job, profile),
        language_scorer.score(job, profile),
        seniority_scorer.score(job, profile),
        compensation_scorer.score(job, profile),
        growth_scorer.score(job, profile),
        culture_scorer.score(job, profile),
        application_strength_scorer.score(job, profile),
        interview_readiness_scorer.score(job, profile),
      )
    → weighted composite → EvaluationResult
```

---

## Domain Models

### DimensionResult

```python
class DimensionResult(BaseModel):
    dimension: str       # e.g. "seniority_fit"
    score: float         # 0.0 - 1.0
    rationale: str       # LLM-generated or default explanation
    weight: int          # configured weight (for display)
```

### EvaluationResult

```python
class EvaluationResult(BaseModel):
    composite_score: float              # weighted average 0.0 - 1.0
    dimensions: list[DimensionResult]   # all 10 dimension results
    job_title: str
    company: str
```

---

## Scorer Interface

### DimensionScorer Protocol

```python
class DimensionScorer(Protocol):
    @property
    def dimension_name(self) -> str: ...

    async def score(
        self, job: NormalizedJob, profile: CandidateProfile | None = None
    ) -> DimensionResult: ...
```

Every scorer (including the existing 4, wrapped) implements this protocol.

---

## New Scorer Dimensions

### 1. SeniorityScorer

**Dimension name:** `seniority_fit`
**Needs CV:** No (uses job description only)
**LLM prompt:**
```
Analyze this job posting for seniority level. Rate how well it fits a mid-senior backend/AI engineer (3-5 years experience).
Score 0.0 (terrible fit) to 1.0 (perfect fit).
Return JSON: {"score": <float>, "rationale": "<1-2 sentences>"}

Title: {title}
Company: {company}
Description: {description[:2000]}
```

### 2. CompensationScorer

**Dimension name:** `compensation`
**Needs CV:** No
**LLM prompt:**
```
Evaluate the compensation competitiveness of this role based on the job posting.
Consider: salary info if present, role level, company type, location.
Score 0.0 (likely underpaid) to 1.0 (likely well-compensated).
Return JSON: {"score": <float>, "rationale": "<1-2 sentences>"}

Title: {title}
Company: {company}
Location: {location}
Salary: {salary_range or "Not specified"}
Description: {description[:2000]}
```

### 3. GrowthScorer

**Dimension name:** `growth_potential`
**Needs CV:** No
**LLM prompt:**
```
Evaluate career growth potential in this role. Consider: learning opportunities, technology stack, team size, mentorship signals, promotion trajectory.
Score 0.0 (dead-end) to 1.0 (excellent growth).
Return JSON: {"score": <float>, "rationale": "<1-2 sentences>"}

Title: {title}
Company: {company}
Description: {description[:2000]}
```

### 4. CultureScorer

**Dimension name:** `culture_fit`
**Needs CV:** No
**LLM prompt:**
```
Evaluate work culture fit based on job posting signals. Consider: remote/hybrid/office, work-life balance cues, team collaboration style, company values mentioned.
Score 0.0 (poor cultural fit) to 1.0 (excellent cultural fit).
Return JSON: {"score": <float>, "rationale": "<1-2 sentences>"}

Title: {title}
Company: {company}
Location: {location}
Description: {description[:2000]}
```

### 5. ApplicationStrengthScorer

**Dimension name:** `application_strength`
**Needs CV:** Yes
**LLM prompt:**
```
Evaluate how strongly this candidate's CV positions them for this role. Consider: relevant experience, skill overlap, project relevance, education fit.
Score 0.0 (weak application) to 1.0 (very strong application).
Return JSON: {"score": <float>, "rationale": "<1-2 sentences>"}

Job Title: {title}
Company: {company}
Job Description: {description[:2000]}

Candidate Skills: {skills}
Candidate Experience: {experience_section[:1500]}
```

### 6. InterviewReadinessScorer

**Dimension name:** `interview_readiness`
**Needs CV:** Yes
**LLM prompt:**
```
Evaluate how ready this candidate would be to interview for this role. Consider: STAR stories they could tell from their experience, technical depth in required areas, potential weak spots.
Score 0.0 (not ready) to 1.0 (very well prepared).
Return JSON: {"score": <float>, "rationale": "<1-2 sentences>"}

Job Title: {title}
Company: {company}
Job Description: {description[:2000]}

Candidate Skills: {skills}
Candidate Experience: {experience_section[:1500]}
```

---

## Scoring Weights

Configurable via environment variables. Must sum to 100.

| Dimension | Env Var | Default |
|---|---|---|
| Semantic similarity | `WEIGHT_SEMANTIC` | 15 |
| Skill match | `WEIGHT_SKILL_MATCH` | 20 |
| Experience fit | `WEIGHT_EXPERIENCE` | 10 |
| Language match | `WEIGHT_LANGUAGE` | 5 |
| Seniority fit | `WEIGHT_SENIORITY` | 10 |
| Compensation | `WEIGHT_COMPENSATION` | 10 |
| Growth potential | `WEIGHT_GROWTH` | 5 |
| Culture fit | `WEIGHT_CULTURE` | 5 |
| Application strength | `WEIGHT_APPLICATION` | 10 |
| Interview readiness | `WEIGHT_INTERVIEW` | 10 |

**Note:** Existing weights change from 30/40/20/10 to 15/20/10/5. This is a breaking change to default behavior but the env vars override, so existing `.env` files with explicit values are unaffected.

---

## LLM Wiring

### App Factory Changes

In `main.py`, wire the Anthropic LLM adapter:

```python
from hiresense.adapters.llm.anthropic import AnthropicLLMAdapter

llm = AnthropicLLMAdapter(api_key=settings.llm_api_key, model=settings.llm_model)
```

Pass `llm` to:
- `MatchingOrchestrator(llm=llm, ...)` (currently `llm=None`)
- Each new dimension scorer: `SeniorityScorer(llm=llm)`, etc.

If `llm_api_key` is empty/unset, set `llm = None` and scorers degrade gracefully.

---

## Error Handling

### LLM Call Failures
- Each scorer wraps its LLM call in try/except
- On failure: returns `DimensionResult(score=0.5, rationale="Evaluation failed: {error}")`
- `asyncio.gather(return_exceptions=True)` ensures one failure doesn't block others
- Results are filtered: exceptions become default 0.5 scores

### LLM Response Parsing
- Expect JSON `{"score": <float>, "rationale": "<string>"}`
- If JSON parsing fails: attempt regex extraction of a float between 0 and 1
- If regex fails: return 0.5 default

### Profile Availability
- CV-dependent dimensions (application_strength, interview_readiness) check `profile is not None`
- If no profile: return `score=0.5, rationale="No CV provided for evaluation"`

### Missing LLM
- If `llm is None`: all 6 new scorers return `score=0.5, rationale="LLM not configured"`
- Existing scorers already handle `llm=None` with 0.5 defaults

---

## API Changes

### Existing Endpoint Extension

The existing matching endpoint stays as-is. A new evaluation endpoint is added:

### `POST /api/matching/evaluate`

**Request body:**
```json
{
  "job_id": "uuid-of-ingested-job",
  "profile_id": "uuid-of-profile"
}
```

Both optional — can also pass raw data:
```json
{
  "job_title": "Backend Engineer",
  "company": "Anthropic",
  "description": "Build APIs...",
  "skills": ["python", "fastapi"],
  "location": "Remote",
  "profile_id": "uuid"
}
```

**Response:**
```json
{
  "composite_score": 0.72,
  "job_title": "Backend Engineer",
  "company": "Anthropic",
  "dimensions": [
    { "dimension": "semantic_similarity", "score": 0.85, "rationale": "Strong semantic match...", "weight": 15 },
    { "dimension": "skill_match", "score": 0.90, "rationale": "8 of 10 required skills...", "weight": 20 },
    { "dimension": "seniority_fit", "score": 0.70, "rationale": "Role targets senior...", "weight": 10 },
    ...
  ]
}
```

### Pydantic Schemas

```python
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

---

## Frontend Changes

### Matching Page Extension

Extend the existing matching page to display evaluation results:

- **Composite score** prominently at top (large number + progress ring)
- **Dimension breakdown table** with columns: Dimension (human-readable name), Score (progress bar 0-100%), Weight, Rationale (expandable)
- **Two groups:** "Job Analysis" (6 job-only dimensions) and "CV Match" (4 CV-dependent dimensions including skill match and semantic similarity)
- **Evaluate button** triggers `POST /api/matching/evaluate` with the current job + profile

### TypeScript Models

```typescript
interface DimensionResult {
  dimension: string;
  score: number;
  rationale: string;
  weight: number;
}

interface EvaluationResult {
  composite_score: number;
  job_title: string;
  company: string;
  dimensions: DimensionResult[];
}
```

---

## App Factory Wiring Summary

In `main.py`:
1. Create `AnthropicLLMAdapter` (or None if no API key)
2. Create 6 new scorers, each receiving `llm`
3. Pass all scorers + weights to `MatchingOrchestrator`
4. Wire the new evaluate endpoint

---

## Future Considerations

- **Prompt customization** — User-editable prompt templates per dimension
- **Result caching** — Cache evaluation results per job+profile pair
- **Batch evaluation** — Evaluate multiple jobs at once (Phase 5)
- **Score history** — Track how evaluations change as CV is optimized
