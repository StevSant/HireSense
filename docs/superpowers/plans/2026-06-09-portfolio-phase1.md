# Portfolio Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** New `portfolio` bounded context that syncs projects from the candidate's Supabase portfolio into HireSense and enriches the matching profile with them, plus a profile-page card.

**Architecture:** Standard hexagonal module (mirrors `autohunt`): `api → domain ← infrastructure`, `PortfolioSourcePort` Protocol with `SupabasePortfolioAdapter` as first implementation, snapshot persisted in `portfolio_projects` table, wired only in `bootstrap/portfolio.py`. Enrichment reaches ingestion's `_gather_profile` via an optional FastAPI dependency (None ⇒ exactly today's behavior). Spec: `docs/superpowers/specs/2026-06-09-external-sources-integration-design.md` (Part A, Phase 1).

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy sync sessions (+ `asyncio.to_thread` at async boundaries) / Alembic; Angular 21 standalone + signals / Vitest.

**Working directory:** `C:\Users\Bryan\worktrees\hiresense-portfolio` (branch `feat/portfolio-integration`). Backend commands run from `backend/`, frontend from `frontend/`. **Windows quirk:** always `uv run python -m pytest` / `uv run python -m alembic` (never bare `uv run pytest`).

**Conventions that apply to every task** (from CLAUDE.md / audit PR #83):
- One class/function per file; every package `__init__.py` re-exports its public symbols; import from the package, not the file.
- No hardcoded values — new knobs go in `config.py` + `.env` + `.env.example`.
- Conventional commits `type(portfolio): …`, each ending with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Router-level `require_auth`; expensive endpoints get `enforce_expensive_rate_limit`.
- Unit tests that mount routers override `require_auth` via `app.dependency_overrides[require_auth] = lambda: "test-user"`.

---

### Task 1: Config settings + env files

**Files:**
- Modify: `backend/src/hiresense/config.py`
- Modify: `backend/.env`, `backend/.env.example`
- Test: `backend/tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test** — append to `backend/tests/unit/test_config.py`:

```python
def test_portfolio_settings_defaults_and_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("PORTFOLIO_SOURCES", "supabase,github")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.portfolio_sources == ["supabase", "github"]
    assert settings.portfolio_supabase_url == ""
    assert settings.portfolio_profile_char_cap == 1200
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `backend/`): `uv run python -m pytest tests/unit/test_config.py::test_portfolio_settings_defaults_and_parsing -q`
Expected: FAIL (`portfolio_sources` attribute error / validation error).

- [ ] **Step 3: Implement.** In `config.py`:

(a) add `"portfolio_sources"` to `_CommaSeparatedMixin._COMMA_FIELDS`;
(b) add a settings block after the `# Batch processing` section:

```python
    # --- Portfolio (external proof-of-work sources) ---
    # Comma-separated adapter list (mirrors enabled_job_sources). Empty list
    # disables the portfolio module entirely: no provider is built and every
    # consumer (enrichment, endpoints, frontend card) degrades gracefully.
    portfolio_sources: list[str] = []
    # Supabase PostgREST base URL + public anon key (read-only by RLS) for the
    # "supabase" source adapter.
    portfolio_supabase_url: str = ""
    portfolio_supabase_anon_key: str = ""
    # Char cap for the "Portfolio projects" block appended to the matching
    # profile summary.
    portfolio_profile_char_cap: int = 1200
```

- [ ] **Step 4: Run the test again** — expected: PASS.

- [ ] **Step 5: Update env files.**

`backend/.env.example` — append:

```
# === Portfolio (external proof-of-work sources) ===
# Comma-separated source adapters. Empty disables the portfolio module.
PORTFOLIO_SOURCES=
# Supabase PostgREST base URL + public anon key for the "supabase" source.
PORTFOLIO_SUPABASE_URL=
PORTFOLIO_SUPABASE_ANON_KEY=
# Char cap for the profile-enrichment text block.
PORTFOLIO_PROFILE_CHAR_CAP=1200
```

`backend/.env` — same block but with the real values: `PORTFOLIO_SOURCES=supabase`, and copy `PORTFOLIO_SUPABASE_URL` / `PORTFOLIO_SUPABASE_ANON_KEY` from the portfolio repo's frontend environment (`C:\Users\Bryan\OneDrive\Desktop\Bryan\Dev\Personal\StevSant26\frontend\src\environments\environment.ts` — the `supabaseUrl` / `supabaseKey` constants; the anon key is public by design).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/config.py backend/.env.example backend/tests/unit/test_config.py
git commit -m "feat(portfolio): add portfolio source settings"
```

---

### Task 2: Domain models + ports

**Files:**
- Create: `backend/src/hiresense/portfolio/__init__.py` (empty docstring module)
- Create: `backend/src/hiresense/portfolio/domain/project_text.py`
- Create: `backend/src/hiresense/portfolio/domain/portfolio_project.py`
- Create: `backend/src/hiresense/portfolio/domain/sync_result.py`
- Create: `backend/src/hiresense/portfolio/domain/__init__.py`
- Create: `backend/src/hiresense/portfolio/ports/portfolio_source.py`
- Create: `backend/src/hiresense/portfolio/ports/projects_repository.py`
- Create: `backend/src/hiresense/portfolio/ports/__init__.py`
- Test: `backend/tests/unit/portfolio/test_models.py` (+ empty `backend/tests/unit/portfolio/__init__.py`)

- [ ] **Step 1: Write the failing test** — `backend/tests/unit/portfolio/test_models.py`:

```python
from hiresense.portfolio.domain import PortfolioProject, ProjectText


def _project(**over) -> PortfolioProject:
    base = dict(
        id="p1",
        source="supabase",
        source_key="hiresense",
        tech=["python", "angular"],
        translations={
            "en": ProjectText(title="HireSense", description="AI job hunting"),
            "es": ProjectText(title="HireSense ES", description="Caza de empleo con IA"),
        },
    )
    base.update(over)
    return PortfolioProject(**base)


def test_text_for_prefers_requested_language() -> None:
    assert _project().text_for("es").title == "HireSense ES"


def test_text_for_falls_back_to_english_then_any() -> None:
    assert _project().text_for("fr").title == "HireSense"
    only_es = _project(translations={"es": ProjectText(title="Solo ES")})
    assert only_es.text_for("fr").title == "Solo ES"


def test_text_for_none_when_no_translations() -> None:
    assert _project(translations={}).text_for("en") is None
```

- [ ] **Step 2: Run to verify it fails** — `uv run python -m pytest tests/unit/portfolio -q` → FAIL (module not found).

- [ ] **Step 3: Implement.**

`portfolio/__init__.py`:

```python
"""Portfolio bounded context — external proof-of-work sources."""
```

`portfolio/domain/project_text.py`:

```python
from __future__ import annotations

from pydantic import BaseModel


class ProjectText(BaseModel):
    """One language's title/description for a portfolio project."""

    title: str
    description: str | None = None
```

`portfolio/domain/portfolio_project.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field

from hiresense.portfolio.domain.project_text import ProjectText


class PortfolioProject(BaseModel):
    """A normalized project from any portfolio source adapter."""

    id: str
    source: str
    source_key: str
    url: str | None = None
    demo_url: str | None = None
    pinned: bool = False
    position: int | None = None
    tech: list[str] = Field(default_factory=list)
    translations: dict[str, ProjectText] = Field(default_factory=dict)

    def text_for(self, language: str, fallback: str = "en") -> ProjectText | None:
        """Translation for `language`, else `fallback`, else any, else None."""
        return (
            self.translations.get(language)
            or self.translations.get(fallback)
            or next(iter(self.translations.values()), None)
        )
