# Company-grounded Screening-question Answers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let HireSense draft answers to application screening questions (e.g. "Why do you want to work at X?", "¿Tienes experiencia con Django y React?") grounded in the candidate profile + the job description + real/LLM company info, and surface company info on the company page.

**Architecture:** Add a `CompanyInfo` real-data layer to the existing `research` module, populated for free during GetOnBoard ingestion (which already hits `/companies/{id}`). A `CompanyGroundingProvider` in `research` returns cached grounding text (portal facts first, LLM research second). A new `ScreeningAnswerService` in `applications` composes profile + job snapshot + grounding + an LLM to draft an answer in the question's language. Frontend adds a company-info card (company page) and a screening-question drafter card (application detail page).

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy + Alembic, Pydantic; Angular 21 standalone + signals, Vitest.

## Global Constraints

- Backend runs via `uv run python -m …` (bare `uv run pytest`/`alembic` fail on this machine).
- Hexagonal + bounded contexts: `domain/` imports nothing from `infrastructure/` or frameworks; wiring only in `bootstrap/`. Dependency direction ingestion → research (never research → ingestion).
- One class/function/constant per file. Every package `__init__.py` re-exports public symbols; import from the contextual package, never the implementation file.
- Every ORM class must be imported in `backend/src/hiresense/infrastructure/registry.py` or Alembic autogenerate won't see it.
- No hardcoded config: new tunables go through `config.py` + `.env` + `.env.example` with a comment.
- Full test suite runs DB-free on in-memory SQLite; integration tests build the app against SQLite (`StaticPool`, `require_auth` override, `criteria=None` on fakes).
- Language rule (personal/SteveSant repo): engineering artifacts in English. Product copy follows the codebase's established locale. The drafted *answer* is written in the **same language as the input question** (LLM-detected), independent of UI locale.
- Conventional Commits, scoped by module (`feat(research): …`, `feat(applications): …`, `feat(frontend): …`).
- LLM port interface is `await llm.complete(prompt: str, system: str) -> str` (see `research/domain/services.py`). LLMs are obtained in bootstrap via `tracked("<feature_key>")`.

---

## File Structure

**New (backend):**
- `research/domain/company_info.py` — `CompanyInfo` Pydantic model
- `research/domain/company_grounding.py` — `CompanyGroundingProvider`
- `research/ports/company_info_repository.py` — `CompanyInfoRepositoryPort`
- `research/infrastructure/company_info_orm.py` — `CompanyInfoOrm`
- `research/infrastructure/company_info_repository.py` — `CompanyInfoRepository`
- `research/api/company_info_schemas.py` — `CompanyInfoResponse`
- `ingestion/ports/company_info_sink.py` — `CompanyInfoSinkPort`
- `applications/domain/screening_answer_prompt.py` — pure prompt builder
- `applications/domain/screening_answer_view.py` — `ScreeningAnswerDraft`
- `applications/domain/screening_answer_service.py` — `ScreeningAnswerService`
- `alembic/versions/036_add_company_info.py`

**Modified (backend):** `research/{domain,ports,infrastructure,api}/__init__.py`, `research/api/{routes,provider,dependencies}.py`, `ingestion/ports/__init__.py`, `ingestion/adapters/getonboard.py`, `applications/domain/__init__.py`, `applications/api/{routes,schemas,provider,dependencies}.py`, `bootstrap/{research,ingestion,applications}.py`, `main.py`, `infrastructure/registry.py`, `profile/api/routes.py`, `profile/domain/services.py`.

> No new `config.py`/`.env` value is introduced: the prompt-shaping length caps are module-level constants, matching the existing precedent in `research/domain/services.py` (`job_description[:2000]`).

**New (frontend):**
- `pages/tracking/models/company-info.model.ts`
- `pages/applications/models/screening-answer.model.ts` (draft request/response)
- `pages/company/components/company-info-card/` (component .ts/.html/.scss/.spec)
- `pages/applications/components/screening-question-card/` (component .ts/.html/.scss/.spec)

**Modified (frontend):** `core/services/research.service.ts`, `core/services/applications.service.ts`, `core/services/profile.service.ts` (append-answer), `pages/company/company.component.{ts,html}`, `pages/applications/application-detail.component.{ts,html}`.

---

# PHASE 1 — Company info (real-data layer)

## Task 1: `CompanyInfo` domain model

**Files:**
- Create: `backend/src/hiresense/research/domain/company_info.py`
- Modify: `backend/src/hiresense/research/domain/__init__.py`
- Test: `backend/tests/unit/research/test_company_info_model.py`

**Interfaces:**
- Produces: `CompanyInfo(company_name: str, description: str|None, website: str|None, industry: str|None, size: str|None, logo_url: str|None, source: str, source_ref: str|None, id: UUID|None, created_at, updated_at)` with `model_config = {"from_attributes": True}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/research/test_company_info_model.py
from hiresense.research.domain import CompanyInfo


def test_company_info_defaults_optional_fields_to_none():
    info = CompanyInfo(company_name="SeatGeek", source="getonboard")
    assert info.company_name == "SeatGeek"
    assert info.source == "getonboard"
    assert info.description is None
    assert info.website is None
    assert info.logo_url is None
    assert info.id is None


def test_company_info_from_attributes_reads_orm_like_object():
    class Row:
        id = None
        company_name = "Acme"
        description = "We build things"
        website = "https://acme.test"
        industry = "SaaS"
        size = "51-200"
        logo_url = "https://acme.test/logo.png"
        source = "getonboard"
        source_ref = "42"
        created_at = None
        updated_at = None

    info = CompanyInfo.model_validate(Row())
    assert info.description == "We build things"
    assert info.source_ref == "42"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/research/test_company_info_model.py -v`
Expected: FAIL with `ImportError: cannot import name 'CompanyInfo'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/hiresense/research/domain/company_info.py
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class CompanyInfo(BaseModel):
    """Factual, portal-sourced company info (distinct from LLM CompanyResearch)."""

    id: uuid.UUID | None = None
    company_name: str
    description: str | None = None
    website: str | None = None
    industry: str | None = None
    size: str | None = None
    logo_url: str | None = None
    source: str
    source_ref: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
```

Then add to `backend/src/hiresense/research/domain/__init__.py`:

```python
from hiresense.research.domain.company_info import CompanyInfo
from hiresense.research.domain.services import CompanyResearchService

__all__ = ["CompanyInfo", "CompanyResearchService"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/research/test_company_info_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/research/domain/company_info.py backend/src/hiresense/research/domain/__init__.py backend/tests/unit/research/test_company_info_model.py
git commit -m "feat(research): add CompanyInfo domain model"
```

---

## Task 2: `CompanyInfoOrm` + migration + registry

**Files:**
- Create: `backend/src/hiresense/research/infrastructure/company_info_orm.py`
- Create: `backend/alembic/versions/036_add_company_info.py`
- Modify: `backend/src/hiresense/research/infrastructure/__init__.py`
- Modify: `backend/src/hiresense/infrastructure/registry.py`
- Test: `backend/tests/unit/research/test_company_info_orm.py`

