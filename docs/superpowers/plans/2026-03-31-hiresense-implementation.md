# HireSense Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AI-powered job matching and CV optimization system — open-source, self-hostable, with clean architecture and provider-agnostic design.

**Architecture:** Client-server with a modular monolith FastAPI backend (extractable boundaries via event bus + contracts) and Angular SPA frontend. Five bounded contexts: Ingestion, Profile, Matching, Optimization, Identity. All cross-cutting concerns (LLM, vector store, LaTeX compilation) abstracted behind port/adapter interfaces.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL + pgvector, LangGraph, Pydantic v2, APScheduler, Angular 19+, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-03-31-hiresense-design.md`

---

## Phase 1: Project Skeleton & Kernel

### Task 1: Project scaffolding and dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `src/hiresense/__init__.py`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: Initialize git repo**

```bash
cd "C:/Users/Bryan/OneDrive/Desktop/Bryan/Dev/Personal projects/HireSense"
git init
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
.eggs/
*.egg
.venv/
venv/

# Environment
.env

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Build
*.pdf
cvs/compiled/
cvs/optimized/

# Docker
docker-compose.override.yml

# Superpowers
.superpowers/

# Alembic
alembic/versions/*.pyc
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "hiresense"
version = "0.1.0"
description = "AI-powered job matching and CV optimization system"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",
    "sqlalchemy[asyncio]>=2.0.35",
    "asyncpg>=0.30.0",
    "pgvector>=0.3.5",
    "alembic>=1.14.0",
    "httpx>=0.27.0",
    "apscheduler>=3.10.0",
    "python-multipart>=0.0.12",
    "passlib[bcrypt]>=1.7.4",
    "python-jose[cryptography]>=3.3.0",
    "langgraph>=0.2.0",
    "langchain-core>=0.3.0",
    "feedparser>=6.0.0",
    "beautifulsoup4>=4.12.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",
    "ruff>=0.7.0",
]
anthropic = ["langchain-anthropic>=0.3.0"]
openai = ["langchain-openai>=0.2.0"]
groq = ["langchain-groq>=0.2.0"]
ollama = ["langchain-ollama>=0.2.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/hiresense"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py312"
line-length = 100
```

- [ ] **Step 4: Create `.env.example`**

```env
# === Core ===
APP_NAME=HireSense
APP_PORT=8000
DEBUG=false

# === Auth ===
AUTH_USERNAME=admin
AUTH_PASSWORD=changeme
JWT_SECRET_KEY=change-this-to-a-random-secret

# === Database ===
DATABASE_URL=postgresql+asyncpg://hiresense:hiresense@localhost:5432/hiresense

# === LLM ===
LLM_PROVIDER=anthropic
# Options: anthropic | openai | groq | ollama
LLM_API_KEY=your-api-key-here
LLM_MODEL=claude-sonnet-4-6
EMBEDDING_PROVIDER=openai
# Options: openai | ollama
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_API_KEY=your-openai-key-here

# === Vector Store ===
VECTOR_STORE_PROVIDER=pgvector
# Options: pgvector | chroma

# === Job Ingestion ===
INGESTION_SCHEDULE=0 */6 * * *
ENABLED_JOB_SOURCES=remotive,remoteok,jobicy,himalayas,hn_hiring,weworkremotely,getonboard
# Options: remotive,remoteok,jobicy,himalayas,hn_hiring,weworkremotely,getonboard,csv,json

# === LaTeX ===
LATEX_COMPILER=xelatex
# Options: xelatex | docker_xelatex
CV_DIRECTORY=./cvs

# === Language ===
SUPPORTED_LANGUAGES=en,es
DEFAULT_LANGUAGE=en

# === Matching Weights (must sum to 100) ===
WEIGHT_SEMANTIC=30
WEIGHT_SKILL_MATCH=40
WEIGHT_EXPERIENCE=20
WEIGHT_LANGUAGE=10
```

- [ ] **Step 5: Create `src/hiresense/__init__.py`**

```python
"""HireSense - AI-powered job matching and CV optimization."""
```

- [ ] **Step 6: Create empty directory structure**

```bash
mkdir -p src/hiresense/{kernel/{ports,contracts},adapters/{llm,vector_store,latex,event_bus},ingestion/{domain,ports,adapters,infrastructure,api},profile/{domain,infrastructure,api},matching/{domain,agent,infrastructure,api},optimization/{domain,agent,infrastructure,api},identity/api}
mkdir -p tests/{unit/{ingestion,profile,matching,optimization,identity},integration,e2e}
mkdir -p cvs/{originals,optimized,compiled}
mkdir -p alembic/versions
touch src/hiresense/kernel/__init__.py
touch src/hiresense/kernel/ports/__init__.py
touch src/hiresense/kernel/contracts/__init__.py
touch src/hiresense/adapters/__init__.py
touch src/hiresense/adapters/llm/__init__.py
touch src/hiresense/adapters/vector_store/__init__.py
touch src/hiresense/adapters/latex/__init__.py
touch src/hiresense/adapters/event_bus/__init__.py
touch src/hiresense/ingestion/__init__.py
touch src/hiresense/ingestion/domain/__init__.py
touch src/hiresense/ingestion/ports/__init__.py
touch src/hiresense/ingestion/adapters/__init__.py
touch src/hiresense/ingestion/infrastructure/__init__.py
touch src/hiresense/ingestion/api/__init__.py
touch src/hiresense/profile/__init__.py
touch src/hiresense/profile/domain/__init__.py
touch src/hiresense/profile/infrastructure/__init__.py
touch src/hiresense/profile/api/__init__.py
touch src/hiresense/matching/__init__.py
touch src/hiresense/matching/domain/__init__.py
touch src/hiresense/matching/agent/__init__.py
touch src/hiresense/matching/infrastructure/__init__.py
touch src/hiresense/matching/api/__init__.py
touch src/hiresense/optimization/__init__.py
touch src/hiresense/optimization/domain/__init__.py
touch src/hiresense/optimization/agent/__init__.py
touch src/hiresense/optimization/infrastructure/__init__.py
touch src/hiresense/optimization/api/__init__.py
touch src/hiresense/identity/__init__.py
touch src/hiresense/identity/api/__init__.py
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/unit/ingestion/__init__.py
touch tests/unit/profile/__init__.py
touch tests/unit/matching/__init__.py
touch tests/unit/optimization/__init__.py
touch tests/unit/identity/__init__.py
touch tests/integration/__init__.py
touch tests/e2e/__init__.py
```

- [ ] **Step 7: Install dependencies**

```bash
uv sync
```

- [ ] **Step 8: Commit**

```bash
git add .gitignore pyproject.toml .env.example src/ tests/ cvs/originals/.gitkeep cvs/optimized/.gitkeep cvs/compiled/.gitkeep
git commit -m "chore: scaffold project structure with dependencies"
```

---

### Task 2: Configuration (Pydantic Settings)

**Files:**
- Create: `src/hiresense/config.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_config.py
import os

