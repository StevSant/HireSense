# Scheduler Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make HireSense self-drive its recurring pipeline steps (ingestion fetch, revalidation sweep, autohunt digest, outreach follow-up computation) on a cadence, in-process, behind a master switch, with observable run history.

**Architecture:** A new hexagonal `scheduler/` bounded-context module. A pure-domain `JobRunner` wraps each named job (toggle check → run → record outcome → swallow errors). An infrastructure `ApschedulerRunner` (APScheduler `AsyncIOScheduler`) triggers `JobRunner.run(name)` on the cadence read from existing config cron strings. Run history and per-job enable toggles persist to two new tables. The runner starts in the FastAPI lifespan only when `scheduler_enabled` is true. A minimal admin page surfaces status + manual run.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy (sync repos via `SqlRepository`), APScheduler 3.x (already a dependency), Alembic, Angular 21 (standalone + signals), Vitest.

**Spec:** [`docs/superpowers/specs/2026-06-21-scheduler-foundation-design.md`](../specs/2026-06-21-scheduler-foundation-design.md)

**Conventions to honor (from CLAUDE.md + global rules):**
- One class/enum/constant per file; package `__init__.py` re-exports public symbols; import from the contextual package.
- `domain/` imports no framework packages and nothing from `infrastructure/`.
- Every ORM class must be imported in `infrastructure/registry.py`.
- Tests: `uv run python -m pytest` (never bare `uv run pytest`). Integration tests build the app over in-memory SQLite with `StaticPool` and override `require_auth`/`require_admin`.
- Lint: `uv run ruff check .`. Do NOT run `ruff format .` repo-wide (repo isn't format-clean; CI only runs `ruff check`).
- No hardcoded values — every tunable goes through `config.py` + `.env.example`.

---

## File Structure

**Backend — new module `backend/src/hiresense/scheduler/`:**
- `domain/job_status.py` — `JobStatus` enum.
- `domain/job_run.py` — `JobRun` Pydantic model.
- `domain/scheduled_job_view.py` — `ScheduledJobView` read model.
- `domain/job_definition.py` — `JobDefinition` dataclass (name, run callable, cron, interval_hours, count_items, default_enabled).
- `domain/job_runner.py` — `JobRunner` service (the wrapper).
- `domain/ports/job_run_repository.py` — `JobRunRepository` Protocol.
- `domain/ports/job_toggle_repository.py` — `JobToggleRepository` Protocol.
- `domain/__init__.py`, `domain/ports/__init__.py` — re-exports.
- `infrastructure/job_run_orm.py` — `JobRunOrm`.
- `infrastructure/job_toggle_orm.py` — `JobToggleOrm`.
- `infrastructure/job_run_repository.py` — `JobRunRepositoryImpl`.
- `infrastructure/job_toggle_repository.py` — `JobToggleRepositoryImpl`.
- `infrastructure/apscheduler_runner.py` — `ApschedulerRunner`.
- `infrastructure/__init__.py` — re-exports.
- `api/provider.py` — `SchedulerProvider`.
- `api/dependencies.py` — `get_scheduler_provider`.
- `api/routes.py` — router.
- `api/__init__.py` — re-exports `router`.
- `__init__.py`.
- `bootstrap/scheduler.py` — `build_scheduler` + `SchedulerBuild`.

**Backend — modified:**
- `config.py` — add `scheduler_enabled`, `scheduler_run_retention_days`.
- `infrastructure/registry.py` — import the two new ORM classes.
- `ingestion/domain/__init__.py` — re-export `IngestionCooldownError`.
- `bootstrap/ingestion.py` — expose `revalidation_service` on `IngestionBuild`.
- `bootstrap/__init__.py` — export `build_scheduler`, `SchedulerBuild`.
- `main.py` — build scheduler; start/stop in lifespan.
- `.env.example`, `docker-compose.yml`.
- New Alembic migration under `backend/alembic/versions/` (or the project's versions dir).

**Frontend — new/modified:**
- `core/services/scheduler.service.ts`, `core/models/scheduler.model.ts`.
- `pages/admin/scheduler/scheduler.component.ts` (+ `.html`, `.scss`, `.spec.ts`).
- admin routes file — add the lazy route.

---

## Task 1: Config + env + compose

**Files:**
- Modify: `backend/src/hiresense/config.py`
- Modify: `backend/.env.example`
- Modify: `docker-compose.yml`
- Test: `backend/tests/unit/test_settings_scheduler.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_settings_scheduler.py
from hiresense.config import Settings


def test_scheduler_settings_have_safe_defaults():
    s = Settings()
    # Master switch defaults OFF so `uv run app --reload` never double-fires.
    assert s.scheduler_enabled is False
    assert s.scheduler_run_retention_days == 30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/test_settings_scheduler.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'scheduler_enabled'`.

- [ ] **Step 3: Add the settings**

In `config.py`, near the existing scheduling-related settings (after `outreach_followup_schedule`), add:

```python
    # --- Scheduler (in-app cadence driver; Autopilot Phase 1) ---
    # Master switch. MUST be true on exactly one process (the app self-drives
    # ingestion/revalidation/autohunt/outreach-followups on the cron strings
    # already defined above). Default OFF so `uv run app --reload` in dev does
    # not double-fire; docker-compose sets it true for the `app` service.
    scheduler_enabled: bool = False
    # Prune scheduler_job_runs rows older than this (inline on each insert).
    scheduler_run_retention_days: int = 30
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/test_settings_scheduler.py -v`
Expected: PASS.

- [ ] **Step 5: Update `.env.example` and `docker-compose.yml`**

Append to `backend/.env.example`:

```dotenv
# --- Scheduler (Autopilot Phase 1) ---
# Self-drive the recurring pipeline in-process. Set true on EXACTLY ONE process.
SCHEDULER_ENABLED=false
# Days of scheduler run-history to retain (older rows pruned inline).
SCHEDULER_RUN_RETENTION_DAYS=30
```

In `docker-compose.yml`, under `app:` → `environment:` (alongside `LOG_FORMAT: json`), add:

```yaml
      # Self-drive the recurring pipeline in the containerized deployment.
      SCHEDULER_ENABLED: "true"
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/config.py backend/.env.example docker-compose.yml backend/tests/unit/test_settings_scheduler.py
git commit -m "feat(scheduler): add scheduler_enabled + retention config"
```

---

## Task 2: Domain — JobStatus + JobRun

**Files:**
- Create: `backend/src/hiresense/scheduler/__init__.py` (empty)
- Create: `backend/src/hiresense/scheduler/domain/job_status.py`
- Create: `backend/src/hiresense/scheduler/domain/job_run.py`
- Create: `backend/src/hiresense/scheduler/domain/__init__.py`
- Test: `backend/tests/unit/scheduler/test_job_run.py`

- [ ] **Step 1: Write the failing test**

This fails first because `hiresense.scheduler` does not exist yet.

```python
# backend/tests/unit/scheduler/test_job_run.py
from datetime import datetime, timezone

from hiresense.scheduler.domain import JobRun, JobStatus


def test_job_run_roundtrips_status_and_duration():
    started = datetime(2026, 6, 21, 9, 0, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 6, 21, 9, 0, 2, tzinfo=timezone.utc)
    run = JobRun(
        job_name="autohunt_digest",
        started_at=started,
        finished_at=finished,
        status=JobStatus.SUCCESS,
        detail=None,
        items_affected=5,
        duration_seconds=2.0,
    )
    assert run.status is JobStatus.SUCCESS
    assert run.items_affected == 5
    assert run.duration_seconds == 2.0
```

Also create `backend/tests/unit/scheduler/__init__.py` (empty).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_job_run.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hiresense.scheduler'`.

- [ ] **Step 3: Implement the models**

`backend/src/hiresense/scheduler/__init__.py`: empty file.

`backend/src/hiresense/scheduler/domain/job_status.py`:

```python
from __future__ import annotations

from enum import Enum


class JobStatus(str, Enum):
    """Outcome of one scheduled-job invocation."""

    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
```

`backend/src/hiresense/scheduler/domain/job_run.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from hiresense.scheduler.domain.job_status import JobStatus


class JobRun(BaseModel):
    """One scheduled-job invocation's recorded outcome."""

    job_name: str
    started_at: datetime
    finished_at: datetime
    status: JobStatus
    detail: str | None = None
    items_affected: int | None = None
    duration_seconds: float | None = None
```

`backend/src/hiresense/scheduler/domain/__init__.py`:

```python
from hiresense.scheduler.domain.job_run import JobRun
from hiresense.scheduler.domain.job_status import JobStatus

__all__ = ["JobRun", "JobStatus"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_job_run.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/scheduler/__init__.py backend/src/hiresense/scheduler/domain backend/tests/unit/scheduler
git commit -m "feat(scheduler): add JobStatus + JobRun domain models"
```

---

## Task 3: Domain — ScheduledJobView + JobDefinition

**Files:**
- Create: `backend/src/hiresense/scheduler/domain/scheduled_job_view.py`
- Create: `backend/src/hiresense/scheduler/domain/job_definition.py`
- Modify: `backend/src/hiresense/scheduler/domain/__init__.py`
- Test: `backend/tests/unit/scheduler/test_job_definition.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/scheduler/test_job_definition.py
import asyncio

from hiresense.scheduler.domain import JobDefinition, ScheduledJobView


def test_job_definition_holds_trigger_and_counter():
    async def run():
        return [1, 2, 3]

    d = JobDefinition(
        name="ingestion_fetch",
        run=run,
        cron="0 */6 * * *",
        interval_hours=None,
        count_items=len,
        default_enabled=True,
    )
    assert d.name == "ingestion_fetch"
    assert d.count_items(asyncio.run(d.run())) == 3
    assert d.cron == "0 */6 * * *"


def test_scheduled_job_view_allows_null_run_and_next():
    view = ScheduledJobView(
        name="autohunt_digest", cron="0 9 * * *", enabled=True, last_run=None, next_run_at=None
    )
    assert view.last_run is None
    assert view.next_run_at is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_job_definition.py -v`
Expected: FAIL — `ImportError: cannot import name 'JobDefinition'`.

- [ ] **Step 3: Implement**

`backend/src/hiresense/scheduler/domain/scheduled_job_view.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from hiresense.scheduler.domain.job_run import JobRun


class ScheduledJobView(BaseModel):
    """Read model for the scheduler status API: a job plus its latest outcome
    and next fire time."""

    name: str
    cron: str
    enabled: bool
    last_run: JobRun | None = None
    next_run_at: datetime | None = None
```

`backend/src/hiresense/scheduler/domain/job_definition.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class JobDefinition:
    """Wiring record for one scheduled job: how to run it, when, and how to
    count what it affected. Exactly one of ``cron``/``interval_hours`` is set.

    ``cron`` is also used as the human-facing cadence label in the status API;
    for interval jobs a synthetic label is supplied (e.g. ``"every 24h"``).
    """

    name: str
    run: Callable[[], Awaitable[Any]]
    cron: str | None
    interval_hours: int | None
    count_items: Callable[[Any], int | None]
    default_enabled: bool = True

    @property
    def cadence_label(self) -> str:
        return self.cron if self.cron is not None else f"every {self.interval_hours}h"
```

Update `backend/src/hiresense/scheduler/domain/__init__.py`:

```python
from hiresense.scheduler.domain.job_definition import JobDefinition
from hiresense.scheduler.domain.job_run import JobRun
from hiresense.scheduler.domain.job_status import JobStatus
from hiresense.scheduler.domain.scheduled_job_view import ScheduledJobView

__all__ = ["JobDefinition", "JobRun", "JobStatus", "ScheduledJobView"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_job_definition.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/scheduler/domain backend/tests/unit/scheduler/test_job_definition.py
git commit -m "feat(scheduler): add ScheduledJobView + JobDefinition"
```

---

## Task 4: Domain ports — repository Protocols

**Files:**
- Create: `backend/src/hiresense/scheduler/domain/ports/job_run_repository.py`
- Create: `backend/src/hiresense/scheduler/domain/ports/job_toggle_repository.py`
- Create: `backend/src/hiresense/scheduler/domain/ports/__init__.py`
- Test: `backend/tests/unit/scheduler/test_ports_importable.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/scheduler/test_ports_importable.py
from hiresense.scheduler.domain.ports import JobRunRepository, JobToggleRepository


def test_ports_are_runtime_checkable_protocols():
    # Protocols expose their methods; a duck-typed object satisfies isinstance.
    class _Runs:
        def record(self, run): ...
        def recent(self, job_name, limit): ...
        def latest(self, job_name): ...

    class _Toggles:
        def is_enabled(self, job_name, default): ...
        def set_enabled(self, job_name, enabled): ...
        def all_states(self): ...

    assert isinstance(_Runs(), JobRunRepository)
    assert isinstance(_Toggles(), JobToggleRepository)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_ports_importable.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hiresense.scheduler.domain.ports'`.

- [ ] **Step 3: Implement the Protocols**

`backend/src/hiresense/scheduler/domain/ports/job_run_repository.py`:

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from hiresense.scheduler.domain.job_run import JobRun


@runtime_checkable
class JobRunRepository(Protocol):
    """Persistence port for scheduler run history."""

    def record(self, run: JobRun) -> JobRun: ...

    def recent(self, job_name: str, limit: int) -> list[JobRun]: ...

    def latest(self, job_name: str) -> JobRun | None: ...
```

`backend/src/hiresense/scheduler/domain/ports/job_toggle_repository.py`:

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class JobToggleRepository(Protocol):
    """Persistence port for per-job enable/disable state."""

    def is_enabled(self, job_name: str, default: bool) -> bool: ...

    def set_enabled(self, job_name: str, enabled: bool) -> None: ...

    def all_states(self) -> dict[str, bool]: ...
```

`backend/src/hiresense/scheduler/domain/ports/__init__.py`:

```python
from hiresense.scheduler.domain.ports.job_run_repository import JobRunRepository
from hiresense.scheduler.domain.ports.job_toggle_repository import JobToggleRepository

__all__ = ["JobRunRepository", "JobToggleRepository"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_ports_importable.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/scheduler/domain/ports backend/tests/unit/scheduler/test_ports_importable.py
git commit -m "feat(scheduler): add repository ports"
```

---

## Task 5: Domain — JobRunner (the wrapper)

**Files:**
- Create: `backend/src/hiresense/scheduler/domain/job_runner.py`
- Modify: `backend/src/hiresense/scheduler/domain/__init__.py`
- Modify: `backend/src/hiresense/ingestion/domain/__init__.py` (re-export `IngestionCooldownError`)
- Test: `backend/tests/unit/scheduler/test_job_runner.py`

- [ ] **Step 1: Re-export the cooldown exception first**

`IngestionCooldownError` lives in `hiresense/ingestion/domain/services.py` but is not re-exported. Add to `backend/src/hiresense/ingestion/domain/__init__.py` (append the import and add to `__all__`):

```python
from hiresense.ingestion.domain.services import IngestionCooldownError
```

Add `"IngestionCooldownError"` to that file's `__all__` list.

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/unit/scheduler/test_job_runner.py
from datetime import datetime, timezone

import pytest

from hiresense.ingestion.domain import IngestionCooldownError
from hiresense.scheduler.domain import JobDefinition, JobRunner, JobStatus


class _RunRepo:
    def __init__(self):
        self.recorded = []

    def record(self, run):
        self.recorded.append(run)
        return run

    def recent(self, job_name, limit):
        return [r for r in self.recorded if r.job_name == job_name][:limit]

    def latest(self, job_name):
        runs = [r for r in self.recorded if r.job_name == job_name]
        return runs[-1] if runs else None


class _ToggleRepo:
    def __init__(self, enabled=True):
        self._enabled = enabled

    def is_enabled(self, job_name, default):
        return self._enabled

    def set_enabled(self, job_name, enabled):
        self._enabled = enabled

    def all_states(self):
        return {}


def _clock_seq(*times):
    it = iter(times)
    return lambda: next(it)


def _runner(defn, run_repo=None, toggle_repo=None, clock=None):
    return JobRunner(
        definitions=[defn],
        run_repo=run_repo or _RunRepo(),
        toggle_repo=toggle_repo or _ToggleRepo(),
        clock=clock,
    )


def _defn(run, count_items=len, default_enabled=True):
    return JobDefinition(
        name="job", run=run, cron="0 9 * * *", interval_hours=None,
        count_items=count_items, default_enabled=default_enabled,
    )


@pytest.mark.asyncio
async def test_success_records_count_and_duration():
    async def run():
        return [1, 2]

    t0 = datetime(2026, 6, 21, 9, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 6, 21, 9, 0, 3, tzinfo=timezone.utc)
    repo = _RunRepo()
    runner = _runner(_defn(run), run_repo=repo, clock=_clock_seq(t0, t1))
    result = await runner.run("job")
    assert result.status is JobStatus.SUCCESS
    assert result.items_affected == 2
    assert result.duration_seconds == 3.0
    assert repo.recorded[-1].status is JobStatus.SUCCESS


@pytest.mark.asyncio
async def test_disabled_job_is_skipped_without_running():
    ran = {"called": False}

    async def run():
        ran["called"] = True
        return []

    runner = _runner(_defn(run), toggle_repo=_ToggleRepo(enabled=False))
    result = await runner.run("job")
    assert result.status is JobStatus.SKIPPED
    assert ran["called"] is False


@pytest.mark.asyncio
async def test_cooldown_is_skipped_not_failure():
    async def run():
        raise IngestionCooldownError(retry_after=60)

    result = await _runner(_defn(run)).run("job")
    assert result.status is JobStatus.SKIPPED


@pytest.mark.asyncio
async def test_unexpected_error_is_recorded_as_failure_and_swallowed():
    async def run():
        raise RuntimeError("boom")

    result = await _runner(_defn(run)).run("job")
    assert result.status is JobStatus.FAILURE
    assert "boom" in (result.detail or "")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_job_runner.py -v`
Expected: FAIL — `ImportError: cannot import name 'JobRunner'`.

- [ ] **Step 4: Implement JobRunner**

`backend/src/hiresense/scheduler/domain/job_runner.py`:

```python
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from hiresense.ingestion.domain import IngestionCooldownError
from hiresense.scheduler.domain.job_definition import JobDefinition
from hiresense.scheduler.domain.job_run import JobRun
from hiresense.scheduler.domain.job_status import JobStatus
from hiresense.scheduler.domain.ports import JobRunRepository, JobToggleRepository

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobRunner:
    """Runs one named job through a uniform wrapper: toggle check → invoke →
    record outcome. Never raises — a failing job is recorded and swallowed so
    one bad job can't take down the scheduler or the app. Used identically by
    the scheduled trigger and the manual run-now endpoint."""

    def __init__(
        self,
        *,
        definitions: Iterable[JobDefinition],
        run_repo: JobRunRepository,
        toggle_repo: JobToggleRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._defs = {d.name: d for d in definitions}
        self._run_repo = run_repo
        self._toggle_repo = toggle_repo
        self._clock = clock or _utcnow

    async def run(self, name: str) -> JobRun:
        defn = self._defs[name]
        started = self._clock()

        if not self._toggle_repo.is_enabled(name, default=defn.default_enabled):
            return self._record(name, started, started, JobStatus.SKIPPED, "disabled", None)

        try:
            result = await defn.run()
        except IngestionCooldownError as exc:
            return self._record(name, started, self._clock(), JobStatus.SKIPPED, str(exc), None)
        except Exception as exc:  # noqa: BLE001 - scheduler must never crash
            logger.exception("Scheduled job %r failed", name)
            return self._record(name, started, self._clock(), JobStatus.FAILURE, str(exc), None)

        finished = self._clock()
        count = self._count(defn, result)
        return self._record(name, started, finished, JobStatus.SUCCESS, None, count)

    def _count(self, defn: JobDefinition, result: Any) -> int | None:
        try:
            return defn.count_items(result)
        except Exception:  # noqa: BLE001 - counting must never fail the run
            return None

    def _record(
        self,
        name: str,
        started: datetime,
        finished: datetime,
        status: JobStatus,
        detail: str | None,
        items: int | None,
    ) -> JobRun:
        run = JobRun(
            job_name=name,
            started_at=started,
            finished_at=finished,
            status=status,
            detail=detail,
            items_affected=items,
            duration_seconds=(finished - started).total_seconds(),
        )
        return self._run_repo.record(run)
```

Update `backend/src/hiresense/scheduler/domain/__init__.py` to also export `JobRunner`:

```python
from hiresense.scheduler.domain.job_definition import JobDefinition
from hiresense.scheduler.domain.job_run import JobRun
from hiresense.scheduler.domain.job_runner import JobRunner
from hiresense.scheduler.domain.job_status import JobStatus
from hiresense.scheduler.domain.scheduled_job_view import ScheduledJobView

__all__ = ["JobDefinition", "JobRun", "JobRunner", "JobStatus", "ScheduledJobView"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_job_runner.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/scheduler/domain backend/src/hiresense/ingestion/domain/__init__.py backend/tests/unit/scheduler/test_job_runner.py
git commit -m "feat(scheduler): add JobRunner wrapper with toggle/cooldown/failure handling"
```

---

## Task 6: Infrastructure — ORM models + registry

**Files:**
- Create: `backend/src/hiresense/scheduler/infrastructure/job_run_orm.py`
- Create: `backend/src/hiresense/scheduler/infrastructure/job_toggle_orm.py`
- Create: `backend/src/hiresense/scheduler/infrastructure/__init__.py`
- Modify: `backend/src/hiresense/infrastructure/registry.py`
- Test: `backend/tests/unit/scheduler/test_orm_metadata.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/scheduler/test_orm_metadata.py
from hiresense.infrastructure.database import Base
# Importing the registry must register the scheduler tables on Base.metadata.
import hiresense.infrastructure.registry  # noqa: F401


def test_scheduler_tables_registered():
    tables = set(Base.metadata.tables)
    assert "scheduler_job_runs" in tables
    assert "scheduler_job_toggles" in tables
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_orm_metadata.py -v`
Expected: FAIL — assertion error (tables not present) / ModuleNotFoundError.

- [ ] **Step 3: Implement the ORM classes**

`backend/src/hiresense/scheduler/infrastructure/job_run_orm.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class JobRunOrm(Base):
    """One scheduled-job invocation outcome (run history)."""

    __tablename__ = "scheduler_job_runs"
    __table_args__ = (Index("ix_scheduler_job_runs_name_started", "job_name", "started_at"),)

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    job_name: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_affected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
```

`backend/src/hiresense/scheduler/infrastructure/job_toggle_orm.py`:

```python
from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class JobToggleOrm(Base):
    """Per-job enable/disable state. Absence of a row means "use the job's
    default_enabled"."""

    __tablename__ = "scheduler_job_toggles"

    job_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
```

`backend/src/hiresense/scheduler/infrastructure/__init__.py` (repos added in Task 7; ORM only for now):

```python
from hiresense.scheduler.infrastructure.job_run_orm import JobRunOrm
from hiresense.scheduler.infrastructure.job_toggle_orm import JobToggleOrm

__all__ = ["JobRunOrm", "JobToggleOrm"]
```

Add to `backend/src/hiresense/infrastructure/registry.py` (alphabetical with the others):

```python
from hiresense.scheduler.infrastructure import JobRunOrm, JobToggleOrm  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_orm_metadata.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/scheduler/infrastructure backend/src/hiresense/infrastructure/registry.py backend/tests/unit/scheduler/test_orm_metadata.py
git commit -m "feat(scheduler): add JobRunOrm + JobToggleOrm and register them"
```

---

## Task 7: Infrastructure — repositories

**Files:**
- Create: `backend/src/hiresense/scheduler/infrastructure/job_run_repository.py`
- Create: `backend/src/hiresense/scheduler/infrastructure/job_toggle_repository.py`
- Modify: `backend/src/hiresense/scheduler/infrastructure/__init__.py`
- Test: `backend/tests/integration/test_scheduler_repository.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_scheduler_repository.py
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.scheduler.domain import JobRun, JobStatus
from hiresense.scheduler.infrastructure import (
    JobRunOrm,  # noqa: F401
    JobRunRepositoryImpl,
    JobToggleOrm,  # noqa: F401
    JobToggleRepositoryImpl,
)


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _run(name="autohunt_digest", status=JobStatus.SUCCESS, when=None):
    when = when or datetime.now(timezone.utc)
    return JobRun(
        job_name=name, started_at=when, finished_at=when, status=status,
        detail=None, items_affected=1, duration_seconds=0.0,
    )


def test_record_and_latest_and_recent():
    repo = JobRunRepositoryImpl(session_factory=_factory(), retention_days=30)
    repo.record(_run(status=JobStatus.SUCCESS))
    repo.record(_run(status=JobStatus.FAILURE))
    assert repo.latest("autohunt_digest").status is JobStatus.FAILURE
    assert len(repo.recent("autohunt_digest", limit=10)) == 2
    assert repo.latest("nonexistent") is None


def test_record_prunes_rows_older_than_retention():
    factory = _factory()
    repo = JobRunRepositoryImpl(session_factory=factory, retention_days=30)
    old = datetime.now(timezone.utc) - timedelta(days=40)
    repo.record(_run(when=old))
    repo.record(_run())  # recording prunes the 40-day-old row
    remaining = repo.recent("autohunt_digest", limit=10)
    assert len(remaining) == 1


def test_toggle_defaults_then_persists():
    repo = JobToggleRepositoryImpl(session_factory=_factory())
    # No row yet -> falls back to the supplied default.
    assert repo.is_enabled("autohunt_digest", default=True) is True
    repo.set_enabled("autohunt_digest", False)
    assert repo.is_enabled("autohunt_digest", default=True) is False
    assert repo.all_states() == {"autohunt_digest": False}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/integration/test_scheduler_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'JobRunRepositoryImpl'`.

- [ ] **Step 3: Implement the repositories**

`backend/src/hiresense/scheduler/infrastructure/job_run_repository.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from hiresense.infrastructure import SqlRepository
from hiresense.scheduler.domain import JobRun, JobStatus
from hiresense.scheduler.infrastructure.job_run_orm import JobRunOrm


def _to_domain(row: JobRunOrm) -> JobRun:
    return JobRun(
        job_name=row.job_name,
        started_at=row.started_at,
        finished_at=row.finished_at,
        status=JobStatus(row.status),
        detail=row.detail,
        items_affected=row.items_affected,
        duration_seconds=row.duration_seconds,
    )


class JobRunRepositoryImpl(SqlRepository):
    """Run-history persistence. Prunes rows past the retention window inline on
    each insert (one bounded DELETE), so no separate maintenance job is needed."""

    def __init__(self, *, session_factory, retention_days: int) -> None:
        super().__init__(session_factory)
        self._retention_days = retention_days

    def record(self, run: JobRun) -> JobRun:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        with self._session_factory() as session:
            session.add(
                JobRunOrm(
                    job_name=run.job_name,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                    status=run.status.value,
                    detail=run.detail,
                    items_affected=run.items_affected,
                    duration_seconds=run.duration_seconds,
                )
            )
            session.execute(delete(JobRunOrm).where(JobRunOrm.started_at < cutoff))
            session.commit()
        return run

    def recent(self, job_name: str, limit: int) -> list[JobRun]:
        stmt = (
            select(JobRunOrm)
            .where(JobRunOrm.job_name == job_name)
            .order_by(JobRunOrm.started_at.desc())
            .limit(limit)
        )
        return self._select_all(stmt, _to_domain)

    def latest(self, job_name: str) -> JobRun | None:
        stmt = (
            select(JobRunOrm)
            .where(JobRunOrm.job_name == job_name)
            .order_by(JobRunOrm.started_at.desc())
            .limit(1)
        )
        return self._select_one(stmt, _to_domain)
```

`backend/src/hiresense/scheduler/infrastructure/job_toggle_repository.py`:

```python
from __future__ import annotations

from sqlalchemy import select

from hiresense.infrastructure import SqlRepository
from hiresense.scheduler.infrastructure.job_toggle_orm import JobToggleOrm


class JobToggleRepositoryImpl(SqlRepository):
    """Per-job enable/disable persistence. Absent row → caller's default."""

    def is_enabled(self, job_name: str, default: bool) -> bool:
        with self._session_factory() as session:
            row = session.get(JobToggleOrm, job_name)
            return row.enabled if row is not None else default

    def set_enabled(self, job_name: str, enabled: bool) -> None:
        with self._session_factory() as session:
            row = session.get(JobToggleOrm, job_name)
            if row is None:
                session.add(JobToggleOrm(job_name=job_name, enabled=enabled))
            else:
                row.enabled = enabled
            session.commit()

    def all_states(self) -> dict[str, bool]:
        with self._session_factory() as session:
            rows = session.scalars(select(JobToggleOrm)).all()
            return {r.job_name: r.enabled for r in rows}
```

Update `backend/src/hiresense/scheduler/infrastructure/__init__.py`:

```python
from hiresense.scheduler.infrastructure.job_run_orm import JobRunOrm
from hiresense.scheduler.infrastructure.job_run_repository import JobRunRepositoryImpl
from hiresense.scheduler.infrastructure.job_toggle_orm import JobToggleOrm
from hiresense.scheduler.infrastructure.job_toggle_repository import JobToggleRepositoryImpl

__all__ = ["JobRunOrm", "JobRunRepositoryImpl", "JobToggleOrm", "JobToggleRepositoryImpl"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/integration/test_scheduler_repository.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/scheduler/infrastructure backend/tests/integration/test_scheduler_repository.py
git commit -m "feat(scheduler): add run-history + toggle repositories with inline prune"
```

---

## Task 8: Infrastructure — ApschedulerRunner

**Files:**
- Create: `backend/src/hiresense/scheduler/infrastructure/apscheduler_runner.py`
- Modify: `backend/src/hiresense/scheduler/infrastructure/__init__.py`
- Test: `backend/tests/unit/scheduler/test_apscheduler_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/scheduler/test_apscheduler_runner.py
import pytest

from hiresense.scheduler.domain import JobDefinition
from hiresense.scheduler.infrastructure import ApschedulerRunner


class _Runner:
    def __init__(self):
        self.ran = []

    async def run(self, name):
        self.ran.append(name)
        return name


def _defs():
    async def noop():
        return []

    return [
        JobDefinition(name="cron_job", run=noop, cron="0 9 * * *",
                      interval_hours=None, count_items=len),
        JobDefinition(name="interval_job", run=noop, cron=None,
                      interval_hours=24, count_items=len),
    ]


def test_start_registers_one_apscheduler_job_per_definition():
    job_runner = _Runner()
    runner = ApschedulerRunner(job_runner=job_runner, definitions=_defs())
    runner.start()
    try:
        assert runner.next_run_at("cron_job") is not None
        assert runner.next_run_at("interval_job") is not None
        assert runner.next_run_at("unknown") is None
    finally:
        runner.shutdown()


@pytest.mark.asyncio
async def test_trigger_now_delegates_to_job_runner():
    job_runner = _Runner()
    runner = ApschedulerRunner(job_runner=job_runner, definitions=_defs())
    await runner.trigger_now("cron_job")
    assert job_runner.ran == ["cron_job"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_apscheduler_runner.py -v`
Expected: FAIL — `ImportError: cannot import name 'ApschedulerRunner'`.

- [ ] **Step 3: Implement the runner**

`backend/src/hiresense/scheduler/infrastructure/apscheduler_runner.py`:

```python
from __future__ import annotations

import logging
from datetime import datetime
from functools import partial
from typing import Iterable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from hiresense.scheduler.domain import JobDefinition, JobRunner

logger = logging.getLogger(__name__)

# Allow a late fire to still run if the loop was busy/asleep briefly.
_MISFIRE_GRACE_SECONDS = 300


class ApschedulerRunner:
    """Drives JobRunner.run(name) on each definition's cadence via an
    AsyncIOScheduler. max_instances=1 + coalesce prevents overlapping/stacked
    runs."""

    def __init__(self, *, job_runner: JobRunner, definitions: Iterable[JobDefinition]) -> None:
        self._job_runner = job_runner
        self._definitions = list(definitions)
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        for defn in self._definitions:
            self._scheduler.add_job(
                partial(self._job_runner.run, defn.name),
                trigger=self._trigger(defn),
                id=defn.name,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=_MISFIRE_GRACE_SECONDS,
                replace_existing=True,
            )
        self._scheduler.start()
        logger.info("Scheduler started with %d jobs", len(self._definitions))

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def next_run_at(self, name: str) -> datetime | None:
        job = self._scheduler.get_job(name)
        return job.next_run_time if job is not None else None

    async def trigger_now(self, name: str):
        return await self._job_runner.run(name)

    @staticmethod
    def _trigger(defn: JobDefinition):
        if defn.cron is not None:
            return CronTrigger.from_crontab(defn.cron)
        return IntervalTrigger(hours=defn.interval_hours)
```

Update `backend/src/hiresense/scheduler/infrastructure/__init__.py` to add the export:

```python
from hiresense.scheduler.infrastructure.apscheduler_runner import ApschedulerRunner
from hiresense.scheduler.infrastructure.job_run_orm import JobRunOrm
from hiresense.scheduler.infrastructure.job_run_repository import JobRunRepositoryImpl
from hiresense.scheduler.infrastructure.job_toggle_orm import JobToggleOrm
from hiresense.scheduler.infrastructure.job_toggle_repository import JobToggleRepositoryImpl

__all__ = [
    "ApschedulerRunner",
    "JobRunOrm",
    "JobRunRepositoryImpl",
    "JobToggleOrm",
    "JobToggleRepositoryImpl",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_apscheduler_runner.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/scheduler/infrastructure backend/tests/unit/scheduler/test_apscheduler_runner.py
git commit -m "feat(scheduler): add APScheduler runner adapter"
```

---

## Task 9: API — provider, dependencies, routes

**Files:**
- Create: `backend/src/hiresense/scheduler/api/provider.py`
- Create: `backend/src/hiresense/scheduler/api/dependencies.py`
- Create: `backend/src/hiresense/scheduler/api/routes.py`
- Create: `backend/src/hiresense/scheduler/api/__init__.py`
- Test: `backend/tests/integration/test_scheduler_endpoints.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_scheduler_endpoints.py
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.identity.api.dependencies import require_admin, require_auth
from hiresense.infrastructure.database import Base
from hiresense.scheduler.api import router as scheduler_router
from hiresense.scheduler.api.dependencies import get_scheduler_provider
from hiresense.scheduler.api.provider import SchedulerProvider
from hiresense.scheduler.domain import JobDefinition, JobRunner
from hiresense.scheduler.infrastructure import (
    JobRunOrm,  # noqa: F401
    JobRunRepositoryImpl,
    JobToggleOrm,  # noqa: F401
    JobToggleRepositoryImpl,
)


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


class _FakeRunner:
    """Stands in for ApschedulerRunner — no real APScheduler in tests."""

    def __init__(self, job_runner):
        self._job_runner = job_runner

    def next_run_at(self, name):
        return None

    async def trigger_now(self, name):
        return await self._job_runner.run(name)


def _build_app():
    factory = _factory()
    run_repo = JobRunRepositoryImpl(session_factory=factory, retention_days=30)
    toggle_repo = JobToggleRepositoryImpl(session_factory=factory)

    async def fetch():
        return [1, 2, 3]

    defs = [
        JobDefinition(name="ingestion_fetch", run=fetch, cron="0 */6 * * *",
                      interval_hours=None, count_items=len),
    ]
    job_runner = JobRunner(definitions=defs, run_repo=run_repo, toggle_repo=toggle_repo)
    provider = SchedulerProvider(
        definitions=defs, runner=_FakeRunner(job_runner),
        run_repo=run_repo, toggle_repo=toggle_repo,
    )

    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "u"
    app.dependency_overrides[require_admin] = lambda: {"role": "admin"}
    app.dependency_overrides[get_scheduler_provider] = lambda: provider
    app.include_router(scheduler_router)
    return app


@pytest.mark.asyncio
async def test_list_jobs_returns_definitions():
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/scheduler/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["name"] == "ingestion_fetch"
    assert body[0]["enabled"] is True


@pytest.mark.asyncio
async def test_run_now_then_toggle_then_runs_history():
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        run = await client.post("/scheduler/jobs/ingestion_fetch/run-now")
        assert run.status_code == 200
        assert run.json()["status"] == "success"
        assert run.json()["items_affected"] == 3

        runs = await client.get("/scheduler/jobs/ingestion_fetch/runs")
        assert len(runs.json()) == 1

        toggled = await client.post(
            "/scheduler/jobs/ingestion_fetch/toggle", json={"enabled": False}
        )
        assert toggled.status_code == 200
        assert toggled.json()["enabled"] is False

        # Disabled job records a skipped run.
        again = await client.post("/scheduler/jobs/ingestion_fetch/run-now")
        assert again.json()["status"] == "skipped"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/integration/test_scheduler_endpoints.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hiresense.scheduler.api'`.

- [ ] **Step 3: Implement provider**

`backend/src/hiresense/scheduler/api/provider.py`:

```python
from __future__ import annotations

from typing import Iterable

from hiresense.scheduler.domain import JobDefinition, JobRun, ScheduledJobView
from hiresense.scheduler.domain.ports import JobRunRepository, JobToggleRepository


class SchedulerProvider:
    """Read/command surface for the scheduler API. Lists jobs (definitions +
    toggle + latest run + next fire), exposes run history, toggling, and manual
    run-now. Works whether or not the APScheduler runner was started."""

    def __init__(
        self,
        *,
        definitions: Iterable[JobDefinition],
        runner,
        run_repo: JobRunRepository,
        toggle_repo: JobToggleRepository,
    ) -> None:
        self._defs = list(definitions)
        self._runner = runner
        self._run_repo = run_repo
        self._toggle_repo = toggle_repo

    def list_jobs(self) -> list[ScheduledJobView]:
        return [
            ScheduledJobView(
                name=d.name,
                cron=d.cadence_label,
                enabled=self._toggle_repo.is_enabled(d.name, default=d.default_enabled),
                last_run=self._run_repo.latest(d.name),
                next_run_at=self._runner.next_run_at(d.name),
            )
            for d in self._defs
        ]

    def runs(self, name: str, limit: int) -> list[JobRun]:
        return self._run_repo.recent(name, limit)

    def set_enabled(self, name: str, enabled: bool) -> ScheduledJobView:
        self._toggle_repo.set_enabled(name, enabled)
        return self._view(name)

    async def run_now(self, name: str) -> JobRun:
        return await self._runner.trigger_now(name)

    def has_job(self, name: str) -> bool:
        return any(d.name == name for d in self._defs)

    def _view(self, name: str) -> ScheduledJobView:
        return next(v for v in self.list_jobs() if v.name == name)
```

- [ ] **Step 4: Implement dependencies + routes + `__init__`**

`backend/src/hiresense/scheduler/api/dependencies.py`:

```python
from __future__ import annotations

from fastapi import Request

from hiresense.scheduler.api.provider import SchedulerProvider


def get_scheduler_provider(request: Request) -> SchedulerProvider:
    return request.app.state.scheduler
```

`backend/src/hiresense/scheduler/api/routes.py`:

```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from hiresense.identity.api.dependencies import require_admin, require_auth
from hiresense.scheduler.api.dependencies import get_scheduler_provider
from hiresense.scheduler.api.provider import SchedulerProvider
from hiresense.scheduler.domain import JobRun, ScheduledJobView

router = APIRouter(prefix="/scheduler", tags=["scheduler"], dependencies=[Depends(require_auth)])


class ToggleRequest(BaseModel):
    enabled: bool


def _require_known(provider: SchedulerProvider, name: str) -> None:
    if not provider.has_job(name):
        raise HTTPException(status_code=404, detail=f"Unknown job: {name}")


@router.get("/jobs", response_model=list[ScheduledJobView])
def list_jobs(
    provider: Annotated[SchedulerProvider, Depends(get_scheduler_provider)],
) -> list[ScheduledJobView]:
    return provider.list_jobs()


@router.get("/jobs/{name}/runs", response_model=list[JobRun])
def job_runs(
    name: str,
    provider: Annotated[SchedulerProvider, Depends(get_scheduler_provider)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[JobRun]:
    _require_known(provider, name)
    return provider.runs(name, limit)


@router.post("/jobs/{name}/toggle", response_model=ScheduledJobView)
def toggle_job(
    name: str,
    body: ToggleRequest,
    provider: Annotated[SchedulerProvider, Depends(get_scheduler_provider)],
    _admin: Annotated[dict, Depends(require_admin)],
) -> ScheduledJobView:
    _require_known(provider, name)
    return provider.set_enabled(name, body.enabled)


@router.post("/jobs/{name}/run-now", response_model=JobRun)
async def run_now(
    name: str,
    provider: Annotated[SchedulerProvider, Depends(get_scheduler_provider)],
    _admin: Annotated[dict, Depends(require_admin)],
) -> JobRun:
    _require_known(provider, name)
    return await provider.run_now(name)
```

`backend/src/hiresense/scheduler/api/__init__.py`:

```python
from hiresense.scheduler.api.routes import router

__all__ = ["router"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/integration/test_scheduler_endpoints.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/scheduler/api backend/tests/integration/test_scheduler_endpoints.py
git commit -m "feat(scheduler): add provider + status/toggle/run-now routes"
```

---

## Task 10: Bootstrap — build_scheduler + expose revalidation service

**Files:**
- Modify: `backend/src/hiresense/bootstrap/ingestion.py` (add `revalidation_service` to `IngestionBuild`)
- Create: `backend/src/hiresense/bootstrap/scheduler.py`
- Modify: `backend/src/hiresense/bootstrap/__init__.py`
- Test: `backend/tests/unit/scheduler/test_build_scheduler.py`

- [ ] **Step 1: Expose `revalidation_service` on `IngestionBuild`**

In `backend/src/hiresense/bootstrap/ingestion.py`, add the field to the dataclass:

```python
class IngestionBuild:
    provider: IngestionProvider
    orchestrator: IngestionOrchestrator
    boards_jobs_repo: Any
    pre_ranker: Any
    revalidation_service: Any
```

And in the `return IngestionBuild(...)` at the end of `build_ingestion`, add:

```python
    return IngestionBuild(
        provider=provider,
        orchestrator=ingestion_orchestrator,
        boards_jobs_repo=boards_jobs_repo,
        pre_ranker=pre_ranker,
        revalidation_service=revalidation_service,
    )
```

(`revalidation_service` is already a local in that function.)

- [ ] **Step 2: Write the failing test**

This fails first because `hiresense.bootstrap.scheduler` does not exist yet.

```python
# backend/tests/unit/scheduler/test_build_scheduler.py
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
    scheduler_run_retention_days = 30


class _Orchestrator:
    async def run(self):
        return [1, 2]


class _Revalidation:
    async def sweep(self):
        return ["closed-1"]


class _Autohunt:
    async def run(self):
        return type("D", (), {"job_count": 4})()


class _Outreach:
    def due_followups(self):
        return [1, 2, 3]


def test_build_scheduler_registers_all_four_jobs():
    build = build_scheduler(
        settings=_Settings(),
        sync_session_factory=_factory(),
        ingestion_orchestrator=_Orchestrator(),
        revalidation_service=_Revalidation(),
        autohunt_service=_Autohunt(),
        outreach_service=_Outreach(),
    )
    names = {v.name for v in build.provider.list_jobs()}
    assert names == {"ingestion_fetch", "revalidation_sweep", "autohunt_digest", "outreach_followups"}


@pytest.mark.asyncio
async def test_built_autohunt_job_counts_digest_entries():
    build = build_scheduler(
        settings=_Settings(),
        sync_session_factory=_factory(),
        ingestion_orchestrator=_Orchestrator(),
        revalidation_service=_Revalidation(),
        autohunt_service=_Autohunt(),
        outreach_service=_Outreach(),
    )
    run = await build.provider.run_now("autohunt_digest")
    assert run.items_affected == 4
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_build_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hiresense.bootstrap.scheduler'`.

- [ ] **Step 4: Implement `build_scheduler`**

`backend/src/hiresense/bootstrap/scheduler.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hiresense.scheduler.api.provider import SchedulerProvider
from hiresense.scheduler.domain import JobDefinition, JobRunner
from hiresense.scheduler.infrastructure import (
    ApschedulerRunner,
    JobRunRepositoryImpl,
    JobToggleRepositoryImpl,
)


@dataclass(frozen=True)
class SchedulerBuild:
    provider: SchedulerProvider
    runner: ApschedulerRunner


def _digest_count(result: Any) -> int | None:
    return getattr(result, "job_count", None)


def build_scheduler(
    *,
    settings: Any,
    sync_session_factory: Any,
    ingestion_orchestrator: Any,
    revalidation_service: Any,
    autohunt_service: Any,
    outreach_service: Any,
) -> SchedulerBuild:
    definitions = [
        JobDefinition(
            name="ingestion_fetch",
            run=ingestion_orchestrator.run,
            cron=settings.ingestion_schedule,
            interval_hours=None,
            count_items=len,
        ),
        JobDefinition(
            name="revalidation_sweep",
            run=revalidation_service.sweep,
            cron=None,
            interval_hours=settings.job_revalidation_interval_hours,
            count_items=len,
        ),
        JobDefinition(
            name="autohunt_digest",
            run=autohunt_service.run,
            cron=settings.autohunt_schedule,
            interval_hours=None,
            count_items=_digest_count,
        ),
        JobDefinition(
            name="outreach_followups",
            # Compute-only: surfaces due nudges; never sends (Phase 5 gates send).
            run=_as_async(outreach_service.due_followups),
            cron=settings.outreach_followup_schedule,
            interval_hours=None,
            count_items=len,
        ),
    ]
    run_repo = JobRunRepositoryImpl(
        session_factory=sync_session_factory,
        retention_days=settings.scheduler_run_retention_days,
    )
    toggle_repo = JobToggleRepositoryImpl(session_factory=sync_session_factory)
    job_runner = JobRunner(definitions=definitions, run_repo=run_repo, toggle_repo=toggle_repo)
    runner = ApschedulerRunner(job_runner=job_runner, definitions=definitions)
    provider = SchedulerProvider(
        definitions=definitions, runner=runner, run_repo=run_repo, toggle_repo=toggle_repo
    )
    return SchedulerBuild(provider=provider, runner=runner)


def _as_async(sync_fn):
    """Adapt a sync callable (OutreachService.due_followups) to the async job
    signature the runner expects."""

    async def _wrapped():
        return sync_fn()

    return _wrapped
```

Update `backend/src/hiresense/bootstrap/__init__.py` — add the import and `__all__` entries (mirroring the existing `build_autohunt` lines):

```python
from hiresense.bootstrap.scheduler import SchedulerBuild, build_scheduler
```

and add `"SchedulerBuild"` and `"build_scheduler"` to `__all__`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_build_scheduler.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/bootstrap/scheduler.py backend/src/hiresense/bootstrap/__init__.py backend/src/hiresense/bootstrap/ingestion.py backend/tests/unit/scheduler/test_build_scheduler.py
git commit -m "feat(scheduler): wire build_scheduler + expose revalidation service"
```

---

## Task 11: Wire into main.py + lifespan

**Files:**
- Modify: `backend/src/hiresense/main.py`
- Test: `backend/tests/integration/test_scheduler_app_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_scheduler_app_wiring.py
import pytest
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.main import create_app


@pytest.mark.asyncio
async def test_scheduler_router_is_mounted_and_lists_four_jobs(monkeypatch):
    # scheduler_enabled defaults False, so the APScheduler loop does NOT start,
    # but the provider + routes are still mounted and usable.
    app = create_app()
    app.dependency_overrides[require_auth] = lambda: "u"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/scheduler/jobs")
    assert resp.status_code == 200
    names = {j["name"] for j in resp.json()}
    assert names == {"ingestion_fetch", "revalidation_sweep", "autohunt_digest", "outreach_followups"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/integration/test_scheduler_app_wiring.py -v`
Expected: FAIL — 404 on `/scheduler/jobs` (router not mounted).

- [ ] **Step 3: Wire it in `main.py`**

Add the import near the other routers:

```python
from hiresense.scheduler.api import router as scheduler_router
```

Add the `build_scheduler` import to the existing `from hiresense.bootstrap import (...)` block.

After the outreach block (near the end, before the health check), add:

```python
    # --- Scheduler (Autopilot Phase 1: self-drive the recurring pipeline) ---
    scheduler_build = build_scheduler(
        settings=settings,
        sync_session_factory=infra.sync_session_factory,
        ingestion_orchestrator=ingestion.orchestrator,
        revalidation_service=ingestion.revalidation_service,
        autohunt_service=autohunt.service,
        outreach_service=outreach.provider.get_outreach_service(),
    )
    app.state.scheduler = scheduler_build.provider
    app.state.scheduler_runner = scheduler_build.runner
    app.include_router(scheduler_router)
```

Update the `lifespan` to start/stop the runner. Replace the current body:

```python
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Start the in-app scheduler only when explicitly enabled (exactly one
        # process should set SCHEDULER_ENABLED). A startup failure is logged but
        # must not stop the app from serving requests.
        runner = getattr(app.state, "scheduler_runner", None)
        if settings.scheduler_enabled and runner is not None:
            try:
                runner.start()
            except Exception:  # noqa: BLE001 - scheduler must not block boot
                logging.getLogger(__name__).exception("Scheduler failed to start")
        yield
        if settings.scheduler_enabled and runner is not None:
            try:
                runner.shutdown()
            except Exception:  # noqa: BLE001 - teardown must not raise
                pass
        # Drain in-flight event handlers before tearing infrastructure down so
        # events published late in a request aren't silently dropped.
        event_bus = getattr(app.state, "event_bus", None)
        if event_bus is not None:
            await event_bus.aclose(timeout=settings.event_bus_drain_timeout_seconds)
        await http_client.aclose()
        for provider in getattr(app.state, "otel_providers", []):
            shutdown = getattr(provider, "shutdown", None)
            if shutdown is not None:
                try:
                    shutdown()
                except Exception:  # noqa: BLE001 - teardown must not raise
                    pass
```

Add `import logging` at the top of `main.py` if not already present.

> **Note on lifespan + `app.state`:** the lifespan closure reads `app.state.scheduler_runner`, which is set during `create_app()` before the app starts serving — so it is always present by the time the startup branch runs.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/integration/test_scheduler_app_wiring.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full backend suite + lint**

Run: `cd backend && uv run python -m pytest -q && uv run ruff check .`
Expected: all green; ruff reports no new issues.

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/main.py backend/tests/integration/test_scheduler_app_wiring.py
git commit -m "feat(scheduler): mount router + start/stop runner in lifespan"
```

---

## Task 12: Alembic migration

**Files:**
- Create: a new migration in the project's Alembic versions directory.

- [ ] **Step 1: Confirm models are registered (already done in Task 6) and autogenerate**

Run: `cd backend && uv run python -m alembic revision --autogenerate -m "scheduler job runs and toggles"`
Expected: a new file in `alembic/versions/` creating `scheduler_job_runs` and `scheduler_job_toggles` with the `ix_scheduler_job_runs_name_started` index.

- [ ] **Step 2: Inspect the generated migration**

Open the new file. Verify `upgrade()` creates both tables (and the index) and `downgrade()` drops them. Remove any unrelated autogenerated drift (the autogenerate may pick up pre-existing dev-DB diffs — keep ONLY the two scheduler tables + index). If anything unrelated appears, delete those lines so the migration is scoped to this feature.

- [ ] **Step 3: Apply and verify it runs clean on SQLite metadata**

Run: `cd backend && uv run python -m pytest tests/integration/test_scheduler_repository.py -v`
Expected: still PASS (tables build from metadata; this just confirms no schema drift).

> **Post-merge reminder (not a step here):** on the live dev Postgres, run
> `uv run python -m alembic upgrade head` — merged migrations don't auto-apply
> (CI runs on SQLite), and the app will 500 with `UndefinedTable` otherwise.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions
git commit -m "feat(scheduler): migration for job-run + toggle tables"
```

---

## Task 13: Frontend — service + models

**Files:**
- Create: `frontend/src/app/core/models/scheduler.model.ts`
- Create: `frontend/src/app/core/services/scheduler.service.ts`
- Test: `frontend/src/app/core/services/scheduler.service.spec.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/app/core/services/scheduler.service.spec.ts
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { SchedulerService } from './scheduler.service';

describe('SchedulerService', () => {
  let service: SchedulerService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [SchedulerService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(SchedulerService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('lists jobs', () => {
    let result: unknown;
    service.listJobs().subscribe((r) => (result = r));
    const req = httpMock.expectOne('/api/scheduler/jobs');
    expect(req.request.method).toBe('GET');
    req.flush([{ name: 'ingestion_fetch', cron: '0 */6 * * *', enabled: true, lastRun: null, nextRunAt: null }]);
    expect((result as unknown[]).length).toBe(1);
  });

  it('toggles a job', () => {
    service.toggle('ingestion_fetch', false).subscribe();
    const req = httpMock.expectOne('/api/scheduler/jobs/ingestion_fetch/toggle');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ enabled: false });
    req.flush({ name: 'ingestion_fetch', cron: '0 */6 * * *', enabled: false, lastRun: null, nextRunAt: null });
  });

  it('runs a job now', () => {
    service.runNow('ingestion_fetch').subscribe();
    const req = httpMock.expectOne('/api/scheduler/jobs/ingestion_fetch/run-now');
    expect(req.request.method).toBe('POST');
    req.flush({ jobName: 'ingestion_fetch', status: 'success' });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --include "**/scheduler.service.spec.ts"`
Expected: FAIL — cannot find module `./scheduler.service`.

- [ ] **Step 3: Implement models + service**

`frontend/src/app/core/models/scheduler.model.ts`:

```typescript
export interface JobRun {
  jobName: string;
  startedAt: string;
  finishedAt: string;
  status: 'success' | 'failure' | 'skipped';
  detail: string | null;
  itemsAffected: number | null;
  durationSeconds: number | null;
}

export interface ScheduledJob {
  name: string;
  cron: string;
  enabled: boolean;
  lastRun: JobRun | null;
  nextRunAt: string | null;
}
```

> **Field-casing note:** the backend serializes snake_case (`job_name`,
> `items_affected`, `last_run`, `next_run_at`). If the project has a global
> HTTP interceptor that camelCases responses, the interfaces above are correct
> as written. If not, change the interface fields to snake_case to match. Check
> `frontend/src/app/core/interceptors/` before implementing and follow whatever
> the existing services (e.g. `ingestion.service.ts`) assume.

`frontend/src/app/core/services/scheduler.service.ts`:

```typescript
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { JobRun, ScheduledJob } from '../models/scheduler.model';

@Injectable({ providedIn: 'root' })
export class SchedulerService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/scheduler';

  listJobs(): Observable<ScheduledJob[]> {
    return this.http.get<ScheduledJob[]>(`${this.base}/jobs`);
  }

  runs(name: string, limit = 20): Observable<JobRun[]> {
    return this.http.get<JobRun[]>(`${this.base}/jobs/${name}/runs?limit=${limit}`);
  }

  toggle(name: string, enabled: boolean): Observable<ScheduledJob> {
    return this.http.post<ScheduledJob>(`${this.base}/jobs/${name}/toggle`, { enabled });
  }

  runNow(name: string): Observable<JobRun> {
    return this.http.post<JobRun>(`${this.base}/jobs/${name}/run-now`, {});
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --include "**/scheduler.service.spec.ts"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/core/models/scheduler.model.ts frontend/src/app/core/services/scheduler.service.ts frontend/src/app/core/services/scheduler.service.spec.ts
git commit -m "feat(scheduler): frontend scheduler service + models"
```

---

## Task 14: Frontend — admin scheduler page

**Files:**
- Create: `frontend/src/app/pages/admin/scheduler/scheduler.component.ts`
- Create: `frontend/src/app/pages/admin/scheduler/scheduler.component.html`
- Create: `frontend/src/app/pages/admin/scheduler/scheduler.component.scss`
- Create: `frontend/src/app/pages/admin/scheduler/scheduler.component.spec.ts`
- Modify: the admin routes file (find with the grep in Step 1).

- [ ] **Step 1: Locate the admin routing pattern**

Run: `cd frontend && grep -rn "loadComponent\|path:" src/app/pages/admin --include=*.ts | head -20`
Expected: shows how existing admin pages register lazy standalone routes. Mirror that file and pattern exactly for the new route `path: 'scheduler'`.

- [ ] **Step 2: Write the failing component spec**

```typescript
// frontend/src/app/pages/admin/scheduler/scheduler.component.spec.ts
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { SchedulerComponent } from './scheduler.component';

describe('SchedulerComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [SchedulerComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });

  it('loads jobs on init', () => {
    const fixture = TestBed.createComponent(SchedulerComponent);
    fixture.detectChanges();
    const req = httpMock.expectOne('/api/scheduler/jobs');
    req.flush([
      { name: 'ingestion_fetch', cron: '0 */6 * * *', enabled: true, lastRun: null, nextRunAt: null },
    ]);
    expect(fixture.componentInstance.jobs().length).toBe(1);
    httpMock.verify();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npm test -- --include "**/scheduler.component.spec.ts"`
Expected: FAIL — cannot find `./scheduler.component`.

- [ ] **Step 4: Implement the component**

`frontend/src/app/pages/admin/scheduler/scheduler.component.ts`:

```typescript
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { SchedulerService } from '../../../core/services/scheduler.service';
import { ScheduledJob } from '../../../core/models/scheduler.model';

@Component({
  selector: 'app-scheduler',
  standalone: true,
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './scheduler.component.html',
  styleUrl: './scheduler.component.scss',
})
export class SchedulerComponent implements OnInit {
  private readonly service = inject(SchedulerService);
  readonly jobs = signal<ScheduledJob[]>([]);
  readonly busy = signal<string | null>(null);

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.service.listJobs().subscribe((jobs) => this.jobs.set(jobs));
  }

  toggle(job: ScheduledJob): void {
    this.busy.set(job.name);
    this.service.toggle(job.name, !job.enabled).subscribe(() => {
      this.busy.set(null);
      this.reload();
    });
  }

  runNow(job: ScheduledJob): void {
    this.busy.set(job.name);
    this.service.runNow(job.name).subscribe(() => {
      this.busy.set(null);
      this.reload();
    });
  }
}
```

`frontend/src/app/pages/admin/scheduler/scheduler.component.html`:

```html
<section class="scheduler">
  <h1>Scheduler</h1>
  <table>
    <thead>
      <tr><th>Job</th><th>Cadence</th><th>Enabled</th><th>Last run</th><th>Next run</th><th></th></tr>
    </thead>
    <tbody>
      @for (job of jobs(); track job.name) {
        <tr>
          <td>{{ job.name }}</td>
          <td><code>{{ job.cron }}</code></td>
          <td>
            <button type="button" (click)="toggle(job)" [disabled]="busy() === job.name">
              {{ job.enabled ? 'On' : 'Off' }}
            </button>
          </td>
          <td>
            @if (job.lastRun) {
              <span class="status status--{{ job.lastRun.status }}">{{ job.lastRun.status }}</span>
              <small>{{ job.lastRun.finishedAt | date: 'short' }}</small>
            } @else {
              <small>—</small>
            }
          </td>
          <td>{{ job.nextRunAt ? (job.nextRunAt | date: 'short') : '—' }}</td>
          <td>
            <button type="button" (click)="runNow(job)" [disabled]="busy() === job.name">Run now</button>
          </td>
        </tr>
      }
    </tbody>
  </table>
</section>
```

`frontend/src/app/pages/admin/scheduler/scheduler.component.scss`:

```scss
.scheduler {
  padding: 1rem;

  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid var(--border, #e2e2e2); }

  .status {
    text-transform: capitalize;
    font-weight: 600;
    &--success { color: var(--success, #2e7d32); }
    &--failure { color: var(--danger, #c62828); }
    &--skipped { color: var(--muted, #888); }
  }
}
```

- [ ] **Step 5: Register the lazy route**

In the admin routes file located in Step 1, add (matching the existing entries' style):

```typescript
  {
    path: 'scheduler',
    loadComponent: () =>
      import('./scheduler/scheduler.component').then((m) => m.SchedulerComponent),
  },
```

Also add a nav link to the scheduler page wherever the other admin sub-pages are linked (mirror an existing admin link; if admin uses a sidebar/menu component, add one entry there).

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npm test -- --include "**/scheduler.component.spec.ts"`
Expected: PASS.

- [ ] **Step 7: Lint + build the frontend**

Run: `cd frontend && npx ng lint && npm run build`
Expected: lint clean (CI runs `ng lint`, which `npm test`/`build` skip), build succeeds.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/pages/admin/scheduler
git add -A   # include the modified admin routes/nav file
git commit -m "feat(scheduler): admin scheduler page (status, toggle, run-now)"
```

---

## Final verification

- [ ] Backend: `cd backend && uv run python -m pytest -q && uv run ruff check .` — all green.
- [ ] Frontend: `cd frontend && npx ng lint && npm test` — all green.
- [ ] Manual smoke (optional, needs live DB): `docker compose up db`, set `SCHEDULER_ENABLED=true` and a near-future cron in `.env`, run `uv run app`, confirm `GET /scheduler/jobs` shows `nextRunAt` populated and a `run-now` produces a `success` run.

## Spec coverage check (self-review notes — already reconciled)

- Master switch default-off in dev / on in docker → Task 1.
- Four jobs (fetch / revalidation / autohunt / outreach-followup compute-only) → Task 10.
- Job wrapper (toggle-skip / cooldown-skip / failure-swallow / item count / duration) → Task 5.
- Run-history + toggle persistence with inline prune → Tasks 6–7.
- APScheduler runner (max_instances=1, coalesce, cron+interval triggers) → Task 8.
- Status / runs / toggle(admin) / run-now(admin) API → Task 9.
- Lifespan start/stop guarded so startup failure never blocks boot → Task 11.
- Migration + registry import → Tasks 6, 12.
- Minimal admin frontend → Tasks 13–14.
- Known single-runner limitation → documented in spec; no code needed.
