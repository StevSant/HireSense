# Autopilot Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On a cadence, turn the autohunt digest's top new matches into ready-to-review application drafts (application + match + CV optimization + cover letter), then notify — composing Phases 1–3 and reusing the `applications` generation services.

**Architecture:** New hexagonal `autopilot/` module. `AutopilotPipelineService.run()` reads the latest autohunt digest, dedups against an `autopilot_drafts` table, and for each top-N job calls a single `ApplicationDrafter` port. The concrete `ServicesApplicationDrafter` drives `ApplicationService.create_from_ingested` → `ArtifactService.generate_match`/`generate_optimization` → `ApplyService.generate_cover_letter`. A 6th scheduler job runs it (only when enabled+injected); `NotificationService.notify_pipeline_drafts` announces drafts.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, the existing applications services, Angular 21 (standalone + signals), Vitest.

**Spec:** [`docs/superpowers/specs/2026-06-22-autopilot-pipeline-design.md`](../specs/2026-06-22-autopilot-pipeline-design.md)

## Global Constraints

- Orchestration only — reuse `applications` services; do NOT modify the applications module or its schema.
- Drafts are normal applications in `saved` status; nothing is sent/applied/auto-advanced.
- Dedup by `job_id` via the `autopilot_drafts` table (`exists_for_job`); re-runs skip drafted jobs.
- Best-effort: per-job drafting isolated (drafter exception → `failed` draft, batch continues; partial generation → `partial`); `run()` NEVER raises into the scheduler; notification failure swallowed.
- Opt-in + capped: `autopilot_pipeline_enabled` default False; `autopilot_pipeline_top_n` default 3. `build_autopilot` returns `None` when disabled → scheduler job absent → Phases 1–3 byte-identical.
- `domain/` imports no framework packages and nothing from `infrastructure/`; the applications services are reached via the `ApplicationDrafter` port.
- ONE class/enum/function per file; intra-package imports use SIBLING FILES directly (avoid `__init__` circular imports); package `__init__.py` re-exports for external consumers.
- Every ORM class imported in `infrastructure/registry.py`.
- Tests: `cd backend && uv run python -m pytest <path> -v` (never bare pytest); integration over in-memory SQLite + `StaticPool` + `require_auth`/`require_admin` overrides. No real LLM in tests.
- Lint: `cd backend && uv run ruff check <new files>` must be clean (fix F401/E702 from any compact test code — do NOT run `ruff format`).
- No hardcoded values — tunables via `config.py` + `.env.example`.
- Working tree has PRE-EXISTING unrelated WIP. Stage ONLY each task's files with explicit paths. Never `git add -A`.

---

## File Structure

**New `autopilot/` module:**
- `domain/draft_status.py` (`DraftStatus`), `domain/autopilot_draft.py` (`AutopilotDraft`), `domain/pipeline_result.py` (`PipelineResult`).
- `domain/ports/draft_repository.py` (`DraftRepository`), `domain/ports/application_drafter.py` (`ApplicationDrafter`), `domain/ports/__init__.py`.
- `domain/autopilot_pipeline_service.py` (`AutopilotPipelineService`), `domain/__init__.py`.
- `infrastructure/autopilot_draft_orm.py` (`AutopilotDraftOrm`), `infrastructure/draft_repository.py` (`DraftRepositoryImpl`), `infrastructure/services_application_drafter.py` (`ServicesApplicationDrafter`), `infrastructure/__init__.py`.
- `api/provider.py` (`AutopilotProvider`), `api/dependencies.py`, `api/routes.py`, `api/__init__.py`.
- `__init__.py`.

**Modified:** `config.py`, `.env.example`, `infrastructure/registry.py`, `notifications/domain/{pipeline_drafts_email.py (new), notification_service.py, __init__.py}`, `bootstrap/autopilot.py (new)`, `bootstrap/scheduler.py`, `bootstrap/__init__.py`, `main.py`, new migration `035_add_autopilot_drafts.py`.

**Frontend:** `core/models/autopilot.model.ts`, `core/services/autopilot.service.ts` (+spec), `pages/autopilot/drafts/drafts.component.{ts,html,scss,spec.ts}`, `app.routes.ts`, `core/nav/hubs.const.ts`.

---

## Task 1: Config

**Files:** Modify `backend/src/hiresense/config.py`, `backend/.env.example`; Test `backend/tests/unit/test_settings_autopilot.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_settings_autopilot.py
from hiresense.config import Settings


def test_autopilot_pipeline_settings_defaults():
    s = Settings()
    assert s.autopilot_pipeline_enabled is False
    assert s.autopilot_pipeline_top_n == 3
    assert s.autopilot_pipeline_schedule == "0 10 * * *"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/test_settings_autopilot.py -v`
Expected: FAIL — `AttributeError: ... 'autopilot_pipeline_enabled'`.

- [ ] **Step 3: Add the settings**

In `config.py`, after the inbox block, add:

```python
    # --- Autopilot pipeline (Phase 4: auto-draft applications for top matches) ---
    # Gates the autopilot_pipeline scheduler job entirely. Default OFF (auto-drafting
    # CVs/cover letters is LLM-heavy — opt in deliberately).
    autopilot_pipeline_enabled: bool = False
    # Max digest entries to draft per run (bounds LLM spend).
    autopilot_pipeline_top_n: int = 3
    # Cron for the autopilot_pipeline job (after autohunt's 0 9 * * * so a digest exists).
    autopilot_pipeline_schedule: str = "0 10 * * *"
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/test_settings_autopilot.py -v`
Expected: PASS.

- [ ] **Step 5: Update `.env.example`**

Append:

```dotenv
# --- Autopilot pipeline (Phase 4) ---
# Auto-draft applications (CV + cover letter) for top autohunt matches. Default off.
AUTOPILOT_PIPELINE_ENABLED=false
AUTOPILOT_PIPELINE_TOP_N=3
AUTOPILOT_PIPELINE_SCHEDULE=0 10 * * *
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/config.py backend/.env.example backend/tests/unit/test_settings_autopilot.py
git commit -m "feat(autopilot): add pipeline config"
```

---

## Task 2: Domain models + enum

**Files:** Create `backend/src/hiresense/autopilot/__init__.py` (empty), `autopilot/domain/draft_status.py`, `autopilot/domain/autopilot_draft.py`, `autopilot/domain/pipeline_result.py`, `autopilot/domain/__init__.py`; Test `backend/tests/unit/autopilot/test_domain_models.py` (+ `tests/unit/autopilot/__init__.py`)