import pytest


def test_settings_loads_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.app_name == "HireSense"
    assert settings.app_port == 8000
    assert settings.llm_provider == "anthropic"
    assert settings.vector_store_provider == "pgvector"
    assert settings.weight_semantic == 30
    assert settings.weight_skill_match == 40
    assert settings.weight_experience == 20
    assert settings.weight_language == 10


def test_settings_enabled_sources_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")
    monkeypatch.setenv("ENABLED_JOB_SOURCES", "remotive,remoteok")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.enabled_job_sources == ["remotive", "remoteok"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hiresense.config'`

- [ ] **Step 3: Write implementation**

```python
# src/hiresense/config.py
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    app_name: str = "HireSense"
    app_port: int = 8000
    debug: bool = False

    # Auth
    auth_username: str
    auth_password: str
    jwt_secret_key: str

    # Database
    database_url: str

    # LLM
    llm_provider: str = "anthropic"
    llm_api_key: str
    llm_model: str = "claude-sonnet-4-6"
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str

    # Vector Store
    vector_store_provider: str = "pgvector"

    # Ingestion
    ingestion_schedule: str = "0 */6 * * *"
    enabled_job_sources: list[str] = [
        "remotive",
        "remoteok",
        "jobicy",
        "himalayas",
        "hn_hiring",
        "weworkremotely",
        "getonboard",
    ]

    # LaTeX
    latex_compiler: str = "xelatex"
    cv_directory: str = "./cvs"

    # Language
    supported_languages: list[str] = ["en", "es"]
    default_language: str = "en"

    # Matching weights
    weight_semantic: int = 30
    weight_skill_match: int = 40
    weight_experience: int = 20
    weight_language: int = 10

    @field_validator("enabled_job_sources", mode="before")
    @classmethod
    def parse_comma_separated(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return list(v)  # type: ignore[arg-type]

    @field_validator("supported_languages", mode="before")
    @classmethod
    def parse_languages(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return list(v)  # type: ignore[arg-type]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/hiresense/config.py tests/unit/test_config.py
git commit -m "feat(config): add Pydantic Settings with all env configuration"
```

---

### Task 3: Kernel — Value objects

**Files:**
- Create: `src/hiresense/kernel/value_objects.py`
- Create: `tests/unit/test_value_objects.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_value_objects.py
import uuid

from hiresense.kernel.value_objects import (
    JobId,
    Language,
    MatchScore,
    Score,
    SkillTag,
    SourceType,
)


def test_job_id_creates_from_string() -> None:
    jid = JobId("abc-123")
    assert str(jid) == "abc-123"


def test_job_id_equality() -> None:
    a = JobId("x")
    b = JobId("x")
    assert a == b


def test_job_id_generates_new() -> None:
    jid = JobId.generate()
    uuid.UUID(str(jid))  # Should not raise


def test_skill_tag_normalizes() -> None:
    tag = SkillTag("  FastAPI  ")
    assert tag.value == "fastapi"


def test_score_clamps_range() -> None:
    assert Score(150).value == 100
    assert Score(-10).value == 0
    assert Score(75).value == 75


def test_match_score_breakdown() -> None:
    ms = MatchScore(semantic=80, skill_match=60, experience=70, language=100)
    composite = ms.composite(w_semantic=30, w_skill=40, w_exp=20, w_lang=10)
    expected = (80 * 30 + 60 * 40 + 70 * 20 + 100 * 10) / 100
    assert composite == expected


def test_language_enum() -> None:
    assert Language.ENGLISH.value == "en"
    assert Language.SPANISH.value == "es"


def test_source_type_enum() -> None:
    assert SourceType.API.value == "api"
    assert SourceType.RSS.value == "rss"
    assert SourceType.SCRAPER.value == "scraper"
    assert SourceType.MANUAL.value == "manual"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_value_objects.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write implementation**

```python
# src/hiresense/kernel/value_objects.py
from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class JobId:
    _value: str

    @classmethod
    def generate(cls) -> JobId:
        return cls(str(uuid.uuid4()))

    def __str__(self) -> str:
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, JobId):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


@dataclass(frozen=True)
class SkillTag:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", self.value.strip().lower())


@dataclass(frozen=True)
class Score:
    value: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", max(0, min(100, self.value)))


@dataclass(frozen=True)
class MatchScore:
    semantic: int
    skill_match: int
    experience: int
    language: int

    def composite(
        self, w_semantic: int, w_skill: int, w_exp: int, w_lang: int
    ) -> float:
        total = (
            self.semantic * w_semantic
            + self.skill_match * w_skill
            + self.experience * w_exp
            + self.language * w_lang
        )
        return total / (w_semantic + w_skill + w_exp + w_lang)


class Language(Enum):
    ENGLISH = "en"
    SPANISH = "es"


class SourceType(Enum):
    API = "api"
    RSS = "rss"
    SCRAPER = "scraper"
    MANUAL = "manual"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_value_objects.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/hiresense/kernel/value_objects.py tests/unit/test_value_objects.py
git commit -m "feat(kernel): add value objects — JobId, SkillTag, Score, MatchScore, Language, SourceType"
```

---

### Task 4: Kernel — Port protocols

**Files:**
- Create: `src/hiresense/kernel/ports/llm.py`
- Create: `src/hiresense/kernel/ports/vector_store.py`
- Create: `src/hiresense/kernel/ports/latex_compiler.py`
- Create: `src/hiresense/kernel/ports/event_bus.py`
- Create: `src/hiresense/kernel/events.py`
- Create: `src/hiresense/kernel/module.py`

- [ ] **Step 1: Write `events.py` — base domain event**

```python
# src/hiresense/kernel/events.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 2: Write `ports/llm.py`**

```python
# src/hiresense/kernel/ports/llm.py
from __future__ import annotations

from typing import AsyncIterator, Protocol


class LLMPort(Protocol):
    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def stream(self, prompt: str, *, system: str = "") -> AsyncIterator[str]: ...
```

- [ ] **Step 3: Write `ports/vector_store.py`**

```python
# src/hiresense/kernel/ports/vector_store.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ScoredResult:
    id: str
    score: float
    metadata: dict[str, Any]


class VectorStorePort(Protocol):
    async def upsert(self, id: str, embedding: list[float], metadata: dict[str, Any]) -> None: ...

    async def search(
        self, query_embedding: list[float], *, top_k: int = 10, filters: dict[str, Any] | None = None
    ) -> list[ScoredResult]: ...

    async def delete(self, ids: list[str]) -> None: ...
```

- [ ] **Step 4: Write `ports/latex_compiler.py`**

```python
# src/hiresense/kernel/ports/latex_compiler.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class CompilationError:
    line: int
    message: str


class LaTeXCompilerPort(Protocol):
    async def compile(self, tex_content: str) -> bytes: ...

    async def validate(self, tex_content: str) -> list[CompilationError]: ...
```