```

`portfolio/domain/sync_result.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SyncResult(BaseModel):
    """Outcome of one portfolio sync run across all configured sources."""

    counts_by_source: dict[str, int] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)
    synced_at: datetime
```

`portfolio/domain/__init__.py`:

```python
from hiresense.portfolio.domain.portfolio_project import PortfolioProject
from hiresense.portfolio.domain.project_text import ProjectText
from hiresense.portfolio.domain.sync_result import SyncResult

__all__ = ["PortfolioProject", "ProjectText", "SyncResult"]
```

`portfolio/ports/portfolio_source.py`:

```python
from __future__ import annotations

from typing import Protocol

from hiresense.portfolio.domain import PortfolioProject


class PortfolioSourcePort(Protocol):
    """A read-only external source of portfolio projects."""

    def source_name(self) -> str: ...

    async def fetch_projects(self) -> list[PortfolioProject]: ...
```

`portfolio/ports/projects_repository.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from hiresense.portfolio.domain import PortfolioProject


class PortfolioProjectsRepositoryPort(Protocol):
    """Snapshot store for synced portfolio projects."""

    def replace_source(self, source: str, projects: list[PortfolioProject]) -> int:
        """Atomically replace `source`'s slice of the snapshot; returns count."""
        ...

    def list_all(self) -> list[PortfolioProject]: ...

    def last_synced_at(self) -> datetime | None: ...
```

`portfolio/ports/__init__.py`:

```python
from hiresense.portfolio.ports.portfolio_source import PortfolioSourcePort
from hiresense.portfolio.ports.projects_repository import PortfolioProjectsRepositoryPort

__all__ = ["PortfolioProjectsRepositoryPort", "PortfolioSourcePort"]
```

- [ ] **Step 4: Run tests** — `uv run python -m pytest tests/unit/portfolio -q` → PASS. Also `uv run ruff check src/hiresense/portfolio tests/unit/portfolio`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/portfolio backend/tests/unit/portfolio
git commit -m "feat(portfolio): domain models and ports"
```

---

### Task 3: `portfolio_profile_text` (pure enrichment text builder)

**Files:**
- Create: `backend/src/hiresense/portfolio/domain/profile_text.py`
- Modify: `backend/src/hiresense/portfolio/domain/__init__.py`
- Test: `backend/tests/unit/portfolio/test_profile_text.py`

- [ ] **Step 1: Write the failing test:**

```python
from hiresense.portfolio.domain import PortfolioProject, ProjectText, portfolio_profile_text


def _project(key: str, *, pinned=False, position=None, tech=None, title=None, desc=None):
    return PortfolioProject(
        id=key,
        source="supabase",
        source_key=key,
        pinned=pinned,
        position=position,
        tech=tech or [],
        translations={"en": ProjectText(title=title or key, description=desc)},
    )


def test_formats_title_tech_and_first_description_line() -> None:
    text = portfolio_profile_text(
        [_project("hs", tech=["python", "fastapi"], title="HireSense", desc="AI job hunt.\nMore.")],
        language="en",
        char_cap=500,
    )
    assert text.startswith("Portfolio projects:")
    assert "- HireSense [python, fastapi]: AI job hunt." in text
    assert "More." not in text


def test_pinned_projects_come_first_then_position() -> None:
    text = portfolio_profile_text(
        [_project("b", position=2), _project("a", position=1), _project("p", pinned=True, position=9)],
        language="en",
        char_cap=500,
    )
    lines = text.splitlines()
    assert [ln[2:] for ln in lines[1:]] == ["p", "a", "b"]


def test_respects_char_cap_and_empty_input() -> None:
    assert portfolio_profile_text([], language="en", char_cap=100) == ""
    text = portfolio_profile_text([_project("x", desc="y" * 500)], language="en", char_cap=50)
    assert len(text) <= 50
```

- [ ] **Step 2: Run to verify it fails** — `uv run python -m pytest tests/unit/portfolio/test_profile_text.py -q` → FAIL (import error).

- [ ] **Step 3: Implement** `portfolio/domain/profile_text.py`:

```python
from __future__ import annotations

from hiresense.portfolio.domain.portfolio_project import PortfolioProject

_UNPOSITIONED = 1_000_000


def portfolio_profile_text(
    projects: list[PortfolioProject], *, language: str, char_cap: int
) -> str:
    """Compact 'Portfolio projects' block for profile enrichment.

    Pinned projects first, then by position; one line per project
    (title [tech]: first description line); hard-capped at `char_cap`.
    """
    if not projects:
        return ""
    ordered = sorted(
        projects,
        key=lambda p: (not p.pinned, p.position if p.position is not None else _UNPOSITIONED),
    )
    lines = ["Portfolio projects:"]
    for project in ordered:
        text = project.text_for(language)
        if text is None:
            continue
        line = f"- {text.title}"
        if project.tech:
            line += f" [{', '.join(project.tech)}]"
        first_desc_line = (text.description or "").strip().splitlines()
        if first_desc_line and first_desc_line[0]:
            line += f": {first_desc_line[0]}"
        lines.append(line)
    return "\n".join(lines)[:char_cap]
```

Add to `domain/__init__.py`: `from hiresense.portfolio.domain.profile_text import portfolio_profile_text` and `"portfolio_profile_text"` in `__all__`.

- [ ] **Step 4: Run** — `uv run python -m pytest tests/unit/portfolio -q` → PASS; ruff clean.

- [ ] **Step 5: Commit** — `git commit -m "feat(portfolio): profile enrichment text builder"` (add both files + test).

---

### Task 4: ORM + repository + registry + migration

**Files:**
- Create: `backend/src/hiresense/portfolio/infrastructure/orm.py`
- Create: `backend/src/hiresense/portfolio/infrastructure/repository.py`
- Create: `backend/src/hiresense/portfolio/infrastructure/__init__.py`
- Modify: `backend/src/hiresense/infrastructure/registry.py`
- Create: migration via autogenerate
- Test: `backend/tests/unit/portfolio/test_repository.py`

- [ ] **Step 1: Write the failing test** (StaticPool sqlite — required because repo calls run via `to_thread` in prod paths):

```python
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.portfolio.domain import PortfolioProject, ProjectText
from hiresense.portfolio.infrastructure import PortfolioProjectOrm  # noqa: F401 (registers table)
from hiresense.portfolio.infrastructure import PortfolioProjectsRepository


@pytest.fixture
def repo():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield PortfolioProjectsRepository(session_factory=factory)
    Base.metadata.drop_all(engine)


def _project(key: str, source: str = "supabase") -> PortfolioProject:
    return PortfolioProject(
        id=f"id-{source}-{key}",
        source=source,
        source_key=key,
        tech=["python"],
        translations={"en": ProjectText(title=key.title(), description="d")},
    )


def test_replace_source_inserts_and_lists_roundtrip(repo) -> None:
    count = repo.replace_source("supabase", [_project("a"), _project("b")])
    assert count == 2
    stored = {p.source_key: p for p in repo.list_all()}
    assert set(stored) == {"a", "b"}
    assert stored["a"].translations["en"].title == "A"
    assert stored["a"].tech == ["python"]


def test_replace_source_only_touches_its_own_slice(repo) -> None:
    repo.replace_source("supabase", [_project("a")])
    repo.replace_source("github", [_project("r", source="github")])
    repo.replace_source("supabase", [_project("c")])
    by_source = {(p.source, p.source_key) for p in repo.list_all()}
    assert by_source == {("supabase", "c"), ("github", "r")}


def test_last_synced_at_none_then_set(repo) -> None:
    assert repo.last_synced_at() is None
    repo.replace_source("supabase", [_project("a")])
    assert isinstance(repo.last_synced_at(), datetime)
```