**Interfaces:**
- Produces: `DraftStatus` (`DRAFTED`/`PARTIAL`/`FAILED`, values `"drafted"`/`"partial"`/`"failed"`); `AutopilotDraft(id, job_id, application_id, job_title, company, status, detail, created_at)`; `PipelineResult(created, skipped, drafts)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/autopilot/test_domain_models.py
import uuid

from hiresense.autopilot.domain import AutopilotDraft, DraftStatus, PipelineResult


def test_models_construct():
    d = AutopilotDraft(
        job_id="j1", application_id=uuid.uuid4(), job_title="Dev", company="Acme",
        status=DraftStatus.DRAFTED, detail=None,
    )
    assert d.status is DraftStatus.DRAFTED
    assert DraftStatus.PARTIAL.value == "partial"
    r = PipelineResult(created=1, skipped=2, drafts=[d])
    assert r.created == 1 and r.skipped == 2 and len(r.drafts) == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/autopilot/test_domain_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hiresense.autopilot'`.

- [ ] **Step 3: Implement**

`autopilot/__init__.py`: empty. Create `tests/unit/autopilot/__init__.py`: empty.

`autopilot/domain/draft_status.py`:

```python
from __future__ import annotations

from enum import Enum


class DraftStatus(str, Enum):
    """Outcome of drafting one job."""

    DRAFTED = "drafted"   # application + all artifacts generated
    PARTIAL = "partial"   # application created, some artifact generation failed
    FAILED = "failed"     # could not even create the application
```

`autopilot/domain/autopilot_draft.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel

from hiresense.autopilot.domain.draft_status import DraftStatus


class AutopilotDraft(BaseModel):
    """One job processed by an autopilot run (pure domain model)."""

    id: uuid_mod.UUID | None = None
    job_id: str
    application_id: uuid_mod.UUID | None = None
    job_title: str | None = None
    company: str | None = None
    status: DraftStatus
    detail: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
```

`autopilot/domain/pipeline_result.py`:

```python
from __future__ import annotations

from pydantic import BaseModel

from hiresense.autopilot.domain.autopilot_draft import AutopilotDraft


class PipelineResult(BaseModel):
    """Summary of one autopilot pipeline run."""

    created: int = 0
    skipped: int = 0
    drafts: list[AutopilotDraft] = []
```

`autopilot/domain/__init__.py`:

```python
from hiresense.autopilot.domain.autopilot_draft import AutopilotDraft
from hiresense.autopilot.domain.draft_status import DraftStatus
from hiresense.autopilot.domain.pipeline_result import PipelineResult

__all__ = ["AutopilotDraft", "DraftStatus", "PipelineResult"]
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/autopilot/test_domain_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/autopilot/__init__.py backend/src/hiresense/autopilot/domain backend/tests/unit/autopilot
git commit -m "feat(autopilot): add domain models + DraftStatus"
```

---

## Task 3: Domain ports

**Files:** Create `autopilot/domain/ports/draft_repository.py`, `autopilot/domain/ports/application_drafter.py`, `autopilot/domain/ports/__init__.py`; Test `backend/tests/unit/autopilot/test_ports_importable.py`

**Interfaces:**
- Produces: `DraftRepository` (`add(draft) -> AutopilotDraft`, `list(limit) -> list[AutopilotDraft]`, `exists_for_job(job_id) -> bool`); `ApplicationDrafter` (`async draft(job_id: str) -> tuple[uuid.UUID | None, DraftStatus, str | None]` — application_id, status, detail).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/autopilot/test_ports_importable.py
from hiresense.autopilot.domain.ports import ApplicationDrafter, DraftRepository


def test_ports_runtime_checkable():
    class _Repo:
        def add(self, draft): ...
        def list(self, limit): ...
        def exists_for_job(self, job_id): ...

    class _Drafter:
        async def draft(self, job_id): ...

    assert isinstance(_Repo(), DraftRepository)
    assert isinstance(_Drafter(), ApplicationDrafter)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/autopilot/test_ports_importable.py -v`
Expected: FAIL — `ModuleNotFoundError: ...autopilot.domain.ports`.

- [ ] **Step 3: Implement**

`autopilot/domain/ports/draft_repository.py`:

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from hiresense.autopilot.domain.autopilot_draft import AutopilotDraft


@runtime_checkable
class DraftRepository(Protocol):
    def add(self, draft: AutopilotDraft) -> AutopilotDraft: ...

    def list(self, limit: int) -> list[AutopilotDraft]: ...

    def exists_for_job(self, job_id: str) -> bool: ...
```

`autopilot/domain/ports/application_drafter.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from typing import Protocol, runtime_checkable

from hiresense.autopilot.domain.draft_status import DraftStatus


@runtime_checkable
class ApplicationDrafter(Protocol):
    """Creates an application for a job and generates its draft artifacts.
    Returns (application_id, status, detail). Implementations should not raise for
    per-artifact failures — they map those to PARTIAL/FAILED."""

    async def draft(self, job_id: str) -> tuple[uuid_mod.UUID | None, DraftStatus, str | None]: ...
```

`autopilot/domain/ports/__init__.py`:

```python
from hiresense.autopilot.domain.ports.application_drafter import ApplicationDrafter
from hiresense.autopilot.domain.ports.draft_repository import DraftRepository

__all__ = ["ApplicationDrafter", "DraftRepository"]
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/autopilot/test_ports_importable.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/autopilot/domain/ports backend/tests/unit/autopilot/test_ports_importable.py
git commit -m "feat(autopilot): add drafter + draft-repository ports"
```

---

## Task 4: AutopilotPipelineService

**Files:** Create `autopilot/domain/autopilot_pipeline_service.py`; Modify `autopilot/domain/__init__.py`; Test `backend/tests/unit/autopilot/test_pipeline_service.py`

**Interfaces:**
- Consumes: `DraftRepository`, `ApplicationDrafter`; a `latest_digest()` callable returning an object with `.entries` (each entry has `.job_id`, `.title`, `.company`) or `None`; an optional `notifier` with `async notify_pipeline_drafts(count) -> bool`; `top_n: int`.
- Produces: `AutopilotPipelineService(*, latest_digest, drafter, repo, top_n, notifier=None)`; `async run() -> PipelineResult`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/autopilot/test_pipeline_service.py
import uuid

import pytest

from hiresense.autopilot.domain import AutopilotPipelineService, DraftStatus


class _Entry:
    def __init__(self, job_id, title="Dev", company="Acme"):
        self.job_id = job_id
        self.title = title
        self.company = company


class _Digest:
    def __init__(self, entries):
        self.entries = entries


class _Repo:
    def __init__(self, drafted=()):
        self.added = []
        self._drafted = set(drafted)
    def add(self, draft):
        draft.id = uuid.uuid4()
        self.added.append(draft)
        return draft
    def list(self, limit):
        return self.added[:limit]
    def exists_for_job(self, job_id):
        return job_id in self._drafted