- [ ] **Step 5: Write `ports/event_bus.py`**

```python
# src/hiresense/kernel/ports/event_bus.py
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from hiresense.kernel.events import DomainEvent


class EventBus(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...

    def subscribe(self, event_type: str, handler: Callable[[DomainEvent], Awaitable[None]]) -> None: ...
```

- [ ] **Step 6: Write `module.py` — module registration protocol**

```python
# src/hiresense/kernel/module.py
from __future__ import annotations

from typing import Any, Protocol

from fastapi import FastAPI


class Module(Protocol):
    def register(self, app: FastAPI, dependencies: dict[str, Any]) -> None: ...
```

- [ ] **Step 7: Commit**

```bash
git add src/hiresense/kernel/
git commit -m "feat(kernel): add port protocols — LLM, VectorStore, LaTeX, EventBus, Module"
```

---

### Task 5: Kernel — Inter-module contracts

**Files:**
- Create: `src/hiresense/kernel/contracts/ingestion.py`
- Create: `src/hiresense/kernel/contracts/profile.py`
- Create: `src/hiresense/kernel/contracts/matching.py`
- Create: `src/hiresense/kernel/contracts/optimization.py`

- [ ] **Step 1: Write `contracts/ingestion.py`**

```python
# src/hiresense/kernel/contracts/ingestion.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from hiresense.kernel.events import DomainEvent


class NormalizedJobDTO(BaseModel):
    id: str
    title: str
    company: str
    description: str
    skills: list[str]
    location: str
    salary_range: str | None = None
    source: str
    source_type: str
    language: str
    url: str
    posted_date: datetime | None = None


class JobsIngestedEvent(DomainEvent):
    event_type: str = "jobs.ingested"
    payload: dict  # keys: job_ids (list[str]), source (str)
```

- [ ] **Step 2: Write `contracts/profile.py`**

```python
# src/hiresense/kernel/contracts/profile.py
from __future__ import annotations

from pydantic import BaseModel


class CandidateSkillsDTO(BaseModel):
    skills: list[str]
    experience_summary: str
    language: str


class CVEmbeddingDTO(BaseModel):
    cv_id: str
    embedding: list[float]
```

- [ ] **Step 3: Write `contracts/matching.py`**

```python
# src/hiresense/kernel/contracts/matching.py
from __future__ import annotations

from pydantic import BaseModel

from hiresense.kernel.events import DomainEvent


class MatchResultDTO(BaseModel):
    id: str
    job_id: str
    cv_id: str
    overall_score: float
    semantic_score: float
    skill_score: float
    experience_score: float
    language_score: float
    pros: list[str]
    cons: list[str]
    missing_skills: list[str]
    recommendations: list[str]


class MatchCompletedEvent(DomainEvent):
    event_type: str = "match.completed"
    payload: dict  # keys: job_id (str), match_id (str), score (float)
```

- [ ] **Step 4: Write `contracts/optimization.py`**

```python
# src/hiresense/kernel/contracts/optimization.py
from __future__ import annotations

from pydantic import BaseModel


class OptimizationRequestDTO(BaseModel):
    match_id: str
    job_id: str
    cv_id: str


class TexDiffDTO(BaseModel):
    optimization_id: str
    original_path: str
    diff: str
    modified_tex: str
```

- [ ] **Step 5: Commit**

```bash
git add src/hiresense/kernel/contracts/
git commit -m "feat(kernel): add inter-module contract DTOs"
```

---

### Task 6: In-memory event bus adapter

**Files:**
- Create: `src/hiresense/adapters/event_bus/in_memory_bus.py`
- Create: `tests/unit/test_event_bus.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_event_bus.py
import asyncio

import pytest

from hiresense.adapters.event_bus.in_memory_bus import InMemoryEventBus
from hiresense.kernel.events import DomainEvent


@pytest.mark.asyncio
async def test_publish_invokes_subscriber() -> None:
    bus = InMemoryEventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    bus.subscribe("test.event", handler)
    event = DomainEvent(event_type="test.event", payload={"key": "value"})
    await bus.publish(event)

    await asyncio.sleep(0.05)
    assert len(received) == 1
    assert received[0].payload == {"key": "value"}


@pytest.mark.asyncio
async def test_publish_no_subscriber_does_not_raise() -> None:
    bus = InMemoryEventBus()
    event = DomainEvent(event_type="unhandled.event")
    await bus.publish(event)


@pytest.mark.asyncio
async def test_multiple_subscribers() -> None:
    bus = InMemoryEventBus()
    calls: list[str] = []

    async def handler_a(event: DomainEvent) -> None:
        calls.append("a")

    async def handler_b(event: DomainEvent) -> None:
        calls.append("b")

    bus.subscribe("multi.event", handler_a)
    bus.subscribe("multi.event", handler_b)
    await bus.publish(DomainEvent(event_type="multi.event"))

    await asyncio.sleep(0.05)
    assert sorted(calls) == ["a", "b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_event_bus.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write implementation**

```python
# src/hiresense/adapters/event_bus/in_memory_bus.py
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable

from hiresense.kernel.events import DomainEvent

logger = logging.getLogger(__name__)


class InMemoryEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[DomainEvent], Awaitable[None]]]] = defaultdict(
            list
        )

    def subscribe(
        self, event_type: str, handler: Callable[[DomainEvent], Awaitable[None]]
    ) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            asyncio.create_task(self._safe_invoke(handler, event))

    async def _safe_invoke(
        self, handler: Callable[[DomainEvent], Awaitable[None]], event: DomainEvent
    ) -> None:
        try:
            await handler(event)
        except Exception:
            logger.exception("Event handler failed for %s", event.event_type)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_event_bus.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/hiresense/adapters/event_bus/in_memory_bus.py tests/unit/test_event_bus.py
git commit -m "feat(adapters): add in-memory event bus implementation"
```

---

### Task 7: Database setup and Docker Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `Dockerfile`
- Create: `src/hiresense/infrastructure/__init__.py`
- Create: `src/hiresense/infrastructure/database.py`
- Create: `alembic/alembic.ini` (at project root as `alembic.ini`)
- Create: `alembic/env.py`

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: hiresense
      POSTGRES_PASSWORD: hiresense
      POSTGRES_DB: hiresense
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U hiresense"]
      interval: 5s
      timeout: 3s
      retries: 5

  app:
    build: .
    ports:
      - "${APP_PORT:-8000}:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./cvs:/app/cvs

volumes:
  pgdata:
```

- [ ] **Step 2: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-xetex texlive-fonts-recommended texlive-fonts-extra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "hiresense.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Create `src/hiresense/infrastructure/database.py`**

```python
# src/hiresense/infrastructure/database.py
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from hiresense.config import Settings


class Base(DeclarativeBase):
    pass


def build_engine(settings: Settings):  # noqa: ANN201
    return create_async_engine(settings.database_url, echo=settings.debug)


def build_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    engine = build_engine(settings)
    return async_sessionmaker(engine, expire_on_commit=False)
```

