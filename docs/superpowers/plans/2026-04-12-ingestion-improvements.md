# Ingestion Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the Job Ingestion page with two tabs (Job Boards / Company Portals), backend-driven filtering and pagination, a job detail slide-out panel, and fix broken portal configurations.

**Architecture:** Backend adds query parameters to `GET /ingestion/jobs` for tab selection, filtering (source, keyword, location, skills, date range), and pagination. PortalScanner gains internal job storage like IngestionOrchestrator. A shared `job_filter` module handles filtering and pagination logic. Frontend gets new Angular components: tabs, filters bar, pagination, and detail panel — all wired to the paginated API.

**Tech Stack:** Python/FastAPI/Pydantic (backend), Angular 19 with signals (frontend), pytest (testing), uv (package manager)

**Spec:** `docs/superpowers/specs/2026-04-12-ingestion-improvements-design.md`

---

## Task 1: Add `platform` and `categories` fields to NormalizedJob

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/models.py:16-33`
- Test: `backend/tests/unit/ingestion/test_models.py`

- [ ] **Step 1: Write the failing test**

In `backend/tests/unit/ingestion/test_models.py`, add:

```python
def test_normalized_job_has_platform_and_categories() -> None:
    job = NormalizedJob(
        id="1",
        title="Engineer",
        company="Co",
        description="Do stuff",
        source="greenhouse",
        source_type="api",
        url="https://example.com/1",
        platform="greenhouse",
        categories=["ai-research"],
    )
    assert job.platform == "greenhouse"
    assert job.categories == ["ai-research"]


def test_normalized_job_defaults_platform_and_categories() -> None:
    job = NormalizedJob(
        id="1",
        title="Engineer",
        company="Co",
        description="Do stuff",
        source="remotive",
        source_type="api",
        url="https://example.com/1",
    )
    assert job.platform is None
    assert job.categories == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_models.py::test_normalized_job_has_platform_and_categories -v`
Expected: FAIL — `platform` is not a valid field

- [ ] **Step 3: Add fields to NormalizedJob**

In `backend/src/hiresense/ingestion/domain/models.py`, add two fields to `NormalizedJob` after line 29 (`department`):

```python
    platform: str | None = None
    categories: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full ingestion test suite to check nothing broke**