class _Drafter:
    def __init__(self, raise_on=None):
        self.calls = []
        self._raise_on = raise_on
    async def draft(self, job_id):
        self.calls.append(job_id)
        if self._raise_on == job_id:
            raise RuntimeError("boom")
        return uuid.uuid4(), DraftStatus.DRAFTED, None


class _Notifier:
    def __init__(self): self.calls = []
    async def notify_pipeline_drafts(self, count): self.calls.append(count); return True


def _svc(entries, repo, drafter, top_n=3, notifier=None):
    return AutopilotPipelineService(
        latest_digest=lambda: _Digest(entries), drafter=drafter, repo=repo,
        top_n=top_n, notifier=notifier,
    )


@pytest.mark.asyncio
async def test_drafts_top_n_and_records():
    repo, drafter = _Repo(), _Drafter()
    result = await _svc([_Entry("a"), _Entry("b"), _Entry("c"), _Entry("d")], repo, drafter, top_n=2).run()
    assert result.created == 2
    assert drafter.calls == ["a", "b"]
    assert len(repo.added) == 2


@pytest.mark.asyncio
async def test_skips_already_drafted():
    repo, drafter = _Repo(drafted={"a"}), _Drafter()
    result = await _svc([_Entry("a"), _Entry("b")], repo, drafter).run()
    assert drafter.calls == ["b"]
    assert result.created == 1
    assert result.skipped == 1


@pytest.mark.asyncio
async def test_drafter_exception_records_failed_and_continues():
    repo, drafter = _Repo(), _Drafter(raise_on="a")
    result = await _svc([_Entry("a"), _Entry("b")], repo, drafter).run()
    assert result.created == 1  # only b succeeded
    statuses = {d.job_id: d.status for d in repo.added}
    assert statuses["a"] is DraftStatus.FAILED
    assert statuses["b"] is DraftStatus.DRAFTED


@pytest.mark.asyncio
async def test_notifies_only_when_created():
    notifier = _Notifier()
    await _svc([_Entry("a")], _Repo(), _Drafter(), notifier=notifier).run()
    assert notifier.calls == [1]
    notifier2 = _Notifier()
    await _svc([], _Repo(), _Drafter(), notifier=notifier2).run()
    assert notifier2.calls == []


@pytest.mark.asyncio
async def test_no_digest_returns_empty():
    svc = AutopilotPipelineService(latest_digest=lambda: None, drafter=_Drafter(),
                                   repo=_Repo(), top_n=3)
    result = await svc.run()
    assert result.created == 0 and result.drafts == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/autopilot/test_pipeline_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'AutopilotPipelineService'`.

- [ ] **Step 3: Implement**

`autopilot/domain/autopilot_pipeline_service.py`:

```python
from __future__ import annotations

import logging
from typing import Any, Callable

from hiresense.autopilot.domain.autopilot_draft import AutopilotDraft
from hiresense.autopilot.domain.draft_status import DraftStatus
from hiresense.autopilot.domain.pipeline_result import PipelineResult
from hiresense.autopilot.domain.ports import ApplicationDrafter, DraftRepository

logger = logging.getLogger(__name__)


class AutopilotPipelineService:
    """Reads the latest autohunt digest and drafts applications for its top-N new
    matches. Best-effort: per-job failures are recorded and skipped; run() never
    raises into the caller."""

    def __init__(
        self,
        *,
        latest_digest: Callable[[], Any],
        drafter: ApplicationDrafter,
        repo: DraftRepository,
        top_n: int,
        notifier: Any | None = None,
    ) -> None:
        self._latest_digest = latest_digest
        self._drafter = drafter
        self._repo = repo
        self._top_n = top_n
        self._notifier = notifier

    async def run(self) -> PipelineResult:
        digest = self._latest_digest()
        entries = list(getattr(digest, "entries", []) or [])[: self._top_n]
        created = 0
        skipped = 0
        drafts: list[AutopilotDraft] = []
        for entry in entries:
            job_id = entry.job_id
            if self._repo.exists_for_job(job_id):
                skipped += 1
                continue
            draft = await self._draft_one(entry)
            drafts.append(draft)
            if draft.status is not DraftStatus.FAILED:
                created += 1
        if created and self._notifier is not None:
            try:
                await self._notifier.notify_pipeline_drafts(created)
            except Exception:  # noqa: BLE001 - notification is best-effort
                logger.exception("autopilot: draft notification failed")
        return PipelineResult(created=created, skipped=skipped, drafts=drafts)

    async def _draft_one(self, entry: Any) -> AutopilotDraft:
        job_id = entry.job_id
        try:
            application_id, status, detail = await self._drafter.draft(job_id)
        except Exception as exc:  # noqa: BLE001 - one bad job must not abort the batch
            logger.exception("autopilot: drafting job %r failed", job_id)
            application_id, status, detail = None, DraftStatus.FAILED, str(exc)
        draft = AutopilotDraft(
            job_id=job_id,
            application_id=application_id,
            job_title=getattr(entry, "title", None),
            company=getattr(entry, "company", None),
            status=status,
            detail=detail,
        )
        return self._repo.add(draft)
```

Update `autopilot/domain/__init__.py` to add `from hiresense.autopilot.domain.autopilot_pipeline_service import AutopilotPipelineService` and `"AutopilotPipelineService"` in `__all__`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/autopilot/test_pipeline_service.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/autopilot/domain/autopilot_pipeline_service.py backend/src/hiresense/autopilot/domain/__init__.py backend/tests/unit/autopilot/test_pipeline_service.py
git commit -m "feat(autopilot): add AutopilotPipelineService (dedup, best-effort, notify)"
```

---

## Task 5: Infrastructure — ORM + repository

**Files:** Create `autopilot/infrastructure/autopilot_draft_orm.py`, `autopilot/infrastructure/draft_repository.py`, `autopilot/infrastructure/__init__.py`; Modify `backend/src/hiresense/infrastructure/registry.py`; Test `backend/tests/integration/test_autopilot_repository.py`