- [ ] **Step 2: Run to verify it fails** — `uv run python -m pytest tests/unit/portfolio/test_repository.py -q` → FAIL.

- [ ] **Step 3: Implement.**

`portfolio/infrastructure/orm.py`:

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure import JSONB_OR_JSON
from hiresense.infrastructure.database import Base


class PortfolioProjectOrm(Base):
    """Snapshot row for one synced portfolio project (replaced per sync)."""

    __tablename__ = "portfolio_projects"
    __table_args__ = (
        UniqueConstraint("source", "source_key", name="ux_portfolio_projects_source_key"),
        Index("ix_portfolio_projects_source", "source"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_key: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    demo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tech: Mapped[list] = mapped_column(JSONB_OR_JSON, default=list)
    translations: Mapped[dict] = mapped_column(JSONB_OR_JSON, default=dict)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

`portfolio/infrastructure/repository.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select

from hiresense.portfolio.domain import PortfolioProject, ProjectText
from hiresense.portfolio.infrastructure.orm import PortfolioProjectOrm


def _to_orm(project: PortfolioProject, synced_at: datetime) -> PortfolioProjectOrm:
    return PortfolioProjectOrm(
        id=project.id,
        source=project.source,
        source_key=project.source_key,
        url=project.url,
        demo_url=project.demo_url,
        pinned=project.pinned,
        position=project.position,
        tech=list(project.tech),
        translations={k: v.model_dump() for k, v in project.translations.items()},
        synced_at=synced_at,
    )


def _to_domain(row: PortfolioProjectOrm) -> PortfolioProject:
    return PortfolioProject(
        id=row.id,
        source=row.source,
        source_key=row.source_key,
        url=row.url,
        demo_url=row.demo_url,
        pinned=row.pinned,
        position=row.position,
        tech=list(row.tech or []),
        translations={k: ProjectText(**v) for k, v in (row.translations or {}).items()},
    )


class PortfolioProjectsRepository:
    """SQL snapshot store; replace_source is atomic per source slice."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def replace_source(self, source: str, projects: list[PortfolioProject]) -> int:
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            session.execute(
                delete(PortfolioProjectOrm).where(PortfolioProjectOrm.source == source)
            )
            for project in projects:
                session.add(_to_orm(project, now))
            session.commit()
        return len(projects)

    def list_all(self) -> list[PortfolioProject]:
        with self._session_factory() as session:
            rows = session.scalars(select(PortfolioProjectOrm)).all()
            return [_to_domain(r) for r in rows]

    def last_synced_at(self) -> datetime | None:
        with self._session_factory() as session:
            return session.scalar(select(func.max(PortfolioProjectOrm.synced_at)))
```

`portfolio/infrastructure/__init__.py`:

```python
from hiresense.portfolio.infrastructure.orm import PortfolioProjectOrm
from hiresense.portfolio.infrastructure.repository import PortfolioProjectsRepository

__all__ = ["PortfolioProjectOrm", "PortfolioProjectsRepository"]
```

`infrastructure/registry.py` — add (alphabetical position, after `preference`):

```python
from hiresense.portfolio.infrastructure import PortfolioProjectOrm  # noqa: F401
```

- [ ] **Step 4: Run tests** — `uv run python -m pytest tests/unit/portfolio tests/unit/test_orm_registry.py -q` → PASS.

- [ ] **Step 5: Generate the migration** (needs the compose DB):

```bash
docker compose up -d db   # from repo root, if not already running
cd backend
uv run python -m alembic upgrade head
uv run python -m alembic revision --autogenerate -m "add portfolio_projects"
```

Inspect the generated file under `backend/alembic/versions/` — it must contain ONLY the `portfolio_projects` table (+ its index/constraint). Then:

```bash
uv run python -m alembic upgrade head
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/portfolio/infrastructure backend/src/hiresense/infrastructure/registry.py backend/alembic/versions backend/tests/unit/portfolio/test_repository.py
git commit -m "feat(portfolio): projects snapshot repository and migration"
```

---

### Task 5: Supabase source adapter

**Files:**
- Create: `backend/src/hiresense/portfolio/adapters/supabase_portfolio.py`
- Create: `backend/src/hiresense/portfolio/adapters/__init__.py`
- Test: `backend/tests/unit/portfolio/test_supabase_adapter.py`

- [ ] **Step 1: Write the failing test** (fake HTTP client, canned PostgREST payloads):

```python
import pytest


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._payload


class _FakeHttp:
    def __init__(self, payload_by_path: dict):
        self._payloads = payload_by_path
        self.calls: list[tuple[str, dict]] = []

    async def get(self, url, headers=None, params=None):
        self.calls.append((url, dict(params or {})))
        for path, payload in self._payloads.items():
            if path in url:
                return _FakeResponse(payload)
        raise AssertionError(f"unexpected url {url}")


_PAYLOADS = {
    "/rest/v1/language": [{"id": 1, "code": "en"}, {"id": 2, "code": "es"}],
    "/rest/v1/project": [
        {
            "id": 10,
            "code": "hiresense",
            "url": "https://github.com/x/hiresense",
            "demo_url": None,
            "is_pinned": True,
            "position": 1,
            "project_translation": [
                {"language_id": 1, "title": "HireSense", "description": "AI job hunting"},
                {"language_id": 2, "title": "HireSense ES", "description": "Caza de empleo"},
            ],
        },
        {
            "id": 11,
            "code": "untranslated",
            "url": None,
            "demo_url": None,
            "is_pinned": False,
            "position": None,
            "project_translation": [],
        },
    ],
    "/rest/v1/skill_usages": [
        {"source_id": 10, "skill": {"code": "python"}},
        {"source_id": 10, "skill": {"code": "angular"}},
        {"source_id": 99, "skill": {"code": "elsewhere"}},
        {"source_id": 10, "skill": None},
    ],
}


@pytest.mark.asyncio
async def test_fetch_projects_normalizes_translations_and_tech() -> None:
    from hiresense.portfolio.adapters import SupabasePortfolioAdapter

    http = _FakeHttp(_PAYLOADS)
    adapter = SupabasePortfolioAdapter(
        http_client=http, base_url="https://xyz.supabase.co", anon_key="anon"
    )
    assert adapter.source_name() == "supabase"
    projects = await adapter.fetch_projects()

    assert len(projects) == 1  # untranslated project is dropped
    project = projects[0]
    assert project.source == "supabase"
    assert project.source_key == "hiresense"
    assert project.pinned is True
    assert project.tech == ["angular", "python"]
    assert project.translations["es"].title == "HireSense ES"


@pytest.mark.asyncio
async def test_fetch_projects_sends_auth_headers_and_filters() -> None:
    from hiresense.portfolio.adapters import SupabasePortfolioAdapter

    captured_headers = {}

    class _Http(_FakeHttp):
        async def get(self, url, headers=None, params=None):
            captured_headers.update(headers or {})
            return await super().get(url, headers=headers, params=params)

    http = _Http(_PAYLOADS)
    adapter = SupabasePortfolioAdapter(
        http_client=http, base_url="https://xyz.supabase.co", anon_key="anon"
    )
    await adapter.fetch_projects()

    assert captured_headers["apikey"] == "anon"
    assert captured_headers["Authorization"] == "Bearer anon"
    project_call = next(c for c in http.calls if "/rest/v1/project" in c[0])
    assert project_call[1]["is_archived"] == "eq.false"
```

- [ ] **Step 2: Run to verify it fails** — `uv run python -m pytest tests/unit/portfolio/test_supabase_adapter.py -q` → FAIL.

- [ ] **Step 3: Implement** `portfolio/adapters/supabase_portfolio.py`:

```python
from __future__ import annotations

import uuid
from typing import Any

from hiresense.portfolio.domain import PortfolioProject, ProjectText


class SupabasePortfolioAdapter:
    """Reads projects from a Supabase-backed portfolio via PostgREST.

    Relies on the portfolio's public-read RLS for project / project_translation /
    skill_usages / language; the anon key is sufficient.
    """

    def __init__(self, http_client: Any, base_url: str, anon_key: str) -> None:
        self._http = http_client
        self._base = base_url.rstrip("/")
        self._key = anon_key

    def source_name(self) -> str:
        return "supabase"

    async def _get(self, path: str, params: dict[str, str]) -> Any:
        response = await self._http.get(
            f"{self._base}{path}",
            headers={"apikey": self._key, "Authorization": f"Bearer {self._key}"},
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def fetch_projects(self) -> list[PortfolioProject]:
        languages = await self._get("/rest/v1/language", {"select": "id,code"})
        code_by_language_id = {row["id"]: row["code"] for row in languages}

        rows = await self._get(
            "/rest/v1/project",
            {
                "select": "id,code,url,demo_url,is_pinned,position,"
                "project_translation(language_id,title,description)",
                "is_archived": "eq.false",
            },
        )
        usages = await self._get(
            "/rest/v1/skill_usages",
            {"select": "source_id,skill(code)", "source_type": "eq.project", "is_archived": "eq.false"},
        )

        tech_by_project: dict[int, list[str]] = {}
        for usage in usages:
            skill = usage.get("skill") or {}
            code = skill.get("code")
            if code:
                tech_by_project.setdefault(usage["source_id"], []).append(code)

        projects: list[PortfolioProject] = []
        for row in rows:
            translations: dict[str, ProjectText] = {}
            for tr in row.get("project_translation") or []:
                code = code_by_language_id.get(tr["language_id"])
                if code:
                    translations[code] = ProjectText(
                        title=tr["title"], description=tr.get("description")
                    )
            if not translations:
                continue  # nothing presentable — skip
            projects.append(
                PortfolioProject(
                    id=str(uuid.uuid4()),
                    source=self.source_name(),
                    source_key=row["code"],
                    url=row.get("url"),
                    demo_url=row.get("demo_url"),
                    pinned=bool(row.get("is_pinned")),
                    position=row.get("position"),
                    tech=sorted(tech_by_project.get(row["id"], [])),
                    translations=translations,
                )
            )
        return projects
```

`portfolio/adapters/__init__.py`:

```python
from hiresense.portfolio.adapters.supabase_portfolio import SupabasePortfolioAdapter

__all__ = ["SupabasePortfolioAdapter"]
```

- [ ] **Step 4: Run** — `uv run python -m pytest tests/unit/portfolio -q` → PASS; ruff clean.

- [ ] **Step 5: Commit** — `git commit -m "feat(portfolio): Supabase PostgREST source adapter"`.

---

### Task 6: Sync service

**Files:**
- Create: `backend/src/hiresense/portfolio/domain/sync_service.py`
- Modify: `backend/src/hiresense/portfolio/domain/__init__.py`
- Test: `backend/tests/unit/portfolio/test_sync_service.py`

- [ ] **Step 1: Write the failing test:**

```python
import pytest

from hiresense.portfolio.domain import PortfolioProject, PortfolioSyncService, ProjectText


def _project(key: str, source: str) -> PortfolioProject:
    return PortfolioProject(
        id=key, source=source, source_key=key,
        translations={"en": ProjectText(title=key)},
    )


class _FakeSource:
    def __init__(self, name: str, projects=None, error: Exception | None = None):
        self._name, self._projects, self._error = name, projects or [], error

    def source_name(self) -> str:
        return self._name

    async def fetch_projects(self):
        if self._error:
            raise self._error
        return self._projects


class _FakeRepo:
    def __init__(self):
        self.slices: dict[str, list] = {}

    def replace_source(self, source, projects):
        self.slices[source] = projects
        return len(projects)


@pytest.mark.asyncio
async def test_sync_replaces_each_sources_slice() -> None:
    repo = _FakeRepo()
    service = PortfolioSyncService(
        sources=[_FakeSource("supabase", [_project("a", "supabase")])], repository=repo
    )
    result = await service.sync()
    assert result.counts_by_source == {"supabase": 1}
    assert result.errors == {}
    assert [p.source_key for p in repo.slices["supabase"]] == ["a"]


@pytest.mark.asyncio
async def test_failing_source_is_isolated() -> None:
    repo = _FakeRepo()
    service = PortfolioSyncService(
        sources=[
            _FakeSource("supabase", error=RuntimeError("boom")),
            _FakeSource("github", [_project("r", "github")]),
        ],
        repository=repo,
    )
    result = await service.sync()
    assert result.counts_by_source == {"github": 1}
    assert "boom" in result.errors["supabase"]
    assert "supabase" not in repo.slices  # previous slice untouched
```

- [ ] **Step 2: Run to verify it fails** — FAIL (import error).

- [ ] **Step 3: Implement** `portfolio/domain/sync_service.py`:

```python
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from hiresense.portfolio.domain.sync_result import SyncResult
from hiresense.portfolio.ports import PortfolioProjectsRepositoryPort

logger = logging.getLogger(__name__)


class PortfolioSyncService:
    """Fetches every configured source and replaces its snapshot slice.

    Per-source isolation: a failing source keeps its previous slice and is
    reported in SyncResult.errors; the other sources still sync.
    """

    def __init__(self, sources: list[Any], repository: PortfolioProjectsRepositoryPort) -> None:
        self._sources = sources
        self._repository = repository

    async def sync(self) -> SyncResult:
        counts: dict[str, int] = {}
        errors: dict[str, str] = {}
        for source in self._sources:
            name = source.source_name()
            try:
                projects = await source.fetch_projects()
                counts[name] = await asyncio.to_thread(
                    self._repository.replace_source, name, projects
                )
            except Exception as exc:
                logger.exception("Portfolio sync failed for source %s", name)
                errors[name] = str(exc)
        return SyncResult(
            counts_by_source=counts, errors=errors, synced_at=datetime.now(timezone.utc)
        )
```

Add `PortfolioSyncService` to `domain/__init__.py` imports and `__all__`.

- [ ] **Step 4: Run** — PASS; ruff clean.
- [ ] **Step 5: Commit** — `git commit -m "feat(portfolio): multi-source sync service"`.

---

### Task 7: Enrichment service

**Files:**
- Create: `backend/src/hiresense/portfolio/domain/enrichment_service.py`
- Modify: `backend/src/hiresense/portfolio/domain/__init__.py`
- Test: `backend/tests/unit/portfolio/test_enrichment_service.py`

- [ ] **Step 1: Write the failing test:**

```python
import pytest

from hiresense.portfolio.domain import (
    PortfolioEnrichmentService,
    PortfolioProject,
    ProjectText,
)


class _FakeRepo:
    def __init__(self, projects):
        self._projects = projects

    def list_all(self):
        return self._projects


def _project(key: str, tech: list[str]) -> PortfolioProject:
    return PortfolioProject(
        id=key, source="supabase", source_key=key, tech=tech,
        translations={"en": ProjectText(title=key.title(), description="d")},
    )


@pytest.mark.asyncio
async def test_enrichment_unions_tech_and_builds_text() -> None:
    service = PortfolioEnrichmentService(
        repository=_FakeRepo([_project("a", ["Python", "angular"]), _project("b", ["python"])]),
        language="en",
        char_cap=500,
    )
    skills, text = await service.enrichment()
    assert skills == ["Python", "angular", "python"]  # union, sorted, case preserved
    assert text.startswith("Portfolio projects:")
    assert "- A [Python, angular]: d" in text


@pytest.mark.asyncio
async def test_enrichment_empty_snapshot() -> None:
    service = PortfolioEnrichmentService(repository=_FakeRepo([]), language="en", char_cap=500)
    assert await service.enrichment() == ([], "")
```

- [ ] **Step 2: Run to verify it fails** — FAIL.

- [ ] **Step 3: Implement** `portfolio/domain/enrichment_service.py`:

```python
from __future__ import annotations

import asyncio

from hiresense.portfolio.domain.profile_text import portfolio_profile_text
from hiresense.portfolio.ports import PortfolioProjectsRepositoryPort


class PortfolioEnrichmentService:
    """Produces the (extra skills, extra summary text) pair consumed by the
    ingestion/matching profile assembly. Empty snapshot ⇒ ([], "")."""

    def __init__(
        self,
        repository: PortfolioProjectsRepositoryPort,
        *,
        language: str,
        char_cap: int,
    ) -> None:
        self._repository = repository
        self._language = language
        self._char_cap = char_cap

    async def enrichment(self) -> tuple[list[str], str]:
        projects = await asyncio.to_thread(self._repository.list_all)
        if not projects:
            return [], ""
        skills = sorted({tech for project in projects for tech in project.tech})
        text = portfolio_profile_text(projects, language=self._language, char_cap=self._char_cap)
        return skills, text
```

Add `PortfolioEnrichmentService` to `domain/__init__.py`.

- [ ] **Step 4: Run** — PASS. **Step 5: Commit** — `git commit -m "feat(portfolio): profile enrichment service"`.

---

### Task 8: API — provider, dependencies, routes

**Files:**
- Create: `backend/src/hiresense/portfolio/api/provider.py`
- Create: `backend/src/hiresense/portfolio/api/dependencies.py`
- Create: `backend/src/hiresense/portfolio/api/routes.py`
- Create: `backend/src/hiresense/portfolio/api/__init__.py`
- Test: `backend/tests/unit/portfolio/test_routes.py`

- [ ] **Step 1: Write the failing test:**

```python
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.portfolio.api import router
from hiresense.portfolio.api.dependencies import get_projects_repository, get_sync_service
from hiresense.portfolio.domain import PortfolioProject, ProjectText, SyncResult


def _project(key: str) -> PortfolioProject:
    return PortfolioProject(
        id=key, source="supabase", source_key=key,
        translations={"en": ProjectText(title=key)},
    )


class _FakeSync:
    def __init__(self, result: SyncResult):
        self._result = result

    async def sync(self) -> SyncResult:
        return self._result


class _FakeRepo:
    def __init__(self, projects, last):
        self._projects, self._last = projects, last

    def list_all(self):
        return self._projects

    def last_synced_at(self):
        return self._last


def _app(sync=None, repo=None) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_sync_service] = lambda: sync
    app.dependency_overrides[get_projects_repository] = lambda: repo
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_requires_auth_without_token() -> None:
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        assert (await client.get("/portfolio/projects")).status_code == 401


@pytest.mark.asyncio
async def test_sync_503_when_unconfigured() -> None:
    app = _app(sync=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        assert (await client.post("/portfolio/sync")).status_code == 503


@pytest.mark.asyncio
async def test_sync_returns_result() -> None:
    result = SyncResult(
        counts_by_source={"supabase": 3}, errors={}, synced_at=datetime.now(timezone.utc)
    )
    app = _app(sync=_FakeSync(result))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post("/portfolio/sync")
    assert resp.status_code == 200
    assert resp.json()["counts_by_source"] == {"supabase": 3}


@pytest.mark.asyncio
async def test_sync_502_when_all_sources_fail() -> None:
    result = SyncResult(
        counts_by_source={}, errors={"supabase": "boom"}, synced_at=datetime.now(timezone.utc)
    )
    app = _app(sync=_FakeSync(result))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        assert (await client.post("/portfolio/sync")).status_code == 502


@pytest.mark.asyncio
async def test_list_projects_with_and_without_repo() -> None:
    last = datetime.now(timezone.utc)
    app = _app(repo=_FakeRepo([_project("a")], last))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        body = (await client.get("/portfolio/projects")).json()
    assert [p["source_key"] for p in body["projects"]] == ["a"]
    assert body["last_synced_at"] is not None

    app = _app(repo=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        body = (await client.get("/portfolio/projects")).json()
    assert body == {"projects": [], "last_synced_at": None}
```

- [ ] **Step 2: Run to verify it fails** — FAIL.

- [ ] **Step 3: Implement.**

`portfolio/api/provider.py`:

```python
from __future__ import annotations

from hiresense.portfolio.domain import PortfolioEnrichmentService, PortfolioSyncService
from hiresense.portfolio.ports import PortfolioProjectsRepositoryPort


class PortfolioProvider:
    def __init__(
        self,
        sync_service: PortfolioSyncService,
        repository: PortfolioProjectsRepositoryPort,
        enrichment_service: PortfolioEnrichmentService,
    ) -> None:
        self._sync_service = sync_service
        self._repository = repository
        self._enrichment_service = enrichment_service

    def get_sync_service(self) -> PortfolioSyncService:
        return self._sync_service

    def get_repository(self) -> PortfolioProjectsRepositoryPort:
        return self._repository

    def get_enrichment_service(self) -> PortfolioEnrichmentService:
        return self._enrichment_service
```

`portfolio/api/dependencies.py` (every getter degrades to None when the module is unconfigured — bare test apps and disabled installs behave identically):

```python
from __future__ import annotations

from fastapi import Request

from hiresense.portfolio.domain import PortfolioEnrichmentService, PortfolioSyncService
from hiresense.portfolio.ports import PortfolioProjectsRepositoryPort


def _provider(request: Request):
    return getattr(request.app.state, "portfolio", None)


def get_sync_service(request: Request) -> PortfolioSyncService | None:
    provider = _provider(request)
    return provider.get_sync_service() if provider else None


def get_projects_repository(request: Request) -> PortfolioProjectsRepositoryPort | None:
    provider = _provider(request)
    return provider.get_repository() if provider else None


def get_portfolio_enrichment(request: Request) -> PortfolioEnrichmentService | None:
    provider = _provider(request)
    return provider.get_enrichment_service() if provider else None
```

`portfolio/api/routes.py`:

```python
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from hiresense.identity.api.dependencies import enforce_expensive_rate_limit, require_auth
from hiresense.portfolio.api.dependencies import get_projects_repository, get_sync_service
from hiresense.portfolio.domain import PortfolioProject, PortfolioSyncService, SyncResult
from hiresense.portfolio.ports import PortfolioProjectsRepositoryPort

router = APIRouter(prefix="/portfolio", tags=["portfolio"], dependencies=[Depends(require_auth)])


class ProjectsResponse(BaseModel):
    projects: list[PortfolioProject]
    last_synced_at: datetime | None


@router.post(
    "/sync", response_model=SyncResult, dependencies=[Depends(enforce_expensive_rate_limit)]
)
async def sync_portfolio(
    service: Annotated[PortfolioSyncService | None, Depends(get_sync_service)],
) -> SyncResult:
    if service is None:
        raise HTTPException(status_code=503, detail="No portfolio sources configured")
    result = await service.sync()
    if result.errors and not result.counts_by_source:
        raise HTTPException(
            status_code=502, detail=f"All portfolio sources failed: {result.errors}"
        )
    return result


@router.get("/projects", response_model=ProjectsResponse)
async def list_projects(
    repository: Annotated[
        PortfolioProjectsRepositoryPort | None, Depends(get_projects_repository)
    ],
) -> ProjectsResponse:
    if repository is None:
        return ProjectsResponse(projects=[], last_synced_at=None)
    projects = await asyncio.to_thread(repository.list_all)
    last = await asyncio.to_thread(repository.last_synced_at)
    return ProjectsResponse(projects=projects, last_synced_at=last)
```

`portfolio/api/__init__.py`:

```python
from hiresense.portfolio.api.routes import router

__all__ = ["router"]
```

- [ ] **Step 4: Run** — `uv run python -m pytest tests/unit/portfolio -q` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(portfolio): sync and projects endpoints"`.

---

### Task 9: Bootstrap + main wiring

**Files:**
- Create: `backend/src/hiresense/bootstrap/portfolio.py`
- Modify: `backend/src/hiresense/bootstrap/__init__.py` (export `build_portfolio`)
- Modify: `backend/src/hiresense/main.py`
- Test: `backend/tests/unit/portfolio/test_bootstrap.py`

- [ ] **Step 1: Write the failing test:**

```python
import pytest

from hiresense.bootstrap.portfolio import build_portfolio


class _Settings:
    portfolio_sources: list[str] = []
    portfolio_supabase_url = ""
    portfolio_supabase_anon_key = ""
    portfolio_profile_char_cap = 1200
    default_language = "en"


class _Infra:
    def __init__(self, settings):
        self.settings = settings
        self.http_client = object()
        self.sync_session_factory = object()


def test_returns_none_when_no_sources_configured() -> None:
    assert build_portfolio(_Infra(_Settings())) is None


def test_raises_when_supabase_enabled_without_keys() -> None:
    settings = _Settings()
    settings.portfolio_sources = ["supabase"]
    with pytest.raises(ValueError, match="PORTFOLIO_SUPABASE_URL"):
        build_portfolio(_Infra(settings))


def test_raises_on_unknown_source() -> None:
    settings = _Settings()
    settings.portfolio_sources = ["myspace"]
    with pytest.raises(ValueError, match="Unknown portfolio source"):
        build_portfolio(_Infra(settings))


def test_builds_provider_with_supabase() -> None:
    settings = _Settings()
    settings.portfolio_sources = ["supabase"]
    settings.portfolio_supabase_url = "https://xyz.supabase.co"
    settings.portfolio_supabase_anon_key = "anon"
    build = build_portfolio(_Infra(settings))
    assert build is not None
    assert build.provider.get_sync_service() is not None
    assert build.provider.get_enrichment_service() is not None
```

- [ ] **Step 2: Run to verify it fails** — FAIL.

- [ ] **Step 3: Implement** `bootstrap/portfolio.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.portfolio.adapters import SupabasePortfolioAdapter
from hiresense.portfolio.api.provider import PortfolioProvider
from hiresense.portfolio.domain import PortfolioEnrichmentService, PortfolioSyncService
from hiresense.portfolio.infrastructure import PortfolioProjectsRepository


@dataclass(frozen=True)
class PortfolioBuild:
    provider: PortfolioProvider


def build_portfolio(infra: SharedInfra) -> PortfolioBuild | None:
    """None when no sources are configured — the module is fully optional."""
    s = infra.settings
    if not s.portfolio_sources:
        return None

    sources = []
    for name in s.portfolio_sources:
        if name == "supabase":
            if not s.portfolio_supabase_url or not s.portfolio_supabase_anon_key:
                raise ValueError(
                    "portfolio source 'supabase' is enabled but PORTFOLIO_SUPABASE_URL "
                    "and/or PORTFOLIO_SUPABASE_ANON_KEY are not set"
                )
            sources.append(
                SupabasePortfolioAdapter(
                    http_client=infra.http_client,
                    base_url=s.portfolio_supabase_url,
                    anon_key=s.portfolio_supabase_anon_key,
                )
            )
        else:
            raise ValueError(f"Unknown portfolio source: {name}")

    repository = PortfolioProjectsRepository(session_factory=infra.sync_session_factory)
    provider = PortfolioProvider(
        sync_service=PortfolioSyncService(sources=sources, repository=repository),
        repository=repository,
        enrichment_service=PortfolioEnrichmentService(
            repository=repository,
            language=s.default_language,
            char_cap=s.portfolio_profile_char_cap,
        ),
    )
    return PortfolioBuild(provider=provider)
```

`bootstrap/__init__.py`: add `from hiresense.bootstrap.portfolio import build_portfolio` (and `"build_portfolio"` to `__all__` if the file maintains one — match its existing style).

`main.py` — two edits:

(a) imports: add `build_portfolio` to the `hiresense.bootstrap` import list and add
`from hiresense.portfolio.api import router as portfolio_router`.

(b) after the `# --- Profile ---` block:

```python
    # --- Portfolio (external proof-of-work sources; optional) ---
    portfolio = build_portfolio(infra)
    if portfolio is not None:
        app.state.portfolio = portfolio.provider
    # Router is always mounted: with no provider the endpoints degrade
    # (sync → 503, projects → empty) instead of 404ing the frontend card.
    app.include_router(portfolio_router)
```

- [ ] **Step 4: Run** — `uv run python -m pytest tests/unit/portfolio tests/unit/test_app.py -q` → PASS (test_app boots `create_app()` and proves wiring doesn't crash with the module disabled).
- [ ] **Step 5: Commit** — `git commit -m "feat(portfolio): bootstrap wiring"`.

---

### Task 10: Profile enrichment in `_gather_profile`

**Files:**
- Modify: `backend/src/hiresense/ingestion/api/routes.py` (function `_gather_profile` ~line 60; call sites ~line 204 in `list_jobs` and one in the `/jobs/{job_id}/analysis` handler — search for `_gather_profile(`)
- Test: `backend/tests/unit/ingestion/test_gather_profile_enrichment.py`

- [ ] **Step 1: Write the failing test:**

```python
import pytest

from hiresense.ingestion.api.routes import _gather_profile


class _FakeProfileService:
    async def list_profiles(self):
        class _Section:
            content = "CV summary text"

        class _Profile:
            skills = ["python"]
            sections = [_Section()]

        return [_Profile()]


class _FakeEnrichment:
    async def enrichment(self):
        return ["angular", "supabase"], "Portfolio projects:\n- HireSense [python]"


@pytest.mark.asyncio
async def test_gather_profile_without_enrichment_unchanged() -> None:
    skills, summary = await _gather_profile(_FakeProfileService())
    assert skills == ["python"]
    assert summary == "CV summary text"


@pytest.mark.asyncio
async def test_gather_profile_appends_portfolio_enrichment() -> None:
    skills, summary = await _gather_profile(_FakeProfileService(), _FakeEnrichment())
    assert skills == ["python", "angular", "supabase"]
    assert summary.endswith("Portfolio projects:\n- HireSense [python]")
    assert "CV summary text" in summary
```

- [ ] **Step 2: Run to verify it fails** — FAIL (TypeError: unexpected argument).

- [ ] **Step 3: Implement.** In `ingestion/api/routes.py`:

(a) extend `_gather_profile`:

```python
async def _gather_profile(
    profile_service: ProfileService,
    portfolio_enrichment: "PortfolioEnrichmentService | None" = None,
) -> tuple[list[str], str]:
    """Flatten all stored profiles into candidate skills + a summary blob.

    Shared by the list endpoint (quick scoring) and the analysis endpoint
    (deep scoring) so both score against the same profile representation.
    When the portfolio module is configured, its synced projects are appended
    (extra skills + a compact projects block) so scoring sees real projects.
    """
    candidate_skills: list[str] = []
    summary_parts: list[str] = []
    for profile in await profile_service.list_profiles():
        candidate_skills.extend(profile.skills)
        for section in profile.sections:
            summary_parts.append(section.content)
    if portfolio_enrichment is not None:
        extra_skills, extra_text = await portfolio_enrichment.enrichment()
        candidate_skills.extend(extra_skills)
        if extra_text:
            summary_parts.append(extra_text)
    return candidate_skills, "\n".join(summary_parts)
```

(b) imports:

```python
from hiresense.portfolio.api.dependencies import get_portfolio_enrichment
from hiresense.portfolio.domain import PortfolioEnrichmentService
```

(c) in **both** handlers that call `_gather_profile` (`list_jobs` and the analysis endpoint), add a parameter:

```python
    portfolio_enrichment: Annotated[
        PortfolioEnrichmentService | None, Depends(get_portfolio_enrichment)
    ],
```

and change the calls to `await _gather_profile(profile_service, portfolio_enrichment)`.

- [ ] **Step 4: Run the full backend suite** — `uv run python -m pytest -q` → all PASS (existing route tests mount bare apps where `get_portfolio_enrichment` resolves to None — behavior unchanged). `uv run ruff check .` clean.

- [ ] **Step 5: Commit** — `git commit -m "feat(portfolio): enrich matching profile with synced projects"`.

---

### Task 11: Frontend — models + service

**Files:**
- Create: `frontend/src/app/pages/profile/models/portfolio-project.model.ts`
- Create: `frontend/src/app/pages/profile/models/portfolio-projects-response.model.ts`
- Create: `frontend/src/app/pages/profile/models/portfolio-sync-result.model.ts`
- Create: `frontend/src/app/core/services/portfolio.service.ts`
- Test: `frontend/src/app/core/services/portfolio.service.spec.ts`

- [ ] **Step 1: Models.**

`portfolio-project.model.ts`:

```typescript
export interface PortfolioProjectText {
  title: string;
  description: string | null;
}

export interface PortfolioProject {
  id: string;
  source: string;
  source_key: string;
  url: string | null;
  demo_url: string | null;
  pinned: boolean;
  position: number | null;
  tech: string[];
  translations: Record<string, PortfolioProjectText>;
}
```

`portfolio-projects-response.model.ts`:

```typescript
import { PortfolioProject } from './portfolio-project.model';

export interface PortfolioProjectsResponse {
  projects: PortfolioProject[];
  last_synced_at: string | null;
}
```

`portfolio-sync-result.model.ts`:

```typescript
export interface PortfolioSyncResult {
  counts_by_source: Record<string, number>;
  errors: Record<string, string>;
  synced_at: string;
}
```

- [ ] **Step 2: Write the failing service spec** `portfolio.service.spec.ts`:

```typescript
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { PortfolioService } from './portfolio.service';
import { environment } from '../../../environments/environment';

describe('PortfolioService', () => {
  let service: PortfolioService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PortfolioService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('lists projects', () => {
    service.listProjects().subscribe((res) => {
      expect(res.projects.length).toBe(1);
      expect(res.last_synced_at).toBe('2026-06-09T00:00:00Z');
    });
    const req = httpMock.expectOne(`${environment.apiUrl}/portfolio/projects`);
    expect(req.request.method).toBe('GET');
    req.flush({
      projects: [
        {
          id: 'p1', source: 'supabase', source_key: 'hiresense', url: null, demo_url: null,
          pinned: true, position: 1, tech: ['python'],
          translations: { en: { title: 'HireSense', description: 'AI job hunting' } },
        },
      ],
      last_synced_at: '2026-06-09T00:00:00Z',
    });
  });

  it('triggers a sync', () => {
    service.sync().subscribe((res) => expect(res.counts_by_source['supabase']).toBe(3));
    const req = httpMock.expectOne(`${environment.apiUrl}/portfolio/sync`);
    expect(req.request.method).toBe('POST');
    req.flush({ counts_by_source: { supabase: 3 }, errors: {}, synced_at: '2026-06-09T00:00:00Z' });
  });
});
```

- [ ] **Step 3: Run to verify it fails** — from `frontend/`: `npm test -- --include "**/portfolio.service.spec.ts"` → FAIL.

- [ ] **Step 4: Implement** `core/services/portfolio.service.ts`:

```typescript
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { PortfolioProjectsResponse } from '../../pages/profile/models/portfolio-projects-response.model';
import { PortfolioSyncResult } from '../../pages/profile/models/portfolio-sync-result.model';

@Injectable({ providedIn: 'root' })
export class PortfolioService {
  private http = inject(HttpClient);
  private base = `${environment.apiUrl}/portfolio`;

  listProjects(): Observable<PortfolioProjectsResponse> {
    return this.http.get<PortfolioProjectsResponse>(`${this.base}/projects`);
  }

  sync(): Observable<PortfolioSyncResult> {
    return this.http.post<PortfolioSyncResult>(`${this.base}/sync`, {});
  }
}
```

- [ ] **Step 5: Run** — same command → PASS.
- [ ] **Step 6: Commit** — `git commit -m "feat(portfolio): frontend models and service"`.

---

### Task 12: Frontend — portfolio card on the profile page

**Files:**
- Create: `frontend/src/app/pages/profile/components/portfolio-card/portfolio-card.component.ts`
- Create: `frontend/src/app/pages/profile/components/portfolio-card/portfolio-card.component.html`
- Create: `frontend/src/app/pages/profile/components/portfolio-card/portfolio-card.component.scss` (may stay empty `:host {}`-only)
- Create: `frontend/src/app/pages/profile/components/portfolio-card/portfolio-card.component.spec.ts`
- Modify: `frontend/src/app/pages/profile/profile.component.ts` (import) and `profile.component.html` (mount in `panel-personal`, after the existing content of that section)

- [ ] **Step 1: Write the failing component spec:**

```typescript
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { PortfolioCardComponent } from './portfolio-card.component';
import { environment } from '../../../../../environments/environment';

describe('PortfolioCardComponent', () => {
  let fixture: ComponentFixture<PortfolioCardComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PortfolioCardComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(PortfolioCardComponent);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  function flushProjects(projects: unknown[], last: string | null) {
    httpMock
      .expectOne(`${environment.apiUrl}/portfolio/projects`)
      .flush({ projects, last_synced_at: last });
    fixture.detectChanges();
  }

  it('renders synced projects with tech tags', () => {
    fixture.detectChanges(); // ngOnInit → load
    flushProjects(
      [
        {
          id: 'p1', source: 'supabase', source_key: 'hiresense', url: 'https://x', demo_url: null,
          pinned: true, position: 1, tech: ['python', 'angular'],
          translations: { en: { title: 'HireSense', description: 'AI job hunting' } },
        },
      ],
      '2026-06-09T00:00:00Z',
    );
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('HireSense');
    expect(text).toContain('python');
  });

  it('shows the empty state when nothing is synced', () => {
    fixture.detectChanges();
    flushProjects([], null);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('No portfolio projects synced yet');
  });

  it('sync button posts and reloads', () => {
    fixture.detectChanges();
    flushProjects([], null);
    (fixture.nativeElement as HTMLElement).querySelector('button')!.click();
    httpMock
      .expectOne(`${environment.apiUrl}/portfolio/sync`)
      .flush({ counts_by_source: { supabase: 1 }, errors: {}, synced_at: '2026-06-09T00:00:00Z' });
    flushProjects(
      [
        {
          id: 'p1', source: 'supabase', source_key: 'x', url: null, demo_url: null,
          pinned: false, position: null, tech: [],
          translations: { en: { title: 'X', description: null } },
        },
      ],
      '2026-06-09T00:00:00Z',
    );
    expect(((fixture.nativeElement as HTMLElement).textContent ?? '')).toContain('X');
  });
});
```

- [ ] **Step 2: Run to verify it fails** — `npm test -- --include "**/portfolio-card.component.spec.ts"` → FAIL.

- [ ] **Step 3: Implement.**

`portfolio-card.component.ts`:

```typescript
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { PortfolioService } from '../../../../core/services/portfolio.service';
import { PortfolioProject } from '../../models/portfolio-project.model';

@Component({
  selector: 'app-portfolio-card',
  imports: [DatePipe],
  templateUrl: './portfolio-card.component.html',
  styleUrl: './portfolio-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PortfolioCardComponent implements OnInit {
  private service = inject(PortfolioService);
  private destroyRef = inject(DestroyRef);

  readonly projects = signal<PortfolioProject[]>([]);
  readonly lastSyncedAt = signal<string | null>(null);
  readonly syncing = signal(false);
  readonly error = signal('');

  ngOnInit(): void {
    this.load();
  }

  titleOf(project: PortfolioProject): string {
    const text = project.translations['en'] ?? Object.values(project.translations)[0];
    return text?.title ?? project.source_key;
  }

  sync(): void {
    if (this.syncing()) return;
    this.syncing.set(true);
    this.error.set('');
    this.service
      .sync()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.syncing.set(false);
          this.load();
        },
        error: (err) => {
          this.syncing.set(false);
          this.error.set(err?.error?.detail ?? 'Portfolio sync failed');
        },
      });
  }

  private load(): void {
    this.service
      .listProjects()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.projects.set(res.projects);
          this.lastSyncedAt.set(res.last_synced_at);
        },
        error: () => this.error.set('Could not load portfolio projects'),
      });
  }
}
```

`portfolio-card.component.html`:

```html
<section class="card portfolio-card">
  <header class="card-header">
    <h2>Portfolio projects</h2>
    <button type="button" class="btn" (click)="sync()" [disabled]="syncing()">
      {{ syncing() ? 'Syncing…' : 'Sync now' }}
    </button>
  </header>

  @if (error()) {
    <p class="error" role="alert">{{ error() }}</p>
  }

  @if (lastSyncedAt(); as last) {
    <p class="muted">Last synced {{ last | date: 'medium' }}</p>
  }

  @if (projects().length === 0) {
    <p class="muted">No portfolio projects synced yet.</p>
  } @else {
    <ul class="project-list">
      @for (project of projects(); track project.id) {
        <li>
          <span class="project-title">{{ titleOf(project) }}</span>
          @if (project.pinned) {
            <span class="badge">pinned</span>
          }
          @for (tag of project.tech; track tag) {
            <span class="tag">{{ tag }}</span>
          }
          @if (project.url) {
            <a [href]="project.url" target="_blank" rel="noopener">code</a>
          }
          @if (project.demo_url) {
            <a [href]="project.demo_url" target="_blank" rel="noopener">demo</a>
          }
        </li>
      }
    </ul>
  }
</section>
```

`portfolio-card.component.scss` — minimal, match neighboring cards (look at `manual-fields-form.component.scss` for the card/tag styles used on this page and reuse class conventions; keep it small).

Mount it: in `profile.component.ts` add `PortfolioCardComponent` to the `imports` array; in `profile.component.html`, inside `<section id="panel-personal" …>` after its existing content, add:

```html
    <app-portfolio-card />
```

- [ ] **Step 4: Run** — `npm test -- --include "**/portfolio-card.component.spec.ts"` then the full `npm test` and `npx ng lint` (CI runs lint; `npm test` doesn't). All green.

- [ ] **Step 5: Commit** — `git commit -m "feat(portfolio): profile-page portfolio card"`.

---

### Task 13: Full verification + live smoke + PR

- [ ] **Step 1: Backend full suite + lint** (from `backend/`):

```bash
uv run python -m pytest -q          # expect: all pass
uv run ruff check .                 # expect: All checks passed!
```

- [ ] **Step 2: Frontend full suite + lint** (from `frontend/`):

```bash
npm test                            # expect: all pass
npx ng lint                         # expect: all files pass linting
```

- [ ] **Step 3: Live smoke against the real portfolio** (compose db running; real `PORTFOLIO_SUPABASE_*` values in `backend/.env`):

```bash
cd backend && uv run app
# separate shell:
# 1. login
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<AUTH_PASSWORD from backend/.env>"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
# 2. sync — expect counts_by_source.supabase > 0, errors {}
curl -s -X POST http://127.0.0.1:8000/portfolio/sync -H "Authorization: Bearer $TOKEN"
# 3. list — expect the projects with translations + tech
curl -s http://127.0.0.1:8000/portfolio/projects -H "Authorization: Bearer $TOKEN"
# 4. enrichment visible: /ingestion/jobs quick-scores against a summary that now contains "Portfolio projects:"
```

Also open the frontend profile page → Personal details tab → card lists projects; Sync button works.

- [ ] **Step 4: Push + PR**

```bash
git push -u origin feat/portfolio-integration
gh auth switch --user StevSant   # account flips back to BryanP26 between commands
gh pr create --title "feat(portfolio): portfolio sync and profile enrichment (Phase 1)" --body "..."
```

PR body: summarize Phase 1 against the spec (`docs/superpowers/specs/2026-06-09-external-sources-integration-design.md`), list the test evidence from steps 1–3, note that Phases 2–6 follow. End with the Claude Code attribution footer.

---

## Self-review notes (already applied)

- Spec coverage: Task 1→config, 2→models/ports, 3→profile text, 4→persistence+migration, 5→Supabase adapter, 6→sync service, 7→enrichment service, 8→endpoints, 9→bootstrap, 10→`_gather_profile`, 11–12→profile card, 13→verification. Phase 1 spec items all covered; `RelevantProjectSelector`, ref links, GitHub adapter, engagement are later phases by design.
- Type consistency: `PortfolioSourcePort.source_name()/fetch_projects()`, repo `replace_source/list_all/last_synced_at`, enrichment `enrichment() -> tuple[list[str], str]` used consistently across tasks 5–10.
- The ingestion route tests keep passing because `get_portfolio_enrichment` returns None on bare apps (same degradation pattern as `app.state.settings`).