**Interfaces:**
- Produces: `CompanyInfoOrm` (table `company_info`, unique index `ix_company_info_company_name` on `company_name`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/research/test_company_info_orm.py
from hiresense.research.infrastructure import CompanyInfoOrm


def test_company_info_orm_table_shape():
    cols = CompanyInfoOrm.__table__.columns
    assert "company_name" in cols
    assert "description" in cols
    assert "source" in cols
    assert "source_ref" in cols
    assert CompanyInfoOrm.__tablename__ == "company_info"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/research/test_company_info_orm.py -v`
Expected: FAIL with `ImportError: cannot import name 'CompanyInfoOrm'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/hiresense/research/infrastructure/company_info_orm.py
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class CompanyInfoOrm(Base):
    __tablename__ = "company_info"
    __table_args__ = (
        Index("ix_company_info_company_name", "company_name", unique=True),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Update `backend/src/hiresense/research/infrastructure/__init__.py`:

```python
from hiresense.research.infrastructure.company_info_orm import CompanyInfoOrm
from hiresense.research.infrastructure.company_info_repository import CompanyInfoRepository
from hiresense.research.infrastructure.orm import CompanyResearchOrm
from hiresense.research.infrastructure.repository import CompanyResearchRepository

__all__ = [
    "CompanyInfoOrm",
    "CompanyInfoRepository",
    "CompanyResearchOrm",
    "CompanyResearchRepository",
]
```

> Note: `CompanyInfoRepository` is created in Task 3. If running tasks strictly in order, temporarily omit those two lines and add them in Task 3. (They're listed here so the final state is unambiguous.)

Add to `backend/src/hiresense/infrastructure/registry.py`, next to the existing research import:

```python
from hiresense.research.infrastructure import CompanyInfoOrm, CompanyResearchOrm  # noqa: F401
```

Create the migration:

```python
# backend/alembic/versions/036_add_company_info.py
"""add company_info table

Revision ID: 036
Revises: 035
Create Date: 2026-07-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_info",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("website", sa.String(512), nullable=True),
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("size", sa.String(100), nullable=True),
        sa.Column("logo_url", sa.String(1024), nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_company_info_company_name", "company_info", ["company_name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_company_info_company_name", table_name="company_info")
    op.drop_table("company_info")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/research/test_company_info_orm.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/research/infrastructure/company_info_orm.py backend/src/hiresense/research/infrastructure/__init__.py backend/src/hiresense/infrastructure/registry.py backend/alembic/versions/036_add_company_info.py backend/tests/unit/research/test_company_info_orm.py
git commit -m "feat(research): add company_info ORM + migration 036"
```

---

## Task 3: `CompanyInfoRepository` + port

**Files:**
- Create: `backend/src/hiresense/research/ports/company_info_repository.py`
- Create: `backend/src/hiresense/research/infrastructure/company_info_repository.py`
- Modify: `backend/src/hiresense/research/ports/__init__.py`
- Modify: `backend/src/hiresense/research/infrastructure/__init__.py` (already done in Task 2)
- Test: `backend/tests/unit/research/test_company_info_repository.py`

**Interfaces:**
- Produces: `CompanyInfoRepository(session_factory=...)` with
  - `get_by_company_name(company_name: str) -> CompanyInfo | None` (case-insensitive, trimmed)
  - `upsert_company_info(*, company_name: str, description: str|None, website: str|None, industry: str|None, size: str|None, logo_url: str|None, source: str, source_ref: str|None) -> CompanyInfo`
- Produces: `CompanyInfoRepositoryPort` Protocol with the same two methods.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/research/test_company_info_repository.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.infrastructure.registry import *  # noqa: F401,F403  (populate metadata)
from hiresense.research.infrastructure import CompanyInfoRepository


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_upsert_then_get_by_name_is_case_insensitive(session_factory):
    repo = CompanyInfoRepository(session_factory=session_factory)
    repo.upsert_company_info(
        company_name="SeatGeek",
        description="Live event ticketing",
        website="https://seatgeek.com",
        industry=None,
        size=None,
        logo_url=None,
        source="getonboard",
        source_ref="42",
    )
    got = repo.get_by_company_name("  seatgeek ")
    assert got is not None
    assert got.description == "Live event ticketing"
    assert got.source == "getonboard"


def test_upsert_updates_existing_row(session_factory):
    repo = CompanyInfoRepository(session_factory=session_factory)
    repo.upsert_company_info(
        company_name="Acme", description="old", website=None, industry=None,
        size=None, logo_url=None, source="getonboard", source_ref="1",
    )
    repo.upsert_company_info(
        company_name="Acme", description="new", website="https://acme.test", industry=None,
        size=None, logo_url=None, source="getonboard", source_ref="1",
    )
    got = repo.get_by_company_name("Acme")
    assert got.description == "new"
    assert got.website == "https://acme.test"


def test_get_missing_returns_none(session_factory):
    repo = CompanyInfoRepository(session_factory=session_factory)
    assert repo.get_by_company_name("Nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/research/test_company_info_repository.py -v`
Expected: FAIL with `ImportError: cannot import name 'CompanyInfoRepository'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/hiresense/research/ports/company_info_repository.py
from __future__ import annotations

from typing import Protocol

from hiresense.research.domain import CompanyInfo


class CompanyInfoRepositoryPort(Protocol):
    def get_by_company_name(self, company_name: str) -> CompanyInfo | None: ...

    def upsert_company_info(
        self,
        *,
        company_name: str,
        description: str | None,
        website: str | None,
        industry: str | None,
        size: str | None,
        logo_url: str | None,
        source: str,
        source_ref: str | None,
    ) -> CompanyInfo: ...
```

```python
# backend/src/hiresense/research/infrastructure/company_info_repository.py
from __future__ import annotations

from sqlalchemy import func, select

from hiresense.infrastructure import SqlRepository
from hiresense.research.domain import CompanyInfo
from hiresense.research.infrastructure.company_info_orm import CompanyInfoOrm


def _to_domain(row: CompanyInfoOrm) -> CompanyInfo:
    return CompanyInfo.model_validate(row)


class CompanyInfoRepository(SqlRepository):
    def get_by_company_name(self, company_name: str) -> CompanyInfo | None:
        stmt = select(CompanyInfoOrm).where(
            func.lower(CompanyInfoOrm.company_name) == company_name.lower().strip()
        )
        return self._select_one(stmt, _to_domain)

    def upsert_company_info(
        self,
        *,
        company_name: str,
        description: str | None,
        website: str | None,
        industry: str | None,
        size: str | None,
        logo_url: str | None,
        source: str,
        source_ref: str | None,
    ) -> CompanyInfo:
        with self._session_factory() as session:
            stmt = select(CompanyInfoOrm).where(
                func.lower(CompanyInfoOrm.company_name) == company_name.lower().strip()
            )
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                row = CompanyInfoOrm(company_name=company_name.strip(), source=source)
                session.add(row)
            row.description = description
            row.website = website
            row.industry = industry
            row.size = size
            row.logo_url = logo_url
            row.source = source
            row.source_ref = source_ref
            session.commit()
            session.refresh(row)
            return _to_domain(row)
```

> Confirm `SqlRepository` exposes `self._session_factory` and `self._select_one` — it does (see `research/infrastructure/repository.py`). Match that base class exactly.

Update `backend/src/hiresense/research/ports/__init__.py`:

```python
from hiresense.research.ports.company_info_repository import CompanyInfoRepositoryPort
from hiresense.research.ports.repository import CompanyResearchRepositoryPort

__all__ = ["CompanyInfoRepositoryPort", "CompanyResearchRepositoryPort"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/research/test_company_info_repository.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/research/ports/ backend/src/hiresense/research/infrastructure/company_info_repository.py backend/src/hiresense/research/infrastructure/__init__.py backend/tests/unit/research/test_company_info_repository.py
git commit -m "feat(research): add CompanyInfo repository + port"
```

---

## Task 4: `CompanyInfoSinkPort` + GetOnBoard capture

**Files:**
- Create: `backend/src/hiresense/ingestion/ports/company_info_sink.py`
- Modify: `backend/src/hiresense/ingestion/ports/__init__.py`
- Modify: `backend/src/hiresense/ingestion/adapters/getonboard.py`
- Test: `backend/tests/unit/ingestion/test_getonboard_company_info.py` (add to existing getonboard tests if present)

**Interfaces:**
- Consumes: nothing new.
- Produces: `CompanyInfoSinkPort` Protocol with `upsert_company_info(*, company_name, description, website, industry, size, logo_url, source, source_ref) -> object` (structurally satisfied by `CompanyInfoRepository`). `GetOnBoardAdapter.__init__` gains `company_info_sink: CompanyInfoSinkPort | None = None`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/ingestion/test_getonboard_company_info.py
import pytest

from hiresense.ingestion.adapters import GetOnBoardAdapter


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeHttp:
    def __init__(self, company_payload):
        self._company_payload = company_payload
        self.calls = []

    async def get(self, url, params=None):
        self.calls.append(url)
        # search/list endpoint returns one job referencing company id 42
        if "/companies/42" in url:
            return _Resp({"data": {"attributes": self._company_payload}})
        if url.endswith("/search/jobs"):
            return _Resp({
                "data": [{"id": "j1", "attributes": {"title": "Dev",
                    "company": {"data": {"id": 42}}}}],
                "meta": {"total_pages": 1},
            })
        return _Resp({"data": [], "meta": {"total_pages": 1}})


class _SpySink:
    def __init__(self):
        self.rows = []

    def upsert_company_info(self, **kwargs):
        self.rows.append(kwargs)
        return None


@pytest.mark.asyncio
async def test_getonboard_persists_company_info_to_sink():
    http = _FakeHttp({"name": "SeatGeek", "long_description": "Ticketing",
                      "website": "https://seatgeek.com", "logo": {"url": "https://x/logo.png"}})
    sink = _SpySink()
    adapter = GetOnBoardAdapter(
        http_client=http, base_url="https://api.test", categories=None,
        company_info_sink=sink,
    )
    jobs = await adapter.fetch_jobs({})
    assert jobs[0].raw_data["attributes"]["company_name"] == "SeatGeek"
    assert len(sink.rows) == 1
    row = sink.rows[0]
    assert row["company_name"] == "SeatGeek"
    assert row["description"] == "Ticketing"
    assert row["website"] == "https://seatgeek.com"
    assert row["logo_url"] == "https://x/logo.png"
    assert row["source"] == "getonboard"
    assert row["source_ref"] == "42"


@pytest.mark.asyncio
async def test_getonboard_without_sink_still_resolves_name():
    http = _FakeHttp({"name": "SeatGeek"})
    adapter = GetOnBoardAdapter(http_client=http, base_url="https://api.test")
    jobs = await adapter.fetch_jobs({})
    assert jobs[0].raw_data["attributes"]["company_name"] == "SeatGeek"
```

> If a `pytest.ini`/`pyproject` asyncio marker isn't configured, match the pattern used by other async adapter tests in `tests/unit/ingestion/` (they already run async). Remove `@pytest.mark.asyncio` and follow the local convention if needed.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/ingestion/test_getonboard_company_info.py -v`
Expected: FAIL (`GetOnBoardAdapter` has no `company_info_sink` param / sink not called)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/hiresense/ingestion/ports/company_info_sink.py
from __future__ import annotations

from typing import Protocol


class CompanyInfoSinkPort(Protocol):
    """Write-only sink for portal-sourced company facts.

    Structurally satisfied by research's CompanyInfoRepository. Kept in
    ingestion (with primitive params, not research's domain model) so the
    ingestion→research dependency stays one-directional.
    """

    def upsert_company_info(
        self,
        *,
        company_name: str,
        description: str | None,
        website: str | None,
        industry: str | None,
        size: str | None,
        logo_url: str | None,
        source: str,
        source_ref: str | None,
    ) -> object: ...
```

Add to `backend/src/hiresense/ingestion/ports/__init__.py` (re-export alongside existing symbols):

```python
from hiresense.ingestion.ports.company_info_sink import CompanyInfoSinkPort
# ...append "CompanyInfoSinkPort" to __all__
```

Edit `backend/src/hiresense/ingestion/adapters/getonboard.py`. Replace the constructor and the two company-resolution methods:

```python
    def __init__(
        self,
        http_client: Any,
        base_url: str,
        categories: list[str] | None = None,
        company_info_sink: Any = None,
    ) -> None:
        self._http = http_client
        self._base_url = base_url
        self._categories = list(categories) if categories else []
        self._company_info_sink = company_info_sink
        # company id → full attributes dict, resolved lazily and reused per run.
        self._company_cache: dict[str, dict] = {}
```

```python
    async def _resolve_company_names(self, jobs: list[RawJobListing]) -> None:
        for raw in jobs:
            attrs = raw.raw_data.get("attributes", {})
            if attrs.get("company_name"):
                continue
            company_id = (attrs.get("company") or {}).get("data", {}).get("id")
            if company_id is None:
                continue
            company_attrs = await self._fetch_company(str(company_id))
            name = ((company_attrs.get("name")) or "").strip()
            if name:
                attrs["company_name"] = name
                self._sink_company(name, str(company_id), company_attrs)

    async def _fetch_company(self, company_id: str) -> dict:
        if company_id in self._company_cache:
            return self._company_cache[company_id]
        company_attrs: dict = {}
        try:
            response = await self._http.get(f"{self._base_url}/companies/{company_id}")
            response.raise_for_status()
            data = response.json().get("data", {}) or {}
            company_attrs = (data.get("attributes") or {})
        except Exception:
            logger.warning("getonboard: failed to resolve company %s", company_id, exc_info=True)
        self._company_cache[company_id] = company_attrs
        return company_attrs

    def _sink_company(self, name: str, company_id: str, attrs: dict) -> None:
        if self._company_info_sink is None:
            return
        logo = attrs.get("logo")
        logo_url = logo.get("url") if isinstance(logo, dict) else (logo if isinstance(logo, str) else None)
        try:
            self._company_info_sink.upsert_company_info(
                company_name=name,
                description=(attrs.get("long_description") or attrs.get("description") or None),
                website=(attrs.get("website") or attrs.get("url") or None),
                industry=(attrs.get("category") or None),
                size=(attrs.get("size") or None),
                logo_url=logo_url,
                source="getonboard",
                source_ref=company_id,
            )
        except Exception:
            logger.warning("getonboard: failed to persist company info for %s", name, exc_info=True)
```

> The exact GetOnBoard `/companies/{id}` attribute keys (`long_description`, `website`, `logo`, `category`, `size`) should be confirmed against a live response; the `.get(...)`-with-fallbacks keeps missing keys harmless. Note: the old `_company_name` method is removed — grep the file for other callers first (there are none besides `_resolve_company_names`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/ingestion/test_getonboard_company_info.py -v`
Then run the existing getonboard tests to ensure no regression:
Run: `uv run python -m pytest tests/unit/ingestion -k getonboard -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/ports/ backend/src/hiresense/ingestion/adapters/getonboard.py backend/tests/unit/ingestion/test_getonboard_company_info.py
git commit -m "feat(ingestion): capture GetOnBoard company info via sink port"
```

---

## Task 5: `CompanyGroundingProvider` + research read endpoint

**Files:**
- Create: `backend/src/hiresense/research/domain/company_grounding.py`
- Create: `backend/src/hiresense/research/api/company_info_schemas.py`
- Modify: `backend/src/hiresense/research/domain/__init__.py`
- Modify: `backend/src/hiresense/research/api/provider.py`
- Modify: `backend/src/hiresense/research/api/dependencies.py`
- Modify: `backend/src/hiresense/research/api/routes.py`
- Test: `backend/tests/unit/research/test_company_grounding.py`

**Interfaces:**
- Consumes: `CompanyInfoRepositoryPort`, `CompanyResearchRepositoryPort`.
- Produces: `CompanyGroundingProvider(info_repo, research_repo)` with:
  - `get_info(company_name: str) -> CompanyInfo | None`
  - `grounding_text(company_name: str) -> str` (portal facts first, else LLM research summary, else `""`)
- Produces: `ResearchProvider.get_company_info_repo()`, `.get_company_info_sink()`, `.get_company_grounding()`.
- Produces: `GET /research/company-info/{company_name}` → `CompanyInfoResponse | None`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/research/test_company_grounding.py
from hiresense.research.domain import CompanyGrounding, CompanyInfo


class _FakeInfoRepo:
    def __init__(self, info=None):
        self._info = info

    def get_by_company_name(self, name):
        return self._info


class _FakeResearchRepo:
    def __init__(self, research=None):
        self._research = research

    def get_by_company_name(self, name):
        return self._research


def test_grounding_prefers_portal_facts():
    info = CompanyInfo(company_name="SeatGeek", source="getonboard",
                       description="Live event ticketing", website="https://seatgeek.com")
    g = CompanyGrounding(info_repo=_FakeInfoRepo(info), research_repo=_FakeResearchRepo(None))
    text = g.grounding_text("SeatGeek")
    assert "Live event ticketing" in text
    assert g.get_info("SeatGeek") is info


def test_grounding_falls_back_to_llm_research():
    class Research:
        culture_summary = "Fast-paced"
        tech_stack = "Ruby, React"
        pros = "Good pay"
        cons = "Long hours"

    g = CompanyGrounding(info_repo=_FakeInfoRepo(None), research_repo=_FakeResearchRepo(Research()))
    text = g.grounding_text("Acme")
    assert "Ruby, React" in text
    assert "Fast-paced" in text


def test_grounding_empty_when_nothing_cached():
    g = CompanyGrounding(info_repo=_FakeInfoRepo(None), research_repo=_FakeResearchRepo(None))
    assert g.grounding_text("Ghost") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/research/test_company_grounding.py -v`
Expected: FAIL with `ImportError: cannot import name 'CompanyGrounding'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/hiresense/research/domain/company_grounding.py
from __future__ import annotations

from typing import Any

from hiresense.research.domain.company_info import CompanyInfo


class CompanyGrounding:
    """Read-only company grounding for downstream generators.

    Prefers portal-sourced facts (CompanyInfo); falls back to cached LLM
    CompanyResearch. Never triggers an LLM call itself — grounding uses only
    already-cached data, so drafting stays cheap.
    """

    def __init__(self, info_repo: Any, research_repo: Any) -> None:
        self._info_repo = info_repo
        self._research_repo = research_repo

    def get_info(self, company_name: str) -> CompanyInfo | None:
        return self._info_repo.get_by_company_name(company_name)

    def grounding_text(self, company_name: str) -> str:
        info = self._info_repo.get_by_company_name(company_name)
        if info is not None and (info.description or info.website):
            parts = [f"Company: {info.company_name}"]
            if info.description:
                parts.append(f"About: {info.description}")
            if info.website:
                parts.append(f"Website: {info.website}")
            if info.industry:
                parts.append(f"Industry: {info.industry}")
            return "\n".join(parts)
        research = self._research_repo.get_by_company_name(company_name)
        if research is not None:
            return (
                f"Company culture: {research.culture_summary}\n"
                f"Tech stack: {research.tech_stack}\n"
                f"Pros: {research.pros}\nCons: {research.cons}"
            )
        return ""
```

Add to `backend/src/hiresense/research/domain/__init__.py`:

```python
from hiresense.research.domain.company_grounding import CompanyGrounding
from hiresense.research.domain.company_info import CompanyInfo
from hiresense.research.domain.services import CompanyResearchService

__all__ = ["CompanyGrounding", "CompanyInfo", "CompanyResearchService"]
```

```python
# backend/src/hiresense/research/api/company_info_schemas.py
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class CompanyInfoResponse(BaseModel):
    id: uuid.UUID | None = None
    company_name: str
    description: str | None = None
    website: str | None = None
    industry: str | None = None
    size: str | None = None
    logo_url: str | None = None
    source: str
    source_ref: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
```

Update `backend/src/hiresense/research/api/provider.py`:

```python
from __future__ import annotations

from hiresense.research.domain import CompanyGrounding, CompanyResearchService


class ResearchProvider:
    def __init__(
        self,
        research_service: CompanyResearchService,
        company_info_repo,
        company_grounding: CompanyGrounding,
    ) -> None:
        self._research_service = research_service
        self._company_info_repo = company_info_repo
        self._company_grounding = company_grounding

    def get_research_service(self) -> CompanyResearchService:
        return self._research_service

    def get_company_info_repo(self):
        return self._company_info_repo

    def get_company_info_sink(self):
        return self._company_info_repo  # satisfies CompanyInfoSinkPort structurally

    def get_company_grounding(self) -> CompanyGrounding:
        return self._company_grounding
```

Update `backend/src/hiresense/research/api/dependencies.py` (append):

```python
from hiresense.research.domain import CompanyGrounding


def get_company_grounding(request: Request) -> CompanyGrounding:
    return request.app.state.research.get_company_grounding()


def get_company_info_repo(request: Request):
    return request.app.state.research.get_company_info_repo()
```

Add the read route to `backend/src/hiresense/research/api/routes.py`:

```python
from hiresense.research.api.company_info_schemas import CompanyInfoResponse
from hiresense.research.api.dependencies import get_company_info_repo

# ...

@router.get("/company-info/{company_name}", response_model=CompanyInfoResponse | None)
def get_company_info(
    company_name: str,
    repo=Depends(get_company_info_repo),
) -> CompanyInfoResponse | None:
    """Portal-sourced company facts, or null if none cached (never 404s)."""
    info = repo.get_by_company_name(company_name)
    return CompanyInfoResponse.model_validate(info) if info is not None else None
```

> Route ordering: FastAPI matches in declaration order. Put `/company-info/{company_name}` **above** the existing `/{company_name}` route so it isn't shadowed.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/research/test_company_grounding.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/research/domain/company_grounding.py backend/src/hiresense/research/domain/__init__.py backend/src/hiresense/research/api/ backend/tests/unit/research/test_company_grounding.py
git commit -m "feat(research): add CompanyGrounding + company-info read endpoint"
```

---

## Task 6: Bootstrap wiring (build order + sink injection)

**Files:**
- Modify: `backend/src/hiresense/bootstrap/research.py`
- Modify: `backend/src/hiresense/bootstrap/ingestion.py`
- Modify: `backend/src/hiresense/main.py`
- Test: `backend/tests/integration/test_company_info_endpoint.py`

**Interfaces:**
- Consumes: `CompanyInfoRepository`, `CompanyGrounding`, `ResearchProvider(...)` new signature.
- Produces: `build_research` returns a provider carrying company-info repo + grounding; `build_ingestion` accepts `company_info_sink=` and passes it to `GetOnBoardAdapter`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_company_info_endpoint.py
# Follow the existing integration app-builder + require_auth override convention
# used in tests/integration/ (StaticPool sqlite, criteria=None on fakes).
from fastapi.testclient import TestClient


def test_company_info_returns_null_when_absent(app_client: TestClient):
    # `app_client` = the shared integration fixture that builds the app on sqlite
    # with require_auth overridden. Reuse whatever the sibling tests import.
    resp = app_client.get("/research/company-info/UnknownCo")
    assert resp.status_code == 200
    assert resp.json() is None
```

> Open a sibling file in `tests/integration/` (e.g. `test_outreach_endpoints.py`) and copy its fixture wiring exactly — the point of this test is that the app still boots with the reordered bootstrap and the new route resolves.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/integration/test_company_info_endpoint.py -v`
Expected: FAIL (route missing / app not wired) — or ImportError until wiring lands.

- [ ] **Step 3: Write minimal implementation**

Rewrite `backend/src/hiresense/bootstrap/research.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.research.api.provider import ResearchProvider
from hiresense.research.domain import CompanyGrounding, CompanyResearchService
from hiresense.research.infrastructure import CompanyInfoRepository, CompanyResearchRepository


def build_research(infra: SharedInfra, tracked: Callable[[str], Any]) -> ResearchProvider:
    research_repo = CompanyResearchRepository(session_factory=infra.sync_session_factory)
    company_info_repo = CompanyInfoRepository(session_factory=infra.sync_session_factory)
    research_service = CompanyResearchService(
        llm=tracked("company_research"),
        repository=research_repo,
    )
    company_grounding = CompanyGrounding(info_repo=company_info_repo, research_repo=research_repo)
    return ResearchProvider(
        research_service=research_service,
        company_info_repo=company_info_repo,
        company_grounding=company_grounding,
    )
```

Edit `backend/src/hiresense/bootstrap/ingestion.py`:
- Change signature to accept the sink:

```python
def build_ingestion(
    infra: SharedInfra,
    tracked: Callable[[str], Any],
    *,
    preference_query: Any = None,
    company_info_sink: Any = None,
) -> IngestionBuild:
```

- In the `getonboard` branch, pass the sink:

```python
        elif source_name == "getonboard":
            sources.append(
                GetOnBoardAdapter(
                    http_client=http_client,
                    base_url=s.getonboard_api_url,
                    categories=s.getonboard_categories,
                    company_info_sink=company_info_sink,
                )
            )
            normalizers["getonboard"] = GetOnBoardNormalizer()
```

Edit `backend/src/hiresense/main.py` — move `build_research` **above** `build_ingestion`, and pass the sink. Concretely, before the line `ingestion = build_ingestion(...)` (currently ~line 147), insert:

```python
    research = build_research(infra, tracked)
    app.state.research = research
    app.include_router(research_router)
```

Then change the ingestion build call to:

```python
    ingestion = build_ingestion(
        infra,
        tracked,
        preference_query=preference.service,
        company_info_sink=research.get_company_info_sink(),
    )
```

Finally, **delete** the now-duplicate later block (the original lines ~237-239 that did `research = build_research(...)`, `app.state.research = research`, `app.include_router(research_router)`). The `outreach` build at ~line 247 still reads `research.get_research_service()` — it now refers to the earlier `research`, which is fine.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/integration/test_company_info_endpoint.py -v`
Then a broad smoke run:
Run: `uv run python -m pytest tests/integration -q`
Expected: PASS (app boots with reordered bootstrap; no duplicate router include).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/bootstrap/research.py backend/src/hiresense/bootstrap/ingestion.py backend/src/hiresense/main.py backend/tests/integration/test_company_info_endpoint.py
git commit -m "feat(research): wire company-info repo, grounding, and GetOnBoard sink"
```

---

# PHASE 2 — Answer drafter

## Task 7: Screening-answer prompt builder + view model

**Files:**
- Create: `backend/src/hiresense/applications/domain/screening_answer_prompt.py`
- Create: `backend/src/hiresense/applications/domain/screening_answer_view.py`
- Modify: `backend/src/hiresense/applications/domain/__init__.py`
- Test: `backend/tests/unit/applications/test_screening_answer_prompt.py`

**Interfaces:**
- Produces: `ScreeningAnswerDraft(question: str, answer: str, language: str)` (Pydantic).
- Produces: `build_screening_answer_prompt(*, question: str, title: str, company: str, job_description: str, required_skills: list[str], candidate_name: str, candidate_summary: str, candidate_skills: list[str], company_grounding: str) -> str` (pure).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/applications/test_screening_answer_prompt.py
from hiresense.applications.domain import build_screening_answer_prompt


def test_prompt_includes_question_job_and_profile():
    prompt = build_screening_answer_prompt(
        question="¿Tienes experiencia con Django y React?",
        title="Fullstack Dev",
        company="SeatGeek",
        job_description="We use Django and React heavily.",
        required_skills=["Django", "React"],
        candidate_name="Bryan",
        candidate_summary="Fullstack engineer",
        candidate_skills=["Django", "Angular"],
        company_grounding="About: Live event ticketing",
    )
    assert "¿Tienes experiencia con Django y React?" in prompt
    assert "SeatGeek" in prompt
    assert "Django and React heavily" in prompt
    assert "Live event ticketing" in prompt
    # Must instruct same-language + JSON output
    assert "same language" in prompt.lower()
    assert "json" in prompt.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/applications/test_screening_answer_prompt.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/hiresense/applications/domain/screening_answer_view.py
from __future__ import annotations

from pydantic import BaseModel


class ScreeningAnswerDraft(BaseModel):
    question: str
    answer: str
    language: str
```

```python
# backend/src/hiresense/applications/domain/screening_answer_prompt.py
from __future__ import annotations

_JOB_DESC_LIMIT = 3000
_GROUNDING_LIMIT = 1500


def build_screening_answer_prompt(
    *,
    question: str,
    title: str,
    company: str,
    job_description: str,
    required_skills: list[str],
    candidate_name: str,
    candidate_summary: str,
    candidate_skills: list[str],
    company_grounding: str,
) -> str:
    skills = ", ".join(required_skills) if required_skills else "(not specified)"
    cand_skills = ", ".join(candidate_skills) if candidate_skills else "(not specified)"
    grounding = company_grounding.strip() or "(no company info available)"
    return (
        "You are helping a job candidate answer an application screening question.\n"
        "Write a truthful, specific, first-person answer grounded ONLY in the "
        "candidate profile and the job/company context below. Do not invent "
        "experience the candidate does not have; if a required skill is missing, "
        "answer honestly (e.g. transferable experience).\n\n"
        f"SCREENING QUESTION:\n{question}\n\n"
        f"ROLE: {title} at {company}\n"
        f"REQUIRED SKILLS: {skills}\n"
        f"JOB DESCRIPTION:\n{job_description[:_JOB_DESC_LIMIT]}\n\n"
        f"COMPANY INFO:\n{grounding[:_GROUNDING_LIMIT]}\n\n"
        f"CANDIDATE: {candidate_name}\n"
        f"CANDIDATE SUMMARY: {candidate_summary}\n"
        f"CANDIDATE SKILLS: {cand_skills}\n\n"
        "Write the answer in the SAME LANGUAGE as the screening question.\n"
        'Return valid JSON only: {"language": "<ISO 639-1 code>", "answer": "<the answer>"}'
    )
```

Add both to `backend/src/hiresense/applications/domain/__init__.py` re-exports (append names to imports and `__all__`):

```python
from hiresense.applications.domain.screening_answer_prompt import build_screening_answer_prompt
from hiresense.applications.domain.screening_answer_view import ScreeningAnswerDraft
# add "build_screening_answer_prompt", "ScreeningAnswerDraft" to __all__
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/applications/test_screening_answer_prompt.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/applications/domain/screening_answer_prompt.py backend/src/hiresense/applications/domain/screening_answer_view.py backend/src/hiresense/applications/domain/__init__.py backend/tests/unit/applications/test_screening_answer_prompt.py
git commit -m "feat(applications): add screening-answer prompt builder + view"
```

---

## Task 8: `ScreeningAnswerService`

**Files:**
- Create: `backend/src/hiresense/applications/domain/screening_answer_service.py`
- Modify: `backend/src/hiresense/applications/domain/__init__.py`
- Test: `backend/tests/unit/applications/test_screening_answer_service.py`

**Interfaces:**
- Consumes: `ApplicationRepositoryPort.get_snapshot`, `tracking_service.get(application_id) -> (has .title/.company)`, `profile_service.get_current_profile()` (async), `CompanyGrounding.grounding_text`, LLM `.complete`.
- Produces: `ScreeningAnswerService(repository, tracking_service, profile_service, company_grounding, llm)` with `async draft_answer(application_id: uuid.UUID, question: str) -> ScreeningAnswerDraft`. Raises `ValueError` on missing application/snapshot/profile.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/applications/test_screening_answer_service.py
import uuid

import pytest

from hiresense.applications.domain import ScreeningAnswerService


class _Snap:
    description = "We use Django and React."
    required_skills = ["Django", "React"]


class _Tracked:
    title = "Fullstack Dev"
    company = "SeatGeek"


class _Profile:
    name = "Bryan"
    summary = "Fullstack engineer"
    skills = ["Django", "Angular"]


class _Repo:
    def get_snapshot(self, application_id):
        return _Snap()


class _Tracking:
    def get(self, application_id):
        return _Tracked()


class _Profiles:
    async def get_current_profile(self, language=None):
        return _Profile()


class _Grounding:
    def grounding_text(self, company_name):
        return "About: Live event ticketing"


class _LLM:
    def __init__(self, response):
        self._response = response
        self.prompts = []

    async def complete(self, prompt, system=""):
        self.prompts.append(prompt)
        return self._response


@pytest.mark.asyncio
async def test_draft_answer_returns_answer_and_language():
    llm = _LLM('{"language": "es", "answer": "Sí, tengo experiencia con Django."}')
    svc = ScreeningAnswerService(
        repository=_Repo(), tracking_service=_Tracking(), profile_service=_Profiles(),
        company_grounding=_Grounding(), llm=llm,
    )
    draft = await svc.draft_answer(uuid.uuid4(), "¿Tienes experiencia con Django y React?")
    assert draft.language == "es"
    assert "Django" in draft.answer
    assert "Live event ticketing" in llm.prompts[0]


@pytest.mark.asyncio
async def test_draft_answer_raises_when_no_llm():
    svc = ScreeningAnswerService(
        repository=_Repo(), tracking_service=_Tracking(), profile_service=_Profiles(),
        company_grounding=_Grounding(), llm=None,
    )
    with pytest.raises(ValueError):
        await svc.draft_answer(uuid.uuid4(), "Why us?")


@pytest.mark.asyncio
async def test_draft_answer_parses_fenced_json():
    llm = _LLM('```json\n{"language": "en", "answer": "Because..."}\n```')
    svc = ScreeningAnswerService(
        repository=_Repo(), tracking_service=_Tracking(), profile_service=_Profiles(),
        company_grounding=_Grounding(), llm=llm,
    )
    draft = await svc.draft_answer(uuid.uuid4(), "Why do you want to work here?")
    assert draft.answer == "Because..."
    assert draft.language == "en"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/applications/test_screening_answer_service.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/hiresense/applications/domain/screening_answer_service.py
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from hiresense.applications.domain.screening_answer_prompt import build_screening_answer_prompt
from hiresense.applications.domain.screening_answer_view import ScreeningAnswerDraft

_SYSTEM = "You are a job application assistant. Return only valid JSON."


class ScreeningAnswerService:
    def __init__(
        self,
        repository: Any,
        tracking_service: Any,
        profile_service: Any,
        company_grounding: Any,
        llm: Any = None,
    ) -> None:
        self._repo = repository
        self._tracking = tracking_service
        self._profiles = profile_service
        self._grounding = company_grounding
        self._llm = llm

    async def draft_answer(self, application_id: uuid.UUID, question: str) -> ScreeningAnswerDraft:
        if self._llm is None:
            raise ValueError("LLM not configured for screening answers")
        question = (question or "").strip()
        if not question:
            raise ValueError("Question must not be empty")

        tracked = self._tracking.get(application_id)  # raises/returns None if missing
        if tracked is None:
            raise ValueError(f"Application {application_id} not found")
        snapshot = self._repo.get_snapshot(application_id)
        if snapshot is None:
            raise ValueError(f"Job snapshot for {application_id} not found")
        profile = await self._profiles.get_current_profile()
        if profile is None:
            raise ValueError("No candidate profile found — set one up first")

        grounding = self._grounding.grounding_text(tracked.company)
        prompt = build_screening_answer_prompt(
            question=question,
            title=tracked.title,
            company=tracked.company,
            job_description=snapshot.description or "",
            required_skills=list(snapshot.required_skills or []),
            candidate_name=getattr(profile, "name", "") or "",
            candidate_summary=getattr(profile, "summary", "") or "",
            candidate_skills=list(getattr(profile, "skills", []) or []),
            company_grounding=grounding,
        )
        response = await self._llm.complete(prompt, system=_SYSTEM)
        data = self._parse(response)
        return ScreeningAnswerDraft(
            question=question,
            answer=str(data.get("answer", "")).strip(),
            language=str(data.get("language", "")).strip() or "en",
        )

    @staticmethod
    def _parse(response: str) -> dict:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        md = re.search(r"```(?:json)?\s*\n?({.*?})\s*\n?```", response, re.DOTALL)
        if md:
            return json.loads(md.group(1))
        raise ValueError("Could not parse LLM response as JSON")
```

Add to `backend/src/hiresense/applications/domain/__init__.py` re-exports.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/applications/test_screening_answer_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/applications/domain/screening_answer_service.py backend/src/hiresense/applications/domain/__init__.py backend/tests/unit/applications/test_screening_answer_service.py
git commit -m "feat(applications): add ScreeningAnswerService"
```

---

## Task 9: Endpoint + wiring for the drafter

**Files:**
- Modify: `backend/src/hiresense/applications/api/schemas.py`
- Modify: `backend/src/hiresense/applications/api/provider.py`
- Modify: `backend/src/hiresense/applications/api/dependencies.py`
- Modify: `backend/src/hiresense/applications/api/routes.py`
- Modify: `backend/src/hiresense/bootstrap/applications.py`
- Modify: `backend/src/hiresense/main.py`
- Test: `backend/tests/integration/test_screening_answer_endpoint.py`

**Interfaces:**
- Consumes: `ScreeningAnswerService`, `CompanyGrounding` (from research provider), `tracked("screening_answer")`.
- Produces: `POST /applications/{id}/screening-answer` body `{ "question": str }` → `{ "question", "answer", "language" }`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_screening_answer_endpoint.py
# Reuse the integration app fixture (require_auth override, sqlite StaticPool,
# fake LLM). Create a tracked application, then POST a question.
def test_screening_answer_endpoint_returns_draft(app_client, seed_tracked_application):
    app_id = seed_tracked_application(company="SeatGeek", description="Django + React")
    resp = app_client.post(
        f"/applications/{app_id}/screening-answer",
        json={"question": "Why do you want to work here?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["question"] == "Why do you want to work here?"
    assert "answer" in body and "language" in body
```

> Mirror the fixtures used by the existing `tests/integration/test_*applications*` or apply-assist tests — reuse their app builder and any fake-LLM injection so the drafter's `tracked("screening_answer")` returns a deterministic JSON string. If no `seed_tracked_application` helper exists, inline the create-application call the sibling tests use.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/integration/test_screening_answer_endpoint.py -v`
Expected: FAIL (404 route missing / provider has no screening service)

- [ ] **Step 3: Write minimal implementation**

Add schemas to `backend/src/hiresense/applications/api/schemas.py`:

```python
class ScreeningAnswerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class ScreeningAnswerResponse(BaseModel):
    question: str
    answer: str
    language: str
```

> Ensure `Field` is imported from pydantic in that file (it likely already is).

Extend `ApplicationsProvider` (`applications/api/provider.py`): add a `screening_answer_service` constructor arg + `get_screening_answer_service()` getter, mirroring `apply_service`.

Extend `applications/api/dependencies.py`:

```python
from hiresense.applications.domain.screening_answer_service import ScreeningAnswerService


def get_screening_answer_service(
    provider: ApplicationsProvider = Depends(_get_provider),
) -> ScreeningAnswerService:
    return provider.get_screening_answer_service()
```

Add the route to `applications/api/routes.py`:

```python
from hiresense.applications.api.dependencies import get_screening_answer_service
from hiresense.applications.api.schemas import ScreeningAnswerRequest, ScreeningAnswerResponse
from hiresense.applications.domain.screening_answer_service import ScreeningAnswerService


@router.post("/{application_id}/screening-answer", response_model=ScreeningAnswerResponse)
async def draft_screening_answer(
    application_id: uuid_mod.UUID,
    request: ScreeningAnswerRequest,
    service: ScreeningAnswerService = Depends(get_screening_answer_service),
) -> ScreeningAnswerResponse:
    try:
        draft = await service.draft_answer(application_id, request.question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScreeningAnswerResponse(
        question=draft.question, answer=draft.answer, language=draft.language
    )
```

Update `bootstrap/applications.py` — add `company_grounding: Any` parameter to `build_applications`, construct the service, and pass it to the provider:

```python
    from hiresense.applications.domain.screening_answer_service import ScreeningAnswerService

    screening_answer_service = ScreeningAnswerService(
        repository=application_repo,
        tracking_service=tracking_service,
        profile_service=profile_service,
        company_grounding=company_grounding,
        llm=tracked("screening_answer"),
    )
    return ApplicationsProvider(
        application_service=application_service,
        artifact_service=artifact_service,
        apply_service=apply_service,
        screening_answer_service=screening_answer_service,
    )
```

Update the `build_applications(...)` call in `main.py`. Because Task 6 already moved `build_research` above `build_ingestion` (both above `build_applications` at ~line 219), `research` is in scope — pass `company_grounding=research.get_company_grounding()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/integration/test_screening_answer_endpoint.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/applications/api/ backend/src/hiresense/bootstrap/applications.py backend/src/hiresense/main.py backend/tests/integration/test_screening_answer_endpoint.py
git commit -m "feat(applications): add screening-answer drafting endpoint"
```

---

## Task 10: Profile append-screening-answer endpoint (save to bank)

**Files:**
- Modify: `backend/src/hiresense/profile/api/routes.py`
- Modify: `backend/src/hiresense/profile/domain/services.py` (add append method if not present)
- Test: `backend/tests/integration/test_profile_screening_answers.py`

**Interfaces:**
- Consumes: existing `ProfileService.set_apply_profile` / apply-profile persistence.
- Produces: `POST /profile/apply-profile/screening-answers` body `{ "question": str, "answer": str }` → updated `CandidateProfile`. Appends to `apply_profile.screening_answers` (replaces any existing entry with the same question, case-insensitive) atomically server-side.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_profile_screening_answers.py
def test_append_screening_answer(app_client, seed_profile):
    seed_profile()  # ensure a current profile exists
    resp = app_client.post(
        "/profile/apply-profile/screening-answers",
        json={"question": "Why us?", "answer": "Because X"},
    )
    assert resp.status_code == 200
    ap = resp.json()["apply_profile"]
    qs = [a["question"] for a in ap["screening_answers"]]
    assert "Why us?" in qs
```

> Reuse the profile integration fixture used by existing profile tests. If none seeds a profile, inline the profile-create the sibling tests use.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/integration/test_profile_screening_answers.py -v`
Expected: FAIL (route missing)

- [ ] **Step 3: Write minimal implementation**

Add a method to `ProfileService` (near `set_apply_profile`):

```python
    async def append_screening_answer(self, question: str, answer: str) -> CandidateProfile:
        profile = await self.get_current_profile()
        if profile is None:
            raise ValueError("No profile found")
        ap = profile.apply_profile or ApplyProfile()
        others = [a for a in ap.screening_answers if a.question.strip().lower() != question.strip().lower()]
        updated = ap.model_copy(update={
            "screening_answers": [*others, ScreeningAnswer(question=question, answer=answer)],
        })
        return await self.set_apply_profile(updated)
```

> Import `ApplyProfile`, `ScreeningAnswer` from `hiresense.profile.domain` at top of `services.py` if not already. Confirm `set_apply_profile` broadcasts the apply-profile across profile rows (it does — it's the same path the apply-profile card uses).

Add the route to `profile/api/routes.py` (near the existing `PUT /apply-profile`):

```python
from pydantic import BaseModel


class _AppendScreeningAnswer(BaseModel):
    question: str
    answer: str


@router.post("/apply-profile/screening-answers", response_model=CandidateProfile)
async def append_screening_answer(
    body: _AppendScreeningAnswer,
    service: ProfileService = Depends(get_profile_service),  # match existing dep name
) -> CandidateProfile:
    try:
        return await service.append_screening_answer(body.question, body.answer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

> Use the exact dependency + response symbols the existing `set_apply_profile` route uses (see lines around `PUT /apply-profile`). One request model per concern is fine here; if the repo insists on one-class-per-file for schemas, move `_AppendScreeningAnswer` into `profile/api/schemas.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/integration/test_profile_screening_answers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/profile/ backend/tests/integration/test_profile_screening_answers.py
git commit -m "feat(profile): append screening answer to the reusable answer bank"
```

---

# PHASE 3 — Frontend

## Task 11: Models + service methods

**Files:**
- Create: `frontend/src/app/pages/tracking/models/company-info.model.ts`
- Create: `frontend/src/app/pages/applications/models/screening-answer-draft.model.ts`
- Modify: `frontend/src/app/core/services/research.service.ts`
- Modify: `frontend/src/app/core/services/applications.service.ts`
- Modify: `frontend/src/app/core/services/profile.service.ts`
- Test: extend `research.service` / `applications.service` specs if they exist; otherwise a small new spec.

**Interfaces:**
- Produces: `CompanyInfo` interface; `ScreeningAnswerDraft` interface; `ResearchService.getCompanyInfo(name)`; `ApplicationsService.draftScreeningAnswer(id, question)`; `ProfileService.appendScreeningAnswer(question, answer)`.

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/app/core/services/applications.service.spec.ts (add a case)
it('posts a screening-answer draft request', () => {
  const svc = TestBed.inject(ApplicationsService);
  const http = TestBed.inject(HttpTestingController);
  svc.draftScreeningAnswer('app-1', 'Why us?').subscribe();
  const req = http.expectOne(`${environment.apiUrl}/applications/app-1/screening-answer`);
  expect(req.request.method).toBe('POST');
  expect(req.request.body).toEqual({ question: 'Why us?' });
  req.flush({ question: 'Why us?', answer: 'Because', language: 'en' });
});
```

> If `applications.service.spec.ts` has no `HttpTestingController` harness, copy the setup from `research.service.spec.ts` or any existing service spec.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --include "**/applications.service.spec.ts"`
Expected: FAIL (`draftScreeningAnswer` is not a function)

- [ ] **Step 3: Write minimal implementation**

```typescript
// frontend/src/app/pages/tracking/models/company-info.model.ts
export interface CompanyInfo {
  id: string | null;
  company_name: string;
  description: string | null;
  website: string | null;
  industry: string | null;
  size: string | null;
  logo_url: string | null;
  source: string;
  source_ref: string | null;
  created_at: string | null;
  updated_at: string | null;
}
```

```typescript
// frontend/src/app/pages/applications/models/screening-answer-draft.model.ts
export interface ScreeningAnswerDraft {
  question: string;
  answer: string;
  language: string;
}
```

Add to `research.service.ts`:

```typescript
import { CompanyInfo } from '../../pages/tracking/models/company-info.model';

  getCompanyInfo(companyName: string): Observable<CompanyInfo | null> {
    return this.http.get<CompanyInfo | null>(
      `${environment.apiUrl}/research/company-info/${encodeURIComponent(companyName)}`,
    );
  }
```

Add to `applications.service.ts`:

```typescript
import { ScreeningAnswerDraft } from '../../pages/applications/models/screening-answer-draft.model';

  draftScreeningAnswer(id: string, question: string): Observable<ScreeningAnswerDraft> {
    return this.http.post<ScreeningAnswerDraft>(`${this.base}/${id}/screening-answer`, { question });
  }
```

Add to `profile.service.ts` (match its existing base URL/inject style):

```typescript
  appendScreeningAnswer(question: string, answer: string): Observable<CandidateProfile> {
    return this.http.post<CandidateProfile>(
      `${environment.apiUrl}/profile/apply-profile/screening-answers`,
      { question, answer },
    );
  }
```

> Use the `CandidateProfile` model type already imported in `profile.service.ts`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --include "**/applications.service.spec.ts"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/tracking/models/company-info.model.ts frontend/src/app/pages/applications/models/screening-answer-draft.model.ts frontend/src/app/core/services/
git commit -m "feat(frontend): add company-info + screening-answer models and service methods"
```

---

## Task 12: Company-info card on the company page

**Files:**
- Create: `frontend/src/app/pages/company/components/company-info-card/company-info-card.component.ts`
- Create: `.../company-info-card.component.html`
- Create: `.../company-info-card.component.scss`
- Create: `.../company-info-card.component.spec.ts`
- Modify: `frontend/src/app/pages/company/company.component.ts` (import + template tag)
- Modify: `frontend/src/app/pages/company/company.component.html`

**Interfaces:**
- Consumes: `ResearchService.getCompanyInfo`, `ResearchService.research` (existing, for on-demand LLM research).
- Produces: `<app-company-info-card [company]="company()" />`.

- [ ] **Step 1: Write the failing test**

```typescript
// company-info-card.component.spec.ts
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { environment } from '../../../../../environments/environment';
import { CompanyInfoCardComponent } from './company-info-card.component';

describe('CompanyInfoCardComponent', () => {
  beforeEach(() => TestBed.configureTestingModule({
    imports: [CompanyInfoCardComponent],
    providers: [provideHttpClient(), provideHttpClientTesting()],
  }));

  it('loads cached company info on init', () => {
    const fixture = TestBed.createComponent(CompanyInfoCardComponent);
    fixture.componentRef.setInput('company', 'SeatGeek');
    fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    const req = http.expectOne(`${environment.apiUrl}/research/company-info/SeatGeek`);
    req.flush({ company_name: 'SeatGeek', description: 'Ticketing', website: null,
      id: null, industry: null, size: null, logo_url: null, source: 'getonboard',
      source_ref: null, created_at: null, updated_at: null });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Ticketing');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --include "**/company-info-card.component.spec.ts"`
Expected: FAIL (component does not exist)

- [ ] **Step 3: Write minimal implementation**

```typescript
// company-info-card.component.ts
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ResearchService } from '../../../../core/services/research.service';
import { CompanyInfo } from '../../../tracking/models/company-info.model';
import { CompanyResearch } from '../../../tracking/models/company-research.model';

@Component({
  selector: 'app-company-info-card',
  standalone: true,
  templateUrl: './company-info-card.component.html',
  styleUrl: './company-info-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CompanyInfoCardComponent implements OnInit {
  private research = inject(ResearchService);
  private destroyRef = inject(DestroyRef);

  company = input.required<string>();

  info = signal<CompanyInfo | null>(null);
  llmResearch = signal<CompanyResearch | null>(null);
  loading = signal(true);
  researching = signal(false);

  hasAnything = computed(() => this.info() !== null || this.llmResearch() !== null);

  ngOnInit(): void {
    this.research.getCompanyInfo(this.company())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (info) => { this.info.set(info); this.loading.set(false); },
        error: () => this.loading.set(false),
      });
  }

  runResearch(): void {
    if (this.researching()) return;
    this.researching.set(true);
    this.research.research({ company_name: this.company(), job_description: '' })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (r) => { this.llmResearch.set(r); this.researching.set(false); },
        error: () => this.researching.set(false),
      });
  }
}
```

```html
<!-- company-info-card.component.html -->
@if (!loading()) {
  <section class="company-info">
    @if (info(); as ci) {
      <h2>About {{ ci.company_name }}</h2>
      @if (ci.description) { <p>{{ ci.description }}</p> }
      @if (ci.website) { <a [href]="ci.website" target="_blank" rel="noopener">{{ ci.website }}</a> }
      @if (ci.industry) { <span class="tag">{{ ci.industry }}</span> }
    } @else if (llmResearch(); as r) {
      <h2>Company research</h2>
      <p><strong>Culture:</strong> {{ r.culture_summary }}</p>
      <p><strong>Tech stack:</strong> {{ r.tech_stack }}</p>
      <p><strong>Pros:</strong> {{ r.pros }}</p>
      <p><strong>Cons:</strong> {{ r.cons }}</p>
    } @else {
      <button type="button" (click)="runResearch()" [disabled]="researching()">
        {{ researching() ? 'Researching…' : 'Research company' }}
      </button>
    }
  </section>
}
```

Add minimal styles in the `.scss` (match existing card styling in the company page).

Integrate into `company.component.ts`: add `CompanyInfoCardComponent` to `imports`. In `company.component.html`, add below the header block (near the `<p>` with counts):

```html
<app-company-info-card [company]="company()" />
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --include "**/company-info-card.component.spec.ts"`
Then: `cd frontend && npm test -- --include "**/company.component.spec.ts"`
Expected: PASS (fix the existing company spec if the new child triggers an extra HTTP expectation — add the `company-info` GET to its harness).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/company/
git commit -m "feat(frontend): show company info/research on the company page"
```

---

## Task 13: Screening-question drafter card on the application page

**Files:**
- Create: `frontend/src/app/pages/applications/components/screening-question-card/screening-question-card.component.ts`
- Create: `.../screening-question-card.component.html`
- Create: `.../screening-question-card.component.scss`
- Create: `.../screening-question-card.component.spec.ts`
- Modify: `frontend/src/app/pages/applications/application-detail.component.ts` (import + tag)
- Modify: `frontend/src/app/pages/applications/application-detail.component.html`

**Interfaces:**
- Consumes: `ApplicationsService.draftScreeningAnswer`, `ProfileService.appendScreeningAnswer`.
- Produces: `<app-screening-question-card [applicationId]="..." />`.

- [ ] **Step 1: Write the failing test**

```typescript
// screening-question-card.component.spec.ts
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { environment } from '../../../../../environments/environment';
import { ScreeningQuestionCardComponent } from './screening-question-card.component';

describe('ScreeningQuestionCardComponent', () => {
  beforeEach(() => TestBed.configureTestingModule({
    imports: [ScreeningQuestionCardComponent],
    providers: [provideHttpClient(), provideHttpClientTesting()],
  }));

  it('drafts an answer for the typed question', () => {
    const fixture = TestBed.createComponent(ScreeningQuestionCardComponent);
    fixture.componentRef.setInput('applicationId', 'app-1');
    fixture.detectChanges();
    const cmp = fixture.componentInstance;
    cmp.question.set('Why us?');
    cmp.draft();
    const http = TestBed.inject(HttpTestingController);
    const req = http.expectOne(`${environment.apiUrl}/applications/app-1/screening-answer`);
    expect(req.request.body).toEqual({ question: 'Why us?' });
    req.flush({ question: 'Why us?', answer: 'Because X', language: 'en' });
    fixture.detectChanges();
    expect(cmp.answer()).toBe('Because X');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --include "**/screening-question-card.component.spec.ts"`
Expected: FAIL (component does not exist)

- [ ] **Step 3: Write minimal implementation**

```typescript
// screening-question-card.component.ts
import { ChangeDetectionStrategy, Component, DestroyRef, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ApplicationsService } from '../../../../core/services/applications.service';
import { ProfileService } from '../../../../core/services/profile.service';

@Component({
  selector: 'app-screening-question-card',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './screening-question-card.component.html',
  styleUrl: './screening-question-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ScreeningQuestionCardComponent {
  private applications = inject(ApplicationsService);
  private profile = inject(ProfileService);
  private destroyRef = inject(DestroyRef);

  applicationId = input.required<string>();

  question = signal('');
  answer = signal('');
  language = signal('');
  loading = signal(false);
  saved = signal(false);
  error = signal(false);

  draft(): void {
    const q = this.question().trim();
    if (!q || this.loading()) return;
    this.loading.set(true);
    this.error.set(false);
    this.saved.set(false);
    this.applications.draftScreeningAnswer(this.applicationId(), q)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (d) => { this.answer.set(d.answer); this.language.set(d.language); this.loading.set(false); },
        error: () => { this.error.set(true); this.loading.set(false); },
      });
  }

  copy(): void {
    void navigator.clipboard?.writeText(this.answer());
  }

  saveToBank(): void {
    const q = this.question().trim();
    const a = this.answer().trim();
    if (!q || !a) return;
    this.profile.appendScreeningAnswer(q, a)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ next: () => this.saved.set(true), error: () => this.error.set(true) });
  }
}
```

```html
<!-- screening-question-card.component.html -->
<section class="screening-card">
  <h3>Screening question</h3>
  <p class="hint">Draft an answer grounded in your profile, this job, and the company.</p>
  <textarea
    [ngModel]="question()"
    (ngModelChange)="question.set($event)"
    rows="3"
    placeholder="e.g. Why do you want to work here?"></textarea>
  <button type="button" (click)="draft()" [disabled]="loading() || !question().trim()">
    {{ loading() ? 'Drafting…' : 'Draft answer' }}
  </button>

  @if (error()) { <p class="error">Couldn't draft an answer. Try again.</p> }

  @if (answer()) {
    <div class="answer">
      <p>{{ answer() }}</p>
      <div class="actions">
        <button type="button" (click)="copy()">Copy</button>
        <button type="button" (click)="saveToBank()">{{ saved() ? 'Saved ✓' : 'Save to answer bank' }}</button>
      </div>
    </div>
  }
</section>
```

Integrate into `application-detail.component.ts`: add `ScreeningQuestionCardComponent` to `imports`; in the HTML add, in a sensible section of the detail page:

```html
<app-screening-question-card [applicationId]="applicationId" />
```

> Use the application id the component already has — the `:id` route param it loads, or the loaded aggregate's `.id`. Read `application-detail.component.ts` to use the exact signal/property name (e.g. `id()` or `application()?.id`). Pass a guaranteed-non-null string (guard with `@if` on the loaded aggregate if needed).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --include "**/screening-question-card.component.spec.ts"`
Then: `cd frontend && npm test -- --include "**/application-detail.component.spec.ts"`
Expected: PASS (adjust the detail spec harness if the new child needs no extra HTTP on init — it doesn't, so no new expectations).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/applications/
git commit -m "feat(frontend): add screening-question answer drafter to application page"
```

---

# Final verification

- [ ] **Backend full suite:** `cd backend && uv run python -m pytest` → green (note the known spurious autopilot-default FAIL from local `.env`; ignore per project memory).
- [ ] **Backend lint:** `cd backend && uv run ruff check .` → clean (CI runs `ruff check`, not `ruff format`).
- [ ] **Frontend tests:** `cd frontend && npm test` → green.
- [ ] **Frontend lint (CI runs this; `npm test`/`build` skip it):** `cd frontend && npx ng lint` → clean.
- [ ] **Apply the migration to the dev DB** (CI runs on SQLite, so merged migrations don't auto-upgrade): `cd backend && uv run python -m alembic upgrade head`.
- [ ] **Manual smoke:** run an ingestion of GetOnBoard, confirm a `company_info` row appears; open a GetOnBoard company's page and an application detail page; draft an answer to a Spanish question and confirm the answer comes back in Spanish; Save to bank and confirm it appears on the profile apply-profile card.

---

## Notes / risks

- **GetOnBoard company payload keys** (`long_description`, `website`, `logo`, `category`, `size`) are best-effort; confirm against a live `/companies/{id}` response and adjust the `.get()` keys in `_sink_company`. Missing keys degrade to `null`, never errors.
- **Grounding is cache-only** by design — the drafter never triggers an LLM research call (keeps drafting cheap/fast). For companies with neither portal facts nor cached research, answers rely on profile + JD alone; the company page's **Research company** button populates the cache for next time.
- **Build order:** Task 6 moves `build_research` above `build_ingestion`/`build_applications` in `main.py` and removes the old later block. Double-check no code between the old and new positions depends on `app.state.research` before it's set (only `outreach` uses it, and it's built after both positions).
