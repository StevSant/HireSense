# Company Deep Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LLM-powered company research with DB caching, triggered inline from the Pipeline page, producing structured analysis of funding, tech stack, culture, growth, pros/cons, and red flags.

**Architecture:** New `research/` bounded context following the interview module's pattern — ORM model, sync SQLAlchemy repository, async service with LLM integration, FastAPI routes with auth. Third Alembic migration creates the `company_research` table. Frontend adds inline research button + collapsible detail panel on the Pipeline page.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, Angular 21, pytest-asyncio

---

## File Map

### New Files

| File | Responsibility |
|---|---|
| `backend/src/hiresense/research/__init__.py` | Package marker |
| `backend/src/hiresense/research/domain/__init__.py` | Package marker |
| `backend/src/hiresense/research/domain/models.py` | CompanyResearch ORM model |
| `backend/src/hiresense/research/domain/services.py` | CompanyResearchService |
| `backend/src/hiresense/research/infrastructure/__init__.py` | Package marker |
| `backend/src/hiresense/research/infrastructure/repository.py` | CompanyResearchRepository |
| `backend/src/hiresense/research/api/__init__.py` | Package marker |
| `backend/src/hiresense/research/api/schemas.py` | Request/response Pydantic models |
| `backend/src/hiresense/research/api/routes.py` | REST endpoints |
| `backend/src/hiresense/research/api/dependencies.py` | DI stubs |
| `backend/alembic/versions/003_create_company_research.py` | Third migration |
| `backend/tests/unit/research/__init__.py` | Package marker |
| `backend/tests/unit/research/test_models.py` | ORM model tests |
| `backend/tests/unit/research/test_repository.py` | Repository tests |
| `backend/tests/unit/research/test_services.py` | Service tests |
| `backend/tests/unit/research/test_routes.py` | Route tests |
| `frontend/src/app/core/models/company-research.model.ts` | TS interface |

### Modified Files

| File | Change |
|---|---|
| `backend/src/hiresense/infrastructure/registry.py` | Register CompanyResearch model |
| `backend/src/hiresense/main.py` | Wire research module |
| `frontend/src/app/pages/tracking/tracking.component.ts` | Add research state + methods |
| `frontend/src/app/pages/tracking/tracking.component.html` | Add button + detail panel |

---

## Task 1: CompanyResearch ORM model and migration

**Files:**
- Create: `backend/src/hiresense/research/__init__.py`, `domain/__init__.py`
- Create: `backend/src/hiresense/research/domain/models.py`
- Create: `backend/alembic/versions/003_create_company_research.py`
- Modify: `backend/src/hiresense/infrastructure/registry.py`
- Create: `backend/tests/unit/research/__init__.py`
- Create: `backend/tests/unit/research/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/research/__init__.py` (empty).

Create `backend/tests/unit/research/test_models.py`:

