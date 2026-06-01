# Outreach & Networking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new `outreach` bounded context: generate on-brand recruiter/hiring-manager messages (grounded in profile + cached company research + a file-backed style guide), record outreach as append-only events on tracked applications (copy-only), and surface follow-up nudges via an external-cron sweep.

**Architecture:** `OutreachMessageGenerator` (pure LLM unit, mirrors `CoverLetterGenerator`) + `OutreachService` (orchestrates tracking/profile/research/generator/repo) over an `outreach_events` append-only table. Endpoints: `POST /outreach/generate` (draft), `POST /outreach/record`, `GET /outreach/events`, `POST /outreach/nudge` (cron). Built after tracking/profile/research in `main.create_app()`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy (sync session factory), Alembic, Pydantic v2, pytest (`asyncio_mode=auto`), `uv`.

**Spec:** `docs/superpowers/specs/2026-05-31-outreach-networking-design.md`. Scope: generation + tracking + nudges, **copy-only** (no outbound send, no contacts entity, no frontend — all out of scope).

**Tooling (this machine):** pytest = `uv run python -m pytest ...` (NOT bare; if a running app.exe locks the venv, use `uv run --no-sync python -m pytest ...`). From `backend/`. Ruff: `uv run python -m ruff check <paths>`.

**Verified integration facts:**
- `CoverLetterGenerator` (`applications/domain/cover_letter_generator.py`) is the template: module-level `SYSTEM_PROMPT` + `USER_PROMPT_TEMPLATE`, `async generate(*, ...) -> str` that raises `RuntimeError` when `llm is None`, calls `await self._llm.complete(prompt, system=SYSTEM_PROMPT)`, returns `.strip()`.
- `TrackingService.get(id: uuid.UUID) -> TrackedApplication` (sync; raises `ValueError` if missing). `TrackedApplication` has `id, job_id, title, company, url, status, notes, applied_at, created_at`. `ApplicationStatus` values: `saved/applied/interviewing/offered/accepted/rejected`.
- `ProfileService.get_current_profile(language=None) -> CandidateProfile | None` (async; `.name`, `.email`); `get_for_language(language) -> ProfileLanguageView | None` (sync; `.skills`, `.summary`).
- `CompanyResearchService.get(company_name) -> CompanyResearch | None` (sync, cache-only — never generates). `CompanyResearch`: `company_name, funding_stage, tech_stack, culture_summary, growth_trajectory, red_flags, pros, cons`.
- `tracked("feature_key") -> LLMPort | None` (None when no API key). Settings in `config.py`. Default language `settings.default_language = "en"`.
- `build_research(infra, tracked) -> ResearchProvider` (returns the provider directly, not a build); `ResearchProvider.get_research_service() -> CompanyResearchService`. In `main.py` research is built near the end (`app.state.research = build_research(infra, tracked)`); `tracking` and `profile` are built earlier with `.service` on their builds.
- Alembic head `018` → new `019`. Persistence-stack template: autohunt/preference. `created_at` needs a **Python-side microsecond default** (`default=lambda: datetime.now(timezone.utc)`) alongside `server_default=func.now()` for deterministic `latest_for` ordering on SQLite (same fix as digests). Integration tests: in-memory SQLite + `StaticPool` + `Base.metadata.create_all`, override `require_auth` → `"test-user"`, `AsyncClient(transport=ASGITransport(app=app))`.

---

## File Structure

**Create (`backend/src/hiresense/outreach/`):**
- `domain/outreach_event_kind.py` — `OutreachEventKind` enum.
- `domain/outreach_event.py` — `OutreachEvent`.
- `domain/outreach_nudge.py` — `OutreachNudge`.
- `domain/style_guide.py` — `load_style_guide`.
- `domain/message_generator.py` — `OutreachMessageGenerator` (+ `OutreachUnavailableError`).
- `domain/outreach_service.py` — `OutreachService`.
- `domain/__init__.py` — re-exports.
- `infrastructure/orm.py` — `OutreachEventOrm`.
- `infrastructure/repository.py` — `OutreachRepository`.
- `infrastructure/__init__.py` — re-export.
- `ports/repository.py` — `OutreachRepositoryPort`.
- `ports/__init__.py` — re-export.
- `api/schemas.py`, `api/provider.py`, `api/dependencies.py`, `api/routes.py`, `api/__init__.py`.
- `__init__.py`.
- `backend/alembic/versions/019_create_outreach_events.py`.
- `backend/src/hiresense/bootstrap/outreach.py`.

**Modify:** `config.py` + `.env.example` (settings); `bootstrap/__init__.py` (export `build_outreach`, `OutreachBuild`); `main.py` (capture research provider + build/register outreach).

**Tests:** `backend/tests/unit/outreach/` (generator, style_guide, service); `backend/tests/integration/test_outreach_repository.py`, `test_outreach_endpoints.py`.

---

## Task 1: Settings

**Files:** Modify `config.py`, `.env.example`.

- [ ] **Step 1: Add settings** (after the autohunt block in `config.py`):

```python
    # --- Outreach & Networking (on-brand message generation + follow-up nudges) ---
    # Path to the style-guide doc injected into the generation prompt (editable).
    outreach_style_guide_path: str = "docs/reference/message_To_apprach_recruiters.md"
    # Follow-up is "due" this many days after a 'sent' outreach with no progress.
    outreach_followup_cadence_days: int = 7
    # Soft length guard passed to the generator (chars).
    outreach_max_chars: int = 500
    # Intended cron cadence for the follow-up nudge sweep — INFORMATIONAL ONLY.
    outreach_followup_schedule: str = "0 10 * * *"
```

