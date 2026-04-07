# Portal Scanning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Greenhouse, Lever, and Ashby ATS platform adapters to the ingestion module, with a YAML-based company registry and a new `POST /scan-portals` endpoint.

**Architecture:** Extend the existing ingestion adapter/normalizer pattern. Each ATS platform gets its own adapter (fetches raw JSON from public APIs) and normalizer (maps to `NormalizedJobDTO`). A new `PortalScanner` service loads `portals.yml`, fans out to adapters, deduplicates, and returns results. The existing `IngestionOrchestrator` is not modified — portal scanning is a parallel entry point.

**Tech Stack:** Python 3.12, FastAPI, httpx, Pydantic v2, PyYAML, BeautifulSoup4 (HTML stripping), pytest-asyncio

---

## File Map

### New Files

| File | Responsibility |
|---|---|
| `backend/src/hiresense/ingestion/config/portals.yml` | YAML company registry |
| `backend/src/hiresense/ingestion/domain/portal_config.py` | Pydantic models for portal config + YAML loader |
| `backend/src/hiresense/ingestion/domain/html_stripper.py` | Shared HTML-to-text utility |
| `backend/src/hiresense/ingestion/adapters/greenhouse_adapter.py` | Greenhouse API adapter |
| `backend/src/hiresense/ingestion/adapters/lever_adapter.py` | Lever API adapter |
| `backend/src/hiresense/ingestion/adapters/ashby_adapter.py` | Ashby API adapter |
| `backend/src/hiresense/ingestion/domain/normalizers/greenhouse_normalizer.py` | Greenhouse → NormalizedJob mapper |
| `backend/src/hiresense/ingestion/domain/normalizers/lever_normalizer.py` | Lever → NormalizedJob mapper |
| `backend/src/hiresense/ingestion/domain/normalizers/ashby_normalizer.py` | Ashby → NormalizedJob mapper |
| `backend/src/hiresense/ingestion/domain/portal_scanner.py` | Portal scanning orchestrator |
| `backend/tests/unit/ingestion/test_html_stripper.py` | Tests for HTML stripper |
| `backend/tests/unit/ingestion/test_portal_config.py` | Tests for YAML config loading |
| `backend/tests/unit/ingestion/test_greenhouse.py` | Tests for Greenhouse adapter + normalizer |
| `backend/tests/unit/ingestion/test_lever.py` | Tests for Lever adapter + normalizer |
| `backend/tests/unit/ingestion/test_ashby.py` | Tests for Ashby adapter + normalizer |
| `backend/tests/unit/ingestion/test_portal_scanner.py` | Tests for portal scanner orchestrator |
| `backend/tests/unit/ingestion/test_scan_routes.py` | Tests for scan-portals API endpoint |
| `frontend/src/app/core/models/scan-portals-request.model.ts` | Request model |
| `frontend/src/app/core/models/scan-result.model.ts` | Response model |
| `frontend/src/app/core/models/portal-entry.model.ts` | Portal config model |

### Modified Files

| File | Change |
|---|---|
| `backend/src/hiresense/config.py` | Add portal scanning env vars |
| `backend/src/hiresense/ingestion/api/routes.py` | Add `POST /scan-portals` and `GET /portals` endpoints |
| `backend/src/hiresense/main.py` | Wire `PortalScanner` and register new route dependencies |
| `.env.example` | Add portal scanning env var documentation |
| `frontend/src/app/pages/ingestion/ingestion.component.ts` | Add scan portals UI |
| `frontend/src/app/pages/ingestion/ingestion.component.html` | Add scan portals template |

---

## Task 1: Add PyYAML dependency

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add pyyaml to dependencies**

In `backend/pyproject.toml`, add `"pyyaml>=6.0"` to the `dependencies` list:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",
    "httpx>=0.27.0",
    "feedparser>=6.0.0",
    "beautifulsoup4>=4.12.0",
    "pyyaml>=6.0",
]
```

- [ ] **Step 2: Install dependencies**

Run: `cd backend && uv sync`
Expected: Clean install with pyyaml resolved

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "build(backend): add pyyaml dependency for portal config"
```

---

## Task 2: Add portal scanning config to Settings

**Files:**
- Modify: `backend/src/hiresense/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Add portal config fields to Settings**

Add these fields to the `Settings` class in `backend/src/hiresense/config.py`, after the existing ingestion settings:

```python
    # Portal scanning
    portals_config_path: str = "ingestion/config/portals.yml"
    portal_scan_timeout: float = 30.0
    greenhouse_api_url: str = "https://boards-api.greenhouse.io/v1/boards"
    lever_api_url: str = "https://api.lever.co/v0/postings"
    ashby_api_url: str = "https://api.ashbyhq.com/posting-api/job-board"
```

- [ ] **Step 2: Add env vars to .env.example**

Append to `.env.example`:

```env
# === Portal Scanning ===
PORTALS_CONFIG_PATH=ingestion/config/portals.yml
PORTAL_SCAN_TIMEOUT=30
GREENHOUSE_API_URL=https://boards-api.greenhouse.io/v1/boards
LEVER_API_URL=https://api.lever.co/v0/postings
ASHBY_API_URL=https://api.ashbyhq.com/posting-api/job-board
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/hiresense/config.py .env.example
git commit -m "feat(config): add portal scanning environment variables"
```

---

## Task 3: Create HTML stripper utility

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/html_stripper.py`
- Create: `backend/tests/unit/ingestion/test_html_stripper.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_html_stripper.py`:

```python
from hiresense.ingestion.domain.html_stripper import strip_html


def test_strips_basic_tags() -> None:
    html = "<p>Hello <b>world</b></p>"
    assert strip_html(html) == "Hello world"


def test_preserves_paragraph_breaks() -> None:
    html = "<p>First paragraph</p><p>Second paragraph</p>"
    result = strip_html(html)
    assert "First paragraph" in result
    assert "Second paragraph" in result
    assert "\n" in result


def test_handles_empty_string() -> None:
    assert strip_html("") == ""


def test_handles_plain_text() -> None:
    assert strip_html("no html here") == "no html here"


def test_strips_nested_tags() -> None:
    html = "<div><ul><li>Item 1</li><li>Item 2</li></ul></div>"
    result = strip_html(html)
    assert "Item 1" in result
    assert "Item 2" in result


def test_decodes_html_entities() -> None:
    html = "<p>Salary &gt; $100k &amp; benefits</p>"
    assert strip_html(html) == "Salary > $100k & benefits"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_html_stripper.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hiresense.ingestion.domain.html_stripper'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/src/hiresense/ingestion/domain/html_stripper.py`:

```python
from __future__ import annotations

from bs4 import BeautifulSoup


def strip_html(html: str) -> str:
    """Convert HTML to plain text, preserving paragraph breaks."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["p", "br", "div", "li"]):
        tag.insert_before("\n")
    text = soup.get_text()
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_html_stripper.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/html_stripper.py backend/tests/unit/ingestion/test_html_stripper.py
git commit -m "feat(ingestion): add HTML stripper utility for portal normalizers"
```

---

