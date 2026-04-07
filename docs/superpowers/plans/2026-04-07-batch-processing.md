# Batch Processing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add batch evaluation that runs the 10-dimension scoring system across multiple jobs concurrently with a job-level semaphore, returning a ranked leaderboard.

**Architecture:** New `BatchEvaluationService` in the matching module wraps `MatchingOrchestrator.evaluate()` with `asyncio.Semaphore` for concurrency control. A new `POST /matching/batch-evaluate` endpoint resolves jobs from tracking DB and/or in-memory ingested jobs, passes them to the batch service, and returns results sorted by composite score. Frontend adds "Evaluate All" button to the Pipeline page and "Rank Results" button to the Ingestion page.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, asyncio, Angular 21, pytest-asyncio

---

## File Map

### New Files

| File | Responsibility |
|---|---|
| `backend/src/hiresense/matching/domain/batch_service.py` | BatchEvaluationService with semaphore concurrency |
| `backend/tests/unit/matching/test_batch_service.py` | Batch service tests |
| `backend/tests/unit/matching/test_batch_route.py` | Batch route tests |
| `frontend/src/app/core/models/batch-result.model.ts` | BatchResult TS interface |
| `frontend/src/app/core/models/batch-evaluation-response.model.ts` | BatchEvaluationResponse TS interface |

### Modified Files

| File | Change |
|---|---|
| `backend/src/hiresense/config.py` | Add `batch_concurrency` setting (default 3) |
| `.env.example` | Add `BATCH_CONCURRENCY=3` |
| `backend/src/hiresense/matching/api/schemas.py` | Add batch request/response schemas |
| `backend/src/hiresense/matching/api/dependencies.py` | Add `get_batch_evaluation_service`, `get_tracking_service_for_matching`, `get_ingestion_orchestrator_for_matching` stubs |
| `backend/src/hiresense/matching/api/routes.py` | Add `POST /batch-evaluate` endpoint |
| `backend/src/hiresense/ingestion/domain/services.py` | Add `list_jobs()` method to IngestionOrchestrator |
| `backend/src/hiresense/main.py` | Wire batch service + DI overrides |
| `frontend/src/app/pages/tracking/tracking.component.ts` | Add evaluate all + leaderboard state |
| `frontend/src/app/pages/tracking/tracking.component.html` | Add button + leaderboard section |

---

## Task 1: BatchEvaluationService with semaphore concurrency

**Files:**
- Create: `backend/src/hiresense/matching/domain/batch_service.py`
- Create: `backend/tests/unit/matching/test_batch_service.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/matching/test_batch_service.py`:

```python
from __future__ import annotations

import asyncio

import pytest

from hiresense.matching.domain.batch_service import BatchEvaluationService, BatchResult
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
    assert results[0].job_title == "SWE"
    assert results[0].source == "tracked"
    assert results[0].source_id == "id-1"
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
            return EvaluationResult(
                composite_score=score,
                job_title=job.get("title", ""),
                company=job.get("company", ""),
                dimensions=[],
            )

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
    jobs = [
        {"title": "SWE", "company": "Acme", "description": "", "source": "tracked", "source_id": "id-1"},
    ]
    results = await service.evaluate_batch(jobs)
    assert len(results) == 1
    assert results[0].composite_score == 0.5
    assert results[0].dimensions == []


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/matching/test_batch_service.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/hiresense/matching/domain/batch_service.py`:

