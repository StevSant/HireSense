# Company Intel Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show company intel (firmographics + LLM research, with a logo) on the `/dashboard/company/:name` page — auto-generated on first visit, cached, with a manual refresh.

**Architecture:** Extend the existing hexagonal `research` module — add firmographics fields to the model/ORM (migration), a layered `FirmographicsPort` (external provider → LLM fallback), API-derived logo URL, and get-or-create on `GET /research/{name}`. Frontend adds a `CompanyIntelComponent` fed by the research service, loaded independently of the job list.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy + Alembic, Pydantic, pytest (backend); Angular 21 standalone + signals, Vitest (frontend).

## Global Constraints

- Backend commands from `backend/` via `uv run python -m …` (broken trampoline). Migrations: `uv run python -m alembic …`.
- No hardcoded configurable values: provider URL/key + logo service URL go through `config/groups/` + `.env.example`. All blank by default (local mode degrades gracefully).
- Every new ORM class imported in `infrastructure/registry.py`; every new package symbol re-exported from its `__init__.py`; import from the contextual package.
- `domain/` imports no framework packages (no `sqlalchemy`/`httpx`); external HTTP lives in `infrastructure/`.
- After merge, apply migrations to the dev DB (`uv run python -m alembic upgrade head`) — CI runs on SQLite and won't do it for you.
- Commit after each task, Conventional Commits, scope `research` (backend) / `company` (frontend).

---

### Task 1: Firmographics config

**Files:**
- Create: `backend/src/hiresense/config/groups/research.py`
- Modify: `backend/src/hiresense/config/settings.py`
- Modify: `backend/src/hiresense/config/groups/__init__.py`
- Modify: `backend/.env.example`

**Interfaces:**
- Produces: `settings.firmographics_provider_url: str`, `settings.firmographics_api_key: str`, `settings.logo_service_url: str` (flat access).

- [ ] **Step 1: Create the settings group**

Create `backend/src/hiresense/config/groups/research.py`:

```python
from pydantic_settings import BaseSettings


class ResearchSettings(BaseSettings):
    """Company research firmographics enrichment + logo derivation."""

    # External firmographics provider (industry/size/HQ/website). Blank ⇒ the
    # external adapter is disabled and the LLM fallback is used. The URL is a
    # template the adapter fills with the company domain/name; see the adapter.
    firmographics_provider_url: str = ""
    firmographics_api_key: str = ""
    # Logo/favicon service, templated with the company's website domain. Blank ⇒
    # no logo_url is derived (frontend shows a monogram). Example form:
    #   https://logo.clearbit.com/{domain}
    logo_service_url: str = ""
```

- [ ] **Step 2: Compose it into `Settings`**

Inspect `backend/src/hiresense/config/settings.py` to see the mixin pattern, then add `ResearchSettings` to the `Settings` base classes exactly like the other groups (import + add to the class bases). Add `ResearchSettings` to `config/groups/__init__.py` re-exports (`from hiresense.config.groups.research import ResearchSettings` + `__all__`).

- [ ] **Step 3: Document in `.env.example`**

Add a Research block to `backend/.env.example`:

```bash
# --- Company research: firmographics enrichment + logo ---
# External firmographics provider (industry/size/HQ/website). Blank => LLM fallback.
FIRMOGRAPHICS_PROVIDER_URL=
FIRMOGRAPHICS_API_KEY=
# Logo service templated with the company website domain, e.g.
# https://logo.clearbit.com/{domain} . Blank => monogram avatar only.
LOGO_SERVICE_URL=
```

- [ ] **Step 4: Verify**

Run: `cd backend && uv run python -c "from hiresense.config.settings import Settings; s=Settings(); print(s.firmographics_provider_url, s.logo_service_url, s.firmographics_api_key)"`
Expected: three blank lines (empty strings).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/config/ backend/.env.example
git commit -m "feat(research): config for firmographics provider + logo service"
```

---

### Task 2: Firmographics domain value object + port

**Files:**
- Create: `backend/src/hiresense/research/domain/firmographics.py`
- Modify: `backend/src/hiresense/research/domain/__init__.py`
- Create: `backend/src/hiresense/research/ports/firmographics.py`
- Modify: `backend/src/hiresense/research/ports/__init__.py`
- Test: `backend/tests/unit/research/test_firmographics.py`

**Interfaces:**
- Produces:
  - `Firmographics` (Pydantic): `industry: str | None`, `company_size: str | None`, `headquarters: str | None`, `website: str | None`.
  - `FirmographicsPort` (Protocol): `async def fetch(self, company_name: str) -> Firmographics | None`.

- [ ] **Step 1: Write failing test**

Create `backend/tests/unit/research/test_firmographics.py`:

```python
from hiresense.research.domain import Firmographics