Run: `cd backend && uv run pytest tests/unit/ingestion/ -v`
Expected: ALL PASS (existing tests use defaults, so new optional fields don't break them)

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/models.py backend/tests/unit/ingestion/test_models.py
git commit -m "feat(ingestion): add platform and categories fields to NormalizedJob"
```

---

## Task 2: Add `enabled` field to PortalEntry

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/portal_config.py:10-14`
- Test: `backend/tests/unit/ingestion/test_portal_config.py`

- [ ] **Step 1: Write the failing test**

In `backend/tests/unit/ingestion/test_portal_config.py`, add:

```python
def test_portal_entry_enabled_defaults_true() -> None:
    entry = PortalEntry(name="Acme", platform="greenhouse", board_id="acme")
    assert entry.enabled is True


def test_portal_entry_can_be_disabled() -> None:
    entry = PortalEntry(name="Acme", platform="greenhouse", board_id="acme", enabled=False)
    assert entry.enabled is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_portal_config.py::test_portal_entry_enabled_defaults_true -v`
Expected: FAIL — `enabled` is not a valid field

- [ ] **Step 3: Add the field**

In `backend/src/hiresense/ingestion/domain/portal_config.py`, add to `PortalEntry` after line 14:

```python
    enabled: bool = True
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_portal_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/portal_config.py backend/tests/unit/ingestion/test_portal_config.py
git commit -m "feat(ingestion): add enabled flag to PortalEntry"
```

---

## Task 3: Create job_filter module for shared filtering and pagination

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/job_filter.py`
- Create: `backend/tests/unit/ingestion/test_job_filter.py`
- Modify: `backend/src/hiresense/ingestion/domain/__init__.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/ingestion/test_job_filter.py`:

```python
from __future__ import annotations

from datetime import datetime

import pytest

from hiresense.ingestion.domain.job_filter import JobQueryParams, PaginatedResult, filter_and_paginate
from hiresense.ingestion.domain.models import NormalizedJob


def _job(
    id: str = "1",
    title: str = "Engineer",
    company: str = "Co",
    source: str = "remotive",
    source_type: str = "api",
    location: str = "Remote",
    skills: list[str] | None = None,
    posted_date: datetime | None = None,
    description: str = "Do stuff",
    url: str = "https://example.com",
) -> NormalizedJob:
    return NormalizedJob(
        id=id,
        title=title,
        company=company,
        description=description,
        skills=skills or [],
        location=location,
        source=source,
        source_type=source_type,
        url=url,
        posted_date=posted_date,
    )


def test_paginate_first_page() -> None:
    jobs = [_job(id=str(i)) for i in range(50)]
    params = JobQueryParams(page=1, page_size=20)
    result = filter_and_paginate(jobs, params)
    assert len(result.jobs) == 20
    assert result.total == 50
    assert result.page == 1
    assert result.page_size == 20
    assert result.total_pages == 3


def test_paginate_last_page() -> None:
    jobs = [_job(id=str(i)) for i in range(50)]
    params = JobQueryParams(page=3, page_size=20)
    result = filter_and_paginate(jobs, params)
    assert len(result.jobs) == 10
    assert result.page == 3


def test_filter_by_source() -> None:
    jobs = [
        _job(id="1", source="remotive"),
        _job(id="2", source="linkedin"),
        _job(id="3", source="remotive"),
    ]
    params = JobQueryParams(source="remotive")
    result = filter_and_paginate(jobs, params)
    assert result.total == 2
    assert all(j.source == "remotive" for j in result.jobs)


def test_filter_by_keyword_in_title() -> None:
    jobs = [
        _job(id="1", title="Backend Engineer"),
        _job(id="2", title="Designer"),
    ]
    params = JobQueryParams(keyword="engineer")
    result = filter_and_paginate(jobs, params)
    assert result.total == 1
    assert result.jobs[0].title == "Backend Engineer"


def test_filter_by_keyword_in_description() -> None:
    jobs = [
        _job(id="1", title="Role", description="We need a Python expert"),
        _job(id="2", title="Role", description="Marketing position"),
    ]
    params = JobQueryParams(keyword="python")
    result = filter_and_paginate(jobs, params)
    assert result.total == 1


def test_filter_by_location() -> None:
    jobs = [
        _job(id="1", location="San Francisco, CA"),
        _job(id="2", location="Remote"),
        _job(id="3", location="Remote, US"),
    ]
    params = JobQueryParams(location="remote")
    result = filter_and_paginate(jobs, params)
    assert result.total == 2


def test_filter_by_skills() -> None:
    jobs = [
        _job(id="1", skills=["python", "fastapi"]),
        _job(id="2", skills=["react", "typescript"]),
        _job(id="3", skills=["python", "django"]),
    ]
    params = JobQueryParams(skills="python")
    result = filter_and_paginate(jobs, params)
    assert result.total == 2


def test_filter_by_multiple_skills() -> None:
    jobs = [
        _job(id="1", skills=["python", "fastapi"]),
        _job(id="2", skills=["react", "typescript"]),
        _job(id="3", skills=["python", "django"]),
    ]
    params = JobQueryParams(skills="python,react")
    result = filter_and_paginate(jobs, params)
    assert result.total == 3


def test_filter_by_date_range() -> None:
    jobs = [
        _job(id="1", posted_date=datetime(2026, 4, 1)),
        _job(id="2", posted_date=datetime(2026, 4, 5)),
        _job(id="3", posted_date=datetime(2026, 4, 10)),
        _job(id="4", posted_date=None),
    ]
    params = JobQueryParams(
        date_from=datetime(2026, 4, 3),
        date_to=datetime(2026, 4, 8),
    )
    result = filter_and_paginate(jobs, params)
    assert result.total == 1
    assert result.jobs[0].id == "2"


def test_combined_filters_and_pagination() -> None:
    jobs = [
        _job(id=str(i), source="remotive", location="Remote", skills=["python"])
        for i in range(30)
    ] + [
        _job(id=str(i + 30), source="linkedin", location="NYC")
        for i in range(20)
    ]
    params = JobQueryParams(source="remotive", page=1, page_size=20)
    result = filter_and_paginate(jobs, params)
    assert result.total == 30
    assert len(result.jobs) == 20
    assert result.total_pages == 2


def test_empty_result() -> None:
    params = JobQueryParams(source="nonexistent")
    result = filter_and_paginate([], params)
    assert result.total == 0
    assert result.jobs == []
    assert result.total_pages == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_job_filter.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement the job_filter module**

Create `backend/src/hiresense/ingestion/domain/job_filter.py`:

```python
from __future__ import annotations

import math
from datetime import datetime

from pydantic import BaseModel, Field

from hiresense.ingestion.domain.models import NormalizedJob


class JobQueryParams(BaseModel):
    page: int = 1
    page_size: int = 20
    source: str | None = None
    keyword: str | None = None
    location: str | None = None
    skills: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class PaginatedResult(BaseModel):
    jobs: list[NormalizedJob]
    total: int
    page: int
    page_size: int
    total_pages: int


def filter_and_paginate(
    jobs: list[NormalizedJob],
    params: JobQueryParams,
) -> PaginatedResult:
    filtered = jobs

    if params.source:
        filtered = [j for j in filtered if j.source == params.source]

    if params.keyword:
        kw = params.keyword.lower()
        filtered = [
            j for j in filtered
            if kw in j.title.lower() or kw in j.description.lower()
        ]

    if params.location:
        loc = params.location.lower()
        filtered = [j for j in filtered if loc in j.location.lower()]

    if params.skills:
        skill_set = {s.strip().lower() for s in params.skills.split(",") if s.strip()}
        filtered = [
            j for j in filtered
            if skill_set & {s.lower() for s in j.skills}
        ]

    if params.date_from:
        filtered = [
            j for j in filtered
            if j.posted_date is not None and j.posted_date >= params.date_from
        ]

    if params.date_to:
        filtered = [
            j for j in filtered
            if j.posted_date is not None and j.posted_date <= params.date_to
        ]

    total = len(filtered)
    total_pages = math.ceil(total / params.page_size) if total > 0 else 0
    start = (params.page - 1) * params.page_size
    end = start + params.page_size
    page_jobs = filtered[start:end]

    return PaginatedResult(
        jobs=page_jobs,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_job_filter.py -v`
Expected: ALL PASS

- [ ] **Step 5: Update domain __init__.py**

In `backend/src/hiresense/ingestion/domain/__init__.py`, add the re-exports:

```python
from hiresense.ingestion.domain.job_filter import JobQueryParams, PaginatedResult, filter_and_paginate
```

And update `__all__` to include `"JobQueryParams"`, `"PaginatedResult"`, `"filter_and_paginate"`.

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/job_filter.py backend/src/hiresense/ingestion/domain/__init__.py backend/tests/unit/ingestion/test_job_filter.py
git commit -m "feat(ingestion): add job_filter module for shared filtering and pagination"
```

---

## Task 4: Add job storage to PortalScanner + set platform/categories

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/portal_scanner.py:37-127`
- Modify: `backend/tests/unit/ingestion/test_portal_scanner.py`

- [ ] **Step 1: Write the failing tests**

In `backend/tests/unit/ingestion/test_portal_scanner.py`, add:

```python
@pytest.mark.asyncio
async def test_scan_stores_jobs_internally() -> None:
    """After scanning, jobs are accessible via list_jobs()."""
    raw = _make_raw("Engineer", "Acme", "https://example.com/1")
    adapter = FakeAdapter([raw])

    config = _make_config(
        PortalEntry(name="Acme", platform="greenhouse", board_id="acme", categories=["engineering"]),
    )
    adapters = {"greenhouse": adapter}
    normalizers = {"greenhouse": FakeNormalizer()}
    bus = FakeEventBus()

    scanner = PortalScanner(config=config, adapters=adapters, normalizers=normalizers, event_bus=bus)
    assert scanner.list_jobs() == []

    await scanner.scan(ScanFilters())
    stored = scanner.list_jobs()
    assert len(stored) == 1
    assert stored[0].title == "Engineer"


@pytest.mark.asyncio
async def test_scan_sets_platform_and_categories() -> None:
    """Scanned jobs get platform and categories from the portal config."""
    raw = _make_raw("Engineer", "Acme", "https://example.com/1")
    adapter = FakeAdapter([raw])

    config = _make_config(
        PortalEntry(name="Acme", platform="greenhouse", board_id="acme", categories=["ai-research"]),
    )
    adapters = {"greenhouse": adapter}
    normalizers = {"greenhouse": FakeNormalizer()}
    bus = FakeEventBus()

    scanner = PortalScanner(config=config, adapters=adapters, normalizers=normalizers, event_bus=bus)
    result = await scanner.scan(ScanFilters())

    assert result.jobs[0].source == "Acme"
    assert result.jobs[0].platform == "greenhouse"
    assert result.jobs[0].categories == ["ai-research"]


@pytest.mark.asyncio
async def test_scan_skips_disabled_portals() -> None:
    """Disabled portals are not scanned."""
    raw = _make_raw()
    adapter_enabled = FakeAdapter([raw])
    adapter_disabled = FakeAdapter([raw])

    config = _make_config(
        PortalEntry(name="EnabledCo", platform="greenhouse", board_id="enabled", categories=[], enabled=True),
        PortalEntry(name="DisabledCo", platform="lever", board_id="disabled", categories=[], enabled=False),
    )
    adapters = {"greenhouse": adapter_enabled, "lever": adapter_disabled}
    normalizers = {"greenhouse": FakeNormalizer(), "lever": FakeNormalizer()}
    bus = FakeEventBus()

    scanner = PortalScanner(config=config, adapters=adapters, normalizers=normalizers, event_bus=bus)
    result = await scanner.scan(ScanFilters())

    assert result.new == 1
    assert len(adapter_enabled.calls) == 1
    assert len(adapter_disabled.calls) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_portal_scanner.py::test_scan_stores_jobs_internally -v`
Expected: FAIL — `list_jobs` does not exist

- [ ] **Step 3: Modify PortalScanner**

In `backend/src/hiresense/ingestion/domain/portal_scanner.py`:

1. Add `_jobs` dict to `__init__`:
```python
    self._jobs: dict[str, NormalizedJob] = {}
```

2. Add `list_jobs` method after `__init__`:
```python
    def list_jobs(self) -> list[NormalizedJob]:
        return list(self._jobs.values())
```

3. In `_filter_portals`, after filtering by companies, add enabled filter:
```python
        portals = [p for p in portals if p.enabled]
```

4. In `scan()`, after creating the job (line ~96-101), set source to company name, and add platform and categories:
```python
                job = NormalizedJob(
                    id=str(uuid.uuid4()),
                    source=portal.name,
                    source_type="api",
                    platform=portal.platform,
                    categories=list(portal.categories),
                    **normalized_data,
                )
```
**Important:** `source` changes from `portal.platform` to `portal.name` so portal jobs show the company name (e.g., "Anthropic") instead of the ATS platform ("greenhouse"). The `platform` field now carries the ATS info.

5. After dedup check passes and job is added to `new_jobs`, also store it:
```python
                if dedup_key not in seen_dedup_keys:
                    seen_dedup_keys.add(dedup_key)
                    new_jobs.append(job)
                    self._jobs[job.id] = job
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_portal_scanner.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/portal_scanner.py backend/tests/unit/ingestion/test_portal_scanner.py
git commit -m "feat(ingestion): add job storage, platform/categories, and enabled flag to PortalScanner"
```

---

## Task 5: Update GET /ingestion/jobs endpoint with filtering and pagination

**Files:**
- Modify: `backend/src/hiresense/ingestion/api/routes.py:50-54`
- Modify: `backend/tests/unit/ingestion/test_routes.py`

- [ ] **Step 1: Write the failing tests**

In `backend/tests/unit/ingestion/test_routes.py`, update imports and add a FakeScanner, then add tests:

```python
import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from hiresense.ingestion.api import get_ingestion_orchestrator, get_portal_scanner, router
from hiresense.ingestion.domain.models import NormalizedJob


BOARD_JOB = NormalizedJob(
    id="board-1",
    title="Board Engineer",
    company="Co",
    description="Board job",
    skills=["python"],
    location="Remote",
    source="remotive",
    source_type="api",
    language="en",
    url="https://example.com/board",
)

PORTAL_JOB = NormalizedJob(
    id="portal-1",
    title="Portal Engineer",
    company="PortalCo",
    description="Portal job",
    skills=["go"],
    location="NYC",
    source="PortalCo",
    source_type="api",
    platform="greenhouse",
    categories=["ai-research"],
    language="en",
    url="https://example.com/portal",
)


class FakeOrchestrator:
    def __init__(self) -> None:
        self.called = False

    async def run(self, filters=None) -> list[NormalizedJob]:
        self.called = True
        return [BOARD_JOB]

    def list_jobs(self) -> list[NormalizedJob]:
        return [BOARD_JOB]


class FakeScanner:
    def list_jobs(self) -> list[NormalizedJob]:
        return [PORTAL_JOB]


def _make_app() -> tuple[FastAPI, FakeOrchestrator, FakeScanner]:
    app = FastAPI()
    orch = FakeOrchestrator()
    scanner = FakeScanner()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: orch
    app.dependency_overrides[get_portal_scanner] = lambda: scanner
    app.include_router(router)
    return app, orch, scanner


@pytest.mark.asyncio
async def test_list_jobs_boards_tab() -> None:
    app, _, _ = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs?tab=boards")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["jobs"][0]["source"] == "remotive"
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total_pages"] == 1


@pytest.mark.asyncio
async def test_list_jobs_portals_tab() -> None:
    app, _, _ = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs?tab=portals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["jobs"][0]["source"] == "PortalCo"


@pytest.mark.asyncio
async def test_list_jobs_pagination() -> None:
    app, _, _ = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs?tab=boards&page=1&page_size=20")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 20


@pytest.mark.asyncio
async def test_list_jobs_filter_by_source() -> None:
    app, _, _ = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs?tab=boards&source=nonexistent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_fetch_jobs_endpoint() -> None:
    """Existing fetch test — keep working."""
    app, fake_orch, _ = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/fetch")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert fake_orch.called
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_routes.py::test_list_jobs_boards_tab -v`
Expected: FAIL — endpoint signature mismatch or missing `tab` param

- [ ] **Step 3: Update the endpoint**

Rewrite `GET /ingestion/jobs` in `backend/src/hiresense/ingestion/api/routes.py`:

```python
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from hiresense.ingestion.api.dependencies import (
    get_ingestion_orchestrator,
    get_portal_scanner,
    get_portals_config,
)
from hiresense.ingestion.domain.job_filter import JobQueryParams, PaginatedResult, filter_and_paginate
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.portal_config import PortalEntry, PortalsConfig
from hiresense.ingestion.domain.portal_scanner import PortalScanner, ScanFilters, ScanResult
from hiresense.ingestion.domain.services import IngestionCooldownError, IngestionOrchestrator

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class FetchResponse(BaseModel):
    count: int
    jobs: list[NormalizedJob]


@router.post("/fetch", response_model=FetchResponse)
async def fetch_jobs(
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
) -> FetchResponse | JSONResponse:
    try:
        jobs = await orchestrator.run()
    except IngestionCooldownError as exc:
        return JSONResponse(
            status_code=429,
            content={"detail": str(exc), "retry_after": exc.retry_after},
            headers={"Retry-After": str(exc.retry_after)},
        )
    return FetchResponse(count=len(jobs), jobs=jobs)


@router.post("/scan-portals", response_model=ScanResult)
async def scan_portals(
    filters: ScanFilters,
    scanner: Annotated[PortalScanner, Depends(get_portal_scanner)],
) -> ScanResult:
    return await scanner.scan(filters)


@router.get("/jobs", response_model=PaginatedResult)
async def list_jobs(
    tab: Annotated[Literal["boards", "portals"], Query()],
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
    scanner: Annotated[PortalScanner, Depends(get_portal_scanner)],
    page: int = 1,
    page_size: int = 20,
    source: str | None = None,
    keyword: str | None = None,
    location: str | None = None,
    skills: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> PaginatedResult:
    all_jobs = orchestrator.list_jobs() if tab == "boards" else scanner.list_jobs()
    params = JobQueryParams(
        page=page,
        page_size=page_size,
        source=source,
        keyword=keyword,
        location=location,
        skills=skills,
        date_from=date_from,
        date_to=date_to,
    )
    return filter_and_paginate(all_jobs, params)


@router.get("/portals", response_model=list[PortalEntry])
async def list_portals(
    config: Annotated[PortalsConfig, Depends(get_portals_config)],
) -> list[PortalEntry]:
    return config.portals
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_routes.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full ingestion test suite**

Run: `cd backend && uv run pytest tests/unit/ingestion/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/ingestion/api/routes.py backend/tests/unit/ingestion/test_routes.py
git commit -m "feat(ingestion): add tab-based filtering and pagination to GET /ingestion/jobs"
```

---

## Task 6: Fix broken portal configurations

**Files:**
- Modify: `backend/src/hiresense/ingestion/config/portals.yml`

- [ ] **Step 1: Research each broken portal's current careers page**

For each of the 9 failing companies, visit their careers page and determine:
- What ATS platform they currently use
- What the correct board ID is
- Whether they have a public API board at all

Check each by testing the URL pattern:
- Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{board_id}/jobs`
- Lever: `https://api.lever.co/v0/postings/{board_id}`
- Ashby: `https://api.ashbyhq.com/posting-api/job-board/{board_id}`

- [ ] **Step 2: Update portals.yml**

Update `backend/src/hiresense/ingestion/config/portals.yml` with:
- Fixed board IDs for companies that moved
- `enabled: false` for companies with no public API board
- Correct platform values for companies that switched ATS

Keep the working portals (Anthropic, Hugging Face, Stability AI, Scale AI, Pinecone, Vercel, Temporal) unchanged.

- [ ] **Step 3: Test each portal manually**

Run the backend and trigger a portal scan to verify each portal works:

```bash
cd backend && uv run python -c "
import asyncio
import httpx
from hiresense.ingestion.domain.portal_config import load_portals_config
from pathlib import Path

async def test():
    config = load_portals_config(Path('src/hiresense/ingestion/config/portals.yml'))
    for portal in config.portals:
        if not portal.enabled:
            print(f'SKIP (disabled): {portal.name}')
            continue
        if portal.platform == 'greenhouse':
            url = f'https://boards-api.greenhouse.io/v1/boards/{portal.board_id}/jobs'
        elif portal.platform == 'lever':
            url = f'https://api.lever.co/v0/postings/{portal.board_id}'
        elif portal.platform == 'ashby':
            url = f'https://api.ashbyhq.com/posting-api/job-board/{portal.board_id}'
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
                print(f'{portal.name} ({portal.platform}): {resp.status_code}')
        except Exception as e:
            print(f'{portal.name} ({portal.platform}): ERROR - {e}')

asyncio.run(test())
"
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/ingestion/config/portals.yml
git commit -m "fix(ingestion): update portal board IDs and disable broken portals"
```

---

## Task 7: Update frontend NormalizedJob model and add PaginatedJobsResponse

**Files:**
- Modify: `frontend/src/app/pages/ingestion/models/normalized-job.model.ts`
- Create: `frontend/src/app/pages/ingestion/models/paginated-jobs-response.model.ts`

- [ ] **Step 1: Update NormalizedJob model**

In `frontend/src/app/pages/ingestion/models/normalized-job.model.ts`, add the missing fields:

```typescript
export interface NormalizedJob {
  id: string;
  title: string;
  company: string;
  description: string;
  skills: string[];
  location: string;
  salary_range: string | null;
  source: string;
  source_type: string;
  platform: string | null;
  categories: string[];
  department: string | null;
  url: string;
  posted_date: string | null;
}
```

- [ ] **Step 2: Create PaginatedJobsResponse model**

Create `frontend/src/app/pages/ingestion/models/paginated-jobs-response.model.ts`:

```typescript
import { NormalizedJob } from './normalized-job.model';

export interface PaginatedJobsResponse {
  jobs: NormalizedJob[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pages/ingestion/models/normalized-job.model.ts frontend/src/app/pages/ingestion/models/paginated-jobs-response.model.ts
git commit -m "feat(ingestion): update frontend NormalizedJob model and add PaginatedJobsResponse"
```

---

## Task 8: Rewrite IngestionService for paginated queries

**Files:**
- Modify: `frontend/src/app/core/services/ingestion.service.ts`

- [ ] **Step 1: Rewrite the service**

Replace `frontend/src/app/core/services/ingestion.service.ts` with:

```typescript
import { Injectable, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { FetchResponse } from '../../pages/ingestion/models/fetch-response.model';
import { NormalizedJob } from '../../pages/ingestion/models/normalized-job.model';
import { PaginatedJobsResponse } from '../../pages/ingestion/models/paginated-jobs-response.model';
import { PortalEntry } from '../../pages/ingestion/models/portal-entry.model';
import { ScanPortalsRequest } from '../../pages/ingestion/models/scan-portals-request.model';
import { ScanResult } from '../../pages/ingestion/models/scan-result.model';

export interface JobFilters {
  source?: string;
  keyword?: string;
  location?: string;
  skills?: string;
  date_from?: string;
  date_to?: string;
}

@Injectable({ providedIn: 'root' })
export class IngestionService {
  readonly trackedJobIds = signal<Set<string>>(new Set());

  constructor(private http: HttpClient) {}

  fetchJobs(): Observable<FetchResponse> {
    return this.http.post<FetchResponse>(`${environment.apiUrl}/ingestion/fetch`, {});
  }

  queryJobs(
    tab: 'boards' | 'portals',
    page: number,
    pageSize: number,
    filters: JobFilters = {},
  ): Observable<PaginatedJobsResponse> {
    let params = new HttpParams()
      .set('tab', tab)
      .set('page', page.toString())
      .set('page_size', pageSize.toString());

    if (filters.source) params = params.set('source', filters.source);
    if (filters.keyword) params = params.set('keyword', filters.keyword);
    if (filters.location) params = params.set('location', filters.location);
    if (filters.skills) params = params.set('skills', filters.skills);
    if (filters.date_from) params = params.set('date_from', filters.date_from);
    if (filters.date_to) params = params.set('date_to', filters.date_to);

    return this.http.get<PaginatedJobsResponse>(`${environment.apiUrl}/ingestion/jobs`, { params });
  }

  loadPortals(): Observable<PortalEntry[]> {
    return this.http.get<PortalEntry[]>(`${environment.apiUrl}/ingestion/portals`);
  }

  scanPortals(body: ScanPortalsRequest): Observable<ScanResult> {
    return this.http.post<ScanResult>(`${environment.apiUrl}/ingestion/scan-portals`, body);
  }

  markTracked(jobId: string): void {
    this.trackedJobIds.update((ids) => new Set([...ids, jobId]));
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/core/services/ingestion.service.ts
git commit -m "feat(ingestion): rewrite IngestionService with paginated queryJobs method"
```

---

## Task 9: Create PaginationComponent

**Files:**
- Create: `frontend/src/app/pages/ingestion/components/pagination/pagination.component.ts`
- Create: `frontend/src/app/pages/ingestion/components/pagination/pagination.component.html`
- Create: `frontend/src/app/pages/ingestion/components/pagination/pagination.component.scss`

- [ ] **Step 1: Create the component class**

Create `frontend/src/app/pages/ingestion/components/pagination/pagination.component.ts`:

```typescript
import { Component, input, output } from '@angular/core';

@Component({
  selector: 'app-pagination',
  standalone: true,
  imports: [],
  templateUrl: './pagination.component.html',
  styleUrl: './pagination.component.scss',
})
export class PaginationComponent {
  page = input.required<number>();
  pageSize = input.required<number>();
  total = input.required<number>();
  totalPages = input.required<number>();

  pageChange = output<number>();
  pageSizeChange = output<number>();

  get showingFrom(): number {
    return this.total() === 0 ? 0 : (this.page() - 1) * this.pageSize() + 1;
  }

  get showingTo(): number {
    return Math.min(this.page() * this.pageSize(), this.total());
  }

  onPrev(): void {
    if (this.page() > 1) {
      this.pageChange.emit(this.page() - 1);
    }
  }

  onNext(): void {
    if (this.page() < this.totalPages()) {
      this.pageChange.emit(this.page() + 1);
    }
  }

  onPageSizeChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.pageSizeChange.emit(Number(select.value));
  }
}
```

- [ ] **Step 2: Create the template**

Create `frontend/src/app/pages/ingestion/components/pagination/pagination.component.html`:

```html
<div class="pagination-bar">
  <span class="pagination-info">
    Showing {{ showingFrom }}–{{ showingTo }} of {{ total() | number }} jobs
  </span>

  <div class="pagination-controls">
    <label class="page-size-label">
      Rows per page:
      <select [value]="pageSize()" (change)="onPageSizeChange($event)" class="page-size-select">
        <option value="20">20</option>
        <option value="50">50</option>
        <option value="100">100</option>
      </select>
    </label>

    <button (click)="onPrev()" [disabled]="page() <= 1" class="btn-page">
      ← Prev
    </button>

    <span class="page-indicator">Page {{ page() }} of {{ totalPages() }}</span>

    <button (click)="onNext()" [disabled]="page() >= totalPages()" class="btn-page">
      Next →
    </button>
  </div>
</div>
```

- [ ] **Step 3: Create the styles**

Create `frontend/src/app/pages/ingestion/components/pagination/pagination.component.scss`:

```scss
.pagination-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border-subtle);
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.page-size-label {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.8125rem;
}

.page-size-select {
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  font-size: 0.8125rem;
  background: var(--bg-card);
  color: var(--text-primary);
}

.btn-page {
  padding: 0.25rem 0.625rem;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: 0.8125rem;
  cursor: pointer;
  transition: border-color var(--duration) var(--ease), color var(--duration) var(--ease);

  &:hover:not(:disabled) {
    border-color: var(--accent);
    color: var(--accent);
  }

  &:disabled {
    opacity: 0.4;
    cursor: default;
  }
}

.page-indicator {
  font-weight: 600;
  color: var(--text-primary);
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pages/ingestion/components/pagination/
git commit -m "feat(ingestion): create PaginationComponent"
```

---

## Task 10: Create JobFiltersComponent

**Files:**
- Create: `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.ts`
- Create: `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.html`
- Create: `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.scss`

- [ ] **Step 1: Create the component class**

Create `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.ts`:

```typescript
import { Component, input, output } from '@angular/core';
import { JobFilters } from '../../../../core/services/ingestion.service';

@Component({
  selector: 'app-job-filters',
  standalone: true,
  imports: [],
  templateUrl: './job-filters.component.html',
  styleUrl: './job-filters.component.scss',
})
export class JobFiltersComponent {
  sources = input.required<string[]>();
  filters = input.required<JobFilters>();

  filtersChange = output<JobFilters>();

  private debounceTimer: ReturnType<typeof setTimeout> | null = null;

  onSourceChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const value = select.value;
    this.emitFilters({ source: value || undefined });
  }

  onKeywordInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value.trim();
    this.debounceEmit({ keyword: value || undefined });
  }

  onLocationInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value.trim();
    this.debounceEmit({ location: value || undefined });
  }

  onSkillsInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value.trim();
    this.debounceEmit({ skills: value || undefined });
  }

  onDateFromChange(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.emitFilters({ date_from: value || undefined });
  }

  onDateToChange(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.emitFilters({ date_to: value || undefined });
  }

  clearAll(): void {
    this.filtersChange.emit({});
  }

  private emitFilters(partial: Partial<JobFilters>): void {
    this.filtersChange.emit({ ...this.filters(), ...partial });
  }

  private debounceEmit(partial: Partial<JobFilters>): void {
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => this.emitFilters(partial), 300);
  }
}
```

- [ ] **Step 2: Create the template**

Create `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.html`:

```html
<div class="filters-bar">
  <div class="filter-item">
    <label class="filter-label">Source</label>
    <select (change)="onSourceChange($event)" class="filter-control">
      <option value="">All sources</option>
      @for (source of sources(); track source) {
        <option [value]="source" [selected]="filters().source === source">{{ source }}</option>
      }
    </select>
  </div>

  <div class="filter-item">
    <label class="filter-label">Keyword</label>
    <input
      type="text"
      [value]="filters().keyword ?? ''"
      (input)="onKeywordInput($event)"
      placeholder="Search title, description..."
      class="filter-control"
    />
  </div>

  <div class="filter-item">
    <label class="filter-label">Location</label>
    <input
      type="text"
      [value]="filters().location ?? ''"
      (input)="onLocationInput($event)"
      placeholder="e.g. Remote, USA..."
      class="filter-control"
    />
  </div>

  <div class="filter-item">
    <label class="filter-label">Skills</label>
    <input
      type="text"
      [value]="filters().skills ?? ''"
      (input)="onSkillsInput($event)"
      placeholder="Python, React..."
      class="filter-control"
    />
  </div>

  <div class="filter-item">
    <label class="filter-label">Date From</label>
    <input
      type="date"
      [value]="filters().date_from ?? ''"
      (change)="onDateFromChange($event)"
      class="filter-control"
    />
  </div>

  <div class="filter-item">
    <label class="filter-label">Date To</label>
    <input
      type="date"
      [value]="filters().date_to ?? ''"
      (change)="onDateToChange($event)"
      class="filter-control"
    />
  </div>

  <div class="filter-item filter-item-clear">
    <button (click)="clearAll()" class="btn-clear">Clear all</button>
  </div>
</div>
```

- [ ] **Step 3: Create the styles**

Create `frontend/src/app/pages/ingestion/components/job-filters/job-filters.component.scss`:

```scss
.filters-bar {
  display: flex;
  align-items: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 130px;
  flex: 1;
}

.filter-item-clear {
  flex: 0;
  justify-content: flex-end;
}

.filter-label {
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  font-weight: 600;
}

.filter-control {
  padding: 0.375rem 0.625rem;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  font-size: 0.8125rem;
  background: var(--bg-card);
  color: var(--text-primary);
  width: 100%;
}

.btn-clear {
  padding: 0.375rem 0.875rem;
  background: none;
  border: none;
  color: var(--danger);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;

  &:hover {
    text-decoration: underline;
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pages/ingestion/components/job-filters/
git commit -m "feat(ingestion): create JobFiltersComponent"
```

---

## Task 11: Create JobDetailPanelComponent

**Files:**
- Create: `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.ts`
- Create: `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.html`
- Create: `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.scss`

- [ ] **Step 1: Create the component class**

Create `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.ts`:

```typescript
import { Component, input, output } from '@angular/core';
import { DatePipe } from '@angular/common';
import { NormalizedJob } from '../../models/normalized-job.model';

@Component({
  selector: 'app-job-detail-panel',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './job-detail-panel.component.html',
  styleUrl: './job-detail-panel.component.scss',
})
export class JobDetailPanelComponent {
  job = input.required<NormalizedJob>();
  tracked = input<boolean>(false);

  close = output<void>();
  track = output<string>();

  onOverlayClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('panel-overlay')) {
      this.close.emit();
    }
  }

  onTrack(): void {
    this.track.emit(this.job().id);
  }
}
```

- [ ] **Step 2: Create the template**

Create `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.html`:

```html
<div class="panel-overlay" (click)="onOverlayClick($event)">
  <div class="panel">
    <!-- Header -->
    <div class="panel-header">
      <div>
        <h2 class="panel-title">{{ job().title }}</h2>
        <p class="panel-company">{{ job().company }}</p>
      </div>
      <button (click)="close.emit()" class="btn-close">✕</button>
    </div>

    <!-- Meta grid -->
    <div class="panel-section meta-grid">
      <div class="meta-item">
        <span class="meta-label">Location</span>
        <span class="meta-value">{{ job().location || '—' }}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">Posted</span>
        <span class="meta-value">{{ job().posted_date ? (job().posted_date | date:'longDate') : '—' }}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">Salary Range</span>
        <span class="meta-value">{{ job().salary_range || '—' }}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">Department</span>
        <span class="meta-value">{{ job().department || '—' }}</span>
      </div>
    </div>

    <!-- Source -->
    <div class="panel-section">
      <span class="section-label">Source</span>
      <div class="source-badges">
        <span class="badge source-badge">{{ job().source }}</span>
        <span class="badge type-badge">{{ job().source_type }}</span>
        @if (job().platform) {
          <span class="badge platform-badge">{{ job().platform }}</span>
        }
      </div>
      @if (job().categories.length > 0) {
        <div class="category-tags">
          @for (cat of job().categories; track cat) {
            <span class="badge category-badge">{{ cat }}</span>
          }
        </div>
      }
    </div>

    <!-- Skills -->
    @if (job().skills.length > 0) {
      <div class="panel-section">
        <span class="section-label">Skills</span>
        <div class="skill-chips">
          @for (skill of job().skills; track skill) {
            <span class="skill-tag">{{ skill }}</span>
          }
        </div>
      </div>
    }

    <!-- Description -->
    <div class="panel-section">
      <span class="section-label">Description</span>
      <div class="description-text">{{ job().description }}</div>
    </div>

    <!-- Actions -->
    <div class="panel-actions">
      <a [href]="job().url" target="_blank" rel="noopener" class="btn-primary btn-action">
        View Original ↗
      </a>
      @if (tracked()) {
        <button class="btn-tracked btn-action" disabled>Tracked ✓</button>
      } @else {
        <button (click)="onTrack()" class="btn-secondary btn-action">Track</button>
      }
    </div>
  </div>
</div>
```

- [ ] **Step 3: Create the styles**

Create `frontend/src/app/pages/ingestion/components/job-detail-panel/job-detail-panel.component.scss`:

```scss
.panel-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 100;
  display: flex;
  justify-content: flex-end;
}

.panel {
  width: 460px;
  max-width: 90vw;
  background: var(--bg-card);
  border-left: 1px solid var(--border-default);
  box-shadow: var(--shadow-lg);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  animation: slideIn 0.2s var(--ease);
}

@keyframes slideIn {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border-subtle);
}

.panel-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.panel-company {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  font-weight: 500;
  margin: 0.25rem 0 0;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.25rem;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  line-height: 1;

  &:hover { color: var(--text-primary); }
}

.panel-section {
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-subtle);
}

.section-label {
  display: block;
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
  font-weight: 600;
}

.meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.meta-label {
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  font-weight: 600;
}

.meta-value {
  font-size: 0.8125rem;
  color: var(--text-primary);
}

.source-badges,
.category-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.category-tags {
  margin-top: 0.5rem;
}

.source-badge {
  background: var(--accent-bg, #e0f2f1);
  color: var(--accent);
}

.type-badge {
  background: var(--bg-inset);
  color: var(--text-secondary);
}

.platform-badge {
  background: #dbeafe;
  color: #1e40af;
}

.category-badge {
  background: #fef3c7;
  color: #92400e;
}

.skill-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.description-text {
  font-size: 0.875rem;
  line-height: 1.7;
  color: var(--text-secondary);
  white-space: pre-line;
  max-height: 300px;
  overflow-y: auto;
}

.panel-actions {
  padding: 1.25rem 1.5rem;
  display: flex;
  gap: 0.75rem;
  margin-top: auto;
}

.btn-action {
  flex: 1;
  text-align: center;
  padding: 0.625rem 1rem;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  font-weight: 500;
  text-decoration: none;
  display: inline-block;
}

.btn-tracked {
  background: var(--success-bg);
  color: var(--success);
  border: 1px solid #bbf7d0;
  cursor: default;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pages/ingestion/components/job-detail-panel/
git commit -m "feat(ingestion): create JobDetailPanelComponent"
```

---

## Task 12: Rewrite IngestionComponent with tabs

**Files:**
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.ts`
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.html`
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.scss`

- [ ] **Step 1: Rewrite the component class**

Replace `frontend/src/app/pages/ingestion/ingestion.component.ts` with:

```typescript
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { IngestionService, JobFilters } from '../../core/services/ingestion.service';
import { TrackingService } from '../../core/services/tracking.service';
import { CreateApplicationRequest } from '../../core/models/create-application-request.model';
import { NormalizedJob } from './models/normalized-job.model';
import { PortalEntry } from './models/portal-entry.model';
import { ScanPortalsRequest } from './models/scan-portals-request.model';
import { ScanError } from './models/scan-result.model';
import { PaginationComponent } from './components/pagination/pagination.component';
import { JobFiltersComponent } from './components/job-filters/job-filters.component';
import { JobDetailPanelComponent } from './components/job-detail-panel/job-detail-panel.component';
import { DatePipe } from '@angular/common';

@Component({
  selector: 'app-ingestion',
  standalone: true,
  imports: [PaginationComponent, JobFiltersComponent, JobDetailPanelComponent, DatePipe],
  templateUrl: './ingestion.component.html',
  styleUrl: './ingestion.component.scss',
})
export class IngestionComponent implements OnInit {
  private ingestionService = inject(IngestionService);
  private trackingService = inject(TrackingService);

  trackedJobIds = computed(() => this.ingestionService.trackedJobIds());

  // Tab state
  activeTab = signal<'boards' | 'portals'>('boards');

  // Jobs + pagination
  jobs = signal<NormalizedJob[]>([]);
  total = signal(0);
  page = signal(1);
  pageSize = signal(20);
  totalPages = signal(0);

  // Filters
  filters = signal<JobFilters>({});
  boardSources = signal<string[]>([
    'remotive', 'remoteok', 'jobicy', 'himalayas',
    'hn_hiring', 'weworkremotely', 'getonboard', 'linkedin',
  ]);
  portalSources = signal<string[]>([]);

  // Loading
  loading = signal(false);
  error = signal('');

  // Portal scan state
  portals = signal<PortalEntry[]>([]);
  availableCategories = signal<string[]>([]);
  selectedCategories = signal<string[]>([]);
  selectedCompanies = signal<string[]>([]);
  scanKeyword = signal('');
  scanning = signal(false);
  scanSummary = signal('');
  scanErrors = signal<ScanError[]>([]);
  showScanFilters = signal(false);

  // Detail panel
  selectedJob = signal<NormalizedJob | null>(null);

  ngOnInit(): void {
    this.loadPortals();
    this.loadJobs();
  }

  switchTab(tab: 'boards' | 'portals'): void {
    this.activeTab.set(tab);
    this.page.set(1);
    this.filters.set({});
    this.loadJobs();
  }

  loadJobs(): void {
    this.loading.set(true);
    this.error.set('');
    this.ingestionService
      .queryJobs(this.activeTab(), this.page(), this.pageSize(), this.filters())
      .subscribe({
        next: (res) => {
          this.jobs.set(res.jobs);
          this.total.set(res.total);
          this.totalPages.set(res.total_pages);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Failed to load jobs');
          this.loading.set(false);
        },
      });
  }

  fetchJobs(): void {
    this.loading.set(true);
    this.error.set('');
    this.ingestionService.fetchJobs().subscribe({
      next: () => {
        this.loadJobs();
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to fetch jobs');
        this.loading.set(false);
      },
    });
  }

  loadPortals(): void {
    this.ingestionService.loadPortals().subscribe({
      next: (portals) => {
        this.portals.set(portals);
        const allCategories = portals.flatMap((p) => p.categories);
        this.availableCategories.set([...new Set(allCategories)].sort());
        this.portalSources.set(portals.map((p) => p.name));
      },
      error: () => {},
    });
  }

  scanPortals(): void {
    this.scanning.set(true);
    this.scanSummary.set('');
    this.scanErrors.set([]);

    const body: ScanPortalsRequest = {};
    if (this.selectedCategories().length > 0) body.categories = this.selectedCategories();
    if (this.selectedCompanies().length > 0) body.companies = this.selectedCompanies();
    const kw = this.scanKeyword().trim();
    if (kw) body.keyword = kw;

    this.ingestionService.scanPortals(body).subscribe({
      next: (res) => {
        this.scanSummary.set(
          `Scan complete: ${res.total_fetched} fetched, ${res.new} new, ${res.duplicates} duplicates.`,
        );
        this.scanErrors.set(res.errors);
        this.scanning.set(false);
        this.loadJobs();
      },
      error: (err) => {
        this.scanSummary.set(err.error?.detail || 'Scan failed.');
        this.scanning.set(false);
      },
    });
  }

  onFiltersChange(newFilters: JobFilters): void {
    this.filters.set(newFilters);
    this.page.set(1);
    this.loadJobs();
  }

  onPageChange(newPage: number): void {
    this.page.set(newPage);
    this.loadJobs();
  }

  onPageSizeChange(newSize: number): void {
    this.pageSize.set(newSize);
    this.page.set(1);
    this.loadJobs();
  }

  openDetail(job: NormalizedJob): void {
    this.selectedJob.set(job);
  }

  closeDetail(): void {
    this.selectedJob.set(null);
  }

  toggleScanFilters(): void {
    this.showScanFilters.update((v) => !v);
  }

  onCategoryChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.selectedCategories.set(Array.from(select.selectedOptions).map((o) => o.value));
  }

  onCompanyChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.selectedCompanies.set(Array.from(select.selectedOptions).map((o) => o.value));
  }

  onScanKeywordInput(event: Event): void {
    this.scanKeyword.set((event.target as HTMLInputElement).value);
  }

  trackJob(jobId: string): void {
    const body: CreateApplicationRequest = { job_id: jobId };
    this.trackingService.create(body).subscribe({
      next: () => this.ingestionService.markTracked(jobId),
      error: (err) => {
        if (err.status === 409) this.ingestionService.markTracked(jobId);
      },
    });
  }

  isTracked(jobId: string): boolean {
    return this.trackedJobIds().has(jobId);
  }
}
```

- [ ] **Step 2: Rewrite the template**

Replace `frontend/src/app/pages/ingestion/ingestion.component.html` with:

```html
<div class="page">
  <!-- Tab bar -->
  <div class="tab-bar">
    <div class="tab-list">
      <button
        (click)="switchTab('boards')"
        class="tab-btn"
        [class.active]="activeTab() === 'boards'"
      >
        Job Boards
      </button>
      <button
        (click)="switchTab('portals')"
        class="tab-btn"
        [class.active]="activeTab() === 'portals'"
      >
        Company Portals
      </button>
    </div>
    <div class="tab-actions">
      @if (activeTab() === 'boards') {
        <button (click)="fetchJobs()" [disabled]="loading()" class="btn-primary">
          @if (loading()) { Fetching... } @else { Fetch Jobs }
        </button>
      } @else {
        <button (click)="scanPortals()" [disabled]="scanning()" class="btn-primary">
          @if (scanning()) { Scanning... } @else { Scan Portals }
        </button>
      }
    </div>
  </div>

  @if (error()) {
    <div class="alert alert-error">{{ error() }}</div>
  }

  <!-- Scan filters (portals tab only) -->
  @if (activeTab() === 'portals') {
    <div class="section">
      <div class="section-header">
        <h2>Scan Filters</h2>
        <button (click)="toggleScanFilters()" class="btn-secondary">
          @if (showScanFilters()) { Hide Scan Filters } @else { Show Scan Filters }
        </button>
      </div>

      @if (showScanFilters()) {
        <div class="scan-filter-panel">
          <div class="filter-group">
            <label for="category-select">Categories</label>
            <select id="category-select" multiple (change)="onCategoryChange($event)" class="filter-select">
              @for (cat of availableCategories(); track cat) {
                <option [value]="cat">{{ cat }}</option>
              }
            </select>
          </div>
          <div class="filter-group">
            <label for="company-select">Companies</label>
            <select id="company-select" multiple (change)="onCompanyChange($event)" class="filter-select">
              @for (portal of portals(); track portal.name) {
                <option [value]="portal.name">{{ portal.name }}</option>
              }
            </select>
          </div>
          <div class="filter-group">
            <label for="scan-keyword-input">Keyword</label>
            <input
              id="scan-keyword-input"
              type="text"
              [value]="scanKeyword()"
              (input)="onScanKeywordInput($event)"
              placeholder="e.g. React, Python, remote..."
              class="filter-input"
            />
          </div>
        </div>
      }

      @if (scanSummary()) {
        <div class="alert alert-info">{{ scanSummary() }}</div>
      }

      @if (scanErrors().length > 0) {
        <details class="scan-errors">
          <summary>{{ scanErrors().length }} portal error(s)</summary>
          <ul>
            @for (err of scanErrors(); track err.portal) {
              <li><strong>{{ err.portal }}</strong> ({{ err.platform }}): {{ err.error }}</li>
            }
          </ul>
        </details>
      }
    </div>
  }

  <!-- Table filters -->
  <app-job-filters
    [sources]="activeTab() === 'boards' ? boardSources() : portalSources()"
    [filters]="filters()"
    (filtersChange)="onFiltersChange($event)"
  />

  <!-- Loading -->
  @if (loading() || scanning()) {
    <div class="loading-card">
      <div class="spinner"></div>
      <div class="loading-text">
        <h3>{{ scanning() ? 'Scanning portals...' : 'Loading jobs...' }}</h3>
        <p>Pulling from configured sources. This may take a moment.</p>
      </div>
    </div>
  }

  <!-- Jobs table -->
  @if (jobs().length > 0) {
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Company</th>
            <th>Location</th>
            <th>Source</th>
            <th>Posted</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          @for (job of jobs(); track job.id) {
            <tr (click)="openDetail(job)" class="clickable-row">
              <td class="title">{{ job.title }}</td>
              <td>{{ job.company }}</td>
              <td>{{ job.location }}</td>
              <td><span class="badge source-badge-{{ job.source }}">{{ job.source }}</span></td>
              <td class="date-cell">{{ job.posted_date ? (job.posted_date | date:'mediumDate') : '—' }}</td>
              <td class="actions-cell">
                <a [href]="job.url" target="_blank" class="link" (click)="$event.stopPropagation()">View</a>
                @if (isTracked(job.id)) {
                  <button class="btn-tracked" disabled (click)="$event.stopPropagation()">Tracked</button>
                } @else {
                  <button (click)="trackJob(job.id); $event.stopPropagation()" class="btn-track">Track</button>
                }
              </td>
            </tr>
          }
        </tbody>
      </table>

      <app-pagination
        [page]="page()"
        [pageSize]="pageSize()"
        [total]="total()"
        [totalPages]="totalPages()"
        (pageChange)="onPageChange($event)"
        (pageSizeChange)="onPageSizeChange($event)"
      />
    </div>
  } @else if (!loading() && !scanning()) {
    <div class="empty-state">
      @if (activeTab() === 'boards') {
        <p>No jobs loaded yet. Click "Fetch Jobs" to pull from job boards.</p>
      } @else {
        <p>No portal jobs loaded yet. Click "Scan Portals" to pull from company career pages.</p>
      }
    </div>
  }

  <!-- Detail panel -->
  @if (selectedJob()) {
    <app-job-detail-panel
      [job]="selectedJob()!"
      [tracked]="isTracked(selectedJob()!.id)"
      (close)="closeDetail()"
      (track)="trackJob($event)"
    />
  }