```python
from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import BaseModel

from hiresense.matching.domain.scorers.base import DimensionResult

logger = logging.getLogger(__name__)


class BatchResult(BaseModel):
    job_title: str
    company: str
    source: str
    source_id: str
    composite_score: float
    dimensions: list[DimensionResult]


class BatchEvaluationService:
    def __init__(self, orchestrator: Any, concurrency: int = 3) -> None:
        self._orchestrator = orchestrator
        self._semaphore = asyncio.Semaphore(concurrency)

    async def evaluate_batch(self, jobs: list[dict]) -> list[BatchResult]:
        if not jobs:
            return []

        async def evaluate_one(job: dict) -> BatchResult:
            async with self._semaphore:
                try:
                    result = await self._orchestrator.evaluate(job=job, profile=None)
                    return BatchResult(
                        job_title=result.job_title,
                        company=result.company,
                        source=job.get("source", "unknown"),
                        source_id=job.get("source_id", ""),
                        composite_score=result.composite_score,
                        dimensions=list(result.dimensions),
                    )
                except Exception as exc:
                    logger.warning("Batch evaluation failed for %s: %s", job.get("title", ""), exc)
                    return BatchResult(
                        job_title=job.get("title", "Unknown"),
                        company=job.get("company", "Unknown"),
                        source=job.get("source", "unknown"),
                        source_id=job.get("source_id", ""),
                        composite_score=0.5,
                        dimensions=[],
                    )

        results = await asyncio.gather(*[evaluate_one(j) for j in jobs])
        return sorted(results, key=lambda r: r.composite_score, reverse=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/matching/test_batch_service.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/matching/domain/batch_service.py backend/tests/unit/matching/test_batch_service.py
git commit -m "feat(matching): add BatchEvaluationService with semaphore concurrency"
```

---

## Task 2: Config, schemas, and IngestionOrchestrator.list_jobs()

**Files:**
- Modify: `backend/src/hiresense/config.py`
- Modify: `.env.example`
- Modify: `backend/src/hiresense/matching/api/schemas.py`
- Modify: `backend/src/hiresense/ingestion/domain/services.py`

- [ ] **Step 1: Add batch_concurrency to Settings**

In `backend/src/hiresense/config.py`, add after the matching weights block (after line 93):

```python
    # Batch processing
    batch_concurrency: int = 3
```

- [ ] **Step 2: Add to .env.example**

Add to `.env.example`:

```env
# === Batch Processing ===
BATCH_CONCURRENCY=3
```

- [ ] **Step 3: Add batch schemas**

Add to `backend/src/hiresense/matching/api/schemas.py`:

```python
import uuid as uuid_mod


class BatchEvaluateRequest(BaseModel):
    tracked_app_ids: list[uuid_mod.UUID] = []
    include_ingested: bool = False


class BatchResultResponse(BaseModel):
    job_title: str
    company: str
    source: str
    source_id: str
    composite_score: float
    dimensions: list[DimensionResultResponse]


class BatchEvaluationResponse(BaseModel):
    total_jobs: int
    results: list[BatchResultResponse]
```

- [ ] **Step 4: Add list_jobs() to IngestionOrchestrator**

In `backend/src/hiresense/ingestion/domain/services.py`, add after `get_job_by_id` method (after line 75):

```python
    def list_jobs(self) -> list[NormalizedJob]:
        return list(self._jobs.values())
```

- [ ] **Step 5: Run all tests to verify no regressions**

Run: `cd backend && uv run python -m pytest tests/ -q`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/config.py .env.example backend/src/hiresense/matching/api/schemas.py backend/src/hiresense/ingestion/domain/services.py
git commit -m "feat(matching): add batch config, API schemas, and IngestionOrchestrator.list_jobs()"
```

---

## Task 3: Batch evaluate endpoint and DI stubs

**Files:**
- Modify: `backend/src/hiresense/matching/api/dependencies.py`
- Modify: `backend/src/hiresense/matching/api/routes.py`
- Create: `backend/tests/unit/matching/test_batch_route.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/matching/test_batch_route.py`:

```python
from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.matching.api.dependencies import (
    get_batch_evaluation_service,
    get_ingestion_orchestrator_for_matching,
    get_tracking_service_for_matching,
)
from hiresense.matching.api.routes import router
from hiresense.matching.domain.batch_service import BatchResult
from hiresense.matching.domain.scorers.base import DimensionResult


class FakeBatchService:
    async def evaluate_batch(self, jobs):
        return [
            BatchResult(
                job_title=j.get("title", ""),
                company=j.get("company", ""),
                source=j.get("source", "unknown"),
                source_id=j.get("source_id", ""),
                composite_score=0.8,
                dimensions=[
                    DimensionResult(dimension="seniority_fit", score=0.8, rationale="Good", weight=10),
                ],
            )
            for j in jobs
        ]


class FakeTrackedApp:
    def __init__(self, id, title, company, url=None):
        self.id = id
        self.title = title
        self.company = company
        self.url = url