- [ ] **Step 2: `.env.example`** (after the autohunt block):

```
# --- Outreach & Networking ---
OUTREACH_STYLE_GUIDE_PATH=docs/reference/message_To_apprach_recruiters.md
OUTREACH_FOLLOWUP_CADENCE_DAYS=7
OUTREACH_MAX_CHARS=500
OUTREACH_FOLLOWUP_SCHEDULE=0 10 * * *
```

- [ ] **Step 3: Verify + commit**

Run: `cd backend && uv run python -m pytest -q -k "nothing" 2>/dev/null; uv run python -c "from hiresense.config import Settings; s=Settings(); print(s.outreach_followup_cadence_days, s.outreach_max_chars)"`
Expected: `7 500`

```bash
git add backend/src/hiresense/config.py backend/.env.example
git commit -m "feat(outreach): add outreach settings"
```

---

## Task 2: Domain models (kind, event, nudge)

**Files:** Create `outreach/__init__.py` (empty), `domain/outreach_event_kind.py`, `domain/outreach_event.py`, `domain/outreach_nudge.py`, `domain/__init__.py`.

- [ ] **Step 1: `outreach_event_kind.py`**

```python
from __future__ import annotations

import enum


class OutreachEventKind(str, enum.Enum):
    SENT = "sent"
    FOLLOWED_UP = "followed_up"
    REPLIED = "replied"
```

- [ ] **Step 2: `outreach_event.py`**

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel

from hiresense.outreach.domain.outreach_event_kind import OutreachEventKind


class OutreachEvent(BaseModel):
    """One recorded outreach action on a tracked application (append-only)."""

    id: uuid_mod.UUID | None = None
    application_id: uuid_mod.UUID
    kind: OutreachEventKind
    contact_name: str | None = None
    channel: str | None = None
    message: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: `outreach_nudge.py`**

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel


class OutreachNudge(BaseModel):
    """A due follow-up (computed, not persisted)."""

    application_id: uuid_mod.UUID
    company: str
    contact_name: str | None
    sent_at: datetime
    days_since: int
```

- [ ] **Step 4: `outreach/__init__.py`** — empty package marker (just a blank file).

- [ ] **Step 5: `domain/__init__.py`**

```python
from hiresense.outreach.domain.outreach_event import OutreachEvent
from hiresense.outreach.domain.outreach_event_kind import OutreachEventKind
from hiresense.outreach.domain.outreach_nudge import OutreachNudge

__all__ = ["OutreachEvent", "OutreachEventKind", "OutreachNudge"]
```

- [ ] **Step 6: Verify + commit**

Run: `cd backend && uv run python -c "from hiresense.outreach.domain import OutreachEvent, OutreachEventKind, OutreachNudge; import uuid; print(OutreachEvent(application_id=uuid.uuid4(), kind=OutreachEventKind.SENT).kind.value)"`
Expected: `sent`

```bash
git add backend/src/hiresense/outreach/__init__.py backend/src/hiresense/outreach/domain/outreach_event_kind.py backend/src/hiresense/outreach/domain/outreach_event.py backend/src/hiresense/outreach/domain/outreach_nudge.py backend/src/hiresense/outreach/domain/__init__.py
git commit -m "feat(outreach): add OutreachEvent/Kind/Nudge domain models"
```

---

## Task 3: ORM + migration

**Files:** Create `outreach/infrastructure/orm.py`, `outreach/infrastructure/__init__.py` (empty for now — Task 4 overwrites), `alembic/versions/019_create_outreach_events.py`.

- [ ] **Step 1: `orm.py`**

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class OutreachEventOrm(Base):
    """Append-only log of outreach actions on a tracked application."""

    __tablename__ = "outreach_events"
    __table_args__ = (
        Index("ix_outreach_events_application_id", "application_id"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    application_id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),  # microsecond precision (SQLite-deterministic)
        server_default=func.now(),
        nullable=False,
    )
```

- [ ] **Step 2: empty `outreach/infrastructure/__init__.py`** (blank file; Task 4 fills it).

- [ ] **Step 3: Verify ORM imports**

Run: `cd backend && uv run python -c "from hiresense.outreach.infrastructure.orm import OutreachEventOrm; print(OutreachEventOrm.__tablename__)"`
Expected: `outreach_events`

- [ ] **Step 4: Migration `019_create_outreach_events.py`**

```python
"""create outreach_events (append-only outreach log per application)

Revision ID: 019
Revises: 018
Create Date: 2026-05-31
"""
from typing import Sequence, Union

from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_events (
            id UUID PRIMARY KEY,
            application_id UUID NOT NULL,
            kind VARCHAR(16) NOT NULL,
            contact_name VARCHAR(255),
            channel VARCHAR(32),
            message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_outreach_events_application_id "
        "ON outreach_events (application_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_outreach_events_application_id")
    op.execute("DROP TABLE IF EXISTS outreach_events")
```

- [ ] **Step 5: Verify parses (do NOT run alembic upgrade)**