</div>
```

- [ ] **Step 3: Update the styles**

Replace `frontend/src/app/pages/ingestion/ingestion.component.scss` with:

```scss
/* --- Tabs --- */
.tab-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 2px solid var(--border-subtle);
  margin-bottom: 1.25rem;
}

.tab-list {
  display: flex;
}

.tab-btn {
  padding: 0.75rem 1.5rem;
  background: none;
  border: none;
  font-size: 0.9375rem;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  border-bottom: 3px solid transparent;
  margin-bottom: -2px;
  transition: color var(--duration) var(--ease), border-color var(--duration) var(--ease);

  &:hover { color: var(--text-primary); }

  &.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }
}

.tab-actions {
  padding: 0.5rem 0;
}

/* --- Scan filters (portal tab) --- */
.section {
  margin-bottom: 1.25rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;

  h2 {
    font-size: 1rem;
    color: var(--text-primary);
  }
}

.scan-filter-panel {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1rem;
  padding: 1.25rem;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  margin-bottom: 1rem;

  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;

  label {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--text-secondary);
  }
}

.filter-select { min-height: 5rem; }
.filter-input { width: 100%; }

.scan-errors {
  margin-top: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--danger-bg);
  border-radius: var(--radius-md);
  font-size: 0.8125rem;
  border-left: 3px solid var(--danger);

  summary { cursor: pointer; font-weight: 500; color: var(--danger); }
  ul { margin-top: 0.5rem; padding-left: 1.25rem; color: var(--text-secondary); }
}