**Interfaces:**
- Produces: `AutopilotDraftOrm` (table `autopilot_drafts`); `DraftRepositoryImpl(session_factory)` implementing `DraftRepository`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_autopilot_repository.py
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.autopilot.domain import AutopilotDraft, DraftStatus
from hiresense.autopilot.infrastructure import AutopilotDraftOrm, DraftRepositoryImpl  # noqa: F401
from hiresense.infrastructure.database import Base


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_add_list_exists():
    repo = DraftRepositoryImpl(session_factory=_factory())
    repo.add(AutopilotDraft(job_id="j1", application_id=uuid.uuid4(), job_title="Dev",
                            company="Acme", status=DraftStatus.DRAFTED, detail=None))
    assert repo.exists_for_job("j1") is True
    assert repo.exists_for_job("nope") is False
    items = repo.list(limit=10)
    assert len(items) == 1
    assert items[0].status is DraftStatus.DRAFTED
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/integration/test_autopilot_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'AutopilotDraftOrm'`.

- [ ] **Step 3: Implement the ORM**

`autopilot/infrastructure/autopilot_draft_orm.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class AutopilotDraftOrm(Base):
    """One job processed by an autopilot pipeline run."""

    __tablename__ = "autopilot_drafts"

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    job_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    application_id: Mapped[uuid_mod.UUID | None] = mapped_column(Uuid, nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    company: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
```

- [ ] **Step 4: Implement the repository**

`autopilot/infrastructure/draft_repository.py`:

```python
from __future__ import annotations

from sqlalchemy import select

from hiresense.autopilot.domain import AutopilotDraft, DraftStatus
from hiresense.autopilot.infrastructure.autopilot_draft_orm import AutopilotDraftOrm
from hiresense.infrastructure import SqlRepository


def _to_domain(row: AutopilotDraftOrm) -> AutopilotDraft:
    return AutopilotDraft(
        id=row.id,
        job_id=row.job_id,
        application_id=row.application_id,
        job_title=row.job_title,
        company=row.company,
        status=DraftStatus(row.status),
        detail=row.detail,
        created_at=row.created_at,
    )


class DraftRepositoryImpl(SqlRepository):
    def add(self, draft: AutopilotDraft) -> AutopilotDraft:
        row = AutopilotDraftOrm(
            job_id=draft.job_id,
            application_id=draft.application_id,
            job_title=draft.job_title,
            company=draft.company,
            status=draft.status.value,
            detail=draft.detail,
        )
        return self._insert(row, _to_domain)

    def list(self, limit: int) -> list[AutopilotDraft]:
        stmt = select(AutopilotDraftOrm).order_by(AutopilotDraftOrm.created_at.desc()).limit(limit)
        return self._select_all(stmt, _to_domain)

    def exists_for_job(self, job_id: str) -> bool:
        with self._session_factory() as session:
            stmt = select(AutopilotDraftOrm.id).where(
                AutopilotDraftOrm.job_id == job_id
            ).limit(1)
            return session.scalars(stmt).first() is not None
```

`autopilot/infrastructure/__init__.py`:

```python
from hiresense.autopilot.infrastructure.autopilot_draft_orm import AutopilotDraftOrm
from hiresense.autopilot.infrastructure.draft_repository import DraftRepositoryImpl

__all__ = ["AutopilotDraftOrm", "DraftRepositoryImpl"]
```

Add to `backend/src/hiresense/infrastructure/registry.py` (alphabetical):

```python
from hiresense.autopilot.infrastructure import AutopilotDraftOrm  # noqa: F401
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/integration/test_autopilot_repository.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/autopilot/infrastructure backend/src/hiresense/infrastructure/registry.py backend/tests/integration/test_autopilot_repository.py
git commit -m "feat(autopilot): add draft ORM + repository"
```

---

## Task 6: ServicesApplicationDrafter adapter

**Files:** Create `autopilot/infrastructure/services_application_drafter.py`; Modify `autopilot/infrastructure/__init__.py`; Test `backend/tests/unit/autopilot/test_services_drafter.py`

**Interfaces:**
- Consumes: `ApplicationService.create_from_ingested(job_id) -> aggregate (with .id)`; `ArtifactService.generate_match(application_id, cv_language=) -> match (with .id)`; `ArtifactService.generate_optimization(application_id, cv_language=, match_id=)`; `ApplyService.generate_cover_letter(application_id, cv_language=, tone=)`.
- Produces: `ServicesApplicationDrafter(*, application_service, artifact_service, apply_service, cv_language)` implementing `ApplicationDrafter`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/autopilot/test_services_drafter.py
import uuid

import pytest

from hiresense.autopilot.domain import DraftStatus
from hiresense.autopilot.infrastructure import ServicesApplicationDrafter


class _Agg:
    def __init__(self): self.id = uuid.uuid4()


class _Match:
    def __init__(self): self.id = uuid.uuid4()


class _AppSvc:
    def __init__(self, agg=None, raise_exc=None):
        self._agg = agg or _Agg()
        self._raise = raise_exc
    async def create_from_ingested(self, job_id):
        if self._raise: raise self._raise
        return self._agg


class _ArtifactSvc:
    def __init__(self, opt_raise=None):
        self.calls = []
        self._opt_raise = opt_raise
    async def generate_match(self, application_id, cv_language=""):
        self.calls.append("match"); return _Match()
    async def generate_optimization(self, application_id, cv_language="", match_id=None):
        self.calls.append("optimize")
        if self._opt_raise: raise self._opt_raise


class _ApplySvc:
    def __init__(self): self.calls = []
    async def generate_cover_letter(self, application_id, cv_language="", tone=None):
        self.calls.append("cover")


def _drafter(app_svc, artifact_svc, apply_svc):
    return ServicesApplicationDrafter(
        application_service=app_svc, artifact_service=artifact_svc,
        apply_service=apply_svc, cv_language="en",
    )


@pytest.mark.asyncio
async def test_full_success_is_drafted():
    art = _ArtifactSvc(); apply = _ApplySvc()
    app_id, status, detail = await _drafter(_AppSvc(), art, apply).draft("j1")
    assert status is DraftStatus.DRAFTED
    assert app_id is not None
    assert art.calls == ["match", "optimize"]
    assert apply.calls == ["cover"]


@pytest.mark.asyncio
async def test_create_failure_is_failed():
    app_id, status, detail = await _drafter(
        _AppSvc(raise_exc=ValueError("Job not found")), _ArtifactSvc(), _ApplySvc()).draft("j1")
    assert status is DraftStatus.FAILED
    assert app_id is None
    assert "not found" in (detail or "").lower()


@pytest.mark.asyncio
async def test_artifact_failure_after_create_is_partial():
    app_id, status, detail = await _drafter(
        _AppSvc(), _ArtifactSvc(opt_raise=RuntimeError("LLM down")), _ApplySvc()).draft("j1")
    assert status is DraftStatus.PARTIAL
    assert app_id is not None  # application kept
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/autopilot/test_services_drafter.py -v`
Expected: FAIL — `ImportError: cannot import name 'ServicesApplicationDrafter'`.

- [ ] **Step 3: Implement**

`autopilot/infrastructure/services_application_drafter.py`:

```python
from __future__ import annotations

import logging
import uuid as uuid_mod
from typing import Any

from hiresense.autopilot.domain import DraftStatus

logger = logging.getLogger(__name__)


class ServicesApplicationDrafter:
    """Drives the existing applications services to create an application and
    generate its draft artifacts. Maps failures to PARTIAL/FAILED rather than
    raising: a create failure → FAILED (no application); a later artifact failure
    → PARTIAL (application + whatever generated is kept)."""

    def __init__(
        self,
        *,
        application_service: Any,
        artifact_service: Any,
        apply_service: Any,
        cv_language: str,
    ) -> None:
        self._applications = application_service
        self._artifacts = artifact_service
        self._apply = apply_service
        self._cv_language = cv_language

    async def draft(
        self, job_id: str
    ) -> tuple[uuid_mod.UUID | None, DraftStatus, str | None]:
        try:
            aggregate = await self._applications.create_from_ingested(job_id)
        except Exception as exc:  # noqa: BLE001 - no application could be created
            return None, DraftStatus.FAILED, str(exc)

        application_id = aggregate.id
        try:
            match = await self._artifacts.generate_match(
                application_id, cv_language=self._cv_language
            )
            await self._artifacts.generate_optimization(
                application_id, cv_language=self._cv_language, match_id=match.id
            )
            await self._apply.generate_cover_letter(
                application_id, cv_language=self._cv_language, tone=None
            )
        except Exception as exc:  # noqa: BLE001 - keep the application as a partial draft
            logger.exception("autopilot: artifact generation failed for job %r", job_id)
            return application_id, DraftStatus.PARTIAL, str(exc)

        return application_id, DraftStatus.DRAFTED, None
```

Update `autopilot/infrastructure/__init__.py` to add `from hiresense.autopilot.infrastructure.services_application_drafter import ServicesApplicationDrafter` and `"ServicesApplicationDrafter"` in `__all__`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/autopilot/test_services_drafter.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/autopilot/infrastructure/services_application_drafter.py backend/src/hiresense/autopilot/infrastructure/__init__.py backend/tests/unit/autopilot/test_services_drafter.py
git commit -m "feat(autopilot): add ServicesApplicationDrafter adapter"
```

---

## Task 7: NotificationService.notify_pipeline_drafts

**Files:** Create `backend/src/hiresense/notifications/domain/pipeline_drafts_email.py`; Modify `notifications/domain/notification_service.py`, `notifications/domain/__init__.py`; Test `backend/tests/unit/notifications/test_pipeline_drafts_notify.py`

**Interfaces:**
- Produces: `render_pipeline_drafts_email(count) -> tuple[str, str]`; `NotificationService.notify_pipeline_drafts(count: int) -> bool` (best-effort).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/notifications/test_pipeline_drafts_notify.py
import pytest

from hiresense.notifications.domain import NotificationService, render_pipeline_drafts_email


class _Sender:
    def __init__(self): self.sent = []
    def send(self, message): self.sent.append(message)


def test_render_includes_count():
    subject, body = render_pipeline_drafts_email(3)
    assert "3" in subject
    assert "3" in body


@pytest.mark.asyncio
async def test_notify_sends_when_enabled():
    sender = _Sender()
    assert await NotificationService(sender=sender, to_email="me@x.com").notify_pipeline_drafts(2) is True
    assert len(sender.sent) == 1


@pytest.mark.asyncio
async def test_notify_noop_when_disabled():
    sender = _Sender()
    assert await NotificationService(sender=sender, to_email="").notify_pipeline_drafts(2) is False
    assert sender.sent == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/notifications/test_pipeline_drafts_notify.py -v`
Expected: FAIL — `ImportError: cannot import name 'render_pipeline_drafts_email'`.

- [ ] **Step 3: Implement**

`notifications/domain/pipeline_drafts_email.py`:

```python
from __future__ import annotations


def render_pipeline_drafts_email(count: int) -> tuple[str, str]:
    """Render an autopilot-drafts alert into (subject, plain-text body)."""
    noun = "draft" if count == 1 else "drafts"
    subject = f"HireSense: {count} application {noun} ready to review"
    body = (
        f"Autopilot prepared {count} application {noun} (CV + cover letter) for your "
        "top new matches.\n\nOpen HireSense to review, edit, and apply."
    )
    return subject, body
```

In `notification_service.py`, add the import:

```python
from hiresense.notifications.domain.pipeline_drafts_email import render_pipeline_drafts_email
```

and the method (after `notify_inbox_signals`):

```python
    async def notify_pipeline_drafts(self, count: int) -> bool:
        subject, body = render_pipeline_drafts_email(count)
        return await self._safe_send(subject, body)
```

Update `notifications/domain/__init__.py` to export `render_pipeline_drafts_email`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/notifications/test_pipeline_drafts_notify.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/notifications/domain/pipeline_drafts_email.py backend/src/hiresense/notifications/domain/notification_service.py backend/src/hiresense/notifications/domain/__init__.py backend/tests/unit/notifications/test_pipeline_drafts_notify.py
git commit -m "feat(autopilot): add notify_pipeline_drafts to NotificationService"
```

---

## Task 8: API — provider, dependencies, routes

**Files:** Create `autopilot/api/provider.py`, `autopilot/api/dependencies.py`, `autopilot/api/routes.py`, `autopilot/api/__init__.py`; Test `backend/tests/integration/test_autopilot_endpoints.py`

**Interfaces:**
- Consumes: `AutopilotPipelineService`, `DraftRepository`, `require_auth`, `require_admin`.
- Produces: `AutopilotProvider(service, repo)` with `get_service()`/`get_repo()`; `get_autopilot_provider`; router with `GET /autopilot/drafts`, `POST /autopilot/run` (admin).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_autopilot_endpoints.py
import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.autopilot.api import router as autopilot_router
from hiresense.autopilot.api.dependencies import get_autopilot_provider
from hiresense.autopilot.api.provider import AutopilotProvider
from hiresense.autopilot.domain import AutopilotPipelineService, DraftStatus
from hiresense.identity.api.dependencies import require_admin, require_auth


class _Entry:
    def __init__(self, job_id): self.job_id = job_id; self.title = "Dev"; self.company = "Acme"


class _Repo:
    def __init__(self): self.added = []
    def add(self, d): d.id = uuid.uuid4(); self.added.append(d); return d
    def list(self, limit): return self.added[:limit]
    def exists_for_job(self, job_id): return False


class _Drafter:
    async def draft(self, job_id): return uuid.uuid4(), DraftStatus.DRAFTED, None


def _build_app():
    repo = _Repo()
    service = AutopilotPipelineService(
        latest_digest=lambda: type("D", (), {"entries": [_Entry("j1")]})(),
        drafter=_Drafter(), repo=repo, top_n=3,
    )
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "u"
    app.dependency_overrides[require_admin] = lambda: {"role": "admin"}
    app.dependency_overrides[get_autopilot_provider] = lambda: AutopilotProvider(service=service, repo=repo)
    app.include_router(autopilot_router)
    return app, repo


@pytest.mark.asyncio
async def test_run_then_list():
    app, repo = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        run = await client.post("/autopilot/run")
        assert run.status_code == 200
        assert run.json()["created"] == 1
        lst = await client.get("/autopilot/drafts")
        assert lst.status_code == 200
        assert len(lst.json()) == 1
        assert lst.json()[0]["status"] == "drafted"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/integration/test_autopilot_endpoints.py -v`
Expected: FAIL — `ModuleNotFoundError: ...autopilot.api`.

- [ ] **Step 3: Implement provider + dependencies**

`autopilot/api/provider.py`:

```python
from __future__ import annotations

from hiresense.autopilot.domain import AutopilotPipelineService
from hiresense.autopilot.domain.ports import DraftRepository


class AutopilotProvider:
    def __init__(self, *, service: AutopilotPipelineService, repo: DraftRepository) -> None:
        self._service = service
        self._repo = repo

    def get_service(self) -> AutopilotPipelineService:
        return self._service

    def get_repo(self) -> DraftRepository:
        return self._repo
```

`autopilot/api/dependencies.py`:

```python
from __future__ import annotations

from fastapi import Request

from hiresense.autopilot.api.provider import AutopilotProvider


def get_autopilot_provider(request: Request) -> AutopilotProvider:
    return request.app.state.autopilot
```

- [ ] **Step 4: Implement routes + `__init__`**

`autopilot/api/routes.py`:

```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from hiresense.autopilot.api.dependencies import get_autopilot_provider
from hiresense.autopilot.api.provider import AutopilotProvider
from hiresense.autopilot.domain import AutopilotDraft, PipelineResult
from hiresense.identity.api.dependencies import require_admin, require_auth

router = APIRouter(prefix="/autopilot", tags=["autopilot"], dependencies=[Depends(require_auth)])


@router.get("/drafts", response_model=list[AutopilotDraft])
def list_drafts(
    provider: Annotated[AutopilotProvider, Depends(get_autopilot_provider)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[AutopilotDraft]:
    return provider.get_repo().list(limit)


@router.post("/run", response_model=PipelineResult)
async def run_now(
    provider: Annotated[AutopilotProvider, Depends(get_autopilot_provider)],
    _admin: Annotated[dict, Depends(require_admin)],
) -> PipelineResult:
    return await provider.get_service().run()
```

`autopilot/api/__init__.py`:

```python
from hiresense.autopilot.api.routes import router

__all__ = ["router"]
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/integration/test_autopilot_endpoints.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/autopilot/api backend/tests/integration/test_autopilot_endpoints.py
git commit -m "feat(autopilot): add drafts list + run API"
```

---

## Task 9: Bootstrap + scheduler job + main wiring

**Files:** Create `backend/src/hiresense/bootstrap/autopilot.py`; Modify `backend/src/hiresense/bootstrap/scheduler.py`, `backend/src/hiresense/bootstrap/__init__.py`, `backend/src/hiresense/main.py`; Test `backend/tests/unit/scheduler/test_build_scheduler_autopilot.py`, `backend/tests/integration/test_autopilot_app_wiring.py`

**Interfaces:**
- Consumes: `ServicesApplicationDrafter`, `DraftRepositoryImpl`, `AutopilotPipelineService`, `AutopilotProvider`; the applications provider (`get_application_service`/`get_artifact_service`/`get_apply_service`); `autohunt.service.latest`; `notifications.service`.
- Produces: `build_autopilot(infra, *, applications_provider, latest_digest, notification_service) -> AutopilotBuild | None` (None when disabled); `build_scheduler(..., autopilot_pipeline_service=None)` adds an `autopilot_pipeline` job when provided.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/scheduler/test_build_scheduler_autopilot.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.bootstrap.scheduler import build_scheduler
from hiresense.infrastructure.database import Base
from hiresense.scheduler.infrastructure import JobRunOrm, JobToggleOrm  # noqa: F401


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


class _Settings:
    ingestion_schedule = "0 */6 * * *"
    job_revalidation_interval_hours = 24
    autohunt_schedule = "0 9 * * *"
    outreach_followup_schedule = "0 10 * * *"
    autopilot_pipeline_schedule = "0 10 * * *"
    scheduler_run_retention_days = 30


class _Noop:
    async def run(self): return []
    async def sweep(self): return []


class _Auto:
    async def run(self): return type("D", (), {"job_count": 0})()


class _Out:
    def due_followups(self): return []


class _Pipeline:
    async def run(self): return type("R", (), {"created": 5})()


def _build(pipeline):
    return build_scheduler(
        settings=_Settings(), sync_session_factory=_factory(),
        ingestion_orchestrator=_Noop(), revalidation_service=_Noop(),
        autohunt_service=_Auto(), outreach_service=_Out(),
        autopilot_pipeline_service=pipeline,
    )


@pytest.mark.asyncio
async def test_autopilot_job_present_when_injected():
    build = _build(_Pipeline())
    names = {v.name for v in build.provider.list_jobs()}
    assert "autopilot_pipeline" in names
    run = await build.provider.run_now("autopilot_pipeline")
    assert run.items_affected == 5


def test_autopilot_job_absent_by_default():
    build = _build(None)
    names = {v.name for v in build.provider.list_jobs()}
    assert "autopilot_pipeline" not in names
```

```python
# backend/tests/integration/test_autopilot_app_wiring.py
import pytest
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.main import create_app


@pytest.mark.asyncio
async def test_autopilot_drafts_route_mounted():
    app = create_app()
    app.dependency_overrides[require_auth] = lambda: "u"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/autopilot/drafts")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_build_scheduler_autopilot.py tests/integration/test_autopilot_app_wiring.py -v`
Expected: FAIL — `build_scheduler() got an unexpected keyword argument 'autopilot_pipeline_service'` / 404 on `/autopilot/drafts`.

- [ ] **Step 3: Implement build_autopilot**

`backend/src/hiresense/bootstrap/autopilot.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from hiresense.autopilot.api.provider import AutopilotProvider
from hiresense.autopilot.domain import AutopilotPipelineService
from hiresense.autopilot.infrastructure import DraftRepositoryImpl, ServicesApplicationDrafter
from hiresense.bootstrap.shared_infra import SharedInfra


@dataclass(frozen=True)
class AutopilotBuild:
    provider: AutopilotProvider
    service: AutopilotPipelineService


def build_autopilot(
    infra: SharedInfra,
    *,
    applications_provider: Any,
    latest_digest: Callable[[], Any],
    notification_service: Any = None,
) -> AutopilotBuild | None:
    s = infra.settings
    if not s.autopilot_pipeline_enabled:
        return None
    repo = DraftRepositoryImpl(session_factory=infra.sync_session_factory)
    drafter = ServicesApplicationDrafter(
        application_service=applications_provider.get_application_service(),
        artifact_service=applications_provider.get_artifact_service(),
        apply_service=applications_provider.get_apply_service(),
        cv_language=s.default_language,
    )
    service = AutopilotPipelineService(
        latest_digest=latest_digest,
        drafter=drafter,
        repo=repo,
        top_n=s.autopilot_pipeline_top_n,
        notifier=notification_service,
    )
    return AutopilotBuild(provider=AutopilotProvider(service=service, repo=repo), service=service)
```

Add to `bootstrap/__init__.py` (alphabetical) + `__all__`:

```python
from hiresense.bootstrap.autopilot import AutopilotBuild, build_autopilot
```

- [ ] **Step 4: Add the autopilot_pipeline job to build_scheduler**

In `bootstrap/scheduler.py`, add `autopilot_pipeline_service: Any = None` to the signature. After the inbox job append block (added in Phase 3), add:

```python
    if autopilot_pipeline_service is not None:
        definitions.append(
            JobDefinition(
                name="autopilot_pipeline",
                run=autopilot_pipeline_service.run,
                cron=settings.autopilot_pipeline_schedule,
                interval_hours=None,
                count_items=lambda r: getattr(r, "created", None),
            )
        )
```

(`AutopilotPipelineService.run()` returns a `PipelineResult` with `.created`.)

- [ ] **Step 5: Wire main.py**

Add the router import:

```python
from hiresense.autopilot.api import router as autopilot_router
```

Add `build_autopilot` to the `from hiresense.bootstrap import (...)` block.

After the inbox block and BEFORE the scheduler block, add:

```python
    # --- Autopilot pipeline (Phase 4: auto-draft applications for top matches) ---
    autopilot = build_autopilot(
        infra,
        applications_provider=app.state.applications_provider,
        latest_digest=autohunt.service.latest,
        notification_service=notifications.service,
    )
    if autopilot is not None:
        app.state.autopilot = autopilot.provider
        app.include_router(autopilot_router)
```

> The autopilot router is mounted ONLY when enabled (build_autopilot returns a build).
> When disabled, `/autopilot/*` is absent — the integration wiring test enables it
> (see note below) OR asserts the disabled behavior. Since `autopilot_pipeline_enabled`
> defaults False, `test_autopilot_drafts_route_mounted` must set it true: in that test,
> monkeypatch the env BEFORE `create_app()` — `monkeypatch.setenv("AUTOPILOT_PIPELINE_ENABLED", "true")`
> and also set the SQLite DB env the other wiring tests use (mirror `test_inbox_app_wiring.py`/`test_app.py`).
> Update the test accordingly when you hit the 404.

Then add `autopilot_pipeline_service=autopilot.service if autopilot is not None else None` to the `build_scheduler(...)` call.

- [ ] **Step 6: Adjust the wiring test to enable autopilot, then run**

Update `test_autopilot_app_wiring.py` to enable the feature and use the SQLite test env, mirroring `backend/tests/integration/test_inbox_app_wiring.py` (read it first for the exact `monkeypatch`/lifespan pattern). The test must `monkeypatch.setenv("AUTOPILOT_PIPELINE_ENABLED", "true")` before `create_app()`.

Run: `cd backend && uv run python -m pytest tests/unit/scheduler tests/integration/test_autopilot_app_wiring.py -v`
Expected: PASS — autopilot tests green AND existing scheduler tests still green.

- [ ] **Step 7: Run full suite + lint**

Run: `cd backend && uv run python -m pytest -q && uv run ruff check .`
Expected: green (the only pre-existing ruff issue is the known `profile/test_routes.py` E402); no NEW issues.

- [ ] **Step 8: Commit**

```bash
git add backend/src/hiresense/bootstrap/autopilot.py backend/src/hiresense/bootstrap/scheduler.py backend/src/hiresense/bootstrap/__init__.py backend/src/hiresense/main.py backend/tests/unit/scheduler/test_build_scheduler_autopilot.py backend/tests/integration/test_autopilot_app_wiring.py
git commit -m "feat(autopilot): build_autopilot + scheduler job + main wiring"
```

---

## Task 10: Alembic migration

**Files:** Create `backend/alembic/versions/035_add_autopilot_drafts.py`

- [ ] **Step 1: Hand-write the migration**

Mirror `034_add_inbox_detected_signals.py` style. `revision="035"`, `down_revision="034"`:

```python
"""add autopilot_drafts

Revision ID: 035
Revises: 034
Create Date: 2026-06-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "autopilot_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=True),
        sa.Column("job_title", sa.String(length=512), nullable=True),
        sa.Column("company", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_autopilot_drafts_job_id", "autopilot_drafts", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_autopilot_drafts_job_id", table_name="autopilot_drafts")
    op.drop_table("autopilot_drafts")
```

- [ ] **Step 2: Verify history is linear (no DB)**

Run: `cd backend && uv run python -m alembic history`
Expected: `035` after `034`; no multiple-heads error.

- [ ] **Step 3: Confirm metadata builds**

Run: `cd backend && uv run python -m pytest tests/integration/test_autopilot_repository.py -v`
Expected: PASS.

> Post-merge: run `uv run python -m alembic upgrade head` on the dev DB.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/035_add_autopilot_drafts.py
git commit -m "feat(autopilot): migration for autopilot_drafts"
```

---

## Task 11: Frontend — Autopilot drafts review surface

**Files:** Create `frontend/src/app/core/models/autopilot.model.ts`, `frontend/src/app/core/services/autopilot.service.ts` (+spec), `frontend/src/app/pages/autopilot/drafts/drafts.component.{ts,html,scss,spec.ts}`; Modify `frontend/src/app/app.routes.ts`, `frontend/src/app/core/nav/hubs.const.ts`

**Interfaces:**
- Consumes: `GET /api/autopilot/drafts?limit=` → `AutopilotDraft[]` (snake_case wire format — no camelCasing interceptor; confirm against `core/interceptors/`).

- [ ] **Step 1: Write the failing service spec**

```typescript
// frontend/src/app/core/services/autopilot.service.spec.ts
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { AutopilotService } from './autopilot.service';

describe('AutopilotService', () => {
  let service: AutopilotService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [AutopilotService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AutopilotService);
    httpMock = TestBed.inject(HttpTestingController);
  });
  afterEach(() => httpMock.verify());

  it('lists drafts', () => {
    let result: unknown;
    service.listDrafts().subscribe((r) => (result = r));
    const req = httpMock.expectOne('/api/autopilot/drafts?limit=20');
    expect(req.request.method).toBe('GET');
    req.flush([{ id: '1', job_id: 'j1', application_id: 'a1', job_title: 'Dev',
      company: 'Acme', status: 'drafted', detail: null }]);
    expect((result as unknown[]).length).toBe(1);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npm test -- --include "**/autopilot.service.spec.ts"`
Expected: FAIL — cannot find `./autopilot.service`.

- [ ] **Step 3: Implement model + service**

`frontend/src/app/core/models/autopilot.model.ts`:

```typescript
export interface AutopilotDraft {
  id: string;
  job_id: string;
  application_id: string | null;
  job_title: string | null;
  company: string | null;
  status: 'drafted' | 'partial' | 'failed';
  detail: string | null;
}
```

(Snake_case to match the wire format — no camelCasing interceptor; confirm against `core/interceptors/` as in prior phases.)

`frontend/src/app/core/services/autopilot.service.ts`:

```typescript
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { AutopilotDraft } from '../models/autopilot.model';

@Injectable({ providedIn: 'root' })
export class AutopilotService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/autopilot';

  listDrafts(limit = 20): Observable<AutopilotDraft[]> {
    return this.http.get<AutopilotDraft[]>(`${this.base}/drafts?limit=${limit}`);
  }
}
```

- [ ] **Step 4: Run to verify the service spec passes**

Run: `cd frontend && npm test -- --include "**/autopilot.service.spec.ts"`
Expected: PASS.

- [ ] **Step 5: Write the failing component spec**

```typescript
// frontend/src/app/pages/autopilot/drafts/drafts.component.spec.ts
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { DraftsComponent } from './drafts.component';

describe('DraftsComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [DraftsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });
  afterEach(() => httpMock.verify());

  it('loads drafts on init', () => {
    const fixture = TestBed.createComponent(DraftsComponent);
    fixture.detectChanges();
    const req = httpMock.expectOne('/api/autopilot/drafts?limit=20');
    req.flush([{ id: '1', job_id: 'j1', application_id: 'a1', job_title: 'Dev',
      company: 'Acme', status: 'drafted', detail: null }]);
    expect(fixture.componentInstance.drafts().length).toBe(1);
  });
});
```

- [ ] **Step 6: Run to verify it fails**

Run: `cd frontend && npm test -- --include "**/drafts.component.spec.ts"`
Expected: FAIL — cannot find `./drafts.component`.

- [ ] **Step 7: Implement the component**

`frontend/src/app/pages/autopilot/drafts/drafts.component.ts`:

```typescript
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AutopilotService } from '../../../core/services/autopilot.service';
import { AutopilotDraft } from '../../../core/models/autopilot.model';