## Task 4: Create portal config model and YAML loader

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/portal_config.py`
- Create: `backend/src/hiresense/ingestion/config/portals.yml`
- Create: `backend/tests/unit/ingestion/test_portal_config.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_portal_config.py`:

```python
import pytest
from pathlib import Path
from hiresense.ingestion.domain.portal_config import (
    PortalEntry,
    PortalsConfig,
    load_portals_config,
)


def test_portal_entry_model() -> None:
    entry = PortalEntry(name="Anthropic", platform="greenhouse", board_id="anthropic")
    assert entry.name == "Anthropic"
    assert entry.platform == "greenhouse"
    assert entry.board_id == "anthropic"
    assert entry.categories == []


def test_portal_entry_with_categories() -> None:
    entry = PortalEntry(
        name="Anthropic",
        platform="greenhouse",
        board_id="anthropic",
        categories=["ai-research"],
    )
    assert entry.categories == ["ai-research"]


def test_portal_entry_rejects_invalid_platform() -> None:
    with pytest.raises(ValueError):
        PortalEntry(name="Foo", platform="invalid", board_id="foo")


def test_portals_config_model() -> None:
    config = PortalsConfig(
        portals=[
            PortalEntry(name="A", platform="greenhouse", board_id="a"),
            PortalEntry(name="B", platform="lever", board_id="b"),
        ]
    )
    assert len(config.portals) == 2


def test_load_portals_config(tmp_path: Path) -> None:
    yml = tmp_path / "portals.yml"
    yml.write_text(
        "portals:\n"
        "  - name: TestCo\n"
        "    platform: ashby\n"
        "    board_id: testco\n"
        "    categories: [ai]\n"
    )
    config = load_portals_config(yml)
    assert len(config.portals) == 1
    assert config.portals[0].name == "TestCo"
    assert config.portals[0].platform == "ashby"
    assert config.portals[0].categories == ["ai"]


def test_load_portals_config_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_portals_config(Path("/nonexistent/portals.yml"))


def test_filter_by_category() -> None:
    config = PortalsConfig(
        portals=[
            PortalEntry(name="A", platform="greenhouse", board_id="a", categories=["ai"]),
            PortalEntry(name="B", platform="lever", board_id="b", categories=["devtools"]),
            PortalEntry(name="C", platform="ashby", board_id="c", categories=["ai", "devtools"]),
        ]
    )
    filtered = [p for p in config.portals if "ai" in p.categories]
    assert len(filtered) == 2
    assert {p.name for p in filtered} == {"A", "C"}


def test_filter_by_company() -> None:
    config = PortalsConfig(
        portals=[
            PortalEntry(name="Anthropic", platform="greenhouse", board_id="anthropic"),
            PortalEntry(name="Retool", platform="lever", board_id="retool"),
        ]
    )
    filtered = [p for p in config.portals if p.name in ["Anthropic"]]
    assert len(filtered) == 1
    assert filtered[0].board_id == "anthropic"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_portal_config.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/hiresense/ingestion/domain/portal_config.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel


class PortalEntry(BaseModel):
    name: str
    platform: Literal["greenhouse", "lever", "ashby"]
    board_id: str
    categories: list[str] = []


class PortalsConfig(BaseModel):
    portals: list[PortalEntry]