/* --- Loading --- */
.loading-card {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  padding: 2rem 2.5rem;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  margin-bottom: 1rem;
  animation: pulseCard 2s ease-in-out infinite;

  h3 { font-size: 1rem; color: var(--text-primary); margin-bottom: 0.25rem; }
  p { font-size: 0.8125rem; color: var(--text-muted); }
}

@keyframes pulseCard {
  0%, 100% { border-color: var(--border-subtle); }
  50% { border-color: var(--accent); }
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-default);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* --- Table --- */
.table-container { overflow-x: auto; }

table {
  min-width: 900px;
  th, td { padding: 0.625rem 0.75rem; font-size: 0.8125rem; white-space: nowrap; }
  th { font-size: 0.6875rem; }
}

.clickable-row {
  cursor: pointer;
  &:hover { background: var(--bg-inset); }
}

.title {
  font-weight: 500;
  color: var(--text-primary);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.date-cell {
  color: var(--text-secondary);
}

.actions-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  white-space: nowrap;
}

.btn-track {
  padding: 0.2rem 0.6rem;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 0.6875rem;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--duration) var(--ease);
  &:hover { background: var(--accent-hover); }
}

.btn-tracked {
  padding: 0.2rem 0.6rem;
  background: var(--success-bg);
  color: var(--success);
  border: 1px solid #bbf7d0;
  border-radius: var(--radius-sm);
  font-size: 0.6875rem;
  font-weight: 500;
  cursor: default;
}