- [ ] **Step 4: Create `alembic.ini`** (project root)

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://hiresense:hiresense@localhost:5432/hiresense

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 5: Create `alembic/env.py`**

```python
# alembic/env.py
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from hiresense.infrastructure.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # noqa: ANN001
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 6: Create `src/hiresense/infrastructure/__init__.py`**

```python
```

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml Dockerfile src/hiresense/infrastructure/ alembic.ini alembic/
git commit -m "feat(infra): add Docker Compose, database setup, and Alembic migrations"
```

---

### Task 8: Identity module — basic auth

**Files:**
- Create: `src/hiresense/identity/services.py`
- Create: `src/hiresense/identity/api/dependencies.py`
- Create: `src/hiresense/identity/api/routes.py`
- Create: `tests/unit/identity/test_auth.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/identity/test_auth.py
import pytest

from hiresense.identity.services import AuthService


def test_verify_valid_credentials() -> None:
    service = AuthService(username="admin", password="secret", jwt_secret="key")
    token = service.login("admin", "secret")
    assert token is not None
    assert isinstance(token, str)


def test_verify_invalid_credentials() -> None:
    service = AuthService(username="admin", password="secret", jwt_secret="key")
    token = service.login("admin", "wrong")
    assert token is None


def test_validate_token() -> None:
    service = AuthService(username="admin", password="secret", jwt_secret="key")
    token = service.login("admin", "secret")
    assert token is not None
    payload = service.validate_token(token)
    assert payload is not None
    assert payload["sub"] == "admin"


def test_validate_invalid_token() -> None:
    service = AuthService(username="admin", password="secret", jwt_secret="key")
    payload = service.validate_token("garbage.token.here")
    assert payload is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/identity/test_auth.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write `identity/services.py`**

```python
# src/hiresense/identity/services.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt


class AuthService:
    def __init__(self, username: str, password: str, jwt_secret: str) -> None:
        self._username = username
        self._password = password
        self._jwt_secret = jwt_secret

    def login(self, username: str, password: str) -> str | None:
        if username == self._username and password == self._password:
            return self._create_token(username)
        return None

    def validate_token(self, token: str) -> dict[str, Any] | None:
        try:
            return jwt.decode(token, self._jwt_secret, algorithms=["HS256"])
        except JWTError:
            return None

    def _create_token(self, subject: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(hours=24)
        return jwt.encode({"sub": subject, "exp": expire}, self._jwt_secret, algorithm="HS256")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/identity/test_auth.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Write `identity/api/dependencies.py`**

```python
# src/hiresense/identity/api/dependencies.py
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hiresense.identity.services import AuthService

security = HTTPBearer()


def get_auth_service() -> AuthService:
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")


def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> str:
    payload = auth_service.validate_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload["sub"]
```

- [ ] **Step 6: Write `identity/api/routes.py`**

```python
# src/hiresense/identity/api/routes.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from hiresense.identity.api.dependencies import get_auth_service
from hiresense.identity.services import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    token = auth_service.login(body.username, body.password)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=token)
```

- [ ] **Step 7: Commit**

```bash
git add src/hiresense/identity/ tests/unit/identity/
git commit -m "feat(identity): add JWT auth service with login endpoint"
```

---

### Task 9: App factory — `main.py`

**Files:**
- Create: `src/hiresense/main.py`
- Create: `tests/unit/test_app.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_app.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")

    from hiresense.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_login_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "testpass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")

    from hiresense.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/auth/login", json={"username": "admin", "password": "testpass"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_app.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write implementation**

```python
# src/hiresense/main.py
from __future__ import annotations

from fastapi import FastAPI

from hiresense.adapters.event_bus.in_memory_bus import InMemoryEventBus
from hiresense.config import Settings
from hiresense.identity.api.dependencies import get_auth_service
from hiresense.identity.api.routes import router as auth_router
from hiresense.identity.services import AuthService


def create_app() -> FastAPI:
    settings = Settings()

    app = FastAPI(title=settings.app_name, debug=settings.debug)

    # --- Shared infrastructure ---
    event_bus = InMemoryEventBus()

    # --- Identity module ---
    auth_service = AuthService(
        username=settings.auth_username,
        password=settings.auth_password,
        jwt_secret=settings.jwt_secret_key,
    )
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.include_router(auth_router)

    # --- Health check ---
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_app.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/hiresense/main.py tests/unit/test_app.py
git commit -m "feat: add app factory with health check and auth module registration"
```

---

## Phase 2: Job Ingestion Module

### Task 10: Ingestion domain models

**Files:**
- Create: `src/hiresense/ingestion/domain/models.py`
- Create: `tests/unit/ingestion/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/ingestion/test_models.py
from datetime import datetime, timezone

from hiresense.ingestion.domain.models import NormalizedJob, RawJobListing


def test_raw_job_listing_creation() -> None:
    raw = RawJobListing(
        source="remotive",
        source_id="123",
        raw_data={"title": "Backend Engineer", "company": "Acme"},
    )
    assert raw.source == "remotive"
    assert raw.raw_data["title"] == "Backend Engineer"


def test_normalized_job_from_raw() -> None:
    job = NormalizedJob(
        id="job-1",
        title="Backend Engineer",
        company="Acme Corp",
        description="Build scalable APIs with FastAPI",
        skills=["python", "fastapi", "postgresql"],
        location="Remote",
        salary_range="$80k-$120k",
        source="remotive",
        source_type="api",
        language="en",
        url="https://example.com/job/1",
        posted_date=datetime(2026, 3, 30, tzinfo=timezone.utc),
    )
    assert job.title == "Backend Engineer"
    assert "fastapi" in job.skills


def test_normalized_job_deduplication_key() -> None:
    job = NormalizedJob(
        id="job-1",
        title="Backend Engineer",
        company="Acme Corp",
        description="Build APIs",
        skills=[],
        location="Remote",
        source="remotive",
        source_type="api",
        language="en",
        url="https://example.com/job/1",
    )
    key = job.dedup_key()
    assert isinstance(key, str)
    assert len(key) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/ingestion/test_models.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write implementation**

```python
# src/hiresense/ingestion/domain/models.py
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RawJobListing(BaseModel):
    source: str
    source_id: str
    raw_data: dict[str, Any]


class NormalizedJob(BaseModel):
    id: str
    title: str
    company: str
    description: str
    skills: list[str] = Field(default_factory=list)
    location: str = ""
    salary_range: str | None = None
    source: str
    source_type: str
    language: str = "en"
    url: str
    posted_date: datetime | None = None

    def dedup_key(self) -> str:
        raw = f"{self.source}:{self.title.lower().strip()}:{self.company.lower().strip()}:{self.url}"
        return hashlib.sha256(raw.encode()).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/ingestion/test_models.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/hiresense/ingestion/domain/models.py tests/unit/ingestion/test_models.py
git commit -m "feat(ingestion): add domain models — RawJobListing, NormalizedJob"
```

---

### Task 11: Ingestion port — `JobSourcePort`

**Files:**
- Create: `src/hiresense/ingestion/ports/job_source.py`

- [ ] **Step 1: Write the port protocol**

```python
# src/hiresense/ingestion/ports/job_source.py
from __future__ import annotations

from typing import Any, Protocol

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType


class JobSourcePort(Protocol):
    def source_name(self) -> str: ...

    def source_type(self) -> SourceType: ...

    async def fetch_jobs(self, filters: dict[str, Any] | None = None) -> list[RawJobListing]: ...
```

- [ ] **Step 2: Commit**

```bash
git add src/hiresense/ingestion/ports/job_source.py
git commit -m "feat(ingestion): add JobSourcePort protocol"
```

---

### Task 12: Remotive job source adapter

**Files:**
- Create: `src/hiresense/ingestion/adapters/remotive.py`
- Create: `tests/unit/ingestion/test_remotive.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/ingestion/test_remotive.py
import json

import pytest

from hiresense.ingestion.adapters.remotive import RemotiveAdapter
from hiresense.kernel.value_objects import SourceType


class FakeResponse:
    def __init__(self, data: dict) -> None:
        self._data = data
        self.status_code = 200

    def json(self) -> dict:
        return self._data

    def raise_for_status(self) -> None:
        pass


class FakeHttpClient:
    def __init__(self, response_data: dict) -> None:
        self._response_data = response_data

    async def get(self, url: str, **kwargs) -> FakeResponse:  # noqa: ANN003
        return FakeResponse(self._response_data)


@pytest.mark.asyncio
async def test_remotive_fetches_and_normalizes() -> None:
    sample_response = {
        "jobs": [
            {
                "id": 12345,
                "title": "Backend Engineer",
                "company_name": "Acme",
                "description": "<p>Build APIs with FastAPI</p>",
                "tags": ["python", "fastapi"],
                "candidate_required_location": "Worldwide",
                "salary": "$80k - $120k",
                "url": "https://remotive.com/remote-jobs/12345",
                "publication_date": "2026-03-28T12:00:00",
                "category": "Software Development",
            }
        ]
    }
    client = FakeHttpClient(sample_response)
    adapter = RemotiveAdapter(http_client=client)

    jobs = await adapter.fetch_jobs()

    assert len(jobs) == 1
    assert jobs[0].source == "remotive"
    assert jobs[0].source_id == "12345"
    assert jobs[0].raw_data["title"] == "Backend Engineer"


def test_remotive_source_name() -> None:
    adapter = RemotiveAdapter(http_client=None)  # type: ignore[arg-type]
    assert adapter.source_name() == "remotive"
    assert adapter.source_type() == SourceType.API
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/ingestion/test_remotive.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write implementation**

```python
# src/hiresense/ingestion/adapters/remotive.py
from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"


class RemotiveAdapter:
    def __init__(self, http_client: Any) -> None:
        self._http = http_client

    def source_name(self) -> str:
        return "remotive"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(self, filters: dict[str, Any] | None = None) -> list[RawJobListing]:
        params: dict[str, str] = {}
        if filters and "category" in filters:
            params["category"] = filters["category"]
        if filters and "search" in filters:
            params["search"] = filters["search"]

        response = await self._http.get(REMOTIVE_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        return [
            RawJobListing(
                source="remotive",
                source_id=str(job["id"]),
                raw_data=job,
            )
            for job in data.get("jobs", [])
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/ingestion/test_remotive.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/hiresense/ingestion/adapters/remotive.py tests/unit/ingestion/test_remotive.py
git commit -m "feat(ingestion): add Remotive job source adapter"
```

---

### Task 13: RemoteOK job source adapter

**Files:**
- Create: `src/hiresense/ingestion/adapters/remoteok.py`
- Create: `tests/unit/ingestion/test_remoteok.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/ingestion/test_remoteok.py
import pytest

from hiresense.ingestion.adapters.remoteok import RemoteOKAdapter
from hiresense.kernel.value_objects import SourceType


class FakeResponse:
    def __init__(self, data: list) -> None:
        self._data = data
        self.status_code = 200

    def json(self) -> list:
        return self._data

    def raise_for_status(self) -> None:
        pass


class FakeHttpClient:
    def __init__(self, response_data: list) -> None:
        self._response_data = response_data

    async def get(self, url: str, **kwargs) -> FakeResponse:  # noqa: ANN003
        return FakeResponse(self._response_data)


@pytest.mark.asyncio
async def test_remoteok_fetches_and_normalizes() -> None:
    sample_response = [
        {"legal": "This is a legal notice"},  # RemoteOK returns legal notice as first item
        {
            "id": "67890",
            "position": "Python Developer",
            "company": "StartupX",
            "description": "Join our team to build AI tools",
            "tags": ["python", "ai", "fastapi"],
            "location": "Worldwide",
            "salary_min": 80000,
            "salary_max": 120000,
            "url": "https://remoteok.com/l/67890",
            "date": "2026-03-27T10:00:00",
        },
    ]
    client = FakeHttpClient(sample_response)
    adapter = RemoteOKAdapter(http_client=client)

    jobs = await adapter.fetch_jobs()

    assert len(jobs) == 1
    assert jobs[0].source == "remoteok"
    assert jobs[0].source_id == "67890"
    assert jobs[0].raw_data["position"] == "Python Developer"


def test_remoteok_source_name() -> None:
    adapter = RemoteOKAdapter(http_client=None)  # type: ignore[arg-type]
    assert adapter.source_name() == "remoteok"
    assert adapter.source_type() == SourceType.API
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/ingestion/test_remoteok.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write implementation**

```python
# src/hiresense/ingestion/adapters/remoteok.py
from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

REMOTEOK_API_URL = "https://remoteok.com/api"


class RemoteOKAdapter:
    def __init__(self, http_client: Any) -> None:
        self._http = http_client

    def source_name(self) -> str:
        return "remoteok"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(self, filters: dict[str, Any] | None = None) -> list[RawJobListing]:
        headers = {"User-Agent": "HireSense/1.0"}
        response = await self._http.get(REMOTEOK_API_URL, headers=headers)
        response.raise_for_status()
        data = response.json()

        jobs: list[RawJobListing] = []
        for item in data:
            if "id" not in item or "position" not in item:
                continue
            jobs.append(
                RawJobListing(
                    source="remoteok",
                    source_id=str(item["id"]),
                    raw_data=item,
                )
            )
        return jobs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/ingestion/test_remoteok.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/hiresense/ingestion/adapters/remoteok.py tests/unit/ingestion/test_remoteok.py
git commit -m "feat(ingestion): add RemoteOK job source adapter"
```

---

### Task 14: CSV manual import adapter

**Files:**
- Create: `src/hiresense/ingestion/adapters/csv_import.py`
- Create: `tests/unit/ingestion/test_csv_import.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/ingestion/test_csv_import.py
import tempfile
from pathlib import Path

import pytest

from hiresense.ingestion.adapters.csv_import import CSVImportAdapter
from hiresense.kernel.value_objects import SourceType


@pytest.mark.asyncio
async def test_csv_import_reads_file() -> None:
    csv_content = (
        "title,company,description,skills,location,url\n"
        'Backend Engineer,Acme,"Build APIs",python;fastapi,Remote,https://example.com/1\n'
        'Frontend Dev,Beta,"Build UIs",angular;typescript,Remote,https://example.com/2\n'
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        csv_path = f.name

    adapter = CSVImportAdapter()
    jobs = await adapter.fetch_jobs(filters={"file_path": csv_path})

    assert len(jobs) == 2
    assert jobs[0].source == "csv"
    assert jobs[0].raw_data["title"] == "Backend Engineer"
    assert jobs[1].raw_data["company"] == "Beta"

    Path(csv_path).unlink()


def test_csv_source_name() -> None:
    adapter = CSVImportAdapter()
    assert adapter.source_name() == "csv"
    assert adapter.source_type() == SourceType.MANUAL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/ingestion/test_csv_import.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write implementation**

```python
# src/hiresense/ingestion/adapters/csv_import.py
from __future__ import annotations

import csv
import uuid
from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType


class CSVImportAdapter:
    def source_name(self) -> str:
        return "csv"

    def source_type(self) -> SourceType:
        return SourceType.MANUAL

    async def fetch_jobs(self, filters: dict[str, Any] | None = None) -> list[RawJobListing]:
        if not filters or "file_path" not in filters:
            return []

        file_path = filters["file_path"]
        jobs: list[RawJobListing] = []

        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                jobs.append(
                    RawJobListing(
                        source="csv",
                        source_id=str(uuid.uuid4()),
                        raw_data=dict(row),
                    )
                )
        return jobs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/ingestion/test_csv_import.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/hiresense/ingestion/adapters/csv_import.py tests/unit/ingestion/test_csv_import.py
git commit -m "feat(ingestion): add CSV manual import adapter"
```

---

### Task 15: Ingestion orchestrator service

**Files:**
- Create: `src/hiresense/ingestion/domain/services.py`
- Create: `src/hiresense/ingestion/domain/normalizer.py`
- Create: `tests/unit/ingestion/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/ingestion/test_orchestrator.py
import pytest

from hiresense.adapters.event_bus.in_memory_bus import InMemoryEventBus
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizer import RemotiveNormalizer
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.kernel.events import DomainEvent
from hiresense.kernel.value_objects import SourceType


class FakeJobSource:
    def source_name(self) -> str:
        return "fake"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def fetch_jobs(self, filters=None) -> list[RawJobListing]:  # noqa: ANN001
        return [
            RawJobListing(
                source="fake",
                source_id="1",
                raw_data={
                    "title": "Engineer",
                    "company_name": "Co",
                    "description": "Do stuff",
                    "tags": ["python"],
                    "candidate_required_location": "Remote",
                    "salary": "",
                    "url": "https://example.com/1",
                    "publication_date": "2026-03-28T12:00:00",
                },
            )
        ]


class FakeNormalizer:
    def normalize(self, raw: RawJobListing) -> dict:
        return {
            "title": raw.raw_data["title"],
            "company": raw.raw_data.get("company_name", ""),
            "description": raw.raw_data.get("description", ""),
            "skills": raw.raw_data.get("tags", []),
            "location": raw.raw_data.get("candidate_required_location", ""),
            "salary_range": raw.raw_data.get("salary") or None,
            "url": raw.raw_data.get("url", ""),
            "language": "en",
        }


@pytest.mark.asyncio
async def test_orchestrator_fetches_and_publishes() -> None:
    bus = InMemoryEventBus()
    events: list[DomainEvent] = []

    async def capture(event: DomainEvent) -> None:
        events.append(event)

    bus.subscribe("jobs.ingested", capture)

    normalizers = {"fake": FakeNormalizer()}
    orchestrator = IngestionOrchestrator(
        sources=[FakeJobSource()],
        normalizers=normalizers,
        event_bus=bus,
    )

    result = await orchestrator.run()

    assert len(result) == 1
    assert result[0].title == "Engineer"

    import asyncio
    await asyncio.sleep(0.05)
    assert len(events) == 1
    assert events[0].event_type == "jobs.ingested"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/ingestion/test_orchestrator.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write `normalizer.py`**

```python
# src/hiresense/ingestion/domain/normalizer.py
from __future__ import annotations

from typing import Any, Protocol

from hiresense.ingestion.domain.models import RawJobListing


class JobNormalizer(Protocol):
    def normalize(self, raw: RawJobListing) -> dict[str, Any]: ...


class RemotiveNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        return {
            "title": d.get("title", ""),
            "company": d.get("company_name", ""),
            "description": d.get("description", ""),
            "skills": d.get("tags", []),
            "location": d.get("candidate_required_location", ""),
            "salary_range": d.get("salary") or None,
            "url": d.get("url", ""),
            "language": "en",
        }


class RemoteOKNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        salary_min = d.get("salary_min")
        salary_max = d.get("salary_max")
        salary_range = f"${salary_min}-${salary_max}" if salary_min and salary_max else None
        return {
            "title": d.get("position", ""),
            "company": d.get("company", ""),
            "description": d.get("description", ""),
            "skills": d.get("tags", []),
            "location": d.get("location", "Worldwide"),
            "salary_range": salary_range,
            "url": d.get("url", ""),
            "language": "en",
        }


class CSVNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        skills_str = d.get("skills", "")
        skills = [s.strip() for s in skills_str.split(";")] if skills_str else []
        return {
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "description": d.get("description", ""),
            "skills": skills,
            "location": d.get("location", ""),
            "salary_range": d.get("salary_range") or None,
            "url": d.get("url", ""),
            "language": "en",
        }
```

- [ ] **Step 4: Write `services.py`**

```python
# src/hiresense/ingestion/domain/services.py
from __future__ import annotations

import logging
import uuid
from typing import Any

from hiresense.ingestion.domain.models import NormalizedJob, RawJobListing
from hiresense.ingestion.domain.normalizer import JobNormalizer
from hiresense.kernel.contracts.ingestion import JobsIngestedEvent

logger = logging.getLogger(__name__)


class IngestionOrchestrator:
    def __init__(
        self,
        sources: list[Any],
        normalizers: dict[str, JobNormalizer],
        event_bus: Any,
    ) -> None:
        self._sources = sources
        self._normalizers = normalizers
        self._event_bus = event_bus

    async def run(self, filters: dict[str, Any] | None = None) -> list[NormalizedJob]:
        all_jobs: list[NormalizedJob] = []
        seen_dedup_keys: set[str] = set()

        for source in self._sources:
            source_name = source.source_name()
            normalizer = self._normalizers.get(source_name)
            if normalizer is None:
                logger.warning("No normalizer for source: %s", source_name)
                continue

            try:
                raw_jobs = await source.fetch_jobs(filters)
            except Exception:
                logger.exception("Failed to fetch from %s", source_name)
                continue

            for raw in raw_jobs:
                normalized_data = normalizer.normalize(raw)
                job = NormalizedJob(
                    id=str(uuid.uuid4()),
                    source=source_name,
                    source_type=source.source_type().value,
                    **normalized_data,
                )
                dedup = job.dedup_key()
                if dedup not in seen_dedup_keys:
                    seen_dedup_keys.add(dedup)
                    all_jobs.append(job)

        if all_jobs:
            event = JobsIngestedEvent(
                payload={
                    "job_ids": [j.id for j in all_jobs],
                    "source": "batch",
                }
            )
            await self._event_bus.publish(event)

        return all_jobs
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/ingestion/test_orchestrator.py -v`
Expected: PASS (1 test)

- [ ] **Step 6: Commit**

```bash
git add src/hiresense/ingestion/domain/ tests/unit/ingestion/test_orchestrator.py
git commit -m "feat(ingestion): add orchestrator service with normalizers and deduplication"
```

---

### Task 16: Ingestion API routes

**Files:**
- Create: `src/hiresense/ingestion/api/routes.py`
- Create: `tests/unit/ingestion/test_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/ingestion/test_routes.py
import pytest
from httpx import ASGITransport, AsyncClient

from hiresense.ingestion.api.routes import router
from hiresense.ingestion.domain.models import NormalizedJob

from fastapi import FastAPI


class FakeOrchestrator:
    def __init__(self) -> None:
        self.called = False

    async def run(self, filters=None) -> list[NormalizedJob]:  # noqa: ANN001
        self.called = True
        return [
            NormalizedJob(
                id="test-1",
                title="Engineer",
                company="Co",
                description="Do things",
                skills=["python"],
                location="Remote",
                source="remotive",
                source_type="api",
                language="en",
                url="https://example.com/1",
            )
        ]


def get_orchestrator() -> FakeOrchestrator:
    return FakeOrchestrator()


@pytest.mark.asyncio
async def test_fetch_jobs_endpoint() -> None:
    from hiresense.ingestion.api.routes import get_ingestion_orchestrator

    app = FastAPI()
    fake = FakeOrchestrator()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: fake
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/ingestion/fetch")

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["jobs"][0]["title"] == "Engineer"
    assert fake.called
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/ingestion/test_routes.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write implementation**

```python
# src/hiresense/ingestion/api/routes.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.services import IngestionOrchestrator

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def get_ingestion_orchestrator() -> IngestionOrchestrator:
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")


class FetchResponse(BaseModel):
    count: int
    jobs: list[NormalizedJob]


@router.post("/fetch", response_model=FetchResponse)
async def fetch_jobs(
    orchestrator: Annotated[IngestionOrchestrator, Depends(get_ingestion_orchestrator)],
) -> FetchResponse:
    jobs = await orchestrator.run()
    return FetchResponse(count=len(jobs), jobs=jobs)


@router.get("/jobs", response_model=list[NormalizedJob])
async def list_jobs() -> list[NormalizedJob]:
    # Will be connected to repository in Phase 2 integration
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/ingestion/test_routes.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add src/hiresense/ingestion/api/routes.py tests/unit/ingestion/test_routes.py
git commit -m "feat(ingestion): add API routes — POST /fetch, GET /jobs"
```

---

## Phase 3–7: Remaining Phases (Summary)

> The remaining phases follow the same TDD pattern established above. Each task has: failing test → implementation → passing test → commit. Below are the task outlines. Full code for each will be provided when the implementing agent reaches that phase.

### Phase 3: Profile Module

**Task 17: LaTeX parser** — Parse `.tex` sections (HEADER, SUMMARY, SKILLS, PROJECTS, EDUCATION) into structured data. The parser reads the `\section*{...}` markers from files like `cv_backend_english_2026.tex`.

**Files:**
- Create: `src/hiresense/profile/domain/tex_parser.py`
- Create: `tests/unit/profile/test_tex_parser.py`

Key: The parser splits on `% ================= SECTION =================` comment markers and `\section*{NAME}` commands found in the LaTeX source. Returns a `dict[str, str]` mapping section name to raw LaTeX content.

---

**Task 18: Profile domain models** — `CandidateProfile`, `CVDocument`, `ExtractedSkill`.

**Files:**
- Create: `src/hiresense/profile/domain/models.py`
- Create: `tests/unit/profile/test_models.py`

---

**Task 19: Skill extraction service** — Uses `LLMPort.complete()` to extract structured skills from parsed CV sections.

**Files:**
- Create: `src/hiresense/profile/domain/services.py`
- Create: `tests/unit/profile/test_services.py`

---

**Task 20: Profile API routes** — `POST /profile/cv` (upload .tex or .pdf), `GET /profile/skills`.

**Files:**
- Create: `src/hiresense/profile/api/routes.py`
- Create: `tests/unit/profile/test_routes.py`

---

### Phase 4: Matching Module

**Task 21: Matching domain models** — `MatchResult`, `AnalysisBreakdown`.

**Files:**
- Create: `src/hiresense/matching/domain/models.py`
- Create: `tests/unit/matching/test_models.py`

---

**Task 22: LangGraph matching agent — state and nodes** — Define `MatchingAgentState` TypedDict and node functions: `extract_job_skills`, `extract_cv_skills`, `semantic_compare`, `score`, `generate_analysis`. Each node receives `LLMPort` via closure.

**Files:**
- Create: `src/hiresense/matching/agent/state.py`
- Create: `src/hiresense/matching/agent/nodes.py`
- Create: `tests/unit/matching/test_nodes.py`

---

**Task 23: LangGraph matching graph** — Wire nodes into a `StateGraph` with edges: `extract_job_skills → extract_cv_skills → semantic_compare → score → generate_analysis`.

**Files:**
- Create: `src/hiresense/matching/agent/graph.py`
- Create: `tests/unit/matching/test_graph.py`

---

**Task 24: Matching service** — Coordinates embedding retrieval, agent invocation, and result persistence.

**Files:**
- Create: `src/hiresense/matching/domain/services.py`
- Create: `tests/unit/matching/test_services.py`

---

**Task 25: Matching API routes** — `POST /match/{job_id}`, `GET /matches`, `GET /matches/{id}`.

**Files:**
- Create: `src/hiresense/matching/api/routes.py`
- Create: `tests/unit/matching/test_routes.py`

---

### Phase 5: CV Optimization Module

**Task 26: Optimization domain models** — `OptimizationJob`, `TexDiff`, `ApprovalStatus`.

**Files:**
- Create: `src/hiresense/optimization/domain/models.py`
- Create: `tests/unit/optimization/test_models.py`

---

**Task 27: LangGraph optimization agent** — Nodes: `analyze_gaps`, `propose_edits`, `validate_tex`, `generate_diff`. The `propose_edits` node has the honesty constraint system prompt.

**Files:**
- Create: `src/hiresense/optimization/agent/state.py`
- Create: `src/hiresense/optimization/agent/nodes.py`
- Create: `src/hiresense/optimization/agent/graph.py`
- Create: `tests/unit/optimization/test_nodes.py`
- Create: `tests/unit/optimization/test_graph.py`

---

**Task 28: XeLaTeX compiler adapter** — Implements `LaTeXCompilerPort`. Writes `.tex` to temp file, runs `xelatex`, returns PDF bytes.

**Files:**
- Create: `src/hiresense/adapters/latex/xelatex_adapter.py`
- Create: `tests/unit/test_xelatex_adapter.py`

---

**Task 29: Optimization service and diff engine** — Coordinates agent invocation, diff generation (using Python `difflib`), and approval workflow.

**Files:**
- Create: `src/hiresense/optimization/domain/services.py`
- Create: `tests/unit/optimization/test_services.py`

---

**Task 30: Optimization API routes** — `POST /optimize/{job_id}`, `POST /optimize/{id}/approve`, `GET /optimize/{id}/diff`.

**Files:**
- Create: `src/hiresense/optimization/api/routes.py`
- Create: `tests/unit/optimization/test_routes.py`

---

### Phase 6: LLM Adapters

**Task 31: Anthropic LLM adapter** — Implements `LLMPort` using `langchain-anthropic`.

**Files:**
- Create: `src/hiresense/adapters/llm/anthropic_adapter.py`
- Create: `tests/unit/test_anthropic_adapter.py`

---

**Task 32: OpenAI LLM adapter** — Implements `LLMPort` using `langchain-openai`.

**Files:**
- Create: `src/hiresense/adapters/llm/openai_adapter.py`
- Create: `tests/unit/test_openai_adapter.py`

---

**Task 33: LLM adapter factory** — Factory that reads `LLM_PROVIDER` from config and returns the correct adapter.

**Files:**
- Create: `src/hiresense/adapters/llm/factory.py`
- Create: `tests/unit/test_llm_factory.py`

---

**Task 34: pgvector adapter** — Implements `VectorStorePort` using SQLAlchemy + pgvector.

**Files:**
- Create: `src/hiresense/adapters/vector_store/pgvector_adapter.py`
- Create: `tests/integration/test_pgvector.py`

---

### Phase 7: Angular Frontend

**Task 35: Angular project scaffolding** — `ng new frontend` with standalone components, routing, Angular Material.

**Files:**
- Create: `frontend/` (Angular project via CLI)

---

**Task 36: Core services** — `ApiService` (HTTP client wrapper), `AuthService`, `AuthInterceptor`, `AuthGuard`.

**Files:**
- Create: `frontend/src/app/core/services/api.service.ts`
- Create: `frontend/src/app/core/services/auth.service.ts`
- Create: `frontend/src/app/core/interceptors/auth.interceptor.ts`
- Create: `frontend/src/app/core/guards/auth.guard.ts`

---

**Task 37: Login page** — Simple form posting to `POST /auth/login`, stores JWT.

**Files:**
- Create: `frontend/src/app/features/auth/login.component.ts`

---

**Task 38: Dashboard page** — Overview with recent jobs count, top matches, quick stats.

**Files:**
- Create: `frontend/src/app/features/dashboard/dashboard.component.ts`

---

**Task 39: Jobs list page** — Filterable table of ingested jobs with source, date, skills, location.

**Files:**
- Create: `frontend/src/app/features/jobs/job-list.component.ts`
- Create: `frontend/src/app/features/jobs/job-detail.component.ts`

---

**Task 40: Match results page** — Job match detail with score breakdown (color-coded badge), pros/cons lists, missing skills, recommendations.

**Files:**
- Create: `frontend/src/app/features/matching/match-results.component.ts`
- Create: `frontend/src/app/features/matching/match-detail.component.ts`
- Create: `frontend/src/app/shared/components/score-badge.component.ts`
- Create: `frontend/src/app/shared/components/skill-tag.component.ts`

---

**Task 41: CV optimization page** — Side-by-side diff viewer, approve/reject buttons, PDF download.

**Files:**
- Create: `frontend/src/app/features/optimization/diff-viewer.component.ts`
- Create: `frontend/src/app/features/optimization/approval.component.ts`

---

**Task 42: i18n setup** — English and Spanish translation JSON files, language toggle.

**Files:**
- Create: `frontend/src/assets/i18n/en.json`
- Create: `frontend/src/assets/i18n/es.json`

---

### Phase 8: Integration & Polish

**Task 43: Wire all modules in `main.py`** — Register ingestion, profile, matching, and optimization modules with their dependencies.

**Files:**
- Modify: `src/hiresense/main.py`

---

**Task 44: Remaining job source adapters** — Jobicy, Himalayas, HN Who's Hiring, We Work Remotely (RSS), GetOnBoard (scraper), JSON import.

**Files:**
- Create: `src/hiresense/ingestion/adapters/jobicy.py`
- Create: `src/hiresense/ingestion/adapters/himalayas.py`
- Create: `src/hiresense/ingestion/adapters/hn_who_is_hiring.py`
- Create: `src/hiresense/ingestion/adapters/weworkremotely_rss.py`
- Create: `src/hiresense/ingestion/adapters/getonboard_scraper.py`
- Create: `src/hiresense/ingestion/adapters/json_import.py`
- Create: corresponding test files in `tests/unit/ingestion/`

---

**Task 45: APScheduler integration** — Cron-based job fetching using `INGESTION_SCHEDULE` from config.

**Files:**
- Create: `src/hiresense/ingestion/infrastructure/scheduler.py`
- Create: `tests/unit/ingestion/test_scheduler.py`

---

**Task 46: End-to-end integration test** — Full pipeline: ingest sample jobs → analyze → optimize CV → verify PDF.

**Files:**
- Create: `tests/e2e/test_full_pipeline.py`

---

**Task 47: README and setup documentation** — Setup guide for self-hosting in under 5 minutes.

**Files:**
- Modify: `README.md`

---

## Verification

After all tasks:

1. **Unit tests pass:** `uv run pytest tests/unit/ -v`
2. **Integration tests pass:** `uv run pytest tests/integration/ -v` (requires running PostgreSQL)
3. **E2E test passes:** `uv run pytest tests/e2e/ -v` (requires all services)
4. **Docker Compose works:** `docker-compose up --build` from clean clone
5. **Frontend builds:** `cd frontend && ng build`
6. **Manual test:** Open dashboard, trigger job fetch, view matches, optimize CV, download PDF