```python
from hiresense.research.domain.models import CompanyResearch


def test_company_research_creation() -> None:
    research = CompanyResearch(
        company_name="anthropic",
        funding_stage="Series D",
        tech_stack="Python, Rust, distributed systems",
        culture_summary="Research-driven AI safety culture",
        growth_trajectory="Rapid growth with enterprise partnerships",
        red_flags=None,
        pros="Cutting-edge AI work, strong mission",
        cons="High intensity environment",
        raw_llm_response='{"funding_stage": "Series D"}',
    )
    assert research.company_name == "anthropic"
    assert research.funding_stage == "Series D"
    assert research.red_flags is None
    assert research.raw_llm_response is not None


def test_company_research_all_fields() -> None:
    research = CompanyResearch(
        company_name="startup",
        funding_stage="Seed",
        tech_stack="Node.js, React",
        culture_summary="Fast-paced startup",
        growth_trajectory="Early stage",
        red_flags="High burn rate, small team",
        pros="Equity upside",
        cons="Unstable",
        raw_llm_response="{}",
    )
    assert research.red_flags == "High burn rate, small team"
    assert research.cons == "Unstable"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create empty `backend/src/hiresense/research/__init__.py`.
Create empty `backend/src/hiresense/research/domain/__init__.py`.

Create `backend/src/hiresense/research/domain/models.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class CompanyResearch(Base):
    __tablename__ = "company_research"
    __table_args__ = (
        Index("ix_company_research_company_name", "company_name", unique=True),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    funding_stage: Mapped[str] = mapped_column(String(100), nullable=False)
    tech_stack: Mapped[str] = mapped_column(Text, nullable=False)
    culture_summary: Mapped[str] = mapped_column(Text, nullable=False)
    growth_trajectory: Mapped[str] = mapped_column(Text, nullable=False)
    red_flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    pros: Mapped[str] = mapped_column(Text, nullable=False)
    cons: Mapped[str] = mapped_column(Text, nullable=False)
    raw_llm_response: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

Register in `backend/src/hiresense/infrastructure/registry.py` — add:
```python
from hiresense.research.domain.models import CompanyResearch  # noqa: F401
```

Create `backend/alembic/versions/003_create_company_research.py`:

```python
"""create company_research table

Revision ID: 003
Revises: 002
Create Date: 2026-04-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_research",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("funding_stage", sa.String(100), nullable=False),
        sa.Column("tech_stack", sa.Text(), nullable=False),
        sa.Column("culture_summary", sa.Text(), nullable=False),
        sa.Column("growth_trajectory", sa.Text(), nullable=False),
        sa.Column("red_flags", sa.Text(), nullable=True),
        sa.Column("pros", sa.Text(), nullable=False),
        sa.Column("cons", sa.Text(), nullable=False),
        sa.Column("raw_llm_response", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_company_research_company_name", "company_research", ["company_name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_company_research_company_name")
    op.drop_table("company_research")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_models.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/research/ backend/src/hiresense/infrastructure/registry.py backend/alembic/versions/003_create_company_research.py backend/tests/unit/research/
git commit -m "feat(research): add CompanyResearch ORM model and Alembic migration"
```

---

## Task 2: CompanyResearchRepository

**Files:**
- Create: `backend/src/hiresense/research/infrastructure/__init__.py`
- Create: `backend/src/hiresense/research/infrastructure/repository.py`
- Create: `backend/tests/unit/research/test_repository.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/research/test_repository.py`:

```python
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.infrastructure.database import Base
from hiresense.research.domain.models import CompanyResearch
from hiresense.research.infrastructure.repository import CompanyResearchRepository


@pytest.fixture
def sync_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    Base.metadata.drop_all(engine)


@pytest.fixture
def repo(sync_session_factory):
    return CompanyResearchRepository(session_factory=sync_session_factory)


def _make_research(**kwargs) -> CompanyResearch:
    defaults = dict(
        company_name="anthropic",
        funding_stage="Series D",
        tech_stack="Python, Rust",
        culture_summary="AI safety focused",
        growth_trajectory="Rapid growth",
        red_flags=None,
        pros="Great mission",
        cons="High intensity",
        raw_llm_response="{}",
    )
    defaults.update(kwargs)
    return CompanyResearch(**defaults)


def test_create_and_get_by_company_name(repo) -> None:
    research = _make_research()
    created = repo.create(research)
    assert created.id is not None
    found = repo.get_by_company_name("anthropic")
    assert found is not None
    assert found.company_name == "anthropic"
    assert found.funding_stage == "Series D"


def test_get_by_company_name_not_found(repo) -> None:
    result = repo.get_by_company_name("nonexistent")
    assert result is None


def test_get_by_company_name_case_insensitive(repo) -> None:
    repo.create(_make_research(company_name="Anthropic"))
    found = repo.get_by_company_name("anthropic")
    assert found is not None
    assert found.company_name == "Anthropic"


def test_save_updates_existing(repo) -> None:
    research = _make_research()
    created = repo.create(research)
    created.funding_stage = "Series E"
    updated = repo.save(created)
    assert updated.funding_stage == "Series E"
    found = repo.get_by_company_name("anthropic")
    assert found.funding_stage == "Series E"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_repository.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create empty `backend/src/hiresense/research/infrastructure/__init__.py`.

Create `backend/src/hiresense/research/infrastructure/repository.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import select, func

from hiresense.research.domain.models import CompanyResearch


class CompanyResearchRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def get_by_company_name(self, company_name: str) -> CompanyResearch | None:
        with self._session_factory() as session:
            stmt = select(CompanyResearch).where(
                func.lower(CompanyResearch.company_name) == company_name.lower().strip()
            )
            return session.scalars(stmt).first()

    def create(self, research: CompanyResearch) -> CompanyResearch:
        with self._session_factory() as session:
            session.add(research)
            session.commit()
            session.refresh(research)
            return research

    def save(self, research: CompanyResearch) -> CompanyResearch:
        with self._session_factory() as session:
            research = session.merge(research)
            session.commit()
            session.refresh(research)
            return research
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_repository.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/research/infrastructure/ backend/tests/unit/research/test_repository.py
git commit -m "feat(research): add CompanyResearchRepository"
```

---

## Task 3: CompanyResearchService

**Files:**
- Create: `backend/src/hiresense/research/domain/services.py`
- Create: `backend/tests/unit/research/test_services.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/research/test_services.py`:

```python
from __future__ import annotations

import json

import pytest

from hiresense.research.domain.models import CompanyResearch
from hiresense.research.domain.services import CompanyResearchService


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_prompt: str = ""

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.last_prompt = prompt
        return self._response


class FakeRepo:
    def __init__(self) -> None:
        self._store: dict[str, CompanyResearch] = {}

    def get_by_company_name(self, company_name: str) -> CompanyResearch | None:
        return self._store.get(company_name.lower().strip())

    def create(self, research: CompanyResearch) -> CompanyResearch:
        self._store[research.company_name.lower().strip()] = research
        return research

    def save(self, research: CompanyResearch) -> CompanyResearch:
        self._store[research.company_name.lower().strip()] = research
        return research


def _llm_response() -> str:
    return json.dumps({
        "funding_stage": "Series D",
        "tech_stack": "Python, Rust",
        "culture_summary": "AI safety focused",
        "growth_trajectory": "Rapid growth",
        "red_flags": None,
        "pros": "Great mission",
        "cons": "High intensity",
    })


@pytest.mark.asyncio
async def test_research_calls_llm_and_persists() -> None:
    llm = FakeLLM(_llm_response())
    repo = FakeRepo()
    service = CompanyResearchService(llm=llm, repository=repo)
    result = await service.research("Anthropic")
    assert result.company_name == "anthropic"
    assert result.funding_stage == "Series D"
    assert result.tech_stack == "Python, Rust"
    assert "Anthropic" in llm.last_prompt
    assert repo.get_by_company_name("anthropic") is not None


@pytest.mark.asyncio
async def test_research_returns_cached() -> None:
    llm = FakeLLM(_llm_response())
    repo = FakeRepo()
    service = CompanyResearchService(llm=llm, repository=repo)
    first = await service.research("Anthropic")
    llm.last_prompt = ""
    second = await service.research("Anthropic")
    assert second.funding_stage == first.funding_stage
    assert llm.last_prompt == ""


@pytest.mark.asyncio
async def test_research_includes_job_description_in_prompt() -> None:
    llm = FakeLLM(_llm_response())
    repo = FakeRepo()
    service = CompanyResearchService(llm=llm, repository=repo)
    await service.research("Anthropic", job_description="Build AI safety systems")
    assert "Build AI safety systems" in llm.last_prompt


@pytest.mark.asyncio
async def test_refresh_overwrites_cached() -> None:
    llm = FakeLLM(_llm_response())
    repo = FakeRepo()
    service = CompanyResearchService(llm=llm, repository=repo)
    await service.research("Anthropic")
    new_response = json.dumps({
        "funding_stage": "Series E",
        "tech_stack": "Python, Rust, Go",
        "culture_summary": "Updated culture",
        "growth_trajectory": "Still growing",
        "red_flags": None,
        "pros": "Even better",
        "cons": "Still intense",
    })
    llm._response = new_response
    refreshed = await service.refresh("Anthropic")
    assert refreshed.funding_stage == "Series E"


@pytest.mark.asyncio
async def test_research_no_llm_returns_fallback_not_persisted() -> None:
    repo = FakeRepo()
    service = CompanyResearchService(llm=None, repository=repo)
    result = await service.research("Anthropic")
    assert "not configured" in result.funding_stage.lower()
    assert repo.get_by_company_name("anthropic") is None


@pytest.mark.asyncio
async def test_research_llm_failure_returns_fallback_not_persisted() -> None:
    class FailingLLM:
        async def complete(self, prompt, *, system="", model=""):
            raise RuntimeError("API timeout")

    repo = FakeRepo()
    service = CompanyResearchService(llm=FailingLLM(), repository=repo)
    result = await service.research("Anthropic")
    assert "unavailable" in result.funding_stage.lower()
    assert repo.get_by_company_name("anthropic") is None


@pytest.mark.asyncio
async def test_get_returns_cached() -> None:
    llm = FakeLLM(_llm_response())
    repo = FakeRepo()
    service = CompanyResearchService(llm=llm, repository=repo)
    await service.research("Anthropic")
    result = service.get("Anthropic")
    assert result is not None
    assert result.funding_stage == "Series D"


@pytest.mark.asyncio
async def test_get_returns_none_when_not_cached() -> None:
    repo = FakeRepo()
    service = CompanyResearchService(llm=None, repository=repo)
    result = service.get("Anthropic")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_services.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/hiresense/research/domain/services.py`:

```python
from __future__ import annotations

import json
import logging
import re
from typing import Any

from hiresense.research.domain.models import CompanyResearch

logger = logging.getLogger(__name__)

_FALLBACK_TEXT_NO_LLM = "LLM not configured"
_FALLBACK_TEXT_FAILURE = "Research unavailable"


class CompanyResearchService:
    def __init__(self, llm: Any, repository: Any) -> None:
        self._llm = llm
        self._repo = repository

    async def research(self, company_name: str, job_description: str = "") -> CompanyResearch:
        normalized = company_name.lower().strip()
        cached = self._repo.get_by_company_name(normalized)
        if cached is not None:
            return cached
        return await self._do_research(normalized, job_description)

    async def refresh(self, company_name: str, job_description: str = "") -> CompanyResearch:
        normalized = company_name.lower().strip()
        return await self._do_research(normalized, job_description)

    def get(self, company_name: str) -> CompanyResearch | None:
        return self._repo.get_by_company_name(company_name.lower().strip())

    async def _do_research(self, company_name: str, job_description: str) -> CompanyResearch:
        if self._llm is None:
            return self._make_fallback(company_name, _FALLBACK_TEXT_NO_LLM)

        try:
            prompt = self._build_prompt(company_name, job_description)
            response = await self._llm.complete(
                prompt, system="You are a company research analyst. Return only valid JSON."
            )
            data = self._parse_response(response)
            research = CompanyResearch(
                company_name=company_name,
                funding_stage=data.get("funding_stage", "Unknown"),
                tech_stack=data.get("tech_stack", "Unknown"),
                culture_summary=data.get("culture_summary", "Unknown"),
                growth_trajectory=data.get("growth_trajectory", "Unknown"),
                red_flags=data.get("red_flags"),
                pros=data.get("pros", "Unknown"),
                cons=data.get("cons", "Unknown"),
                raw_llm_response=response,
            )
            existing = self._repo.get_by_company_name(company_name)
            if existing is not None:
                existing.funding_stage = research.funding_stage
                existing.tech_stack = research.tech_stack
                existing.culture_summary = research.culture_summary
                existing.growth_trajectory = research.growth_trajectory
                existing.red_flags = research.red_flags
                existing.pros = research.pros
                existing.cons = research.cons
                existing.raw_llm_response = research.raw_llm_response
                return self._repo.save(existing)
            return self._repo.create(research)
        except Exception as exc:
            logger.warning("Company research failed for %s: %s", company_name, exc)
            return self._make_fallback(company_name, _FALLBACK_TEXT_FAILURE)

    def _build_prompt(self, company_name: str, job_description: str) -> str:
        desc_section = ""
        if job_description:
            desc_section = f"\nJob Description (for additional context):\n{job_description[:2000]}\n"

        return (
            f"Research the company \"{company_name}\" for a job seeker.\n"
            f"{desc_section}\n"
            "Return JSON with these fields:\n"
            '- "funding_stage": string (e.g. "Series B", "Public", "Bootstrapped", "Unknown")\n'
            '- "tech_stack": string (known technologies, languages, frameworks)\n'
            '- "culture_summary": string (2-3 sentences about work culture)\n'
            '- "growth_trajectory": string (2-3 sentences about company growth)\n'
            '- "red_flags": string or null (any concerns a candidate should know)\n'
            '- "pros": string (positive aspects for a candidate)\n'
            '- "cons": string (negative aspects or challenges)\n\n'
            "Return valid JSON only."
        )

    def _parse_response(self, response: str) -> dict:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        md_match = re.search(r"```(?:json)?\s*\n?({.*?})\s*\n?```", response, re.DOTALL)
        if md_match:
            try:
                return json.loads(md_match.group(1))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not parse LLM response: {response[:200]}")

    @staticmethod
    def _make_fallback(company_name: str, text: str) -> CompanyResearch:
        return CompanyResearch(
            company_name=company_name,
            funding_stage=text,
            tech_stack=text,
            culture_summary=text,
            growth_trajectory=text,
            red_flags=None,
            pros=text,
            cons=text,
            raw_llm_response="",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_services.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/research/domain/services.py backend/tests/unit/research/test_services.py
git commit -m "feat(research): add CompanyResearchService with LLM integration and caching"
```

---

## Task 4: API schemas, dependencies, and routes

**Files:**
- Create: `backend/src/hiresense/research/api/__init__.py`
- Create: `backend/src/hiresense/research/api/schemas.py`
- Create: `backend/src/hiresense/research/api/dependencies.py`
- Create: `backend/src/hiresense/research/api/routes.py`
- Create: `backend/tests/unit/research/test_routes.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/research/test_routes.py`:

```python
from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.research.api.dependencies import get_company_research_service
from hiresense.research.api.routes import router
from hiresense.research.domain.models import CompanyResearch


class FakeService:
    def __init__(self) -> None:
        self._cache: dict[str, CompanyResearch] = {}

    async def research(self, company_name, job_description=""):
        key = company_name.lower().strip()
        if key not in self._cache:
            self._cache[key] = CompanyResearch(
                id=uuid.uuid4(),
                company_name=key,
                funding_stage="Series D",
                tech_stack="Python, Rust",
                culture_summary="AI safety focused",
                growth_trajectory="Rapid growth",
                red_flags=None,
                pros="Great mission",
                cons="High intensity",
                raw_llm_response="{}",
            )
        return self._cache[key]

    async def refresh(self, company_name, job_description=""):
        key = company_name.lower().strip()
        self._cache[key] = CompanyResearch(
            id=uuid.uuid4(),
            company_name=key,
            funding_stage="Series E",
            tech_stack="Python, Rust, Go",
            culture_summary="Updated",
            growth_trajectory="Still growing",
            red_flags=None,
            pros="Even better",
            cons="Still intense",
            raw_llm_response="{}",
        )
        return self._cache[key]

    def get(self, company_name):
        return self._cache.get(company_name.lower().strip())


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_company_research_service] = lambda: FakeService()
    return app


def test_research_company() -> None:
    client = TestClient(_make_app())
    response = client.post("/research", json={"company_name": "Anthropic"})
    assert response.status_code == 200
    data = response.json()
    assert data["company_name"] == "anthropic"
    assert data["funding_stage"] == "Series D"


def test_research_with_job_description() -> None:
    client = TestClient(_make_app())
    response = client.post("/research", json={
        "company_name": "Anthropic",
        "job_description": "Build AI safety systems",
    })
    assert response.status_code == 200
    assert response.json()["funding_stage"] == "Series D"


def test_refresh_company() -> None:
    app = _make_app()
    client = TestClient(app)
    client.post("/research", json={"company_name": "Anthropic"})
    response = client.post("/research/refresh", json={"company_name": "Anthropic"})
    assert response.status_code == 200
    data = response.json()
    assert data["funding_stage"] == "Series E"


def test_get_cached_research() -> None:
    app = _make_app()
    svc = FakeService()
    app.dependency_overrides[get_company_research_service] = lambda: svc
    client = TestClient(app)
    client.post("/research", json={"company_name": "Anthropic"})
    response = client.get("/research/anthropic")
    assert response.status_code == 200
    assert response.json()["company_name"] == "anthropic"


def test_get_cached_not_found() -> None:
    client = TestClient(_make_app())
    response = client.get("/research/nonexistent")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_routes.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create empty `backend/src/hiresense/research/api/__init__.py`.

Create `backend/src/hiresense/research/api/schemas.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ResearchRequest(BaseModel):
    company_name: str
    job_description: str = ""


class CompanyResearchResponse(BaseModel):
    id: uuid.UUID
    company_name: str
    funding_stage: str
    tech_stack: str
    culture_summary: str
    growth_trajectory: str
    red_flags: str | None
    pros: str
    cons: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
```

Create `backend/src/hiresense/research/api/dependencies.py`:

```python
from __future__ import annotations


def get_company_research_service():
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")
```

Create `backend/src/hiresense/research/api/routes.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from hiresense.identity.api.dependencies import require_auth
from hiresense.research.api.dependencies import get_company_research_service
from hiresense.research.api.schemas import CompanyResearchResponse, ResearchRequest
from hiresense.research.domain.services import CompanyResearchService

router = APIRouter(prefix="/research", tags=["research"], dependencies=[Depends(require_auth)])


@router.post("", response_model=CompanyResearchResponse)
async def research_company(
    request: ResearchRequest,
    service: CompanyResearchService = Depends(get_company_research_service),
) -> CompanyResearchResponse:
    result = await service.research(
        company_name=request.company_name,
        job_description=request.job_description,
    )
    return CompanyResearchResponse.model_validate(result)


@router.post("/refresh", response_model=CompanyResearchResponse)
async def refresh_research(
    request: ResearchRequest,
    service: CompanyResearchService = Depends(get_company_research_service),
) -> CompanyResearchResponse:
    result = await service.refresh(
        company_name=request.company_name,
        job_description=request.job_description,
    )
    return CompanyResearchResponse.model_validate(result)


@router.get("/{company_name}", response_model=CompanyResearchResponse)
def get_research(
    company_name: str,
    service: CompanyResearchService = Depends(get_company_research_service),
) -> CompanyResearchResponse:
    result = service.get(company_name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No research found for {company_name}")
    return CompanyResearchResponse.model_validate(result)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_routes.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Run all tests for regressions**

Run: `cd backend && uv run python -m pytest tests/ -q`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/research/api/ backend/tests/unit/research/test_routes.py
git commit -m "feat(research): add REST API routes for company research"
```

---

## Task 5: Wire into app factory

**Files:**
- Modify: `backend/src/hiresense/main.py`

- [ ] **Step 1: Add imports**

Add to `backend/src/hiresense/main.py` imports:

```python
from hiresense.research.infrastructure.repository import CompanyResearchRepository
from hiresense.research.domain.services import CompanyResearchService
from hiresense.research.api.dependencies import get_company_research_service
from hiresense.research.api.routes import router as research_router
```

- [ ] **Step 2: Wire research module**

After the interview module section (after `app.include_router(interview_router)`), add:

```python
    # --- Research module ---
    research_repo = CompanyResearchRepository(session_factory=sync_session_factory)
    research_service = CompanyResearchService(llm=llm, repository=research_repo)
    app.dependency_overrides[get_company_research_service] = lambda: research_service
    app.include_router(research_router)
```

- [ ] **Step 3: Run all tests**

Run: `cd backend && uv run python -m pytest tests/ -q`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/main.py
git commit -m "feat(app): wire company research module"
```

---

## Task 6: Frontend model and Pipeline page integration

**Files:**
- Create: `frontend/src/app/core/models/company-research.model.ts`
- Modify: `frontend/src/app/pages/tracking/tracking.component.ts`
- Modify: `frontend/src/app/pages/tracking/tracking.component.html`

- [ ] **Step 1: Create TypeScript model**

Create `frontend/src/app/core/models/company-research.model.ts`:

```typescript
export interface CompanyResearch {
  id: string;
  company_name: string;
  funding_stage: string;
  tech_stack: string;
  culture_summary: string;
  growth_trajectory: string;
  red_flags: string | null;
  pros: string;
  cons: string;
  created_at: string | null;
  updated_at: string | null;
}
```

- [ ] **Step 2: Add research state and methods to tracking component**

In `frontend/src/app/pages/tracking/tracking.component.ts`, add import:

```typescript
import { CompanyResearch } from '../../core/models/company-research.model';
```

Add signals after existing signals:

```typescript
  researchCache = signal<Record<string, CompanyResearch>>({});
  researchingCompany = signal<string | null>(null);
  expandedResearchId = signal<string | null>(null);
```

Add methods:

```typescript
  researchCompany(app: TrackedApplication): void {
    this.researchingCompany.set(app.id);
    this.http
      .post<CompanyResearch>(`${environment.apiUrl}/research`, {
        company_name: app.company,
        job_description: app.notes || '',
      })
      .subscribe({
        next: (res) => {
          this.researchCache.update((cache) => ({ ...cache, [app.id]: res }));
          this.researchingCompany.set(null);
          this.expandedResearchId.set(app.id);
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Research failed');
          this.researchingCompany.set(null);
        },
      });
  }

  refreshResearch(app: TrackedApplication): void {
    this.researchingCompany.set(app.id);
    this.http
      .post<CompanyResearch>(`${environment.apiUrl}/research/refresh`, {
        company_name: app.company,
        job_description: app.notes || '',
      })
      .subscribe({
        next: (res) => {
          this.researchCache.update((cache) => ({ ...cache, [app.id]: res }));
          this.researchingCompany.set(null);
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Research refresh failed');
          this.researchingCompany.set(null);
        },
      });
  }

  toggleResearch(appId: string): void {
    this.expandedResearchId.update((current) => (current === appId ? null : appId));
  }

  hasResearch(appId: string): boolean {
    return appId in this.researchCache();
  }
```

- [ ] **Step 3: Add research UI to tracking template**

In the tracking template, find the Actions `<td>` that contains the Delete button. Add a Research button before it:

```html
                <td>
                  <button
                    (click)="researchCompany(app); $event.stopPropagation()"
                    [disabled]="researchingCompany() === app.id"
                    class="btn-secondary btn-sm"
                  >
                    @if (researchingCompany() === app.id) { Researching... } @else if (hasResearch(app.id)) { View Research } @else { Research }
                  </button>
                  <button (click)="deleteApplication(app.id)" class="btn-danger btn-sm">Delete</button>
                </td>
```

After the closing `</tr>` of each application row, add the collapsible research panel:

```html
              @if (expandedResearchId() === app.id && researchCache()[app.id]) {
                <tr class="research-row">
                  <td colspan="6">
                    <div class="research-panel">
                      <div class="research-grid">
                        <div class="research-item">
                          <span class="research-label">Funding Stage</span>
                          <span class="research-badge">{{ researchCache()[app.id].funding_stage }}</span>
                        </div>
                        <div class="research-item">
                          <span class="research-label">Tech Stack</span>
                          <span class="research-value">{{ researchCache()[app.id].tech_stack }}</span>
                        </div>
                      </div>
                      <div class="research-section">
                        <h4>Culture</h4>
                        <p>{{ researchCache()[app.id].culture_summary }}</p>
                      </div>
                      <div class="research-section">
                        <h4>Growth Trajectory</h4>
                        <p>{{ researchCache()[app.id].growth_trajectory }}</p>
                      </div>
                      <div class="research-grid">
                        <div class="research-section">
                          <h4>Pros</h4>
                          <p>{{ researchCache()[app.id].pros }}</p>
                        </div>
                        <div class="research-section">
                          <h4>Cons</h4>
                          <p>{{ researchCache()[app.id].cons }}</p>
                        </div>
                      </div>
                      @if (researchCache()[app.id].red_flags) {
                        <div class="research-section research-red-flags">
                          <h4>Red Flags</h4>
                          <p>{{ researchCache()[app.id].red_flags }}</p>
                        </div>
                      }
                      <div class="research-footer">
                        <button (click)="refreshResearch(app)" [disabled]="researchingCompany() === app.id" class="btn-secondary btn-sm">
                          Refresh
                        </button>
                        @if (researchCache()[app.id].updated_at) {
                          <span class="research-updated">Last updated: {{ researchCache()[app.id].updated_at | date: 'MMM d, y' }}</span>
                        }
                      </div>
                    </div>
                  </td>
                </tr>
              }
```

- [ ] **Step 4: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/core/models/company-research.model.ts frontend/src/app/pages/tracking/tracking.component.ts frontend/src/app/pages/tracking/tracking.component.html
git commit -m "feat(frontend): add company research button and detail panel to Pipeline page"
```

---

## Task 7: Full test suite verification

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && uv run python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Run linter**

Run: `cd backend && uv run ruff check src/hiresense/research/ tests/unit/research/`
Expected: Clean