def test_firmographics_defaults_to_none():
    f = Firmographics()
    assert f.industry is None
    assert f.company_size is None
    assert f.headquarters is None
    assert f.website is None


def test_firmographics_holds_values():
    f = Firmographics(industry="SaaS", company_size="51-200", headquarters="Santiago, CL", website="https://bc.cl")
    assert f.website == "https://bc.cl"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_firmographics.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Implement**

Create `backend/src/hiresense/research/domain/firmographics.py`:

```python
from __future__ import annotations

from pydantic import BaseModel


class Firmographics(BaseModel):
    """Basic company facts, from an external provider or the LLM. All optional."""

    industry: str | None = None
    company_size: str | None = None
    headquarters: str | None = None
    website: str | None = None
```

Create `backend/src/hiresense/research/ports/firmographics.py`:

```python
from __future__ import annotations

from typing import Protocol

from hiresense.research.domain.firmographics import Firmographics


class FirmographicsPort(Protocol):
    async def fetch(self, company_name: str) -> Firmographics | None: ...
```

Update `backend/src/hiresense/research/domain/__init__.py`:

```python
from hiresense.research.domain.firmographics import Firmographics
from hiresense.research.domain.services import CompanyResearchService

__all__ = ["CompanyResearchService", "Firmographics"]
```

Update `backend/src/hiresense/research/ports/__init__.py`:

```python
from hiresense.research.ports.firmographics import FirmographicsPort
from hiresense.research.ports.repository import CompanyResearchRepositoryPort

__all__ = ["CompanyResearchRepositoryPort", "FirmographicsPort"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_firmographics.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/research/domain/ backend/src/hiresense/research/ports/ backend/tests/unit/research/test_firmographics.py
git commit -m "feat(research): add Firmographics model + FirmographicsPort"
```

---

### Task 3: Add firmographics columns to model, ORM + migration

**Files:**
- Modify: `backend/src/hiresense/research/domain/models.py`
- Modify: `backend/src/hiresense/research/infrastructure/orm.py`
- Modify: `backend/src/hiresense/research/infrastructure/repository.py:9-19` (`_CONTENT_FIELDS`)
- Create: migration under `backend/alembic/versions/` (autogenerated)

**Interfaces:**
- Produces: `CompanyResearch` domain model + `CompanyResearchOrm` gain `industry`, `company_size`, `headquarters`, `website` (all `str | None`). Repository persists them.

- [ ] **Step 1: Add fields to the domain model**

In `backend/src/hiresense/research/domain/models.py`, add to `CompanyResearch` (after `cons`, before `raw_llm_response`):

```python
    industry: str | None = None
    company_size: str | None = None
    headquarters: str | None = None
    website: str | None = None
```

- [ ] **Step 2: Add columns to the ORM**

In `backend/src/hiresense/research/infrastructure/orm.py`, add after `cons`:

```python
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    headquarters: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

- [ ] **Step 3: Persist them in the repository**

In `backend/src/hiresense/research/infrastructure/repository.py`, add the four names to `_CONTENT_FIELDS`:

```python
_CONTENT_FIELDS = (
    "company_name",
    "funding_stage",
    "tech_stack",
    "culture_summary",
    "growth_trajectory",
    "red_flags",
    "pros",
    "cons",
    "industry",
    "company_size",
    "headquarters",
    "website",
    "raw_llm_response",
)
```

- [ ] **Step 4: Generate the migration**

`CompanyResearchOrm` is already registered (it's imported in `research/infrastructure/__init__.py`; confirm it's reachable from `infrastructure/registry.py` — if not, add the import there).

Run: `cd backend && uv run python -m alembic revision --autogenerate -m "add firmographics to company_research"`
Then open the generated file and confirm it only `add_column`s the four nullable columns on `company_research` (no unrelated drops). Remove any spurious ops.

- [ ] **Step 5: Verify migration applies (SQLite in-memory round-trips in tests; apply to dev DB after merge)**

Run: `cd backend && uv run python -m pytest tests/integration/test_research_endpoints.py -v` (if present) — or the whole suite builds the schema in-memory: `uv run python -m pytest tests/unit/research -v`.
Expected: PASS (schema builds with new columns).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/research/ backend/alembic/versions/
git commit -m "feat(research): persist firmographics columns on company_research"
```

---

### Task 4: LLM firmographics — extend the research prompt/parsing

**Files:**
- Modify: `backend/src/hiresense/research/domain/services.py`
- Test: `backend/tests/unit/research/test_research_service.py` (extend; create if absent)