@Component({
  selector: 'app-autopilot-drafts',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './drafts.component.html',
  styleUrl: './drafts.component.scss',
})
export class DraftsComponent implements OnInit {
  private readonly service = inject(AutopilotService);
  readonly drafts = signal<AutopilotDraft[]>([]);

  ngOnInit(): void {
    this.service.listDrafts().subscribe((d) => this.drafts.set(d));
  }
}
```

`frontend/src/app/pages/autopilot/drafts/drafts.component.html`:

```html
<section class="drafts">
  <h1>Autopilot drafts</h1>
  @if (drafts().length === 0) {
    <p>No drafts yet.</p>
  }
  @for (d of drafts(); track d.id) {
    <div class="draft">
      <div class="meta">
        <strong>{{ d.job_title || d.job_id }}</strong>
        <small>{{ d.company }}</small>
      </div>
      <span class="status status--{{ d.status }}">{{ d.status }}</span>
      @if (d.application_id) {
        <a [routerLink]="['/dashboard/applications', d.application_id]">Review</a>
      }
    </div>
  }
</section>
```

`frontend/src/app/pages/autopilot/drafts/drafts.component.scss`:

```scss
.drafts {
  padding: 1rem;

  .draft {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border, #e2e2e2);
  }

  .status {
    text-transform: capitalize;
    font-weight: 600;
    &--drafted { color: var(--success, #2e7d32); }
    &--partial { color: var(--warn, #ef6c00); }
    &--failed { color: var(--danger, #c62828); }
  }
}
```

> Verify the application detail route path: the `routerLink` above assumes
> `/dashboard/applications/:id`. Read `app.routes.ts` for the actual applications
> detail route and match its path; adjust if it differs.

- [ ] **Step 8: Register route + nav**

In `app.routes.ts`, add a lazy route (mirror an existing authed dashboard child route — read one first for the guard):

```typescript
  {
    path: 'autopilot/drafts',
    loadComponent: () =>
      import('./pages/autopilot/drafts/drafts.component').then((m) => m.DraftsComponent),
  },
```

In `core/nav/hubs.const.ts`, add a nav entry mirroring an existing one (match the `/dashboard/...` prefix the others use):

```typescript
      { label: 'Autopilot drafts', path: '/dashboard/autopilot/drafts' },
```

- [ ] **Step 9: Run component spec + lint + build**

Run: `cd frontend && npm test -- --include "**/drafts.component.spec.ts"`
Expected: PASS.

Run: `cd frontend && npx ng lint && npm run build`
Expected: lint clean; build succeeds.

- [ ] **Step 10: Verify clean staging and commit**

Confirm via `git status` that ONLY the new autopilot files + `app.routes.ts` + `hubs.const.ts` are staged (NOT pre-existing modified frontend files).

```bash
git add frontend/src/app/core/models/autopilot.model.ts frontend/src/app/core/services/autopilot.service.ts frontend/src/app/core/services/autopilot.service.spec.ts frontend/src/app/pages/autopilot frontend/src/app/app.routes.ts frontend/src/app/core/nav/hubs.const.ts
git commit -m "feat(autopilot): drafts review page"
```

---

## Final verification

- [ ] Backend: `cd backend && uv run python -m pytest -q && uv run ruff check .` — green (only the pre-existing `profile/test_routes.py` E402).
- [ ] Frontend: `cd frontend && npx ng lint && npm test` — green.
- [ ] Manual smoke (optional, needs LLM + a digest): set `AUTOPILOT_PIPELINE_ENABLED=true`, ensure a recent autohunt digest exists, `POST /autopilot/run` → applications created in `saved` status with match/optimization/cover-letter artifacts; `GET /autopilot/drafts` lists them; re-running skips already-drafted jobs.

## Spec coverage check (self-review)

- Config (enabled/top_n/schedule) → Task 1. Domain models/enum → Task 2. Ports → Task 3. Pipeline service (dedup, best-effort, notify, top_n, no-digest) → Task 4. ORM/repo + registry → Task 5. ServicesApplicationDrafter (drafted/partial/failed mapping + call sequence) → Task 6. notify_pipeline_drafts → Task 7. drafts list + run(admin) API → Task 8. build_autopilot (None when disabled) + scheduler 6th job (absent by default) + main wiring → Task 9. Migration 035 → Task 10. Frontend review surface → Task 11. Detect-and-propose / nothing sent → Tasks 4/6 (only create + generate, status stays saved). Phases 1–3 byte-identical when disabled → Task 9 defaults.