/* --- Source badge colors --- */
.source-badge-remotive { background: #e0f2f1; color: #0d9488; }
.source-badge-getonboard { background: #fef3c7; color: #92400e; }
.source-badge-linkedin { background: #ede9fe; color: #5b21b6; }
.source-badge-himalayas { background: #fce7f3; color: #9d174d; }
.source-badge-remoteok { background: #dbeafe; color: #1e40af; }
.source-badge-jobicy { background: #dcfce7; color: #166534; }
.source-badge-weworkremotely { background: #ffedd5; color: #9a3412; }
.source-badge-hn_hiring { background: #fee2e2; color: #991b1b; }
.source-badge-greenhouse { background: #d1fae5; color: #065f46; }
.source-badge-lever { background: #e0e7ff; color: #3730a3; }
.source-badge-ashby { background: #cffafe; color: #155e75; }
.source-badge-csv { background: #f3f4f6; color: #374151; }
```

- [ ] **Step 4: Verify the app compiles**

Run: `cd frontend && npx ng build --configuration development 2>&1 | head -30`
Expected: Successful compilation with no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/ingestion/ingestion.component.ts frontend/src/app/pages/ingestion/ingestion.component.html frontend/src/app/pages/ingestion/ingestion.component.scss
git commit -m "feat(ingestion): rewrite ingestion page with tabs, filters, pagination, and detail panel"
```

---

## Task 13: End-to-end verification

**Files:** None (testing only)

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && uv run pytest tests/unit/ingestion/ -v`
Expected: ALL PASS

- [ ] **Step 2: Start the backend server**

Run: `cd backend && uv run uvicorn hiresense.main:app --reload --port 8000`

- [ ] **Step 3: Test the new endpoint manually**

```bash
# Test boards tab
curl "http://localhost:8000/ingestion/jobs?tab=boards&page=1&page_size=20"

# Test portals tab
curl "http://localhost:8000/ingestion/jobs?tab=portals&page=1&page_size=20"

# Test with filters
curl "http://localhost:8000/ingestion/jobs?tab=boards&page=1&page_size=20&keyword=engineer&location=remote"
```

- [ ] **Step 4: Start the frontend dev server**

Run: `cd frontend && npx ng serve`

- [ ] **Step 5: Test in browser**

Navigate to `http://localhost:4200/dashboard/ingestion` and verify:
1. Two tabs appear (Job Boards / Company Portals)
2. "Fetch Jobs" button works on Job Boards tab
3. "Scan Portals" button works on Company Portals tab
4. Filters bar appears and filters trigger API calls
5. Pagination works (page navigation, page size change)
6. Clicking a job row opens the detail panel
7. Detail panel shows all job info (source, platform, skills, description)
8. "View Original" opens the job URL
9. "Track" button works
10. Switching tabs resets filters and pagination

- [ ] **Step 6: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix(ingestion): polish ingestion page after end-to-end testing"
```