**Interfaces:**
- Consumes: existing `self._llm.complete(...)`.
- Produces: `_do_research` also populates `industry`, `company_size`, `headquarters`, `website` on the saved `CompanyResearch` from the LLM JSON (each optional, `None` when absent).

- [ ] **Step 1: Write failing test**

In `backend/tests/unit/research/test_research_service.py`, add (using the file's existing fake repo; a minimal fake LLM shown here):

```python
import json
import pytest
from hiresense.research.domain import CompanyResearchService


class _FakeRepo:
    def __init__(self): self.saved = None
    def get_by_company_name(self, name): return None
    def create(self, r): self.saved = r; return r
    def save(self, r): self.saved = r; return r


class _FakeLLM:
    async def complete(self, prompt, system=""):
        return json.dumps({
            "funding_stage": "Series A", "tech_stack": "Python", "culture_summary": "ok",
            "growth_trajectory": "up", "red_flags": None, "pros": "p", "cons": "c",
            "industry": "SaaS", "company_size": "51-200",
            "headquarters": "Santiago, CL", "website": "https://bc.cl",
        })


@pytest.mark.asyncio
async def test_research_populates_firmographics():
    svc = CompanyResearchService(repository=_FakeRepo(), llm=_FakeLLM())
    r = await svc.research("BC Tecnología")
    assert r.industry == "SaaS"
    assert r.company_size == "51-200"
    assert r.headquarters == "Santiago, CL"
    assert r.website == "https://bc.cl"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_research_service.py::test_research_populates_firmographics -v`
Expected: FAIL — firmographics not populated.

- [ ] **Step 3: Implement**

In `backend/src/hiresense/research/domain/services.py`:

1. Extend `_build_prompt` field list + the JSON example to include the four fields:

```python
            "- pros: string (benefits of working there)\n"
            "- cons: string (downsides of working there)\n"
            "- industry: string or null\n"
            "- company_size: string or null (e.g. '51-200')\n"
            "- headquarters: string or null (city, country)\n"
            "- website: string or null (official homepage URL)\n\n"
            'Return valid JSON only: {"funding_stage": "...", "tech_stack": "...", '
            '"culture_summary": "...", "growth_trajectory": "...", "red_flags": null, '
            '"pros": "...", "cons": "...", "industry": null, "company_size": null, '
            '"headquarters": null, "website": null}'
```

2. In `_do_research`, set the four fields on both the `existing` update branch and the new `record`, using `data.get(...)`:

```python
                existing.industry = data.get("industry")
                existing.company_size = data.get("company_size")
                existing.headquarters = data.get("headquarters")
                existing.website = data.get("website")
```

and in the `CompanyResearch(...)` constructor:

```python
                industry=data.get("industry"),
                company_size=data.get("company_size"),
                headquarters=data.get("headquarters"),
                website=data.get("website"),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_research_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/research/domain/services.py backend/tests/unit/research/test_research_service.py
git commit -m "feat(research): extend LLM research to emit firmographics"
```

---

### Task 5: External firmographics adapter + layered composition

**Files:**
- Create: `backend/src/hiresense/research/infrastructure/external_firmographics_adapter.py`
- Modify: `backend/src/hiresense/research/infrastructure/__init__.py`
- Modify: `backend/src/hiresense/research/domain/services.py`
- Test: `backend/tests/unit/research/test_firmographics_composition.py`

**Interfaces:**
- Consumes: `FirmographicsPort`, `Firmographics`, `settings.firmographics_provider_url`, `settings.firmographics_api_key`.
- Produces:
  - `ExternalFirmographicsAdapter(provider_url: str, api_key: str)` implementing `FirmographicsPort.fetch` — returns `None` when unconfigured or on any error.
  - `CompanyResearchService(repository, llm=None, firmographics=None)` — new optional `firmographics: FirmographicsPort` arg; when present, external values override LLM values field-by-field (external wins; LLM fills gaps).

- [ ] **Step 1: Write failing test (composition)**

Create `backend/tests/unit/research/test_firmographics_composition.py`:

```python
import json
import pytest
from hiresense.research.domain import CompanyResearchService, Firmographics


class _FakeRepo:
    def get_by_company_name(self, name): return None
    def create(self, r): return r
    def save(self, r): return r


class _FakeLLM:
    async def complete(self, prompt, system=""):
        return json.dumps({
            "funding_stage": "Seed", "tech_stack": "Go", "culture_summary": "c",
            "growth_trajectory": "g", "red_flags": None, "pros": "p", "cons": "c",
            "industry": "LLM-industry", "company_size": None,
            "headquarters": "LLM-HQ", "website": "https://llm.example",
        })


class _FakeProvider:
    async def fetch(self, company_name):
        return Firmographics(industry="Provider-industry", company_size="201-500")


@pytest.mark.asyncio
async def test_external_wins_llm_fills_gaps():
    svc = CompanyResearchService(repository=_FakeRepo(), llm=_FakeLLM(), firmographics=_FakeProvider())
    r = await svc.research("BC")
    assert r.industry == "Provider-industry"   # external wins
    assert r.company_size == "201-500"          # external wins
    assert r.headquarters == "LLM-HQ"           # gap filled by LLM
    assert r.website == "https://llm.example"   # gap filled by LLM
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_firmographics_composition.py -v`
Expected: FAIL — `CompanyResearchService` has no `firmographics` param.

- [ ] **Step 3: Implement the adapter**

Create `backend/src/hiresense/research/infrastructure/external_firmographics_adapter.py`:

```python
from __future__ import annotations

import logging

import httpx

from hiresense.research.domain.firmographics import Firmographics

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 8.0


class ExternalFirmographicsAdapter:
    """Calls a configurable firmographics provider. Returns None when the
    provider is unconfigured (local mode) or on any error/timeout — the service
    then falls back to the LLM."""

    def __init__(self, provider_url: str, api_key: str) -> None:
        self._provider_url = provider_url
        self._api_key = api_key

    async def fetch(self, company_name: str) -> Firmographics | None:
        if not self._provider_url or not self._api_key:
            return None
        try:
            headers = {"Authorization": f"Bearer {self._api_key}"}
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                resp = await client.get(
                    self._provider_url, params={"company": company_name}, headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            logger.warning("firmographics provider failed for %s", company_name, exc_info=True)
            return None
        return Firmographics(
            industry=data.get("industry"),
            company_size=data.get("company_size") or data.get("size"),
            headquarters=data.get("headquarters") or data.get("location"),
            website=data.get("website") or data.get("domain"),
        )
```

Re-export in `backend/src/hiresense/research/infrastructure/__init__.py`:

```python
from hiresense.research.infrastructure.external_firmographics_adapter import ExternalFirmographicsAdapter
from hiresense.research.infrastructure.orm import CompanyResearchOrm
from hiresense.research.infrastructure.repository import CompanyResearchRepository

__all__ = ["CompanyResearchOrm", "CompanyResearchRepository", "ExternalFirmographicsAdapter"]
```

- [ ] **Step 4: Implement composition in the service**

In `backend/src/hiresense/research/domain/services.py`:

1. Constructor:

```python
    def __init__(self, repository: CompanyResearchRepositoryPort, llm: Any = None, firmographics: Any = None) -> None:
        self._repo = repository
        self._llm = llm
        self._firmographics = firmographics
```

2. In `_do_research`, after parsing the LLM `data` and before building/saving, fetch external firmographics and let external win field-by-field. Replace the four `data.get(...)` assignments (from Task 4) with values from a merge helper. Add near the top of the method (after `data = self._parse_response(response)`):

```python
        external = None
        if self._firmographics is not None:
            external = await self._firmographics.fetch(company_name)

        def _pick(field: str):
            if external is not None:
                val = getattr(external, field)
                if val:
                    return val
            return data.get(field)
```

Then use `_pick("industry")`, `_pick("company_size")`, `_pick("headquarters")`, `_pick("website")` in both the `existing` update branch and the new `CompanyResearch(...)` constructor (replacing the `data.get(...)` calls from Task 4).

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/research -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/research/ backend/tests/unit/research/test_firmographics_composition.py
git commit -m "feat(research): external firmographics adapter with LLM-gap-fill composition"
```

---

### Task 6: `get_or_create` + wiring the adapter in bootstrap

**Files:**
- Modify: `backend/src/hiresense/research/domain/services.py`
- Modify: `backend/src/hiresense/bootstrap/research.py`
- Test: `backend/tests/unit/research/test_research_service.py`

**Interfaces:**
- Produces: `CompanyResearchService.get_or_create(company_name, job_description="")` — returns cached if present, else generates once, persists, returns.
- Bootstrap constructs `ExternalFirmographicsAdapter` from settings and passes it into the service.

- [ ] **Step 1: Write failing test**

Add to `test_research_service.py`:

```python
@pytest.mark.asyncio
async def test_get_or_create_returns_cache_without_llm_call():
    from hiresense.research.domain.models import CompanyResearch

    class _CachingRepo:
        def __init__(self): self.calls = 0
        def get_by_company_name(self, name):
            return CompanyResearch(company_name=name, funding_stage="x", tech_stack="x",
                                   culture_summary="x", growth_trajectory="x", red_flags=None,
                                   pros="x", cons="x", raw_llm_response="{}")
        def create(self, r): return r
        def save(self, r): return r

    class _BoomLLM:
        async def complete(self, prompt, system=""): raise AssertionError("must not call LLM")

    svc = CompanyResearchService(repository=_CachingRepo(), llm=_BoomLLM())
    r = await svc.get_or_create("BC")
    assert r.company_name == "BC"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_research_service.py::test_get_or_create_returns_cache_without_llm_call -v`
Expected: FAIL — no `get_or_create`.

- [ ] **Step 3: Implement**

In `services.py`, add:

```python
    async def get_or_create(self, company_name: str, job_description: str = "") -> CompanyResearch:
        cached = self._repo.get_by_company_name(company_name)
        if cached is not None:
            return cached
        return await self._do_research(company_name, job_description)
```

(`research()` already does cache-then-create; `get_or_create` is its explicit name for the GET path. Keep `research()` for the existing POST route.)

- [ ] **Step 4: Wire the adapter in bootstrap**

In `backend/src/hiresense/bootstrap/research.py`:

```python
from hiresense.research.infrastructure import CompanyResearchRepository, ExternalFirmographicsAdapter


def build_research(infra: SharedInfra, tracked: Callable[[str], Any]) -> ResearchProvider:
    research_repo = CompanyResearchRepository(session_factory=infra.sync_session_factory)
    s = infra.settings
    firmographics = ExternalFirmographicsAdapter(
        provider_url=s.firmographics_provider_url,
        api_key=s.firmographics_api_key,
    )
    research_service = CompanyResearchService(
        llm=tracked("company_research"),
        repository=research_repo,
        firmographics=firmographics,
    )
    return ResearchProvider(research_service=research_service)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/research -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/research/domain/services.py backend/src/hiresense/bootstrap/research.py backend/tests/unit/research/test_research_service.py
git commit -m "feat(research): get_or_create path + wire external firmographics"
```

---

### Task 7: API — logo derivation + expanded response, GET generates

**Files:**
- Create: `backend/src/hiresense/research/domain/logo.py`
- Modify: `backend/src/hiresense/research/domain/__init__.py`
- Modify: `backend/src/hiresense/research/api/schemas.py`
- Modify: `backend/src/hiresense/research/api/routes.py`
- Test: `backend/tests/unit/research/test_logo.py`, `backend/tests/integration/test_research_endpoints.py`

**Interfaces:**
- Produces:
  - `logo_url(website: str | None, service_url: str) -> str | None` — extracts the domain from `website` and formats `service_url` (which contains `{domain}`); `None` when either is missing.
  - `CompanyResearchResponse` gains `industry`, `company_size`, `headquarters`, `website`, `logo_url` (all optional).
  - `GET /research/{company_name}` → get-or-create (generate on first visit) instead of 404.

- [ ] **Step 1: Write failing test (logo helper)**

Create `backend/tests/unit/research/test_logo.py`:

```python
from hiresense.research.domain import logo_url


def test_logo_url_from_website():
    assert logo_url("https://www.bc.cl/careers", "https://logo.x/{domain}") == "https://logo.x/bc.cl"


def test_logo_url_bare_domain():
    assert logo_url("bc.cl", "https://logo.x/{domain}") == "https://logo.x/bc.cl"


def test_logo_url_none_when_no_website():
    assert logo_url(None, "https://logo.x/{domain}") is None


def test_logo_url_none_when_no_service():
    assert logo_url("https://bc.cl", "") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_logo.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Implement the logo helper**

Create `backend/src/hiresense/research/domain/logo.py`:

```python
from __future__ import annotations

from urllib.parse import urlparse


def logo_url(website: str | None, service_url: str) -> str | None:
    """Build a logo URL from a company website domain and a templated service
    URL (containing `{domain}`). Returns None when either input is missing."""
    if not website or not service_url:
        return None
    candidate = website if "//" in website else f"//{website}"
    host = urlparse(candidate).netloc or website
    domain = host.split("@")[-1].split(":")[0].strip().lower()
    if domain.startswith("www."):
        domain = domain[4:]
    if not domain:
        return None
    return service_url.replace("{domain}", domain)
```

Re-export in `research/domain/__init__.py`:

```python
from hiresense.research.domain.firmographics import Firmographics
from hiresense.research.domain.logo import logo_url
from hiresense.research.domain.services import CompanyResearchService

__all__ = ["CompanyResearchService", "Firmographics", "logo_url"]
```

- [ ] **Step 4: Run logo test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/research/test_logo.py -v`
Expected: PASS.

- [ ] **Step 5: Expand the response schema**

In `backend/src/hiresense/research/api/schemas.py`, add to `CompanyResearchResponse` (after `cons`):

```python
    industry: str | None = None
    company_size: str | None = None
    headquarters: str | None = None
    website: str | None = None
    logo_url: str | None = None
```

- [ ] **Step 6: Make GET generate + attach logo_url**

In `backend/src/hiresense/research/api/routes.py`, rewrite the GET handler. Since `logo_url` needs `settings.logo_service_url`, read settings from the request app state (match how other routes access settings; if a settings dependency exists, use it). Implementation:

```python
from hiresense.research.domain import logo_url as build_logo_url


@router.get("/{company_name}", response_model=CompanyResearchResponse)
async def get_research(
    company_name: str,
    request: Request,
    service: CompanyResearchService = Depends(get_company_research_service),
) -> CompanyResearchResponse:
    result = await service.get_or_create(company_name)
    resp = CompanyResearchResponse.model_validate(result)
    service_url = request.app.state.settings.logo_service_url
    return resp.model_copy(update={"logo_url": build_logo_url(result.website, service_url)})
```

Add `from fastapi import Request` and confirm `request.app.state.settings` is where settings live (inspect `main.py`/an existing route that reads settings; if the attribute differs, use the correct one). Also attach `logo_url` the same way in the POST and refresh handlers for consistency (factor a small local helper or repeat the two lines).

- [ ] **Step 7: Write/extend the endpoint integration test**

In `backend/tests/integration/test_research_endpoints.py` (create if absent, following the in-memory app harness used by other integration tests, incl. `require_auth` override), assert `GET /research/{name}` returns 200 with the new fields present (values may be null in the no-LLM local test config) — and that it does NOT 404 for an unknown company (it generates a fallback record).

```python
def test_get_research_returns_intel_fields(client):
    resp = client.get("/research/SomeCo")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("industry", "company_size", "headquarters", "website", "logo_url"):
        assert key in body
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/research tests/integration/test_research_endpoints.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/src/hiresense/research/ backend/tests/
git commit -m "feat(research): derive logo_url, expand response, GET generates on first visit"
```

---

### Task 8: Frontend research model + service methods

**Files:**
- Modify: `frontend/src/app/pages/tracking/models/company-research.model.ts`
- Modify: `frontend/src/app/core/services/research.service.ts`
- Test: `frontend/src/app/core/services/research.service.spec.ts` (create if absent)

**Interfaces:**
- Produces:
  - `CompanyResearch` interface gains `industry`, `company_size`, `headquarters`, `website`, `logo_url` (all `string | null`).
  - `ResearchService.get(companyName: string): Observable<CompanyResearch>` → `GET /research/{name}`.

- [ ] **Step 1: Extend the model**

In `frontend/src/app/pages/tracking/models/company-research.model.ts`, add before `created_at`:

```typescript
  industry: string | null;
  company_size: string | null;
  headquarters: string | null;
  website: string | null;
  logo_url: string | null;
```

- [ ] **Step 2: Write failing test**

Create `research.service.spec.ts` using `HttpClientTestingModule`/`provideHttpClientTesting`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ResearchService } from './research.service';
import { environment } from '../../../environments/environment';

describe('ResearchService', () => {
  let service: ResearchService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(ResearchService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  it('GETs research by company name', () => {
    service.get('BC Tecnología').subscribe();
    const req = httpMock.expectOne(`${environment.apiUrl}/research/BC%20Tecnolog%C3%ADa`);
    expect(req.request.method).toBe('GET');
    req.flush({});
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npm test -- --include "**/research.service.spec.ts"`
Expected: FAIL — `get` missing.

- [ ] **Step 4: Implement**

In `research.service.ts`, add:

```typescript
  get(companyName: string): Observable<CompanyResearch> {
    return this.http.get<CompanyResearch>(`${environment.apiUrl}/research/${encodeURIComponent(companyName)}`);
  }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npm test -- --include "**/research.service.spec.ts"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/pages/tracking/models/company-research.model.ts frontend/src/app/core/services/research.service.ts frontend/src/app/core/services/research.service.spec.ts
git commit -m "feat(company): research model firmographics + get-by-name service method"
```

---

### Task 9: `CompanyIntelComponent`

**Files:**
- Create: `frontend/src/app/pages/company/components/company-intel/company-intel.component.ts`
- Create: `frontend/src/app/pages/company/components/company-intel/company-intel.component.html`
- Create: `frontend/src/app/pages/company/components/company-intel/company-intel.component.scss`
- Test: `frontend/src/app/pages/company/components/company-intel/company-intel.component.spec.ts`

**Interfaces:**
- Consumes: `CompanyResearch` model.
- Produces: `CompanyIntelComponent` with inputs `research = input<CompanyResearch | null>(null)`, `loading = input(false)`, `refreshing = input(false)`; output `refresh = output<void>()`. Monogram fallback when no `logo_url` / image error; hides "not configured" sentinel sections.

- [ ] **Step 1: Write failing test**

Create the spec:

```typescript
import { describe, it, expect } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { CompanyIntelComponent } from './company-intel.component';

const research = {
  id: '1', company_name: 'BC Tecnología', funding_stage: 'Series A', tech_stack: 'Python',
  culture_summary: 'Great', growth_trajectory: 'Up', red_flags: null, pros: 'p', cons: 'c',
  industry: 'SaaS', company_size: '51-200', headquarters: 'Santiago, CL',
  website: 'https://bc.cl', logo_url: null, created_at: null, updated_at: null,
};

describe('CompanyIntelComponent', () => {
  it('renders firmographics and a monogram when no logo', () => {
    const fixture = TestBed.createComponent(CompanyIntelComponent);
    fixture.componentRef.setInput('research', research);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('SaaS');
    expect(text).toContain('Santiago, CL');
    expect(text).toContain('B'); // monogram initial
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --include "**/company-intel.component.spec.ts"`
Expected: FAIL — component missing.

- [ ] **Step 3: Implement the component**

`company-intel.component.ts`:

```typescript
import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { CompanyResearch } from '../../../tracking/models/company-research.model';

// Sentinel strings the backend uses when the LLM/provider isn't configured.
const NOT_CONFIGURED = ['LLM not configured', 'Research unavailable'];

@Component({
  selector: 'app-company-intel',
  standalone: true,
  templateUrl: './company-intel.component.html',
  styleUrl: './company-intel.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CompanyIntelComponent {
  research = input<CompanyResearch | null>(null);
  loading = input(false);
  refreshing = input(false);
  refresh = output<void>();

  logoFailed = signal(false);

  monogram = computed(() => (this.research()?.company_name ?? '?').trim().charAt(0).toUpperCase() || '?');

  showLogo = computed(() => !!this.research()?.logo_url && !this.logoFailed());

  notConfigured = computed(() => {
    const r = this.research();
    return !!r && NOT_CONFIGURED.includes(r.funding_stage);
  });

  // Only render a text section when it has real content (not a sentinel).
  has(value: string | null | undefined): boolean {
    return !!value && !NOT_CONFIGURED.includes(value);
  }

  onLogoError(): void { this.logoFailed.set(true); }
  onRefresh(): void { this.refresh.emit(); }
}
```

`company-intel.component.html`:

```html
@if (loading()) {
  <p class="intel-state">Loading company intel…</p>
} @else if (research(); as r) {
  <div class="intel">
    <div class="intel-head">
      @if (showLogo()) {
        <img class="intel-logo" [src]="r.logo_url" [alt]="r.company_name + ' logo'" (error)="onLogoError()" />
      } @else {
        <span class="intel-monogram" aria-hidden="true">{{ monogram() }}</span>
      }
      <ul class="intel-facts">
        @if (has(r.industry)) { <li><span>Industry</span> {{ r.industry }}</li> }
        @if (has(r.company_size)) { <li><span>Size</span> {{ r.company_size }}</li> }
        @if (has(r.headquarters)) { <li><span>HQ</span> {{ r.headquarters }}</li> }
        @if (has(r.website)) { <li><span>Web</span> <a [href]="r.website" target="_blank" rel="noopener">{{ r.website }}</a></li> }
      </ul>
      <button type="button" class="intel-refresh" [disabled]="refreshing()" (click)="onRefresh()">
        {{ refreshing() ? 'Refreshing…' : 'Refresh' }}
      </button>
    </div>

    @if (notConfigured()) {
      <p class="intel-state">Company research isn't configured (no LLM). Add an API key to enable it.</p>
    } @else {
      <div class="intel-sections">
        @if (has(r.funding_stage)) { <section><h4>Funding</h4><p>{{ r.funding_stage }}</p></section> }
        @if (has(r.tech_stack)) { <section><h4>Tech stack</h4><p>{{ r.tech_stack }}</p></section> }
        @if (has(r.culture_summary)) { <section><h4>Culture</h4><p>{{ r.culture_summary }}</p></section> }
        @if (has(r.growth_trajectory)) { <section><h4>Growth</h4><p>{{ r.growth_trajectory }}</p></section> }
        @if (has(r.pros)) { <section><h4>Pros</h4><p>{{ r.pros }}</p></section> }
        @if (has(r.cons)) { <section><h4>Cons</h4><p>{{ r.cons }}</p></section> }
        @if (r.red_flags && has(r.red_flags)) { <section class="intel-flags"><h4>Red flags</h4><p>{{ r.red_flags }}</p></section> }
      </div>
    }
  </div>
}
```

`company-intel.component.scss` — minimal, match the company page's typography: a flex `.intel-head` (logo/monogram left, facts inline, refresh right), circular `.intel-logo`/`.intel-monogram` (48px), muted `.intel-facts span` labels, a responsive `.intel-sections` grid, and a subtle `.intel-flags` accent. Keep it self-contained.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --include "**/company-intel.component.spec.ts"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/company/components/company-intel/
git commit -m "feat(company): CompanyIntelComponent (firmographics + research + monogram)"
```

---

### Task 10: Wire intel into the company page

**Files:**
- Modify: `frontend/src/app/pages/company/company.component.ts`
- Modify: `frontend/src/app/pages/company/company.component.html`
- Test: `frontend/src/app/pages/company/company.component.spec.ts`

**Interfaces:**
- Consumes: `ResearchService.get`/`refresh` (Task 8), `CompanyIntelComponent` (Task 9).
- Produces: research loaded independently of jobs; `<app-company-intel>` rendered above the jobs table; refresh handler.

- [ ] **Step 1: Write failing test**

In `company.component.spec.ts` (follow existing mocks for `IngestionService`/`ApplicationsService`; add a mocked `ResearchService` with `get` returning an `of(research)`), assert the intel component receives the research after init:

```typescript
it('loads company research on init', () => {
  // arrange with ResearchService.get returning of(researchFixture)
  fixture.detectChanges();
  expect(component.research()).not.toBeNull();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --include "**/company.component.spec.ts"`
Expected: FAIL — `research` signal / loading missing.

- [ ] **Step 3: Implement**

In `company.component.ts`:

- Add imports:

```typescript
import { ResearchService } from '../../core/services/research.service';
import { CompanyResearch } from '../tracking/models/company-research.model';
import { CompanyIntelComponent } from './components/company-intel/company-intel.component';
```

- Add `CompanyIntelComponent` to the `imports` array.
- Inject: `private research = inject(ResearchService);`
- Add signals:

```typescript
  research = signal<CompanyResearch | null>(null);
  researchLoading = signal(true);
  researchRefreshing = signal(false);
```

- In `ngOnInit`, after setting `this.company.set(name)` and the `if (!name)` guard, load research independently of the job `forkJoin`:

```typescript
    this.research.get(name).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (r) => { this.research.set(r); this.researchLoading.set(false); },
      error: () => { this.researchLoading.set(false); },
    });
```

- Add a refresh handler:

```typescript
  refreshResearch(): void {
    const name = this.company();
    if (!name || this.researchRefreshing()) return;
    this.researchRefreshing.set(true);
    this.research.refresh({ company_name: name }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (r) => { this.research.set(r); this.researchRefreshing.set(false); },
      error: () => { this.researchRefreshing.set(false); },
    });
  }