Run: `cd backend && uv run python -c "import ast; ast.parse(open('alembic/versions/019_create_outreach_events.py').read()); print('parses')"`
Expected: `parses`

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/outreach/infrastructure/orm.py backend/src/hiresense/outreach/infrastructure/__init__.py backend/alembic/versions/019_create_outreach_events.py
git commit -m "feat(outreach): add outreach_events ORM + migration"
```

---

## Task 4: OutreachRepository + port

**Files:** Create `outreach/ports/repository.py`, `outreach/ports/__init__.py`, `outreach/infrastructure/repository.py`, overwrite `outreach/infrastructure/__init__.py`; Test `backend/tests/integration/test_outreach_repository.py`.

- [ ] **Step 1: Write the failing DB test**

```python
import uuid as uuid_mod

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.outreach.domain import OutreachEvent, OutreachEventKind
from hiresense.outreach.infrastructure import OutreachRepository
from hiresense.outreach.infrastructure.orm import OutreachEventOrm  # noqa: F401


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _evt(app_id, kind, msg="hi"):
    return OutreachEvent(application_id=app_id, kind=kind, message=msg, contact_name="Sam")


def test_add_and_list_for():
    repo = OutreachRepository(session_factory=_factory())
    app_id = uuid_mod.uuid4()
    saved = repo.add(_evt(app_id, OutreachEventKind.SENT))
    assert saved.id is not None and saved.created_at is not None
    events = repo.list_for(app_id)
    assert len(events) == 1 and events[0].kind == OutreachEventKind.SENT


def test_latest_for_returns_most_recent():
    repo = OutreachRepository(session_factory=_factory())
    app_id = uuid_mod.uuid4()
    repo.add(_evt(app_id, OutreachEventKind.SENT))
    repo.add(_evt(app_id, OutreachEventKind.REPLIED, msg=None))
    latest = repo.latest_for(app_id)
    assert latest is not None and latest.kind == OutreachEventKind.REPLIED


def test_latest_per_application():
    repo = OutreachRepository(session_factory=_factory())
    a, b = uuid_mod.uuid4(), uuid_mod.uuid4()
    repo.add(_evt(a, OutreachEventKind.SENT))
    repo.add(_evt(a, OutreachEventKind.FOLLOWED_UP))
    repo.add(_evt(b, OutreachEventKind.SENT))
    latest = repo.latest_per_application()
    by_app = {e.application_id: e.kind for e in latest}
    assert by_app[a] == OutreachEventKind.FOLLOWED_UP and by_app[b] == OutreachEventKind.SENT
    assert len(latest) == 2
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Port** `ports/repository.py`:

```python
from __future__ import annotations

import uuid
from typing import Protocol

from hiresense.outreach.domain import OutreachEvent


class OutreachRepositoryPort(Protocol):
    def add(self, event: OutreachEvent) -> OutreachEvent: ...

    def list_for(self, application_id: uuid.UUID) -> list[OutreachEvent]: ...

    def latest_for(self, application_id: uuid.UUID) -> OutreachEvent | None: ...

    def latest_per_application(self) -> list[OutreachEvent]: ...
```

`ports/__init__.py`:

```python
from hiresense.outreach.ports.repository import OutreachRepositoryPort

__all__ = ["OutreachRepositoryPort"]
```

- [ ] **Step 4: Repository** `infrastructure/repository.py`:

```python
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.outreach.domain import OutreachEvent, OutreachEventKind
from hiresense.outreach.infrastructure.orm import OutreachEventOrm


def _to_domain(row: OutreachEventOrm) -> OutreachEvent:
    return OutreachEvent(
        id=row.id,
        application_id=row.application_id,
        kind=OutreachEventKind(row.kind),
        contact_name=row.contact_name,
        channel=row.channel,
        message=row.message,
        created_at=row.created_at,
    )


class OutreachRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def add(self, event: OutreachEvent) -> OutreachEvent:
        with self._session_factory() as session:
            row = OutreachEventOrm(
                application_id=event.application_id,
                kind=event.kind.value,
                contact_name=event.contact_name,
                channel=event.channel,
                message=event.message,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def list_for(self, application_id: uuid.UUID) -> list[OutreachEvent]:
        with self._session_factory() as session:
            stmt = (
                select(OutreachEventOrm)
                .where(OutreachEventOrm.application_id == application_id)
                .order_by(OutreachEventOrm.created_at)
            )
            return [_to_domain(r) for r in session.scalars(stmt).all()]

    def latest_for(self, application_id: uuid.UUID) -> OutreachEvent | None:
        with self._session_factory() as session:
            stmt = (
                select(OutreachEventOrm)
                .where(OutreachEventOrm.application_id == application_id)
                .order_by(OutreachEventOrm.created_at.desc())
                .limit(1)
            )
            row = session.scalars(stmt).first()
            return _to_domain(row) if row is not None else None

    def latest_per_application(self) -> list[OutreachEvent]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(OutreachEventOrm).order_by(OutreachEventOrm.created_at)
            ).all()
            # Keep the last (most recent) event per application; rows are asc by
            # created_at, so later overwrites earlier.
            latest: dict[uuid.UUID, OutreachEventOrm] = {}
            for r in rows:
                latest[r.application_id] = r
            return [_to_domain(r) for r in latest.values()]
```

`infrastructure/__init__.py` (overwrite):

```python
from hiresense.outreach.infrastructure.repository import OutreachRepository

__all__ = ["OutreachRepository"]
```