def load_portals_config(path: Path) -> PortalsConfig:
    """Load and validate portals.yml from the given path."""
    if not path.exists():
        raise FileNotFoundError(f"Portals config not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return PortalsConfig.model_validate(data)
```

- [ ] **Step 4: Create the default portals.yml**

Create `backend/src/hiresense/ingestion/config/portals.yml`:

```yaml
portals:
  # AI Research Labs
  - name: Anthropic
    platform: greenhouse
    board_id: anthropic
    categories: [ai-research]

  - name: OpenAI
    platform: greenhouse
    board_id: openai
    categories: [ai-research]

  - name: Mistral
    platform: greenhouse
    board_id: mistralai
    categories: [ai-research]

  - name: Cohere
    platform: greenhouse
    board_id: cohere
    categories: [ai-research]

  - name: LangChain
    platform: greenhouse
    board_id: langchain
    categories: [ai-research]

  # Voice Technology
  - name: ElevenLabs
    platform: ashby
    board_id: elevenlabs
    categories: [voice-tech]

  - name: Deepgram
    platform: greenhouse
    board_id: deepgram
    categories: [voice-tech]

  # Development Platforms
  - name: Retool
    platform: lever
    board_id: retool
    categories: [dev-platforms]

  - name: Vercel
    platform: greenhouse
    board_id: vercel
    categories: [dev-platforms]

  - name: Temporal
    platform: greenhouse
    board_id: temporal
    categories: [dev-platforms]

  # LLM Operations
  - name: Weights & Biases
    platform: greenhouse
    board_id: wandb
    categories: [llm-ops]

  # Workflow Automation
  - name: n8n
    platform: greenhouse
    board_id: n8n
    categories: [workflow-automation]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_portal_config.py -v`
Expected: All 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/portal_config.py backend/src/hiresense/ingestion/config/portals.yml backend/tests/unit/ingestion/test_portal_config.py
git commit -m "feat(ingestion): add portal config model and YAML loader with default company list"
```

---

## Task 5: Greenhouse adapter

**Files:**
- Create: `backend/src/hiresense/ingestion/adapters/greenhouse_adapter.py`
- Create: `backend/tests/unit/ingestion/test_greenhouse.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_greenhouse.py`:

```python
import pytest
from hiresense.ingestion.adapters.greenhouse_adapter import GreenhouseAdapter
from hiresense.kernel.value_objects import SourceType


class FakeResponse:
    def __init__(self, data: list | dict, status_code: int = 200) -> None:
        self._data = data
        self.status_code = status_code

    def json(self) -> list | dict:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class FakeHttpClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[str, dict]] = []

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.requests.append((url, kwargs))
        return self._responses.pop(0)


SAMPLE_GREENHOUSE_JOBS = [
    {
        "id": 101,
        "title": "Backend Engineer",
        "location": {"name": "San Francisco, CA"},
        "content": "<p>Build <b>APIs</b> with Python</p>",
        "absolute_url": "https://boards.greenhouse.io/anthropic/jobs/101",
        "updated_at": "2026-04-01T12:00:00Z",
        "departments": [{"name": "Engineering"}],
    },
    {
        "id": 102,
        "title": "ML Researcher",
        "location": {"name": "Remote"},
        "content": "<p>Research LLMs</p>",
        "absolute_url": "https://boards.greenhouse.io/anthropic/jobs/102",
        "updated_at": "2026-03-28T12:00:00Z",
        "departments": [{"name": "Research"}],
    },
]


@pytest.mark.asyncio
async def test_greenhouse_fetches_jobs() -> None:
    client = FakeHttpClient([FakeResponse(SAMPLE_GREENHOUSE_JOBS)])
    adapter = GreenhouseAdapter(
        http_client=client,
        base_url="https://boards-api.greenhouse.io/v1/boards",
        timeout=30.0,
    )
    jobs = await adapter.fetch_jobs(board_id="anthropic", company_name="Anthropic")
    assert len(jobs) == 2
    assert jobs[0].source == "greenhouse"
    assert jobs[0].source_id == "101"
    assert jobs[0].raw_data["title"] == "Backend Engineer"
    assert jobs[0].raw_data["company"] == "Anthropic"


@pytest.mark.asyncio
async def test_greenhouse_builds_correct_url() -> None:
    client = FakeHttpClient([FakeResponse([])])
    adapter = GreenhouseAdapter(
        http_client=client,
        base_url="https://boards-api.greenhouse.io/v1/boards",
        timeout=30.0,
    )
    await adapter.fetch_jobs(board_id="anthropic", company_name="Anthropic")
    url, kwargs = client.requests[0]
    assert url == "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs"
    assert kwargs["params"]["content"] == "true"


@pytest.mark.asyncio
async def test_greenhouse_empty_board() -> None:
    client = FakeHttpClient([FakeResponse([])])
    adapter = GreenhouseAdapter(
        http_client=client,
        base_url="https://boards-api.greenhouse.io/v1/boards",
        timeout=30.0,
    )
    jobs = await adapter.fetch_jobs(board_id="empty", company_name="Empty")
    assert jobs == []


def test_greenhouse_source_metadata() -> None:
    adapter = GreenhouseAdapter(http_client=None, base_url="", timeout=30.0)
    assert adapter.source_name() == "greenhouse"
    assert adapter.source_type() == SourceType.API
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_greenhouse.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/hiresense/ingestion/adapters/greenhouse_adapter.py`:

```python
from __future__ import annotations

import logging
from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

logger = logging.getLogger(__name__)


class GreenhouseAdapter:
    def __init__(self, http_client: Any, base_url: str, timeout: float) -> None:
        self._http = http_client
        self._base_url = base_url
        self._timeout = timeout

    def source_name(self) -> str:
        return "greenhouse"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(
        self, board_id: str, company_name: str
    ) -> list[RawJobListing]:
        url = f"{self._base_url}/{board_id}/jobs"
        params = {"content": "true"}
        response = await self._http.get(
            url, params=params, timeout=self._timeout
        )
        response.raise_for_status()
        data = response.json()
        jobs = data if isinstance(data, list) else data.get("jobs", [])
        return [
            RawJobListing(
                source="greenhouse",
                source_id=str(job["id"]),
                raw_data={**job, "company": company_name},
            )
            for job in jobs
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_greenhouse.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/adapters/greenhouse_adapter.py backend/tests/unit/ingestion/test_greenhouse.py
git commit -m "feat(ingestion): add Greenhouse ATS adapter"
```

---

## Task 6: Greenhouse normalizer

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/normalizers/greenhouse_normalizer.py`
- Modify: `backend/tests/unit/ingestion/test_greenhouse.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/ingestion/test_greenhouse.py`:

```python
from hiresense.ingestion.domain.normalizers.greenhouse_normalizer import GreenhouseNormalizer
from hiresense.ingestion.domain.models import RawJobListing


def test_greenhouse_normalizer() -> None:
    raw = RawJobListing(
        source="greenhouse",
        source_id="101",
        raw_data={
            "title": "Backend Engineer",
            "company": "Anthropic",
            "location": {"name": "San Francisco, CA"},
            "content": "<p>Build <b>APIs</b> with Python</p>",
            "absolute_url": "https://boards.greenhouse.io/anthropic/jobs/101",
            "updated_at": "2026-04-01T12:00:00Z",
            "departments": [{"name": "Engineering"}],
        },
    )
    normalizer = GreenhouseNormalizer()
    result = normalizer.normalize(raw)
    assert result["title"] == "Backend Engineer"
    assert result["company"] == "Anthropic"
    assert result["url"] == "https://boards.greenhouse.io/anthropic/jobs/101"
    assert result["location"] == "San Francisco, CA"
    assert "<p>" not in result["description"]
    assert "Build" in result["description"]
    assert "APIs" in result["description"]


def test_greenhouse_normalizer_missing_fields() -> None:
    raw = RawJobListing(
        source="greenhouse",
        source_id="200",
        raw_data={
            "title": "SWE",
            "company": "X",
            "content": "",
            "absolute_url": "https://example.com/200",
        },
    )
    normalizer = GreenhouseNormalizer()
    result = normalizer.normalize(raw)
    assert result["title"] == "SWE"
    assert result["location"] == ""
    assert result["description"] == ""
    assert result["department"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_greenhouse.py::test_greenhouse_normalizer -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/hiresense/ingestion/domain/normalizers/greenhouse_normalizer.py`:

```python
from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class GreenhouseNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        location_obj = d.get("location")
        location = location_obj.get("name", "") if isinstance(location_obj, dict) else ""
        departments = d.get("departments", [])
        department = departments[0]["name"] if departments else None

        return {
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "description": strip_html(d.get("content", "")),
            "skills": [],
            "location": location,
            "salary_range": None,
            "url": d.get("absolute_url", ""),
            "language": "en",
            "posted_date": d.get("updated_at"),
            "department": department,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_greenhouse.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/normalizers/greenhouse_normalizer.py backend/tests/unit/ingestion/test_greenhouse.py
git commit -m "feat(ingestion): add Greenhouse normalizer"
```

---

## Task 7: Lever adapter

**Files:**
- Create: `backend/src/hiresense/ingestion/adapters/lever_adapter.py`
- Create: `backend/tests/unit/ingestion/test_lever.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_lever.py`:

```python
import pytest
from hiresense.ingestion.adapters.lever_adapter import LeverAdapter
from hiresense.kernel.value_objects import SourceType


class FakeResponse:
    def __init__(self, data: list | dict, status_code: int = 200) -> None:
        self._data = data
        self.status_code = status_code

    def json(self) -> list | dict:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class FakeHttpClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[str, dict]] = []

    async def get(self, url: str, **kwargs) -> FakeResponse:
        self.requests.append((url, kwargs))
        return self._responses.pop(0)


SAMPLE_LEVER_POSTINGS = [
    {
        "id": "abc-123",
        "text": "Frontend Engineer",
        "categories": {
            "location": "New York, NY",
            "team": "Product",
        },
        "description": "<p>Build UIs with React</p>",
        "hostedUrl": "https://jobs.lever.co/retool/abc-123",
        "createdAt": 1711699200000,
    },
]


@pytest.mark.asyncio
async def test_lever_fetches_jobs() -> None:
    client = FakeHttpClient([FakeResponse(SAMPLE_LEVER_POSTINGS)])
    adapter = LeverAdapter(
        http_client=client,
        base_url="https://api.lever.co/v0/postings",
        timeout=30.0,
    )
    jobs = await adapter.fetch_jobs(board_id="retool", company_name="Retool")
    assert len(jobs) == 1
    assert jobs[0].source == "lever"
    assert jobs[0].source_id == "abc-123"
    assert jobs[0].raw_data["text"] == "Frontend Engineer"
    assert jobs[0].raw_data["company"] == "Retool"


@pytest.mark.asyncio
async def test_lever_builds_correct_url() -> None:
    client = FakeHttpClient([FakeResponse([])])
    adapter = LeverAdapter(
        http_client=client,
        base_url="https://api.lever.co/v0/postings",
        timeout=30.0,
    )
    await adapter.fetch_jobs(board_id="retool", company_name="Retool")
    url, kwargs = client.requests[0]
    assert url == "https://api.lever.co/v0/postings/retool"
    assert kwargs["params"]["mode"] == "json"


@pytest.mark.asyncio
async def test_lever_empty_board() -> None:
    client = FakeHttpClient([FakeResponse([])])
    adapter = LeverAdapter(
        http_client=client,
        base_url="https://api.lever.co/v0/postings",
        timeout=30.0,
    )
    jobs = await adapter.fetch_jobs(board_id="empty", company_name="Empty")
    assert jobs == []


def test_lever_source_metadata() -> None:
    adapter = LeverAdapter(http_client=None, base_url="", timeout=30.0)
    assert adapter.source_name() == "lever"
    assert adapter.source_type() == SourceType.API
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_lever.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/hiresense/ingestion/adapters/lever_adapter.py`:

```python
from __future__ import annotations

import logging
from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

logger = logging.getLogger(__name__)


class LeverAdapter:
    def __init__(self, http_client: Any, base_url: str, timeout: float) -> None:
        self._http = http_client
        self._base_url = base_url
        self._timeout = timeout

    def source_name(self) -> str:
        return "lever"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(
        self, board_id: str, company_name: str
    ) -> list[RawJobListing]:
        url = f"{self._base_url}/{board_id}"
        params = {"mode": "json"}
        response = await self._http.get(
            url, params=params, timeout=self._timeout
        )
        response.raise_for_status()
        data = response.json()
        postings = data if isinstance(data, list) else []
        return [
            RawJobListing(
                source="lever",
                source_id=str(posting.get("id", "")),
                raw_data={**posting, "company": company_name},
            )
            for posting in postings
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_lever.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/adapters/lever_adapter.py backend/tests/unit/ingestion/test_lever.py
git commit -m "feat(ingestion): add Lever ATS adapter"
```

---

## Task 8: Lever normalizer

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/normalizers/lever_normalizer.py`
- Modify: `backend/tests/unit/ingestion/test_lever.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/ingestion/test_lever.py`:

```python
from hiresense.ingestion.domain.normalizers.lever_normalizer import LeverNormalizer
from hiresense.ingestion.domain.models import RawJobListing


def test_lever_normalizer() -> None:
    raw = RawJobListing(
        source="lever",
        source_id="abc-123",
        raw_data={
            "text": "Frontend Engineer",
            "company": "Retool",
            "categories": {
                "location": "New York, NY",
                "team": "Product",
            },
            "description": "<p>Build UIs with <b>React</b></p>",
            "hostedUrl": "https://jobs.lever.co/retool/abc-123",
            "createdAt": 1711699200000,
        },
    )
    normalizer = LeverNormalizer()
    result = normalizer.normalize(raw)
    assert result["title"] == "Frontend Engineer"
    assert result["company"] == "Retool"
    assert result["url"] == "https://jobs.lever.co/retool/abc-123"
    assert result["location"] == "New York, NY"
    assert result["department"] == "Product"
    assert "<p>" not in result["description"]
    assert "Build UIs" in result["description"]


def test_lever_normalizer_missing_categories() -> None:
    raw = RawJobListing(
        source="lever",
        source_id="xyz",
        raw_data={
            "text": "SWE",
            "company": "X",
            "description": "",
            "hostedUrl": "https://example.com/xyz",
        },
    )
    normalizer = LeverNormalizer()
    result = normalizer.normalize(raw)
    assert result["title"] == "SWE"
    assert result["location"] == ""
    assert result["department"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_lever.py::test_lever_normalizer -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/hiresense/ingestion/domain/normalizers/lever_normalizer.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class LeverNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        categories = d.get("categories") or {}
        created_ms = d.get("createdAt")
        posted_date = (
            datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc).isoformat()
            if created_ms
            else None
        )

        return {
            "title": d.get("text", ""),
            "company": d.get("company", ""),
            "description": strip_html(d.get("description", "")),
            "skills": [],
            "location": categories.get("location", ""),
            "salary_range": None,
            "url": d.get("hostedUrl", ""),
            "language": "en",
            "posted_date": posted_date,
            "department": categories.get("team"),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_lever.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/normalizers/lever_normalizer.py backend/tests/unit/ingestion/test_lever.py
git commit -m "feat(ingestion): add Lever normalizer"
```

---

## Task 9: Ashby adapter

**Files:**
- Create: `backend/src/hiresense/ingestion/adapters/ashby_adapter.py`
- Create: `backend/tests/unit/ingestion/test_ashby.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_ashby.py`:

```python
import pytest
from hiresense.ingestion.adapters.ashby_adapter import AshbyAdapter
from hiresense.kernel.value_objects import SourceType


class FakeResponse:
    def __init__(self, data: dict, status_code: int = 200) -> None:
        self._data = data
        self.status_code = status_code

    def json(self) -> dict:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class FakeHttpClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[str, dict]] = []

    async def post(self, url: str, **kwargs) -> FakeResponse:
        self.requests.append((url, kwargs))
        return self._responses.pop(0)


SAMPLE_ASHBY_RESPONSE = {
    "jobs": [
        {
            "id": "job-001",
            "title": "AI Engineer",
            "location": "Remote - US",
            "descriptionHtml": "<p>Work on <b>voice synthesis</b></p>",
            "jobUrl": "https://jobs.ashbyhq.com/elevenlabs/job-001",
            "publishedAt": "2026-04-01T00:00:00.000Z",
            "departmentName": "AI Team",
        },
    ]
}


@pytest.mark.asyncio
async def test_ashby_fetches_jobs() -> None:
    client = FakeHttpClient([FakeResponse(SAMPLE_ASHBY_RESPONSE)])
    adapter = AshbyAdapter(
        http_client=client,
        base_url="https://api.ashbyhq.com/posting-api/job-board",
        timeout=30.0,
    )
    jobs = await adapter.fetch_jobs(board_id="elevenlabs", company_name="ElevenLabs")
    assert len(jobs) == 1
    assert jobs[0].source == "ashby"
    assert jobs[0].source_id == "job-001"
    assert jobs[0].raw_data["title"] == "AI Engineer"
    assert jobs[0].raw_data["company"] == "ElevenLabs"


@pytest.mark.asyncio
async def test_ashby_builds_correct_url() -> None:
    client = FakeHttpClient([FakeResponse({"jobs": []})])
    adapter = AshbyAdapter(
        http_client=client,
        base_url="https://api.ashbyhq.com/posting-api/job-board",
        timeout=30.0,
    )
    await adapter.fetch_jobs(board_id="elevenlabs", company_name="ElevenLabs")
    url, _ = client.requests[0]
    assert url == "https://api.ashbyhq.com/posting-api/job-board/elevenlabs"


@pytest.mark.asyncio
async def test_ashby_empty_board() -> None:
    client = FakeHttpClient([FakeResponse({"jobs": []})])
    adapter = AshbyAdapter(
        http_client=client,
        base_url="https://api.ashbyhq.com/posting-api/job-board",
        timeout=30.0,
    )
    jobs = await adapter.fetch_jobs(board_id="empty", company_name="Empty")
    assert jobs == []


def test_ashby_source_metadata() -> None:
    adapter = AshbyAdapter(http_client=None, base_url="", timeout=30.0)
    assert adapter.source_name() == "ashby"
    assert adapter.source_type() == SourceType.API
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_ashby.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/hiresense/ingestion/adapters/ashby_adapter.py`:

```python
from __future__ import annotations

import logging
from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

logger = logging.getLogger(__name__)


class AshbyAdapter:
    def __init__(self, http_client: Any, base_url: str, timeout: float) -> None:
        self._http = http_client
        self._base_url = base_url
        self._timeout = timeout

    def source_name(self) -> str:
        return "ashby"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(
        self, board_id: str, company_name: str
    ) -> list[RawJobListing]:
        url = f"{self._base_url}/{board_id}"
        response = await self._http.post(url, timeout=self._timeout)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs", [])
        return [
            RawJobListing(
                source="ashby",
                source_id=str(job.get("id", "")),
                raw_data={**job, "company": company_name},
            )
            for job in jobs
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_ashby.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/adapters/ashby_adapter.py backend/tests/unit/ingestion/test_ashby.py
git commit -m "feat(ingestion): add Ashby ATS adapter"
```

---

## Task 10: Ashby normalizer

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/normalizers/ashby_normalizer.py`
- Modify: `backend/tests/unit/ingestion/test_ashby.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/ingestion/test_ashby.py`:

```python
from hiresense.ingestion.domain.normalizers.ashby_normalizer import AshbyNormalizer
from hiresense.ingestion.domain.models import RawJobListing


def test_ashby_normalizer() -> None:
    raw = RawJobListing(
        source="ashby",
        source_id="job-001",
        raw_data={
            "title": "AI Engineer",
            "company": "ElevenLabs",
            "location": "Remote - US",
            "descriptionHtml": "<p>Work on <b>voice synthesis</b></p>",
            "jobUrl": "https://jobs.ashbyhq.com/elevenlabs/job-001",
            "publishedAt": "2026-04-01T00:00:00.000Z",
            "departmentName": "AI Team",
        },
    )
    normalizer = AshbyNormalizer()
    result = normalizer.normalize(raw)
    assert result["title"] == "AI Engineer"
    assert result["company"] == "ElevenLabs"
    assert result["url"] == "https://jobs.ashbyhq.com/elevenlabs/job-001"
    assert result["location"] == "Remote - US"
    assert result["department"] == "AI Team"
    assert "<p>" not in result["description"]
    assert "voice synthesis" in result["description"]


def test_ashby_normalizer_missing_fields() -> None:
    raw = RawJobListing(
        source="ashby",
        source_id="x",
        raw_data={
            "title": "SWE",
            "company": "X",
            "descriptionHtml": "",
            "jobUrl": "https://example.com/x",
        },
    )
    normalizer = AshbyNormalizer()
    result = normalizer.normalize(raw)
    assert result["title"] == "SWE"
    assert result["location"] == ""
    assert result["department"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_ashby.py::test_ashby_normalizer -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/hiresense/ingestion/domain/normalizers/ashby_normalizer.py`:

```python
from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class AshbyNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data

        return {
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "description": strip_html(d.get("descriptionHtml", "")),
            "skills": [],
            "location": d.get("location", ""),
            "salary_range": None,
            "url": d.get("jobUrl", ""),
            "language": "en",
            "posted_date": d.get("publishedAt"),
            "department": d.get("departmentName"),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_ashby.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/normalizers/ashby_normalizer.py backend/tests/unit/ingestion/test_ashby.py
git commit -m "feat(ingestion): add Ashby normalizer"
```

---

## Task 11: Portal scanner service

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/portal_scanner.py`
- Create: `backend/tests/unit/ingestion/test_portal_scanner.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_portal_scanner.py`:

```python
import pytest
from hiresense.ingestion.domain.portal_scanner import PortalScanner, ScanFilters, ScanResult
from hiresense.ingestion.domain.portal_config import PortalEntry, PortalsConfig
from hiresense.ingestion.domain.models import RawJobListing


class FakeAdapter:
    def __init__(self, jobs: list[RawJobListing] | Exception) -> None:
        self._jobs = jobs
        self.calls: list[tuple[str, str]] = []

    async def fetch_jobs(self, board_id: str, company_name: str) -> list[RawJobListing]:
        self.calls.append((board_id, company_name))
        if isinstance(self._jobs, Exception):
            raise self._jobs
        return self._jobs


class FakeNormalizer:
    def normalize(self, raw: RawJobListing) -> dict:
        return {
            "title": raw.raw_data.get("title", ""),
            "company": raw.raw_data.get("company", ""),
            "description": raw.raw_data.get("description", ""),
            "skills": [],
            "location": "",
            "salary_range": None,
            "url": raw.raw_data.get("url", f"https://example.com/{raw.source_id}"),
            "language": "en",
        }


class FakeEventBus:
    def __init__(self) -> None:
        self.events: list = []

    async def publish(self, event) -> None:
        self.events.append(event)


def _make_config(portals: list[PortalEntry]) -> PortalsConfig:
    return PortalsConfig(portals=portals)


def _make_raw(source: str, source_id: str, title: str, company: str, url: str) -> RawJobListing:
    return RawJobListing(
        source=source,
        source_id=source_id,
        raw_data={"title": title, "company": company, "url": url},
    )


@pytest.mark.asyncio
async def test_scan_all_portals() -> None:
    gh_jobs = [_make_raw("greenhouse", "1", "SWE", "Anthropic", "https://gh.io/1")]
    lever_jobs = [_make_raw("lever", "2", "FE", "Retool", "https://lever.co/2")]

    gh_adapter = FakeAdapter(gh_jobs)
    lever_adapter = FakeAdapter(lever_jobs)

    config = _make_config([
        PortalEntry(name="Anthropic", platform="greenhouse", board_id="anthropic"),
        PortalEntry(name="Retool", platform="lever", board_id="retool"),
    ])

    scanner = PortalScanner(
        config=config,
        adapters={"greenhouse": gh_adapter, "lever": lever_adapter},
        normalizers={"greenhouse": FakeNormalizer(), "lever": FakeNormalizer()},
        event_bus=FakeEventBus(),
    )

    result = await scanner.scan(ScanFilters())
    assert result.total_fetched == 2
    assert result.new == 2
    assert result.duplicates == 0
    assert len(result.jobs) == 2
    assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_scan_filters_by_category() -> None:
    gh_adapter = FakeAdapter([_make_raw("greenhouse", "1", "SWE", "Anthropic", "https://gh.io/1")])
    lever_adapter = FakeAdapter([_make_raw("lever", "2", "FE", "Retool", "https://lever.co/2")])

    config = _make_config([
        PortalEntry(name="Anthropic", platform="greenhouse", board_id="anthropic", categories=["ai"]),
        PortalEntry(name="Retool", platform="lever", board_id="retool", categories=["devtools"]),
    ])

    scanner = PortalScanner(
        config=config,
        adapters={"greenhouse": gh_adapter, "lever": lever_adapter},
        normalizers={"greenhouse": FakeNormalizer(), "lever": FakeNormalizer()},
        event_bus=FakeEventBus(),
    )

    result = await scanner.scan(ScanFilters(categories=["ai"]))
    assert result.total_fetched == 1
    assert result.jobs[0].title == "SWE"
    assert len(lever_adapter.calls) == 0


@pytest.mark.asyncio
async def test_scan_filters_by_company() -> None:
    gh_adapter = FakeAdapter([_make_raw("greenhouse", "1", "SWE", "Anthropic", "https://gh.io/1")])

    config = _make_config([
        PortalEntry(name="Anthropic", platform="greenhouse", board_id="anthropic"),
        PortalEntry(name="OpenAI", platform="greenhouse", board_id="openai"),
    ])

    scanner = PortalScanner(
        config=config,
        adapters={"greenhouse": gh_adapter},
        normalizers={"greenhouse": FakeNormalizer()},
        event_bus=FakeEventBus(),
    )

    result = await scanner.scan(ScanFilters(companies=["Anthropic"]))
    assert result.total_fetched == 1
    assert len(gh_adapter.calls) == 1
    assert gh_adapter.calls[0] == ("anthropic", "Anthropic")


@pytest.mark.asyncio
async def test_scan_deduplicates() -> None:
    same_job = _make_raw("greenhouse", "1", "SWE", "Anthropic", "https://gh.io/1")
    gh_adapter = FakeAdapter([same_job, same_job])

    config = _make_config([
        PortalEntry(name="Anthropic", platform="greenhouse", board_id="anthropic"),
    ])

    scanner = PortalScanner(
        config=config,
        adapters={"greenhouse": gh_adapter},
        normalizers={"greenhouse": FakeNormalizer()},
        event_bus=FakeEventBus(),
    )

    result = await scanner.scan(ScanFilters())
    assert result.total_fetched == 2
    assert result.new == 1
    assert result.duplicates == 1


@pytest.mark.asyncio
async def test_scan_collects_errors() -> None:
    gh_adapter = FakeAdapter(TimeoutError("timed out"))

    config = _make_config([
        PortalEntry(name="Anthropic", platform="greenhouse", board_id="anthropic"),
    ])

    scanner = PortalScanner(
        config=config,
        adapters={"greenhouse": gh_adapter},
        normalizers={"greenhouse": FakeNormalizer()},
        event_bus=FakeEventBus(),
    )

    result = await scanner.scan(ScanFilters())
    assert result.total_fetched == 0
    assert len(result.errors) == 1
    assert result.errors[0].portal == "Anthropic"
    assert result.errors[0].platform == "greenhouse"
    assert "timed out" in result.errors[0].error


@pytest.mark.asyncio
async def test_scan_publishes_event_when_jobs_found() -> None:
    gh_adapter = FakeAdapter([_make_raw("greenhouse", "1", "SWE", "Anthropic", "https://gh.io/1")])
    event_bus = FakeEventBus()

    config = _make_config([
        PortalEntry(name="Anthropic", platform="greenhouse", board_id="anthropic"),
    ])

    scanner = PortalScanner(
        config=config,
        adapters={"greenhouse": gh_adapter},
        normalizers={"greenhouse": FakeNormalizer()},
        event_bus=event_bus,
    )

    await scanner.scan(ScanFilters())
    assert len(event_bus.events) == 1
    assert event_bus.events[0].event_type == "jobs.ingested"


@pytest.mark.asyncio
async def test_scan_no_event_when_no_new_jobs() -> None:
    gh_adapter = FakeAdapter([])
    event_bus = FakeEventBus()

    config = _make_config([
        PortalEntry(name="Anthropic", platform="greenhouse", board_id="anthropic"),
    ])

    scanner = PortalScanner(
        config=config,
        adapters={"greenhouse": gh_adapter},
        normalizers={"greenhouse": FakeNormalizer()},
        event_bus=event_bus,
    )

    await scanner.scan(ScanFilters())
    assert len(event_bus.events) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_portal_scanner.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/hiresense/ingestion/domain/portal_scanner.py`:

```python
from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.normalizers.job_normalizer import JobNormalizer
from hiresense.ingestion.domain.portal_config import PortalEntry, PortalsConfig
from hiresense.kernel.contracts.jobs_ingested_event import JobsIngestedEvent

logger = logging.getLogger(__name__)


class ScanFilters(BaseModel):
    categories: list[str] = []
    companies: list[str] = []
    keyword: str | None = None


class ScanError(BaseModel):
    portal: str
    platform: str
    error: str


class ScanResult(BaseModel):
    total_fetched: int
    new: int
    duplicates: int
    jobs: list[NormalizedJob]
    errors: list[ScanError]


class PortalScanner:
    def __init__(
        self,
        config: PortalsConfig,
        adapters: dict[str, Any],
        normalizers: dict[str, JobNormalizer],
        event_bus: Any,
    ) -> None:
        self._config = config
        self._adapters = adapters
        self._normalizers = normalizers
        self._event_bus = event_bus

    def _filter_portals(self, filters: ScanFilters) -> list[PortalEntry]:
        portals = self._config.portals
        if filters.categories:
            portals = [
                p for p in portals
                if any(c in p.categories for c in filters.categories)
            ]
        if filters.companies:
            portals = [p for p in portals if p.name in filters.companies]
        return portals

    async def scan(self, filters: ScanFilters) -> ScanResult:
        portals = self._filter_portals(filters)
        all_jobs: list[NormalizedJob] = []
        errors: list[ScanError] = []
        total_fetched = 0
        seen_dedup_keys: set[str] = set()

        for portal in portals:
            adapter = self._adapters.get(portal.platform)
            normalizer = self._normalizers.get(portal.platform)
            if adapter is None or normalizer is None:
                logger.warning("No adapter/normalizer for platform: %s", portal.platform)
                continue

            try:
                raw_jobs = await adapter.fetch_jobs(
                    board_id=portal.board_id,
                    company_name=portal.name,
                )
            except Exception as exc:
                logger.exception("Failed to scan portal %s", portal.name)
                errors.append(ScanError(
                    portal=portal.name,
                    platform=portal.platform,
                    error=str(exc),
                ))
                continue

            total_fetched += len(raw_jobs)

            for raw in raw_jobs:
                normalized_data = normalizer.normalize(raw)
                job = NormalizedJob(
                    id=str(uuid.uuid4()),
                    source=portal.platform,
                    source_type="api",
                    **normalized_data,
                )
                dedup = job.dedup_key()
                if dedup not in seen_dedup_keys:
                    seen_dedup_keys.add(dedup)
                    all_jobs.append(job)

        duplicates = total_fetched - len(all_jobs)

        if all_jobs:
            event = JobsIngestedEvent(
                payload={
                    "job_ids": [j.id for j in all_jobs],
                    "source": "portal_scan",
                },
            )
            await self._event_bus.publish(event)

        return ScanResult(
            total_fetched=total_fetched,
            new=len(all_jobs),
            duplicates=duplicates,
            jobs=all_jobs,
            errors=errors,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_portal_scanner.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/portal_scanner.py backend/tests/unit/ingestion/test_portal_scanner.py
git commit -m "feat(ingestion): add portal scanner orchestrator with filtering, dedup, and error collection"
```

---

## Task 12: API routes for portal scanning

**Files:**
- Modify: `backend/src/hiresense/ingestion/api/routes.py`
- Create: `backend/tests/unit/ingestion/test_scan_routes.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_scan_routes.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hiresense.ingestion.api.routes import router, get_portal_scanner, get_portals_config
from hiresense.ingestion.domain.portal_scanner import PortalScanner, ScanFilters, ScanResult, ScanError
from hiresense.ingestion.domain.portal_config import PortalsConfig, PortalEntry
from hiresense.ingestion.domain.models import NormalizedJob


def _make_app(scanner: PortalScanner, config: PortalsConfig) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_portal_scanner] = lambda: scanner
    app.dependency_overrides[get_portals_config] = lambda: config
    return app


class FakePortalScanner:
    def __init__(self, result: ScanResult) -> None:
        self._result = result
        self.last_filters: ScanFilters | None = None

    async def scan(self, filters: ScanFilters) -> ScanResult:
        self.last_filters = filters
        return self._result


SAMPLE_JOB = NormalizedJob(
    id="abc",
    title="SWE",
    company="Anthropic",
    description="Build stuff",
    skills=[],
    location="Remote",
    source="greenhouse",
    source_type="api",
    url="https://example.com/abc",
)


def test_scan_portals_returns_results() -> None:
    result = ScanResult(total_fetched=1, new=1, duplicates=0, jobs=[SAMPLE_JOB], errors=[])
    scanner = FakePortalScanner(result)
    config = PortalsConfig(portals=[])

    app = _make_app(scanner, config)
    client = TestClient(app)

    response = client.post("/ingestion/scan-portals", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["total_fetched"] == 1
    assert data["new"] == 1
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["title"] == "SWE"


def test_scan_portals_passes_filters() -> None:
    result = ScanResult(total_fetched=0, new=0, duplicates=0, jobs=[], errors=[])
    scanner = FakePortalScanner(result)
    config = PortalsConfig(portals=[])

    app = _make_app(scanner, config)
    client = TestClient(app)

    client.post("/ingestion/scan-portals", json={
        "categories": ["ai-research"],
        "companies": ["Anthropic"],
        "keyword": "python",
    })
    assert scanner.last_filters.categories == ["ai-research"]
    assert scanner.last_filters.companies == ["Anthropic"]
    assert scanner.last_filters.keyword == "python"


def test_scan_portals_returns_errors() -> None:
    result = ScanResult(
        total_fetched=0,
        new=0,
        duplicates=0,
        jobs=[],
        errors=[ScanError(portal="X", platform="greenhouse", error="timeout")],
    )
    scanner = FakePortalScanner(result)
    config = PortalsConfig(portals=[])

    app = _make_app(scanner, config)
    client = TestClient(app)

    response = client.post("/ingestion/scan-portals", json={})
    data = response.json()
    assert len(data["errors"]) == 1
    assert data["errors"][0]["portal"] == "X"


def test_get_portals_config() -> None:
    config = PortalsConfig(portals=[
        PortalEntry(name="Anthropic", platform="greenhouse", board_id="anthropic", categories=["ai"]),
    ])
    scanner = FakePortalScanner(ScanResult(total_fetched=0, new=0, duplicates=0, jobs=[], errors=[]))

    app = _make_app(scanner, config)
    client = TestClient(app)

    response = client.get("/ingestion/portals")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Anthropic"
    assert data[0]["categories"] == ["ai"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_scan_routes.py -v`
Expected: FAIL — `ImportError` (get_portal_scanner not defined yet)

- [ ] **Step 3: Add new endpoints to routes.py**

Add the following to `backend/src/hiresense/ingestion/api/routes.py`:

```python
from hiresense.ingestion.domain.portal_scanner import PortalScanner, ScanFilters, ScanResult
from hiresense.ingestion.domain.portal_config import PortalEntry, PortalsConfig


def get_portal_scanner() -> PortalScanner:
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")


def get_portals_config() -> PortalsConfig:
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")


@router.post("/scan-portals", response_model=ScanResult)
async def scan_portals(
    filters: ScanFilters,
    scanner: Annotated[PortalScanner, Depends(get_portal_scanner)],
) -> ScanResult:
    return await scanner.scan(filters)


@router.get("/portals", response_model=list[PortalEntry])
async def list_portals(
    config: Annotated[PortalsConfig, Depends(get_portals_config)],
) -> list[PortalEntry]:
    return config.portals
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_scan_routes.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/api/routes.py backend/tests/unit/ingestion/test_scan_routes.py
git commit -m "feat(ingestion): add POST /scan-portals and GET /portals API endpoints"
```

---

## Task 13: Wire portal scanner into app factory

**Files:**
- Modify: `backend/src/hiresense/main.py`

- [ ] **Step 1: Add imports**

Add these imports to `backend/src/hiresense/main.py`:

```python
from pathlib import Path
from hiresense.ingestion.adapters.greenhouse_adapter import GreenhouseAdapter
from hiresense.ingestion.adapters.lever_adapter import LeverAdapter
from hiresense.ingestion.adapters.ashby_adapter import AshbyAdapter
from hiresense.ingestion.domain.normalizers.greenhouse_normalizer import GreenhouseNormalizer
from hiresense.ingestion.domain.normalizers.lever_normalizer import LeverNormalizer
from hiresense.ingestion.domain.normalizers.ashby_normalizer import AshbyNormalizer
from hiresense.ingestion.domain.portal_config import load_portals_config
from hiresense.ingestion.domain.portal_scanner import PortalScanner
from hiresense.ingestion.api.routes import get_portal_scanner, get_portals_config
```

- [ ] **Step 2: Wire portal scanner after existing ingestion setup**

Add this block after the existing ingestion orchestrator wiring in `create_app()`:

```python
    # --- Portal scanning ---
    portals_config_path = Path(__file__).parent / settings.portals_config_path
    portals_config = load_portals_config(portals_config_path)

    portal_adapters = {
        "greenhouse": GreenhouseAdapter(
            http_client=http_client,
            base_url=settings.greenhouse_api_url,
            timeout=settings.portal_scan_timeout,
        ),
        "lever": LeverAdapter(
            http_client=http_client,
            base_url=settings.lever_api_url,
            timeout=settings.portal_scan_timeout,
        ),
        "ashby": AshbyAdapter(
            http_client=http_client,
            base_url=settings.ashby_api_url,
            timeout=settings.portal_scan_timeout,
        ),
    }

    portal_normalizers = {
        "greenhouse": GreenhouseNormalizer(),
        "lever": LeverNormalizer(),
        "ashby": AshbyNormalizer(),
    }

    portal_scanner = PortalScanner(
        config=portals_config,
        adapters=portal_adapters,
        normalizers=portal_normalizers,
        event_bus=event_bus,
    )

    app.dependency_overrides[get_portal_scanner] = lambda: portal_scanner
    app.dependency_overrides[get_portals_config] = lambda: portals_config
```

- [ ] **Step 3: Run all ingestion tests to verify nothing broke**

Run: `cd backend && uv run pytest tests/unit/ingestion/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/main.py
git commit -m "feat(app): wire portal scanner with Greenhouse, Lever, and Ashby adapters"
```

---

## Task 14: Frontend models for portal scanning

**Files:**
- Create: `frontend/src/app/core/models/portal-entry.model.ts`
- Create: `frontend/src/app/core/models/scan-portals-request.model.ts`
- Create: `frontend/src/app/core/models/scan-result.model.ts`

- [ ] **Step 1: Create PortalEntry model**

Create `frontend/src/app/core/models/portal-entry.model.ts`:

```typescript
export interface PortalEntry {
  name: string;
  platform: 'greenhouse' | 'lever' | 'ashby';
  board_id: string;
  categories: string[];
}
```

- [ ] **Step 2: Create ScanPortalsRequest model**

Create `frontend/src/app/core/models/scan-portals-request.model.ts`:

```typescript
export interface ScanPortalsRequest {
  categories?: string[];
  companies?: string[];
  keyword?: string;
}
```

- [ ] **Step 3: Create ScanResult model**

Create `frontend/src/app/core/models/scan-result.model.ts`:

```typescript
import { NormalizedJob } from './normalized-job.model';

export interface ScanError {
  portal: string;
  platform: string;
  error: string;
}

export interface ScanResult {
  total_fetched: number;
  new: number;
  duplicates: number;
  jobs: NormalizedJob[];
  errors: ScanError[];
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/core/models/portal-entry.model.ts frontend/src/app/core/models/scan-portals-request.model.ts frontend/src/app/core/models/scan-result.model.ts
git commit -m "feat(frontend): add portal scanning TypeScript models"
```

---

## Task 15: Frontend ingestion page — scan portals UI

**Files:**
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.ts`
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.html`

- [ ] **Step 1: Add scan state and methods to component**

Add these imports and properties to `frontend/src/app/pages/ingestion/ingestion.component.ts`:

```typescript
import { PortalEntry } from '../../core/models/portal-entry.model';
import { ScanPortalsRequest } from '../../core/models/scan-portals-request.model';
import { ScanResult, ScanError } from '../../core/models/scan-result.model';
```

Add these signals and methods to the component class:

```typescript
  // Portal scanning state
  portals = signal<PortalEntry[]>([]);
  availableCategories = signal<string[]>([]);
  selectedCategories = signal<string[]>([]);
  selectedCompanies = signal<string[]>([]);
  scanKeyword = signal('');
  scanning = signal(false);
  scanSummary = signal('');
  scanErrors = signal<ScanError[]>([]);
  showFilters = signal(false);

  ngOnInit(): void {
    this.loadPortals();
  }

  loadPortals(): void {
    this.http.get<PortalEntry[]>(`${environment.apiUrl}/ingestion/portals`).subscribe({
      next: (portals) => {
        this.portals.set(portals);
        const categories = [...new Set(portals.flatMap(p => p.categories))].sort();
        this.availableCategories.set(categories);
      },
    });
  }

  scanPortals(): void {
    this.scanning.set(true);
    this.scanSummary.set('');
    this.scanErrors.set([]);

    const request: ScanPortalsRequest = {};
    if (this.selectedCategories().length) request.categories = this.selectedCategories();
    if (this.selectedCompanies().length) request.companies = this.selectedCompanies();
    if (this.scanKeyword()) request.keyword = this.scanKeyword();

    this.http.post<ScanResult>(`${environment.apiUrl}/ingestion/scan-portals`, request).subscribe({
      next: (result) => {
        this.jobs.update(existing => [...existing, ...result.jobs]);
        this.scanSummary.set(
          `Found ${result.new} new jobs (${result.duplicates} duplicates).` +
          (result.errors.length ? ` ${result.errors.length} portal(s) failed.` : '')
        );
        this.scanErrors.set(result.errors);
        this.scanning.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to scan portals');
        this.scanning.set(false);
      },
    });
  }

  toggleFilters(): void {
    this.showFilters.update(v => !v);
  }
```

- [ ] **Step 2: Add scan portals template section**

Add the following to `frontend/src/app/pages/ingestion/ingestion.component.html`, after the existing fetch jobs button section:

```html
<!-- Portal Scanning Section -->
<section class="scan-section">
  <div class="scan-header">
    <button (click)="scanPortals()" [disabled]="scanning()">
      {{ scanning() ? 'Scanning...' : 'Scan Portals' }}
    </button>
    <button (click)="toggleFilters()" class="filter-toggle">
      {{ showFilters() ? 'Hide Filters' : 'Show Filters' }}
    </button>
  </div>

  @if (showFilters()) {
    <div class="scan-filters">
      <div class="filter-group">
        <label>Categories</label>
        <select multiple (change)="onCategoryChange($event)">
          @for (cat of availableCategories(); track cat) {
            <option [value]="cat">{{ cat }}</option>
          }
        </select>
      </div>
      <div class="filter-group">
        <label>Companies</label>
        <select multiple (change)="onCompanyChange($event)">
          @for (portal of portals(); track portal.board_id) {
            <option [value]="portal.name">{{ portal.name }}</option>
          }
        </select>
      </div>
      <div class="filter-group">
        <label>Keyword</label>
        <input type="text" [value]="scanKeyword()" (input)="onKeywordInput($event)" placeholder="e.g. engineer" />
      </div>
    </div>
  }

  @if (scanSummary()) {
    <div class="scan-summary">{{ scanSummary() }}</div>
  }

  @if (scanErrors().length) {
    <details class="scan-errors">
      <summary>{{ scanErrors().length }} portal(s) failed</summary>
      <ul>
        @for (err of scanErrors(); track err.portal) {
          <li><strong>{{ err.portal }}</strong> ({{ err.platform }}): {{ err.error }}</li>
        }
      </ul>
    </details>
  }
</section>
```

- [ ] **Step 3: Add helper methods for template bindings**

Add these methods to the component class:

```typescript
  onCategoryChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const selected = Array.from(select.selectedOptions).map(o => o.value);
    this.selectedCategories.set(selected);
  }

  onCompanyChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const selected = Array.from(select.selectedOptions).map(o => o.value);
    this.selectedCompanies.set(selected);
  }

  onKeywordInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.scanKeyword.set(input.value);
  }
```

- [ ] **Step 4: Verify the frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/ingestion/ingestion.component.ts frontend/src/app/pages/ingestion/ingestion.component.html
git commit -m "feat(frontend): add scan portals UI with filters to ingestion page"
```

---

## Task 16: Run full test suite and verify

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Run linter**

Run: `cd backend && uv run ruff check src/ tests/`
Expected: No errors

- [ ] **Step 4: Final commit if any lint fixes needed**

```bash
git add -A
git commit -m "fix: address lint issues from portal scanning implementation"
```