```

> Note: `this.research` is both the injected service and the signal name — rename the injected service to `researchService` to avoid the collision. Use `researchService` in the two calls above and keep the `research` signal for the template.

In `company.component.html`, after the `</header>` (line 23) and before the loading/table block, add:

```html
  <app-company-intel
    [research]="research()"
    [loading]="researchLoading()"
    [refreshing]="researchRefreshing()"
    (refresh)="refreshResearch()"
  />
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- --include "**/company.component.spec.ts"`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

Run: `cd frontend && npx ng lint`
Expected: no errors in changed files.

```bash
git add frontend/src/app/pages/company/
git commit -m "feat(company): show company intel panel on the company detail page"
```

---

## Self-Review

- **Spec coverage:** firmographics fields + migration (Task 3 ✓); layered source external→LLM (Tasks 4,5 ✓); logo derivation from domain + config (Tasks 1,7 ✓); config additions all blank-default (Task 1 ✓); GET generates on first visit + cache + POST refresh (Tasks 6,7,10 ✓); response schema fields (Task 7 ✓); frontend intel panel with monogram fallback + not-configured + refresh, loaded independently (Tasks 8,9,10 ✓). Auto-on-first-visit is satisfied by GET → `get_or_create` (generates when absent) rather than a separate POST — matches the "maybe on first visit and then cached" answer.
- **Placeholder scan:** none — all code steps concrete. Two steps ("confirm registry import", "confirm `request.app.state.settings` attribute") are verification instructions with a stated fallback, not deferred implementation.
- **Type consistency:** `Firmographics` fields (`industry`/`company_size`/`headquarters`/`website`) identical across domain model, ORM, LLM parse, adapter, response schema, frontend model, and component; `FirmographicsPort.fetch` async signature consistent (adapter + service call); `logo_url(website, service_url)` signature consistent (helper, tests, route); `get_or_create` consistent (service, route, test). Injected-service vs signal name collision on `research` flagged and resolved (rename to `researchService`) in Task 10.
```