- [ ] **Step 5: Run → PASS** (3 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/outreach/ports/ backend/src/hiresense/outreach/infrastructure/repository.py backend/src/hiresense/outreach/infrastructure/__init__.py backend/tests/integration/test_outreach_repository.py
git commit -m "feat(outreach): add OutreachRepository + port"
```

---

## Task 5: style-guide loader + OutreachMessageGenerator

**Files:** Create `domain/style_guide.py`, `domain/message_generator.py`; update `domain/__init__.py`; Test `backend/tests/unit/outreach/test_style_guide.py`, `test_message_generator.py` (+ `tests/unit/outreach/__init__.py` if the project's other unit dirs have one — match the analytics/autohunt convention).

- [ ] **Step 1: Failing test `test_style_guide.py`**

```python
from hiresense.outreach.domain.style_guide import DEFAULT_STYLE_GUIDE, load_style_guide


def test_loads_existing_file(tmp_path):
    p = tmp_path / "style.md"
    p.write_text("Be concise and specific.", encoding="utf-8")
    assert load_style_guide(str(p)) == "Be concise and specific."


def test_missing_file_returns_default():
    assert load_style_guide("does/not/exist.md") == DEFAULT_STYLE_GUIDE
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement `style_guide.py`**

```python
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STYLE_GUIDE = (
    "Write a short, professional outreach message. Be concise and specific: "
    "name the role, mention one genuine, concrete reason you're a fit, and close "
    "with a light call to connect. No fluff."
)


def load_style_guide(path: str) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8").strip()
        return text or DEFAULT_STYLE_GUIDE
    except OSError:
        logger.warning("outreach: style guide not readable at %s — using default", path)
        return DEFAULT_STYLE_GUIDE
```

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: Failing test `test_message_generator.py`**

```python
import pytest

from hiresense.outreach.domain.message_generator import (
    OutreachMessageGenerator,
    OutreachUnavailableError,
)


class _FakeLLM:
    def __init__(self, text="  Hi Sam, ...  "):
        self.text = text
        self.calls = []

    async def complete(self, prompt, system):
        self.calls.append((prompt, system))
        return self.text


def _gen(llm):
    return OutreachMessageGenerator(llm=llm)


@pytest.mark.asyncio
async def test_generates_stripped_body_with_style_and_research():
    llm = _FakeLLM()
    out = await _gen(llm).generate(
        company="Acme", title="Backend Engineer", job_description="Build APIs",
        candidate_name="Bryan", candidate_summary="FastAPI dev", candidate_skills=["python"],
        company_research="Culture: remote-first", contact_name="Sam", style_guide="BE CONCISE",
        channel="linkedin", max_chars=500,
    )
    assert out == "Hi Sam, ..."
    prompt, system = llm.calls[0]
    assert "BE CONCISE" in prompt and "Bryan" in prompt and "Backend Engineer" in prompt
    assert "Culture: remote-first" in prompt and "Sam" in prompt


@pytest.mark.asyncio
async def test_omits_research_when_none():
    llm = _FakeLLM()
    await _gen(llm).generate(
        company="Acme", title="BE", job_description="x", candidate_name="Bryan",
        candidate_summary="s", candidate_skills=[], company_research=None,
        contact_name=None, style_guide="SG", channel=None, max_chars=500,
    )
    prompt, _ = llm.calls[0]
    assert "Company research" not in prompt  # the research block is omitted


@pytest.mark.asyncio
async def test_raises_when_no_llm():
    with pytest.raises(OutreachUnavailableError):
        await _gen(None).generate(
            company="Acme", title="BE", job_description="x", candidate_name="B",
            candidate_summary="s", candidate_skills=[], company_research=None,
            contact_name=None, style_guide="SG", channel=None, max_chars=500,
        )
```

- [ ] **Step 6: Run → FAIL.**

- [ ] **Step 7: Implement `message_generator.py`**

```python
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class OutreachUnavailableError(RuntimeError):
    """Raised when outreach generation is requested but no LLM is configured."""


SYSTEM_PROMPT = (
    "You draft short, on-brand outreach messages to recruiters and hiring "
    "managers. Concise, specific, and genuine. No fluff, no placeholders, no "
    "markdown. Return only the message body, ready to paste."
)


class OutreachMessageGenerator:
    """Pure LLM unit. Inputs are resolved by OutreachService."""

    def __init__(self, llm: Any | None) -> None:
        self._llm = llm

    async def generate(
        self,
        *,
        company: str,
        title: str,
        job_description: str,
        candidate_name: str,
        candidate_summary: str,
        candidate_skills: list[str],
        company_research: str | None,
        contact_name: str | None,
        style_guide: str,
        channel: str | None,
        max_chars: int,
    ) -> str:
        if self._llm is None:
            raise OutreachUnavailableError("no LLM configured")

        parts = [
            "Draft an outreach message following this style guide:\n"
            f"---\n{style_guide}\n---\n",
            f"Role: {title} at {company}",
            f"Job context: {job_description[:1200]}",
            f"Candidate name (sign with this): {candidate_name or '(unknown)'}",
            f"Candidate summary: {candidate_summary or '(none)'}",
            f"Candidate skills: {', '.join(candidate_skills) or '(none)'}",
        ]
        if company_research:
            parts.append(f"Company research (use lightly): {company_research}")
        if contact_name:
            parts.append(f"Address it to: {contact_name}")
        if channel:
            parts.append(f"Channel: {channel}")
        parts.append(
            f"Keep it under ~{max_chars} characters. Greet (use the contact name "
            "if given), state the role and one specific genuine hook tying the "
            "candidate's strengths to the company, a light call to connect, and "
            "sign with the candidate's name. Return only the message body."
        )
        prompt = "\n".join(parts)
        try:
            response = await self._llm.complete(prompt, system=SYSTEM_PROMPT)
        except Exception:
            logger.exception("outreach: LLM call failed")
            raise
        return response.strip()
```

(NOTE: the test asserts the literal `"Company research"` is absent when research is None — the prompt uses `"Company research (use lightly):"`, so the absence check holds. Keep that exact prefix.)

- [ ] **Step 8: Run → PASS.** Add re-exports to `domain/__init__.py`:

```python
from hiresense.outreach.domain.message_generator import (
    OutreachMessageGenerator,
    OutreachUnavailableError,
)
from hiresense.outreach.domain.outreach_event import OutreachEvent
from hiresense.outreach.domain.outreach_event_kind import OutreachEventKind
from hiresense.outreach.domain.outreach_nudge import OutreachNudge
from hiresense.outreach.domain.style_guide import DEFAULT_STYLE_GUIDE, load_style_guide

__all__ = [
    "DEFAULT_STYLE_GUIDE",
    "OutreachEvent",
    "OutreachEventKind",
    "OutreachMessageGenerator",
    "OutreachNudge",
    "OutreachUnavailableError",
    "load_style_guide",
]
```

- [ ] **Step 9: Commit**

```bash
git add backend/src/hiresense/outreach/domain/style_guide.py backend/src/hiresense/outreach/domain/message_generator.py backend/src/hiresense/outreach/domain/__init__.py backend/tests/unit/outreach/
git commit -m "feat(outreach): add style-guide loader + OutreachMessageGenerator"
```

---

## Task 6: OutreachService

**Files:** Create `domain/outreach_service.py`; update `domain/__init__.py`; Test `backend/tests/unit/outreach/test_outreach_service.py`.

- [ ] **Step 1: Failing test**

```python
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

import pytest

from hiresense.outreach.domain import OutreachEvent, OutreachEventKind
from hiresense.outreach.domain.outreach_service import OutreachService


class _App:
    def __init__(self, id, company="Acme", status="applied"):
        self.id = id
        self.company = company
        self.title = "Backend Engineer"
        self.status = status
        self.url = None


class _Tracking:
    def __init__(self, apps):
        self._apps = {a.id: a for a in apps}

    def get(self, app_id):
        if app_id not in self._apps:
            raise ValueError("not found")
        return self._apps[app_id]


class _Profile:
    async def get_current_profile(self, language=None):
        return type("P", (), {"name": "Bryan"})()

    def get_for_language(self, language):
        return type("V", (), {"skills": ["python"], "summary": "dev"})()


class _Research:
    def get(self, company):
        return None


class _Gen:
    def __init__(self):
        self.called = False

    async def generate(self, **kwargs):
        self.called = True
        return "drafted message"


class _Repo:
    def __init__(self, latest=None):
        self.added = []
        self._latest_per = latest or []

    def add(self, event):
        saved = event.model_copy(update={"id": uuid_mod.uuid4(), "created_at": datetime.now(timezone.utc)})
        self.added.append(saved)
        return saved

    def list_for(self, app_id):
        return [e for e in self.added if e.application_id == app_id]

    def latest_per_application(self):
        return self._latest_per


def _svc(tracking, repo, gen=None, profile=None, research=None):
    return OutreachService(
        tracking_service=tracking, profile_service=profile or _Profile(),
        research_service=research or _Research(), generator=gen or _Gen(), repo=repo,
        style_guide_path="does/not/exist.md", followup_cadence_days=7, max_chars=500, language="en",
    )


@pytest.mark.asyncio
async def test_generate_resolves_and_records_nothing():
    app_id = uuid_mod.uuid4()
    gen = _Gen()
    repo = _Repo()
    svc = _svc(_Tracking([_App(app_id)]), repo, gen=gen)
    out = await svc.generate(app_id, contact_name="Sam")
    assert out == "drafted message" and gen.called
    assert repo.added == []  # generate persists nothing


@pytest.mark.asyncio
async def test_generate_unknown_app_raises():
    repo = _Repo()
    svc = _svc(_Tracking([]), repo)
    with pytest.raises(ValueError):
        await svc.generate(uuid_mod.uuid4())


def test_record_persists_event():
    app_id = uuid_mod.uuid4()
    repo = _Repo()
    svc = _svc(_Tracking([_App(app_id)]), repo)
    evt = svc.record(app_id, kind=OutreachEventKind.SENT, message="hi", contact_name="Sam")
    assert evt.kind == OutreachEventKind.SENT
    assert len(repo.added) == 1


def _latest(app_id, kind, days_ago):
    return OutreachEvent(
        id=uuid_mod.uuid4(), application_id=app_id, kind=kind, message="hi",
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )


def test_due_followups_logic():
    due = uuid_mod.uuid4()       # sent 10d ago, status applied -> due
    fresh = uuid_mod.uuid4()     # sent 2d ago -> not due
    replied = uuid_mod.uuid4()   # latest is replied -> not due
    advanced = uuid_mod.uuid4()  # sent 10d ago but status interviewing -> not due
    repo = _Repo(latest=[
        _latest(due, OutreachEventKind.SENT, 10),
        _latest(fresh, OutreachEventKind.SENT, 2),
        _latest(replied, OutreachEventKind.REPLIED, 10),
        _latest(advanced, OutreachEventKind.SENT, 10),
    ])
    tracking = _Tracking([
        _App(due, status="applied"), _App(fresh, status="applied"),
        _App(replied, status="applied"), _App(advanced, status="interviewing"),
    ])
    svc = _svc(tracking, repo)
    nudges = svc.due_followups()
    ids = {n.application_id for n in nudges}
    assert ids == {due}
    assert nudges[0].days_since >= 10 and nudges[0].company == "Acme"
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement `outreach_service.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from hiresense.outreach.domain.outreach_event import OutreachEvent
from hiresense.outreach.domain.outreach_event_kind import OutreachEventKind
from hiresense.outreach.domain.outreach_nudge import OutreachNudge
from hiresense.outreach.domain.style_guide import load_style_guide

_ACTIVE_STATUSES = {"saved", "applied"}


class OutreachService:
    def __init__(
        self,
        *,
        tracking_service: Any,
        profile_service: Any,
        research_service: Any,
        generator: Any,
        repo: Any,
        style_guide_path: str,
        followup_cadence_days: int,
        max_chars: int,
        language: str,
    ) -> None:
        self._tracking = tracking_service
        self._profile = profile_service
        self._research = research_service
        self._generator = generator
        self._repo = repo
        self._style_guide_path = style_guide_path
        self._cadence = followup_cadence_days
        self._max_chars = max_chars
        self._language = language

    async def generate(
        self, application_id: uuid.UUID, *, contact_name: str | None = None, channel: str | None = None
    ) -> str:
        app = self._tracking.get(application_id)  # raises ValueError if missing
        profile = await self._profile.get_current_profile(self._language)
        view = self._profile.get_for_language(self._language)
        research = self._research.get(app.company)
        return await self._generator.generate(
            company=app.company,
            title=getattr(app, "title", ""),
            job_description=getattr(app, "notes", "") or "",
            candidate_name=(profile.name if profile is not None else ""),
            candidate_summary=(view.summary if view is not None else ""),
            candidate_skills=(list(view.skills) if view is not None else []),
            company_research=self._research_blurb(research),
            contact_name=contact_name,
            style_guide=load_style_guide(self._style_guide_path),
            channel=channel,
            max_chars=self._max_chars,
        )

    def record(
        self,
        application_id: uuid.UUID,
        *,
        kind: OutreachEventKind,
        message: str | None = None,
        contact_name: str | None = None,
        channel: str | None = None,
    ) -> OutreachEvent:
        self._tracking.get(application_id)  # 404 if missing
        return self._repo.add(
            OutreachEvent(
                application_id=application_id, kind=kind, message=message,
                contact_name=contact_name, channel=channel,
            )
        )

    def list_for(self, application_id: uuid.UUID) -> list[OutreachEvent]:
        return self._repo.list_for(application_id)

    def due_followups(self) -> list[OutreachNudge]:
        now = datetime.now(timezone.utc)
        nudges: list[OutreachNudge] = []
        for latest in self._repo.latest_per_application():
            if latest.kind != OutreachEventKind.SENT or latest.created_at is None:
                continue
            sent_at = latest.created_at
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            days_since = (now - sent_at).days
            if days_since < self._cadence:
                continue
            try:
                app = self._tracking.get(latest.application_id)
            except ValueError:
                continue  # application deleted — skip
            if app.status not in _ACTIVE_STATUSES:
                continue
            nudges.append(
                OutreachNudge(
                    application_id=latest.application_id, company=app.company,
                    contact_name=latest.contact_name, sent_at=sent_at, days_since=days_since,
                )
            )
        return nudges

    @staticmethod
    def _research_blurb(research: Any | None) -> str | None:
        if research is None:
            return None
        bits = []
        for label, attr in (("Culture", "culture_summary"), ("Tech", "tech_stack"), ("Pros", "pros")):
            value = getattr(research, attr, None)
            if value:
                bits.append(f"{label}: {value}")
        return " | ".join(bits) or None
```

- [ ] **Step 4: Run → PASS.** Add `OutreachService` to `domain/__init__.py` (`from hiresense.outreach.domain.outreach_service import OutreachService` + add `"OutreachService"` to `__all__`).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/outreach/domain/outreach_service.py backend/src/hiresense/outreach/domain/__init__.py backend/tests/unit/outreach/test_outreach_service.py
git commit -m "feat(outreach): add OutreachService (generate/record/list/due_followups)"
```

---

## Task 7: API layer

**Files:** Create `api/schemas.py`, `api/provider.py`, `api/dependencies.py`, `api/routes.py`, `api/__init__.py`.

- [ ] **Step 1: `schemas.py`** (request bodies + re-export response models)

```python
from __future__ import annotations

import uuid

from pydantic import BaseModel

from hiresense.outreach.domain import OutreachEvent, OutreachEventKind, OutreachNudge


class GenerateRequest(BaseModel):
    application_id: uuid.UUID
    contact_name: str | None = None
    channel: str | None = None


class GenerateResponse(BaseModel):
    message: str


class RecordRequest(BaseModel):
    application_id: uuid.UUID
    kind: OutreachEventKind
    message: str | None = None
    contact_name: str | None = None
    channel: str | None = None


__all__ = [
    "GenerateRequest",
    "GenerateResponse",
    "OutreachEvent",
    "OutreachNudge",
    "RecordRequest",
]
```

- [ ] **Step 2: `provider.py`**

```python
from __future__ import annotations

from hiresense.outreach.domain import OutreachService


class OutreachProvider:
    def __init__(self, outreach_service: OutreachService) -> None:
        self._outreach_service = outreach_service

    def get_outreach_service(self) -> OutreachService:
        return self._outreach_service
```

- [ ] **Step 3: `dependencies.py`**

```python
from __future__ import annotations

from fastapi import Request

from hiresense.outreach.domain import OutreachService


def get_outreach_service(request: Request) -> OutreachService:
    return request.app.state.outreach.get_outreach_service()
```

- [ ] **Step 4: `routes.py`**

```python
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from hiresense.identity.api.dependencies import require_auth
from hiresense.outreach.api.dependencies import get_outreach_service
from hiresense.outreach.api.schemas import (
    GenerateRequest,
    GenerateResponse,
    RecordRequest,
)
from hiresense.outreach.domain import OutreachEvent, OutreachNudge, OutreachService
from hiresense.outreach.domain.message_generator import OutreachUnavailableError

router = APIRouter(prefix="/outreach", tags=["outreach"], dependencies=[Depends(require_auth)])


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    body: GenerateRequest, service: OutreachService = Depends(get_outreach_service)
) -> GenerateResponse:
    try:
        message = await service.generate(
            body.application_id, contact_name=body.contact_name, channel=body.channel
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OutreachUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Outreach generation unavailable") from exc
    return GenerateResponse(message=message)


@router.post("/record", response_model=OutreachEvent, status_code=201)
def record(
    body: RecordRequest, service: OutreachService = Depends(get_outreach_service)
) -> OutreachEvent:
    try:
        return service.record(
            body.application_id, kind=body.kind, message=body.message,
            contact_name=body.contact_name, channel=body.channel,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/events", response_model=list[OutreachEvent])
def list_events(
    application_id: uuid.UUID, service: OutreachService = Depends(get_outreach_service)
) -> list[OutreachEvent]:
    return service.list_for(application_id)


@router.post("/nudge", response_model=list[OutreachNudge])
def nudge(service: OutreachService = Depends(get_outreach_service)) -> list[OutreachNudge]:
    return service.due_followups()
```

(`kind` invalid → FastAPI 422 automatically via the `OutreachEventKind` enum on `RecordRequest`.)

- [ ] **Step 5: `__init__.py`**

```python
from hiresense.outreach.api.routes import router

__all__ = ["router"]
```

- [ ] **Step 6: Verify + commit**

Run: `cd backend && uv run python -c "from hiresense.outreach.api import router; print(len(router.routes))"`
Expected: `4`

```bash
git add backend/src/hiresense/outreach/api/
git commit -m "feat(outreach): add API provider, dependencies, routes"
```

---

## Task 8: Bootstrap + main wiring

**Files:** Create `bootstrap/outreach.py`; Modify `bootstrap/__init__.py`, `main.py`.

- [ ] **Step 1: `bootstrap/outreach.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.outreach.api.provider import OutreachProvider
from hiresense.outreach.domain import OutreachMessageGenerator, OutreachService
from hiresense.outreach.infrastructure import OutreachRepository


@dataclass(frozen=True)
class OutreachBuild:
    provider: OutreachProvider
    service: OutreachService


def build_outreach(
    infra: SharedInfra,
    tracked: Any,
    tracking_service: Any,
    profile_service: Any,
    research_service: Any,
) -> OutreachBuild:
    s = infra.settings
    service = OutreachService(
        tracking_service=tracking_service,
        profile_service=profile_service,
        research_service=research_service,
        generator=OutreachMessageGenerator(llm=tracked("outreach_message")),
        repo=OutreachRepository(session_factory=infra.sync_session_factory),
        style_guide_path=s.outreach_style_guide_path,
        followup_cadence_days=s.outreach_followup_cadence_days,
        max_chars=s.outreach_max_chars,
        language=s.default_language,
    )
    return OutreachBuild(provider=OutreachProvider(outreach_service=service), service=service)
```

- [ ] **Step 2: `bootstrap/__init__.py`** — add import + `__all__` entries:

```python
from hiresense.bootstrap.outreach import OutreachBuild, build_outreach
```
(add `"OutreachBuild"`, `"build_outreach"` to `__all__`.)

- [ ] **Step 3: `main.py`** — router import near the others:

```python
from hiresense.outreach.api import router as outreach_router
```
Add `build_outreach` to the `from hiresense.bootstrap import (...)` block. The research build currently reads `app.state.research = build_research(infra, tracked)`; capture it and wire outreach after it (research is built near the end, after tracking + profile). Change the research block + append outreach:

```python
    # --- Research ---
    research = build_research(infra, tracked)
    app.state.research = research
    app.include_router(research_router)

    # --- Outreach (generation + outreach-event tracking + follow-up nudges) ---
    outreach = build_outreach(
        infra, tracked, tracking.service, profile.service, research.get_research_service()
    )
    app.state.outreach = outreach.provider
    app.include_router(outreach_router)
```

(`build_research` returns a `ResearchProvider`; `research.get_research_service()` yields the `CompanyResearchService`. `tracking.service` and `profile.service` are available from their earlier builds.)

- [ ] **Step 4: Verify the app builds**

Run: `cd backend && uv run python -c "from hiresense.main import create_app; create_app(); print('ok')"`
Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/bootstrap/outreach.py backend/src/hiresense/bootstrap/__init__.py backend/src/hiresense/main.py
git commit -m "feat(outreach): wire outreach context into the app"
```

---

## Task 9: Endpoint integration tests

**Files:** Create `backend/tests/integration/test_outreach_endpoints.py`.

- [ ] **Step 1: Write the integration test** (in-process FastAPI, real SQLite, fakes for LLM/profile/research/tracking, auth overridden)

```python
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.identity.api.dependencies import require_auth
from hiresense.infrastructure.database import Base
from hiresense.outreach.api import router as outreach_router
from hiresense.outreach.api.dependencies import get_outreach_service
from hiresense.outreach.domain import OutreachMessageGenerator, OutreachService
from hiresense.outreach.infrastructure import OutreachRepository
from hiresense.outreach.infrastructure.orm import OutreachEventOrm


class _FakeLLM:
    async def complete(self, prompt, system):
        return "Hi Sam, I'd love to connect about the role."


class _Tracking:
    def __init__(self, apps):
        self._apps = {a.id: a for a in apps}

    def get(self, app_id):
        if app_id not in self._apps:
            raise ValueError("not found")
        return self._apps[app_id]


class _App:
    def __init__(self, id, company="Acme", status="applied"):
        self.id = id
        self.company = company
        self.title = "Backend Engineer"
        self.status = status
        self.url = None
        self.notes = "Build APIs"


class _Profile:
    async def get_current_profile(self, language=None):
        return type("P", (), {"name": "Bryan"})()

    def get_for_language(self, language):
        return type("V", (), {"skills": ["python"], "summary": "dev"})()


class _Research:
    def get(self, company):
        return None


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False), engine


