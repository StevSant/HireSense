# Batch Processing — Design Spec

**Date:** 2026-04-07
**Status:** Approved
**Phase:** 5 of 6 (career-ops feature adoption roadmap)

## Overview

Add batch evaluation that runs the 10-dimension scoring system across multiple jobs concurrently, producing a ranked leaderboard. Jobs can be sourced from tracked applications (DB) and/or in-memory ingested jobs.

## Goals

- Evaluate multiple jobs in parallel with configurable concurrency
- Return a ranked leaderboard sorted by composite score
- Support both tracked applications and ingested jobs as input sources
- Integrate into existing Pipeline and Ingestion pages (no new page)

## Non-Goals

- Persisting batch results to DB (one-shot response)
- Background/async batch jobs with polling
- Scheduled/automated batch evaluation

---

## Architecture

Batch processing lives in the **matching module** as a new service. It orchestrates existing `MatchingOrchestrator.evaluate()` calls with a job-level semaphore for concurrency control.

No new bounded context. No new DB tables.

### New Files

| File | Responsibility |
|---|---|
| `backend/src/hiresense/matching/domain/batch_service.py` | BatchEvaluationService |
| `backend/tests/unit/matching/test_batch_service.py` | Batch service tests |
| `backend/tests/unit/matching/test_batch_route.py` | Batch route tests |

### Modified Files

| File | Change |
|---|---|
| `backend/src/hiresense/config.py` | Add `BATCH_CONCURRENCY` env var (default 3) |
| `backend/src/hiresense/matching/api/schemas.py` | Add batch request/response schemas |
| `backend/src/hiresense/matching/api/routes.py` | Add `POST /matching/batch-evaluate` endpoint |
| `backend/src/hiresense/matching/api/dependencies.py` | Add DI stub for batch service |
| `backend/src/hiresense/main.py` | Wire batch service |
| `.env.example` | Add `BATCH_CONCURRENCY` |
| `frontend/src/app/core/models/batch-result.model.ts` | BatchResult TS model |
| `frontend/src/app/pages/tracking/tracking.component.ts` | Add evaluate all + leaderboard |
| `frontend/src/app/pages/tracking/tracking.component.html` | Add button + leaderboard section |

---

## Domain Model

### BatchResult (Pydantic, not ORM)

```python
class BatchResult(BaseModel):
    job_title: str
    company: str
    source: str              # "tracked" or "ingested"
    source_id: str           # tracked app UUID or ingested job ID
    composite_score: float
    dimensions: list[DimensionResult]
```

### BatchEvaluationResponse

```python
class BatchEvaluationResponse(BaseModel):
    total_jobs: int
    results: list[BatchResultResponse]  # sorted by composite_score desc
```

---

## Service

### BatchEvaluationService

```python
class BatchEvaluationService:
    def __init__(self, orchestrator: MatchingOrchestrator, concurrency: int = 3) -> None

    async def evaluate_batch(self, jobs: list[dict]) -> list[BatchResult]:
        # jobs: list of dicts with keys: title, company, description, skills, location, source, source_id
        # Uses asyncio.Semaphore(concurrency) to cap concurrent evaluations
        # Each job runs orchestrator.evaluate() (which itself parallelizes 6 scorers)
        # Returns sorted by composite_score descending
```

Concurrency model:
- Semaphore caps how many jobs evaluate simultaneously (default 3)
- Within each job, 6 dimension scorers run in parallel via existing `asyncio.gather`
- Max concurrent LLM calls = concurrency * 6 = 18 (with default settings)

Error handling per job:
- If `orchestrator.evaluate()` throws, catch and return a BatchResult with composite_score=0.5, empty dimensions, rationale="Evaluation failed"

---

## API

### POST /matching/batch-evaluate

**Request:**
```json
{
  "tracked_app_ids": ["uuid1", "uuid2"],
  "include_ingested": false
}
```

Both fields optional. If both empty/omitted, evaluates all tracked applications.

**Response:**
```json
{
  "total_jobs": 5,
  "results": [
    {
      "job_title": "Backend Engineer",
      "company": "Anthropic",
      "source": "tracked",
      "source_id": "uuid1",
      "composite_score": 0.82,
      "dimensions": [
        {"dimension": "seniority_fit", "score": 0.9, "rationale": "...", "weight": 10}
      ]
    }
  ]
}
```

Results sorted by `composite_score` descending.

**Resolution logic in the endpoint:**
1. If `tracked_app_ids` provided: fetch those tracked apps from DB via TrackingRepository
2. If `tracked_app_ids` empty and `include_ingested` false (or both omitted): fetch all tracked apps
3. If `include_ingested` true: also fetch all in-memory ingested jobs from IngestionOrchestrator
4. Convert all sources to job dicts with `source` and `source_id` fields
5. Pass to `BatchEvaluationService.evaluate_batch()`

**Dependencies injected:**
- `BatchEvaluationService` (for evaluation)
- `TrackingService` (to resolve tracked app IDs)
- `IngestionOrchestrator` (to fetch ingested jobs, optional)

Auth required (same as other matching endpoints).

---

## Configuration

| Env Var | Default | Description |
|---|---|---|
| `BATCH_CONCURRENCY` | 3 | Max concurrent job evaluations in a batch |

---

## Frontend

### Pipeline (Tracking) Page

- **"Evaluate All" button** above the applications table
- On click: collects all tracked app IDs, calls `POST /matching/batch-evaluate`
- Loading state: button disabled, spinner text "Evaluating N jobs..."
- Results: leaderboard section appears below the table
  - Sorted cards: rank number, job title, company, composite score (color-coded), source badge
  - Each card expandable to show dimension breakdown (score bars + rationale)

### Ingestion Page

- **"Rank Results" button** after a scan completes
- On click: calls `POST /matching/batch-evaluate` with `include_ingested: true`
- Same leaderboard display as tracking page

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Empty job list | Return `{total_jobs: 0, results: []}` with 200 |
| Single job evaluation fails | Include in results with composite_score=0.5, rationale="Evaluation failed" |
| No LLM configured | All jobs get 0.5 scores (existing graceful degradation) |
| Tracked app ID not found | Skip silently (don't fail the batch) |
| Ingested jobs gone (server restart) | Empty set for ingested, no error |

---

## Future Considerations

- Persist batch results for historical comparison
- WebSocket/SSE for streaming results as each job completes
- Scheduled batch evaluation (daily re-rank)
- Filter/sort leaderboard by individual dimensions