class FakeTrackingService:
    def __init__(self):
        self._apps = [
            FakeTrackedApp(id=uuid.uuid4(), title="SWE", company="Acme"),
            FakeTrackedApp(id=uuid.uuid4(), title="ML Eng", company="Beta"),
        ]

    def list(self, status=None):
        return self._apps

    def get(self, id):
        for a in self._apps:
            if a.id == id:
                return a
        raise ValueError(f"Not found: {id}")


class FakeNormalizedJob:
    def __init__(self, id, title, company, description="", skills=None, location=""):
        self.id = id
        self.title = title
        self.company = company
        self.description = description
        self.skills = skills or []
        self.location = location


class FakeIngestionOrchestrator:
    def list_jobs(self):
        return [
            FakeNormalizedJob(id="ing-1", title="Data Eng", company="Gamma"),
        ]


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_batch_evaluation_service] = lambda: FakeBatchService()
    app.dependency_overrides[get_tracking_service_for_matching] = lambda: FakeTrackingService()
    app.dependency_overrides[get_ingestion_orchestrator_for_matching] = lambda: FakeIngestionOrchestrator()
    return app


def test_batch_evaluate_all_tracked() -> None:
    client = TestClient(_make_app())
    response = client.post("/matching/batch-evaluate", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 2
    assert len(data["results"]) == 2
    assert data["results"][0]["source"] == "tracked"


def test_batch_evaluate_specific_ids() -> None:
    client = TestClient(_make_app())
    tracking_svc = FakeTrackingService()
    app_id = str(tracking_svc._apps[0].id)

    app = _make_app()
    app.dependency_overrides[get_tracking_service_for_matching] = lambda: tracking_svc
    client = TestClient(app)

    response = client.post("/matching/batch-evaluate", json={"tracked_app_ids": [app_id]})
    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 1


def test_batch_evaluate_with_ingested() -> None:
    client = TestClient(_make_app())
    response = client.post("/matching/batch-evaluate", json={"include_ingested": True})
    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 3
    sources = {r["source"] for r in data["results"]}
    assert "tracked" in sources
    assert "ingested" in sources


def test_batch_evaluate_empty_pipeline() -> None:
    class EmptyTrackingService:
        def list(self, status=None):
            return []
        def get(self, id):
            raise ValueError("Not found")

    app = _make_app()
    app.dependency_overrides[get_tracking_service_for_matching] = lambda: EmptyTrackingService()
    client = TestClient(app)
    response = client.post("/matching/batch-evaluate", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 0
    assert data["results"] == []


def test_batch_evaluate_skips_missing_tracked_ids() -> None:
    client = TestClient(_make_app())
    fake_id = str(uuid.uuid4())
    response = client.post("/matching/batch-evaluate", json={"tracked_app_ids": [fake_id]})
    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/matching/test_batch_route.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Add DI stubs**

Replace `backend/src/hiresense/matching/api/dependencies.py` with:

```python
from __future__ import annotations


def get_matching_orchestrator():
    raise NotImplementedError(
        "Must be overridden during app startup via dependency_overrides"
    )


def get_batch_evaluation_service():
    raise NotImplementedError(
        "Must be overridden during app startup via dependency_overrides"
    )


def get_tracking_service_for_matching():
    raise NotImplementedError(
        "Must be overridden during app startup via dependency_overrides"
    )


def get_ingestion_orchestrator_for_matching():
    raise NotImplementedError(
        "Must be overridden during app startup via dependency_overrides"
    )
```

- [ ] **Step 4: Add batch-evaluate endpoint**

Add to `backend/src/hiresense/matching/api/routes.py`:

Import at top:
```python
from hiresense.identity.api.dependencies import require_auth
from hiresense.matching.api.dependencies import (
    get_batch_evaluation_service,
    get_ingestion_orchestrator_for_matching,
    get_matching_orchestrator,
    get_tracking_service_for_matching,
)
from hiresense.matching.api.schemas import (
    BatchEvaluateRequest,
    BatchEvaluationResponse,
    BatchResultResponse,
    DimensionResultResponse,
    EvaluateRequest,
    EvaluationResponse,
)
```

Add endpoint:
```python
@router.post("/batch-evaluate", response_model=BatchEvaluationResponse, dependencies=[Depends(require_auth)])
async def batch_evaluate(
    body: BatchEvaluateRequest,
    batch_service: Annotated[object, Depends(get_batch_evaluation_service)],
    tracking_service: Annotated[object, Depends(get_tracking_service_for_matching)],
    ingestion_orchestrator: Annotated[object, Depends(get_ingestion_orchestrator_for_matching)],
) -> BatchEvaluationResponse:
    jobs: list[dict] = []

    if body.tracked_app_ids:
        for app_id in body.tracked_app_ids:
            try:
                app = tracking_service.get(app_id)
                jobs.append({
                    "title": app.title,
                    "company": app.company,
                    "description": "",
                    "source": "tracked",
                    "source_id": str(app.id),
                })
            except ValueError:
                continue
    else:
        for app in tracking_service.list():
            jobs.append({
                "title": app.title,
                "company": app.company,
                "description": "",
                "source": "tracked",
                "source_id": str(app.id),
            })

    if body.include_ingested:
        for job in ingestion_orchestrator.list_jobs():
            jobs.append({
                "title": job.title,
                "company": job.company,
                "description": getattr(job, "description", ""),
                "skills": getattr(job, "skills", []),
                "location": getattr(job, "location", ""),
                "source": "ingested",
                "source_id": str(job.id),
            })

    results = await batch_service.evaluate_batch(jobs)

    return BatchEvaluationResponse(
        total_jobs=len(results),
        results=[
            BatchResultResponse(
                job_title=r.job_title,
                company=r.company,
                source=r.source,
                source_id=r.source_id,
                composite_score=r.composite_score,
                dimensions=[
                    DimensionResultResponse(
                        dimension=d.dimension,
                        score=d.score,
                        rationale=d.rationale,
                        weight=d.weight,
                    )
                    for d in r.dimensions
                ],
            )
            for r in results
        ],
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/matching/test_batch_route.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Run all tests for regressions**

Run: `cd backend && uv run python -m pytest tests/ -q`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/src/hiresense/matching/api/dependencies.py backend/src/hiresense/matching/api/routes.py backend/tests/unit/matching/test_batch_route.py
git commit -m "feat(matching): add POST /matching/batch-evaluate endpoint"
```

---

## Task 4: Wire batch service into app factory

**Files:**
- Modify: `backend/src/hiresense/main.py`

- [ ] **Step 1: Add imports**

Add to `backend/src/hiresense/main.py` imports:

```python
from hiresense.matching.domain.batch_service import BatchEvaluationService
from hiresense.matching.api.dependencies import (
    get_batch_evaluation_service,
    get_tracking_service_for_matching,
    get_ingestion_orchestrator_for_matching,
)
```

- [ ] **Step 2: Wire batch service after matching_orchestrator**

After line 168 (`app.dependency_overrides[get_matching_orchestrator] = lambda: matching_orchestrator`), add:

```python
    batch_evaluation_service = BatchEvaluationService(
        orchestrator=matching_orchestrator,
        concurrency=settings.batch_concurrency,
    )
    app.dependency_overrides[get_batch_evaluation_service] = lambda: batch_evaluation_service
```

- [ ] **Step 3: Wire cross-module DI stubs**

After the tracking module section (after line 186), add:

```python
    # --- Cross-module DI for batch evaluation ---
    app.dependency_overrides[get_tracking_service_for_matching] = lambda: tracking_service
    app.dependency_overrides[get_ingestion_orchestrator_for_matching] = lambda: ingestion_orchestrator
```

- [ ] **Step 4: Run all tests**

Run: `cd backend && uv run python -m pytest tests/ -q`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/main.py
git commit -m "feat(app): wire batch evaluation service"
```

---

## Task 5: Frontend models and tracking page leaderboard

**Files:**
- Create: `frontend/src/app/core/models/batch-result.model.ts`
- Create: `frontend/src/app/core/models/batch-evaluation-response.model.ts`
- Modify: `frontend/src/app/pages/tracking/tracking.component.ts`
- Modify: `frontend/src/app/pages/tracking/tracking.component.html`

- [ ] **Step 1: Create TypeScript models**

Create `frontend/src/app/core/models/batch-result.model.ts`:

```typescript
import { DimensionResult } from './dimension-result.model';

export interface BatchResult {
  job_title: string;
  company: string;
  source: string;
  source_id: string;
  composite_score: number;
  dimensions: DimensionResult[];
}
```

Create `frontend/src/app/core/models/batch-evaluation-response.model.ts`:

```typescript
import { BatchResult } from './batch-result.model';

export interface BatchEvaluationResponse {
  total_jobs: number;
  results: BatchResult[];
}
```

- [ ] **Step 2: Add evaluation state and methods to tracking component**

In `frontend/src/app/pages/tracking/tracking.component.ts`, add imports:

```typescript
import { BatchEvaluationResponse } from '../../core/models/batch-evaluation-response.model';
import { BatchResult } from '../../core/models/batch-result.model';
```

Add signals after existing signals (after line 29):

```typescript
  leaderboard = signal<BatchResult[]>([]);
  evaluating = signal(false);
  expandedResultId = signal<string | null>(null);
```

Add methods before `private resetForm()`:

```typescript
  evaluateAll(): void {
    const apps = this.applications();
    if (apps.length === 0) return;
    this.evaluating.set(true);
    this.leaderboard.set([]);
    const ids = apps.map((a) => a.id);
    this.http
      .post<BatchEvaluationResponse>(`${environment.apiUrl}/matching/batch-evaluate`, {
        tracked_app_ids: ids,
      })
      .subscribe({
        next: (res) => {
          this.leaderboard.set(res.results);
          this.evaluating.set(false);
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Batch evaluation failed');
          this.evaluating.set(false);
        },
      });
  }

  toggleExpand(sourceId: string): void {
    this.expandedResultId.update((current) => (current === sourceId ? null : sourceId));
  }

  scoreColor(score: number): string {
    if (score >= 0.7) return '#16a34a';
    if (score >= 0.4) return '#ca8a04';
    return '#dc2626';
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

- [ ] **Step 3: Add leaderboard UI to tracking template**

In `frontend/src/app/pages/tracking/tracking.component.html`, add after the stats div (after line 85, before the table-container):

```html
      <div class="batch-actions">
        <button (click)="evaluateAll()" [disabled]="evaluating() || applications().length === 0" class="btn-primary">
          @if (evaluating()) { Evaluating {{ applications().length }} jobs... } @else { Evaluate All }
        </button>
      </div>
```

Add after the closing `</div>` of `table-container` (after line 135, before the `} @else {` for empty state):

```html
      @if (leaderboard().length > 0) {
        <div class="leaderboard">
          <h2>Leaderboard</h2>
          <div class="leaderboard-list">
            @for (result of leaderboard(); track result.source_id; let i = $index) {
              <div class="leaderboard-card" (click)="toggleExpand(result.source_id)">
                <div class="leaderboard-header">
                  <span class="rank">#{{ i + 1 }}</span>
                  <div class="leaderboard-info">
                    <span class="leaderboard-title">{{ result.job_title }}</span>
                    <span class="leaderboard-company">{{ result.company }}</span>
                  </div>
                  <span class="leaderboard-badge badge-{{ result.source }}">{{ result.source }}</span>
                  <span class="leaderboard-score" [style.color]="scoreColor(result.composite_score)">
                    {{ (result.composite_score * 100).toFixed(0) }}%
                  </span>
                </div>
                @if (expandedResultId() === result.source_id) {
                  <div class="leaderboard-dimensions">
                    @for (dim of result.dimensions; track dim.dimension) {
                      <div class="dim-row">
                        <span class="dim-name">{{ dimensionLabel(dim.dimension) }}</span>
                        <div class="dim-bar">
                          <div class="dim-bar-fill"
                               [style.width.%]="dim.score * 100"
                               [style.background-color]="scoreColor(dim.score)">
                          </div>
                        </div>
                        <span class="dim-score">{{ (dim.score * 100).toFixed(0) }}%</span>
                      </div>
                    }
                  </div>
                }
              </div>
            }
          </div>
        </div>
      }
```

- [ ] **Step 4: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/core/models/batch-result.model.ts frontend/src/app/core/models/batch-evaluation-response.model.ts frontend/src/app/pages/tracking/tracking.component.ts frontend/src/app/pages/tracking/tracking.component.html
git commit -m "feat(frontend): add batch evaluation leaderboard to Pipeline page"
```

---

## Task 6: Full test suite verification

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && uv run python -m pytest tests/ -v`
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
git commit -m "fix: address lint issues from batch processing implementation"
```