def _build_app(app_id, factory):
    repo = OutreachRepository(session_factory=factory)
    service = OutreachService(
        tracking_service=_Tracking([_App(app_id)]), profile_service=_Profile(),
        research_service=_Research(), generator=OutreachMessageGenerator(llm=_FakeLLM()),
        repo=repo, style_guide_path="does/not/exist.md", followup_cadence_days=7,
        max_chars=500, language="en",
    )
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_outreach_service] = lambda: service
    app.include_router(outreach_router)
    return app


@pytest.mark.asyncio
async def test_generate_record_list_flow():
    factory, _ = _factory()
    app_id = uuid_mod.uuid4()
    app = _build_app(app_id, factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        gen = await c.post("/outreach/generate", json={"application_id": str(app_id), "contact_name": "Sam"})
        assert gen.status_code == 200
        assert "connect" in gen.json()["message"]

        rec = await c.post("/outreach/record", json={
            "application_id": str(app_id), "kind": "sent", "message": gen.json()["message"], "contact_name": "Sam",
        })
        assert rec.status_code == 201

        events = await c.get(f"/outreach/events?application_id={app_id}")
        assert events.status_code == 200 and len(events.json()) == 1


@pytest.mark.asyncio
async def test_nudge_surfaces_then_clears():
    factory, engine = _factory()
    app_id = uuid_mod.uuid4()
    app = _build_app(app_id, factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/outreach/record", json={"application_id": str(app_id), "kind": "sent", "message": "hi"})
        # Back-date the sent event past the cadence so the nudge is due.
        with factory() as s:
            s.execute(
                update(OutreachEventOrm)
                .where(OutreachEventOrm.application_id == app_id)
                .values(created_at=datetime.now(timezone.utc) - timedelta(days=10))
            )
            s.commit()
        due = await c.post("/outreach/nudge")
        assert due.status_code == 200
        assert [n["application_id"] for n in due.json()] == [str(app_id)]

        # Recording a reply clears the nudge (latest event is no longer 'sent').
        await c.post("/outreach/record", json={"application_id": str(app_id), "kind": "replied"})
        cleared = await c.post("/outreach/nudge")
        assert cleared.json() == []
```

- [ ] **Step 2: Run → PASS** (2 tests)

Run: `cd backend && uv run python -m pytest tests/integration/test_outreach_endpoints.py -v`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_outreach_endpoints.py
git commit -m "test(outreach): integration tests for generate/record/list/nudge"
```

---

## Task 10: Final verification

- [ ] **Step 1: Full suite** — `cd backend && uv run python -m pytest -q` → PASS.
- [ ] **Step 2: Lint** — `cd backend && uv run python -m ruff check src/hiresense/outreach src/hiresense/bootstrap/outreach.py tests/unit/outreach tests/integration/test_outreach_repository.py tests/integration/test_outreach_endpoints.py` → clean (fix with `--fix`; pre-existing repo-wide debt out of scope).
- [ ] **Step 3: App smoke** — `cd backend && uv run python -c "from hiresense.main import create_app; create_app(); print('ok')"` → `ok`.

---

## Self-Review notes

- **Spec coverage:** `outreach_events` append-only table + migration 019 + microsecond `created_at` (T3) ✓; domain models incl. `OutreachNudge` (T2) ✓; repo add/list_for/latest_for/latest_per_application (T4) ✓; file-backed style guide w/ default (T5) ✓; pure `OutreachMessageGenerator` mirroring CoverLetterGenerator, research-omitted-when-None, 503 via `OutreachUnavailableError` (T5) ✓; `OutreachService` generate=draft-only/record/list/stateless due_followups keyed on latest-event+status (T6) ✓; four auth-gated endpoints incl. cron `/nudge` (T7) ✓; built after tracking/profile/research, research service via `get_research_service()` (T8) ✓; integration generate→record→list + nudge-surfaces-then-clears (T9) ✓; settings (T1) ✓.
- **Type/name consistency:** `OutreachEvent{application_id,kind,contact_name,channel,message,created_at}` and `OutreachNudge{application_id,company,contact_name,sent_at,days_since}` consistent across model/ORM/repo/service/API/tests; `OutreachService` method names (`generate`/`record`/`list_for`/`due_followups`) match the routes; `generate(...)` generator kwargs match `OutreachMessageGenerator.generate` exactly; `build_outreach(infra, tracked, tracking_service, profile_service, research_service)` matches the `main.py` call passing `tracking.service`, `profile.service`, `research.get_research_service()`.
- **No placeholders:** every step has complete code; the research-omission test relies on the exact `"Company research"` prompt prefix (noted).
- **Out of scope:** contacts entity, outbound send, reply inbox, frontend, multi-user.
