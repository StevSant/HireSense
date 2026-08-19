# Per-Job Audit Trail and Ingestion Run History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record what happened to every job in every ingestion run — inserted, updated, reopened, or closed, with the fields that changed and the reason it closed — and surface it as a per-job timeline and a run history.

**Architecture:** The repository already computes the old-vs-new diff inside `_apply_to_row`; it starts returning that diff on `UpsertOutcome` instead of discarding it. A dedicated `JobHistoryRecorder` (domain) persists those outcomes through `JobHistoryPort` in one bulk insert per source, and swallows its own failures so auditing can never fail an ingestion pass. `IngestionOrchestrator` opens and closes a run row around its pass; `JobRevalidationService` records closures with `run_id=None` because the probe sweep is not an ingestion run.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (sync repositories via `SqlRepository`), Alembic, PostgreSQL 16 (tests run on in-memory SQLite), Angular 22 standalone + signals, Vitest.

**Spec:** `docs/superpowers/specs/2026-08-19-job-audit-trail-design.md`

## Global Constraints

- **Backend commands always via `uv`, always the `-m` form:** `uv run python -m pytest`, `uv run python -m alembic`. Bare `uv run pytest` / `uv run alembic` fail on this machine (broken exe trampolines). `uv run ruff` works normally.
- **Run all backend commands from `backend/`; all frontend commands from `frontend/`.**
- **Frontend needs Node 22.** Before any `npm` command: `export PATH="$HOME/AppData/Roaming/fnm/node-versions/v22.23.1/installation:$PATH"`. Under the default Node, `npm test` fails with an opaque `[vitest-pool]: Failed to start forks worker`.
- **No hardcoded values.** Every threshold or knob goes through `src/hiresense/shared/config/groups/` **and** `backend/.env.example` with a comment.
- **One class/function per file.** Every new file gets its symbol re-exported from the parent package's `__init__.py`; import from the contextual package (`from hiresense.ingestion.domain import JobHistoryRecorder`), never from the implementation module.
- **Hexagonal rules.** `domain/` imports no `sqlalchemy`, no `httpx`, no framework packages — only ports (`Protocol`s). Wiring happens only in `src/hiresense/composition/`.
- **Every new ORM class must be imported in `src/hiresense/shared/infrastructure/registry.py`** or Alembic `--autogenerate` will not see its table.
- **Use `sa.JSON()`, not `JSONB`.** The spec says jsonb; the codebase uses portable `sa.JSON()` throughout (migration 043 is the reference) because the whole integration suite runs on in-memory SQLite. On PostgreSQL SQLAlchemy maps `JSON` to `json`. This is a deliberate, recorded deviation from the spec.
- **Conventional Commits, English, scoped by module:** `feat(ingestion): …`.
- **Two pre-existing test failures are expected** and are not yours: `test_app_mode_defaults_to_local` and `test_public_symbols_importable` fail locally because `backend/.env` sets `APP_MODE=production`. They pass in CI. Do not "fix" them.
- **Never run `uv run python -m pytest -m pgvector`.** That fixture creates, truncates and **drops** the `vector_embeddings` table and would destroy the developer's live embeddings.

## Deviations from the spec (decided during planning, carried into every task)

1. **`sa.JSON()` instead of `jsonb`** — see above.
2. **A fifth closure reason, `closed_marker`.** The spec lists four (`probe_404`, `dead_end_redirect`, `expiry`, `snapshot_disappearance`), but `classify_listing` closes a job on two distinct signals: a 404/410 status, and a 200 page containing a closed-marker phrase. Collapsing them would erase exactly the distinction this feature exists to audit ("is the sweep over-closing?"). Five reasons ship.
3. **`trigger` values are `fetch` and `scheduler`, not three.** The spec listed `manual` as well, but `POST /ingestion/fetch` *is* the manual trigger — there is no third caller of `orchestrator.run()` in the codebase. The column stays `varchar(20)` so adding a third value later needs no migration.
4. **`registry.py` lives at `src/hiresense/shared/infrastructure/registry.py`**, not `ingestion/infrastructure/registry.py` as the spec's file list said.
5. **Response models go inline in `api/routes.py`.** The spec's file list named `api/schemas.py`; no such file exists — `routes.py` declares its own `BaseModel` response types (`FetchResponse`, `SourcesResponse`, …). Follow the existing pattern.
6. **`PortalScanner` is out of scope.** The spec's Recording section names only `IngestionOrchestrator` and `JobRevalidationService`. Portal (ATS) scans will produce no history rows in this iteration. Task 12 notes it as follow-up.

---

## File Structure

**New — backend**

| File | Responsibility |
|---|---|
| `alembic/versions/045_create_ingestion_runs.py` | `ingestion_runs` table |
| `alembic/versions/046_create_job_history_events.py` | `job_history_events` table + 3 indexes |
| `src/hiresense/ingestion/infrastructure/ingestion_run_orm.py` | `IngestionRunOrm` |
| `src/hiresense/ingestion/infrastructure/job_history_event_orm.py` | `JobHistoryEventOrm` |
| `src/hiresense/ingestion/infrastructure/job_history_repository.py` | `JobHistoryRepository` — the only SQL for history |
| `src/hiresense/ingestion/domain/job_history_event_type.py` | `JobHistoryEventType` enum |
| `src/hiresense/ingestion/domain/job_closure_reason.py` | `JobClosureReason` enum |
| `src/hiresense/ingestion/domain/job_history_event.py` | `JobHistoryEvent` domain model |
| `src/hiresense/ingestion/domain/ingestion_run_summary.py` | `IngestionRunSummary` domain model |
| `src/hiresense/ingestion/domain/tracked_job_fields.py` | `TRACKED_FIELDS` + `diff_job_fields()` |
| `src/hiresense/ingestion/domain/job_history_recorder.py` | `JobHistoryRecorder` — failure-swallowing facade |
| `src/hiresense/ingestion/ports/job_history.py` | `JobHistoryPort` protocol |

**Modified — backend**

| File | Change |
|---|---|
| `src/hiresense/ingestion/ports/jobs_repository.py` | `changed_fields` on `UpsertOutcome` |
| `src/hiresense/ingestion/infrastructure/jobs_repository.py:114` | `_apply_to_row` returns the diff |
| `src/hiresense/ingestion/infrastructure/in_memory_jobs_repository.py` | same outcome shape |
| `src/hiresense/shared/infrastructure/registry.py` | import the two new ORM classes |
| `src/hiresense/ingestion/domain/closed_listing_classifier.py` | `closure_reason()` helper |
| `src/hiresense/ingestion/domain/services.py` | open/close run, record outcomes, prune history |
| `src/hiresense/ingestion/domain/job_revalidation_service.py` | carry + record closure reasons |
| `src/hiresense/ingestion/api/provider.py`, `dependencies.py`, `routes.py` | three endpoints |
| `src/hiresense/composition/ingestion.py`, `composition/scheduler.py` | wire the recorder, pass `trigger` |
| `src/hiresense/shared/config/groups/ingestion.py`, `../../../.env.example` | `JOB_HISTORY_RETENTION_DAYS` |

**New — frontend**

| File | Responsibility |
|---|---|
| `src/app/core/contracts/job-history-event.model.ts` | event interface |
| `src/app/core/contracts/ingestion-run.model.ts` | run summary + detail interfaces |
| `src/app/pages/job/job-history-timeline/job-history-timeline.component.{ts,html,scss,spec.ts}` | per-job timeline |
| `src/app/pages/admin/runs/runs.component.{ts,html,scss,spec.ts}` | run list page |

**Modified — frontend:** `core/api/api-routes.ts`, `core/services/ingestion.service.ts`, `core/contracts/index.ts`, `pages/job/job.component.html`, `app.routes.ts`.

---

### Task 1: Schema — tables, ORM classes, migrations

Foundation. Nothing else can be written until the tables exist. `ingested_jobs.id` is `String(36)`, so the FK column must match exactly.

**Files:**
- Create: `backend/alembic/versions/045_create_ingestion_runs.py`
- Create: `backend/alembic/versions/046_create_job_history_events.py`
- Create: `backend/src/hiresense/ingestion/infrastructure/ingestion_run_orm.py`
- Create: `backend/src/hiresense/ingestion/infrastructure/job_history_event_orm.py`
- Modify: `backend/src/hiresense/ingestion/infrastructure/__init__.py`
- Modify: `backend/src/hiresense/shared/infrastructure/registry.py`
- Test: `backend/tests/unit/ingestion/test_job_history_orm.py`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: `IngestionRunOrm` (table `ingestion_runs`, columns `id: uuid`, `started_at`, `finished_at`, `trigger`, `status`), `JobHistoryEventOrm` (table `job_history_events`, columns `id: uuid`, `job_id: str`, `run_id: uuid | None`, `event: str`, `changed_fields: dict`, `reason: str | None`, `occurred_at`). Both importable from `hiresense.ingestion.infrastructure`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_job_history_orm.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from hiresense.ingestion.infrastructure import IngestionRunOrm, JobHistoryEventOrm
from hiresense.shared.infrastructure.database import Base


def _session_factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_run_and_event_round_trip_with_json_changed_fields():
    factory = _session_factory()
    now = datetime.now(timezone.utc)
    run_id = uuid.uuid4()

    with factory() as session:
        session.add(
            IngestionRunOrm(id=run_id, started_at=now, trigger="fetch", status="running")
        )
        session.add(
            JobHistoryEventOrm(
                id=uuid.uuid4(),
                job_id="job-1",
                run_id=run_id,
                event="updated",
                changed_fields={"title": {"old": "Engineer", "new": "Senior Engineer"}},
                reason=None,
                occurred_at=now,
            )
        )
        session.commit()

    with factory() as session:
        event = session.scalars(select(JobHistoryEventOrm)).one()
        assert event.changed_fields["title"]["new"] == "Senior Engineer"
        assert event.run_id == run_id
        run = session.scalars(select(IngestionRunOrm)).one()
        assert run.finished_at is None
        assert run.status == "running"


def test_event_run_id_is_nullable_for_sweep_closures():
    factory = _session_factory()
    with factory() as session:
        session.add(
            JobHistoryEventOrm(
                id=uuid.uuid4(),
                job_id="job-2",
                run_id=None,
                event="closed",
                changed_fields={},
                reason="dead_end_redirect",
                occurred_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    with factory() as session:
        event = session.scalars(select(JobHistoryEventOrm)).one()
        assert event.run_id is None
        assert event.reason == "dead_end_redirect"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/ingestion/test_job_history_orm.py -v`
Expected: FAIL with `ImportError: cannot import name 'IngestionRunOrm'`

- [ ] **Step 3: Write the ORM classes**

Create `backend/src/hiresense/ingestion/infrastructure/ingestion_run_orm.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.shared.infrastructure.database import Base


class IngestionRunOrm(Base):
    """One ingestion pass: when it started, when it ended, how it was triggered."""

    __tablename__ = "ingestion_runs"

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NULL while the pass is still in flight.
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
```

Create `backend/src/hiresense/ingestion/infrastructure/job_history_event_orm.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.shared.infrastructure.database import Base


class JobHistoryEventOrm(Base):
    """One observed lifecycle change to one job.

    `run_id` is nullable on purpose: closures produced by the URL-probe
    revalidation sweep do not belong to an ingestion run, and inventing a
    synthetic run to satisfy NOT NULL would misrepresent when they happened.
    """

    __tablename__ = "job_history_events"
    __table_args__ = (
        Index("ix_job_history_events_job_occurred", "job_id", "occurred_at"),
        Index("ix_job_history_events_run", "run_id"),
        Index("ix_job_history_events_occurred", "occurred_at"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    # String(36) matches ingested_jobs.id exactly; a type mismatch would make
    # the FK unbuildable on PostgreSQL.
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ingested_jobs.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid_mod.UUID | None] = mapped_column(
        Uuid, ForeignKey("ingestion_runs.id", ondelete="SET NULL"), nullable=True
    )
    event: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_fields: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

Append to `backend/src/hiresense/ingestion/infrastructure/__init__.py` — add the two imports and both names to `__all__` (keep both lists alphabetical):

```python
from hiresense.ingestion.infrastructure.ingestion_run_orm import IngestionRunOrm
from hiresense.ingestion.infrastructure.job_history_event_orm import JobHistoryEventOrm
```

In `backend/src/hiresense/shared/infrastructure/registry.py`, extend the existing ingestion import:

```python
from hiresense.ingestion.infrastructure import (  # noqa: F401
    IngestedJob,
    IngestionRunOrm,
    JobHistoryEventOrm,
    JobMatchCache,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/ingestion/test_job_history_orm.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Write the migrations**

Create `backend/alembic/versions/045_create_ingestion_runs.py`:

```python
"""create ingestion_runs table

Revision ID: 045
Revises: 044
Create Date: 2026-08-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "045"
down_revision: Union[str, None] = "044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_runs_started_at", "ingestion_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_runs_started_at", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
```

Create `backend/alembic/versions/046_create_job_history_events.py`:

```python
"""create job_history_events table

Revision ID: 046
Revises: 045
Create Date: 2026-08-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_history_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("event", sa.String(length=20), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("reason", sa.String(length=40), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["job_id"], ["ingested_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_runs.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_job_history_events_job_occurred", "job_history_events", ["job_id", "occurred_at"]
    )
    op.create_index("ix_job_history_events_run", "job_history_events", ["run_id"])
    op.create_index("ix_job_history_events_occurred", "job_history_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_job_history_events_occurred", table_name="job_history_events")
    op.drop_index("ix_job_history_events_run", table_name="job_history_events")
    op.drop_index("ix_job_history_events_job_occurred", table_name="job_history_events")
    op.drop_table("job_history_events")
```

- [ ] **Step 6: Verify the migration chain is intact**

Run: `uv run python -m alembic heads`
Expected: exactly one head, `046`. If two heads appear, `down_revision` is wrong — fix before continuing.

- [ ] **Step 7: Run the full unit suite for regressions**

Run: `uv run python -m pytest tests/unit -q`
Expected: PASS (except the two known `.env` failures listed in Global Constraints)

- [ ] **Step 8: Lint and format**

Run: `uv run ruff format src/hiresense/ingestion/infrastructure src/hiresense/shared/infrastructure alembic/versions tests/unit/ingestion && uv run ruff check .`
Expected: clean

- [ ] **Step 9: Commit**

```bash
git add backend/alembic/versions/045_create_ingestion_runs.py backend/alembic/versions/046_create_job_history_events.py backend/src/hiresense/ingestion/infrastructure/ backend/src/hiresense/shared/infrastructure/registry.py backend/tests/unit/ingestion/test_job_history_orm.py
git commit -m "feat(ingestion): add ingestion_runs and job_history_events tables"
```

---

### Task 2: Domain vocabulary — event types, closure reasons, event and run models

Pure Pydantic/enum value objects with no dependencies. Every later task imports from here, so the names are locked now.

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/job_history_event_type.py`
- Create: `backend/src/hiresense/ingestion/domain/job_closure_reason.py`
- Create: `backend/src/hiresense/ingestion/domain/job_history_event.py`
- Create: `backend/src/hiresense/ingestion/domain/ingestion_run_summary.py`
- Modify: `backend/src/hiresense/ingestion/domain/__init__.py`
- Test: `backend/tests/unit/ingestion/test_job_history_event.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `JobHistoryEventType` — str enum: `INSERTED="inserted"`, `UPDATED="updated"`, `REOPENED="reopened"`, `CLOSED="closed"`
  - `JobClosureReason` — str enum: `PROBE_404="probe_404"`, `CLOSED_MARKER="closed_marker"`, `DEAD_END_REDIRECT="dead_end_redirect"`, `EXPIRY="expiry"`, `SNAPSHOT_DISAPPEARANCE="snapshot_disappearance"`
  - `JobHistoryEvent(job_id: str, event: JobHistoryEventType, changed_fields: dict[str, Any] = {}, reason: JobClosureReason | None = None, occurred_at: datetime)` — frozen Pydantic model
  - `IngestionRunSummary(id: str, started_at: datetime, finished_at: datetime | None, trigger: str, status: str, inserted: int, updated: int, reopened: int, closed: int)` — frozen Pydantic model
  - All four importable from `hiresense.ingestion.domain`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_job_history_event.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hiresense.ingestion.domain import (
    IngestionRunSummary,
    JobClosureReason,
    JobHistoryEvent,
    JobHistoryEventType,
)


def test_event_defaults_to_empty_diff_and_no_reason():
    event = JobHistoryEvent(
        job_id="job-1",
        event=JobHistoryEventType.INSERTED,
        occurred_at=datetime.now(timezone.utc),
    )
    assert event.changed_fields == {}
    assert event.reason is None


def test_event_is_frozen():
    event = JobHistoryEvent(
        job_id="job-1",
        event=JobHistoryEventType.CLOSED,
        reason=JobClosureReason.PROBE_404,
        occurred_at=datetime.now(timezone.utc),
    )
    with pytest.raises(Exception):
        event.job_id = "job-2"


def test_enums_serialise_to_their_stored_string_values():
    assert JobHistoryEventType.REOPENED.value == "reopened"
    assert JobClosureReason.DEAD_END_REDIRECT.value == "dead_end_redirect"
    assert JobClosureReason.SNAPSHOT_DISAPPEARANCE.value == "snapshot_disappearance"
    assert JobClosureReason.CLOSED_MARKER.value == "closed_marker"


def test_run_summary_counts_default_to_zero():
    summary = IngestionRunSummary(
        id="run-1",
        started_at=datetime.now(timezone.utc),
        finished_at=None,
        trigger="fetch",
        status="running",
    )
    assert (summary.inserted, summary.updated, summary.reopened, summary.closed) == (0, 0, 0, 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/ingestion/test_job_history_event.py -v`
Expected: FAIL with `ImportError: cannot import name 'JobHistoryEventType'`

- [ ] **Step 3: Write the four modules**

Create `backend/src/hiresense/ingestion/domain/job_history_event_type.py`:

```python
from __future__ import annotations

from enum import Enum


class JobHistoryEventType(str, Enum):
    """What was observed to happen to a job in one run.

    Mirrors UpsertResult minus UNCHANGED (a no-op is not history), plus
    CLOSED, which no upsert path can produce.
    """

    INSERTED = "inserted"
    UPDATED = "updated"
    REOPENED = "reopened"
    CLOSED = "closed"
```

Create `backend/src/hiresense/ingestion/domain/job_closure_reason.py`:

```python
from __future__ import annotations

from enum import Enum


class JobClosureReason(str, Enum):
    """Why a job was closed — the signal the closure decision rested on.

    PROBE_404 and CLOSED_MARKER are kept apart deliberately: they are the two
    distinct ways the URL-probe sweep decides a listing is gone, and telling
    them apart is what makes "is the sweep over-closing?" answerable.
    """

    PROBE_404 = "probe_404"
    CLOSED_MARKER = "closed_marker"
    DEAD_END_REDIRECT = "dead_end_redirect"
    EXPIRY = "expiry"
    SNAPSHOT_DISAPPEARANCE = "snapshot_disappearance"
```

Create `backend/src/hiresense/ingestion/domain/job_history_event.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from hiresense.ingestion.domain.job_closure_reason import JobClosureReason
from hiresense.ingestion.domain.job_history_event_type import JobHistoryEventType


class JobHistoryEvent(BaseModel):
    """One observed lifecycle change to one job, before persistence.

    Carries no run id: the recorder receives the run id once per batch rather
    than stamping it on every event.
    """

    model_config = ConfigDict(frozen=True)

    job_id: str
    event: JobHistoryEventType
    changed_fields: dict[str, Any] = Field(default_factory=dict)
    reason: JobClosureReason | None = None
    occurred_at: datetime
```

Create `backend/src/hiresense/ingestion/domain/ingestion_run_summary.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IngestionRunSummary(BaseModel):
    """One ingestion run plus its per-event-type totals.

    Counts are aggregated from job_history_events at read time rather than
    denormalised onto the run row, so a run's totals can never drift from the
    events that actually landed.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    started_at: datetime
    finished_at: datetime | None
    trigger: str
    status: str
    inserted: int = 0
    updated: int = 0
    reopened: int = 0
    closed: int = 0
```

Add all four to `backend/src/hiresense/ingestion/domain/__init__.py` (imports and `__all__`, both alphabetical), matching the existing style there.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/ingestion/test_job_history_event.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff format src/hiresense/ingestion/domain tests/unit/ingestion && uv run ruff check .
cd .. && git add backend/src/hiresense/ingestion/domain/ backend/tests/unit/ingestion/test_job_history_event.py
git commit -m "feat(ingestion): add job history event and closure reason vocabulary"
```

---

### Task 3: Field diffing — `TRACKED_FIELDS` and `diff_job_fields`

Pure function, no I/O. Extracted into its own module so the repository can call it without owning the policy of which fields count as a content change.

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/tracked_job_fields.py`
- Modify: `backend/src/hiresense/ingestion/domain/__init__.py`
- Test: `backend/tests/unit/ingestion/test_tracked_job_fields.py`

**Interfaces:**
- Consumes: nothing
- Produces: `TRACKED_FIELDS: tuple[str, ...]` and `diff_job_fields(old: Any, new: Any) -> dict[str, Any]`, both importable from `hiresense.ingestion.domain`. `old` and `new` are duck-typed (an `IngestedJob` ORM row and a `NormalizedJob` respectively) — the function only does `getattr`, so it stays framework-free and testable with simple namespaces.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_tracked_job_fields.py`:

```python
from __future__ import annotations

from types import SimpleNamespace

from hiresense.ingestion.domain import TRACKED_FIELDS, diff_job_fields


def _job(**overrides):
    base = {
        "title": "Engineer",
        "company": "Acme",
        "salary_range": None,
        "location": "Remote",
        "employment_type": "full_time",
        "description": "Build things.",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_identical_jobs_produce_an_empty_diff():
    assert diff_job_fields(_job(), _job()) == {}


def test_changed_scalar_field_records_old_and_new():
    diff = diff_job_fields(_job(), _job(title="Senior Engineer"))
    assert diff == {"title": {"old": "Engineer", "new": "Senior Engineer"}}


def test_none_to_value_is_a_change():
    diff = diff_job_fields(_job(), _job(salary_range="$180-200K"))
    assert diff == {"salary_range": {"old": None, "new": "$180-200K"}}


def test_description_reduces_to_a_boolean_flag():
    diff = diff_job_fields(_job(), _job(description="Build better things."))
    assert diff == {"description": {"changed": True}}


def test_untracked_field_change_produces_no_entry():
    old = _job()
    new = _job()
    old.match_score = 0.1
    new.match_score = 0.9
    assert diff_job_fields(old, new) == {}


def test_several_fields_change_at_once():
    diff = diff_job_fields(
        _job(), _job(title="Staff Engineer", location="Berlin", description="New.")
    )
    assert set(diff) == {"title", "location", "description"}


def test_description_is_not_in_tracked_fields():
    # description is diffed separately as a flag; TRACKED_FIELDS is the
    # before/after set only.
    assert "description" not in TRACKED_FIELDS
    assert "title" in TRACKED_FIELDS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/ingestion/test_tracked_job_fields.py -v`
Expected: FAIL with `ImportError: cannot import name 'TRACKED_FIELDS'`

- [ ] **Step 3: Write the implementation**

Create `backend/src/hiresense/ingestion/domain/tracked_job_fields.py`:

```python
from __future__ import annotations

from typing import Any

# Fields whose before-and-after values are worth storing verbatim. Kept
# deliberately small: these are the ones a human reads on a timeline
# ("salary changed, was blank, now $180-200K"). Fields already excluded from
# content_hash (identity, timestamps, scores) are not content changes and are
# absent here by construction.
TRACKED_FIELDS: tuple[str, ...] = (
    "title",
    "company",
    "salary_range",
    "location",
    "employment_type",
)

# Tracked as a changed/unchanged flag only. Descriptions are large and churn on
# whitespace and boilerplate; storing them before-and-after would dominate the
# table for little analytical value.
_FLAGGED_FIELDS: tuple[str, ...] = ("description",)


def diff_job_fields(old: Any, new: Any) -> dict[str, Any]:
    """Compare two jobs field by field, returning only what actually differed.

    Duck-typed on purpose: `old` is a SQLAlchemy row and `new` a NormalizedJob,
    and this module must not import either. Only getattr is used.
    """
    diff: dict[str, Any] = {}
    for field in TRACKED_FIELDS:
        old_value = getattr(old, field, None)
        new_value = getattr(new, field, None)
        if old_value != new_value:
            diff[field] = {"old": old_value, "new": new_value}
    for field in _FLAGGED_FIELDS:
        if getattr(old, field, None) != getattr(new, field, None):
            diff[field] = {"changed": True}
    return diff
```

Re-export `TRACKED_FIELDS` and `diff_job_fields` from `backend/src/hiresense/ingestion/domain/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/ingestion/test_tracked_job_fields.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff format src/hiresense/ingestion/domain tests/unit/ingestion && uv run ruff check .
cd .. && git add backend/src/hiresense/ingestion/domain/ backend/tests/unit/ingestion/test_tracked_job_fields.py
git commit -m "feat(ingestion): add tracked-field diffing for job history"
```

---

### Task 4: Surface the diff on `UpsertOutcome`

`_apply_to_row` is the one place where the old row and the new job are both in scope. It currently returns a bare `UpsertResult` and discards the comparison. It starts returning both.

`changed_fields` gets a default so every existing `UpsertOutcome(job=…, result=…)` construction — including `InMemoryJobsRepository` and a number of test fakes — keeps compiling.

**Files:**
- Modify: `backend/src/hiresense/ingestion/ports/jobs_repository.py` (the `UpsertOutcome` dataclass, ~line 36)
- Modify: `backend/src/hiresense/ingestion/infrastructure/jobs_repository.py` (`_apply_to_row` at line 114; its two callers `upsert` at 150 and `bulk_upsert` at 171)
- Test: `backend/tests/unit/ingestion/test_jobs_repository_diff.py`

**Interfaces:**
- Consumes: `diff_job_fields` from Task 3
- Produces: `UpsertOutcome.changed_fields: dict[str, Any]` (defaults to `{}`); `JobsRepository._apply_to_row(row, job, new_hash, now) -> tuple[UpsertResult, dict[str, Any]]`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_jobs_repository_diff.py`:

```python
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.infrastructure import JobsRepository
from hiresense.ingestion.domain.upsert_result import UpsertResult
from hiresense.shared.infrastructure.database import Base


def _repo():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return JobsRepository(session_factory=sessionmaker(bind=engine), bucket="boards")


def _job(**overrides) -> NormalizedJob:
    base = {
        "id": "job-1",
        "source": "remotive",
        "source_type": "feed",
        "source_id": "r-1",
        "title": "Engineer",
        "company": "Acme",
        "description": "Build things.",
        "url": "https://example.com/jobs/1",
        "location": "Remote",
    }
    base.update(overrides)
    return NormalizedJob(**base)


def test_insert_reports_no_changed_fields():
    repo = _repo()
    outcomes = repo.bulk_upsert([_job()])
    assert outcomes[0].result == UpsertResult.INSERTED
    assert outcomes[0].changed_fields == {}


def test_unchanged_reports_no_changed_fields():
    repo = _repo()
    repo.bulk_upsert([_job()])
    outcomes = repo.bulk_upsert([_job()])
    assert outcomes[0].result == UpsertResult.UNCHANGED
    assert outcomes[0].changed_fields == {}


def test_update_reports_the_fields_that_differed():
    repo = _repo()
    repo.bulk_upsert([_job()])
    outcomes = repo.bulk_upsert([_job(title="Senior Engineer", salary_range="$180-200K")])
    assert outcomes[0].result == UpsertResult.UPDATED
    assert outcomes[0].changed_fields == {
        "title": {"old": "Engineer", "new": "Senior Engineer"},
        "salary_range": {"old": None, "new": "$180-200K"},
    }


def test_reopen_without_content_change_reports_no_changed_fields():
    repo = _repo()
    outcomes = repo.bulk_upsert([_job()])
    repo.mark_closed([outcomes[0].job.id])
    reopened = repo.bulk_upsert([_job()])
    assert reopened[0].result == UpsertResult.REOPENED
    assert reopened[0].changed_fields == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/ingestion/test_jobs_repository_diff.py -v`
Expected: FAIL with `AttributeError: 'UpsertOutcome' object has no attribute 'changed_fields'`

- [ ] **Step 3: Add the field to the port**

In `backend/src/hiresense/ingestion/ports/jobs_repository.py`, replace the `UpsertOutcome` dataclass body with:

```python
@dataclasses.dataclass(frozen=True)
class UpsertOutcome:
    """Result of one job inside a bulk_upsert call.

    `job` carries the RESOLVED id: when the identity already existed, the
    stored row's id replaces the caller's freshly generated one (absorbing the
    old get_id_by_identity pre-lookup).

    `changed_fields` is the old-vs-new diff for UPDATED outcomes and empty for
    every other result. It is captured here because _apply_to_row is the only
    place both states are in scope; discarding it there is what made job
    history impossible to reconstruct after the fact.
    """

    job: NormalizedJob
    result: "UpsertResult"
    changed_fields: dict[str, Any] = dataclasses.field(default_factory=dict)
```

Add `Any` to the existing `from typing import ...` line in that file.

- [ ] **Step 4: Return the diff from `_apply_to_row`**

In `backend/src/hiresense/ingestion/infrastructure/jobs_repository.py`, add the import:

```python
from hiresense.ingestion.domain.tracked_job_fields import diff_job_fields
```

Replace the `_apply_to_row` method (line 114) with this version. The diff is computed **before** any field is overwritten — after the assignments the old values are gone:

```python
    @staticmethod
    def _apply_to_row(
        row: IngestedJob, job: NormalizedJob, new_hash: str, now: datetime
    ) -> tuple[UpsertResult, dict[str, Any]]:
        """Apply one job's upsert semantics to an existing row (no commit).

        Returns the result and the old-vs-new diff. The diff MUST be taken
        before the assignments below, which destroy the old values.
        """
        row.last_seen_at = now
        row.missed_count = 0
        reopened = row.status == "closed"
        if reopened:
            row.status = "open"
            row.closed_at = None

        changed = row.content_hash != new_hash
        changed_fields: dict[str, Any] = diff_job_fields(row, job) if changed else {}
        if changed:
            row.title = job.title
            row.company = job.company
            row.description = job.description
            row.location = job.location
            row.salary_range = job.salary_range
            row.employment_type = job.employment_type
            row.equity_range = job.equity_range
            row.source_metadata = dict(job.source_metadata or {})
            row.skills = list(job.skills)
            row.categories = list(job.categories)
            row.countries = list(job.countries)
            row.remote_modality = job.remote_modality
            row.requires_existing_work_authorization = job.requires_existing_work_authorization
            row.visa_sponsorship_available = job.visa_sponsorship_available
            row.content_hash = new_hash
            row.updated_at = now

        if reopened:
            # A reopen carries no diff even when content also changed: the
            # headline event is the reopen, and REOPENED already implies a
            # re-index downstream.
            return UpsertResult.REOPENED, {}
        if changed:
            return UpsertResult.UPDATED, changed_fields
        return UpsertResult.UNCHANGED, {}
```

Ensure `Any` is imported in that file (it already imports from `typing`).

- [ ] **Step 5: Update the two callers**

In `upsert` (line ~167), unpack and discard the diff — the single-job path has no history caller:

```python
            result, _ = self._apply_to_row(row, job, new_hash, now)
            session.commit()
            return result
```

In `bulk_upsert` (line ~204), carry it onto the outcome:

```python
                resolved = job.model_copy(update={"id": row.id})
                result, changed_fields = self._apply_to_row(row, resolved, content_hash(resolved), now)
                outcomes.append(
                    UpsertOutcome(job=resolved, result=result, changed_fields=changed_fields)
                )
```

- [ ] **Step 6: Run the new test to verify it passes**

Run: `uv run python -m pytest tests/unit/ingestion/test_jobs_repository_diff.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Run the full backend suite for regressions**

Run: `uv run python -m pytest -q`
Expected: PASS except the two known `.env` failures. `_apply_to_row`'s return type changed, so any other caller would surface here. If a test asserts on the old single-value return, that is a **real contract change** — update the test and say so in the commit body rather than working around it.

- [ ] **Step 8: Lint and commit**

```bash
cd backend && uv run ruff format src/hiresense/ingestion tests/unit/ingestion && uv run ruff check .
cd .. && git add backend/src/hiresense/ingestion/ backend/tests/unit/ingestion/test_jobs_repository_diff.py
git commit -m "feat(ingestion): surface the upsert diff on UpsertOutcome"
```

---

### Task 5: `JobHistoryPort` and `JobHistoryRepository`

All the history SQL, in one place. Run totals are aggregated at read time from the events themselves so a run's counts can never drift from what actually landed.

**Files:**
- Create: `backend/src/hiresense/ingestion/ports/job_history.py`
- Create: `backend/src/hiresense/ingestion/infrastructure/job_history_repository.py`
- Modify: `backend/src/hiresense/ingestion/ports/__init__.py`, `backend/src/hiresense/ingestion/infrastructure/__init__.py`
- Test: `backend/tests/unit/ingestion/test_job_history_repository.py`

**Interfaces:**
- Consumes: `JobHistoryEvent`, `IngestionRunSummary`, `JobHistoryEventType` (Task 2); the ORM classes (Task 1)
- Produces: `JobHistoryPort` protocol and `JobHistoryRepository` implementing it, with exactly these methods:
  - `start_run(trigger: str, started_at: datetime) -> str` — returns the new run id as a string
  - `finish_run(run_id: str, status: str, finished_at: datetime) -> None`
  - `insert_events(run_id: str | None, events: list[JobHistoryEvent]) -> None`
  - `list_events_for_job(job_id: str, limit: int) -> list[JobHistoryEvent]` — newest first
  - `list_runs(limit: int, offset: int) -> list[IngestionRunSummary]` — newest first, counts populated
  - `get_run(run_id: str) -> IngestionRunSummary | None`
  - `list_events_for_run(run_id: str, limit: int) -> list[JobHistoryEvent]`
  - `prune_events_older_than(cutoff: datetime) -> int` — returns rows deleted

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_job_history_repository.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.ingestion.domain import JobClosureReason, JobHistoryEvent, JobHistoryEventType
from hiresense.ingestion.infrastructure import JobHistoryRepository
from hiresense.shared.infrastructure.database import Base

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def _repo():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return JobHistoryRepository(session_factory=sessionmaker(bind=engine))


def _event(job_id: str, event: JobHistoryEventType, *, at: datetime = NOW, **kwargs):
    return JobHistoryEvent(job_id=job_id, event=event, occurred_at=at, **kwargs)


def test_start_run_then_finish_run_updates_status_and_finished_at():
    repo = _repo()
    run_id = repo.start_run("fetch", NOW)
    assert repo.get_run(run_id).status == "running"
    assert repo.get_run(run_id).finished_at is None

    repo.finish_run(run_id, "completed", NOW + timedelta(minutes=3))
    summary = repo.get_run(run_id)
    assert summary.status == "completed"
    assert summary.finished_at is not None


def test_insert_events_and_read_them_back_for_a_job_newest_first():
    repo = _repo()
    run_id = repo.start_run("fetch", NOW)
    repo.insert_events(
        run_id,
        [
            _event("job-1", JobHistoryEventType.INSERTED, at=NOW),
            _event("job-1", JobHistoryEventType.UPDATED, at=NOW + timedelta(days=1)),
            _event("job-2", JobHistoryEventType.INSERTED, at=NOW),
        ],
    )
    events = repo.list_events_for_job("job-1", limit=10)
    assert [e.event for e in events] == [
        JobHistoryEventType.UPDATED,
        JobHistoryEventType.INSERTED,
    ]


def test_run_summary_counts_are_aggregated_per_event_type():
    repo = _repo()
    run_id = repo.start_run("scheduler", NOW)
    repo.insert_events(
        run_id,
        [
            _event("a", JobHistoryEventType.INSERTED),
            _event("b", JobHistoryEventType.INSERTED),
            _event("c", JobHistoryEventType.UPDATED),
            _event("d", JobHistoryEventType.REOPENED),
        ],
    )
    summary = repo.get_run(run_id)
    assert (summary.inserted, summary.updated, summary.reopened, summary.closed) == (2, 1, 1, 0)


def test_events_with_no_run_are_stored_and_keep_their_reason():
    repo = _repo()
    repo.insert_events(
        None,
        [
            _event(
                "job-9",
                JobHistoryEventType.CLOSED,
                reason=JobClosureReason.DEAD_END_REDIRECT,
            )
        ],
    )
    event = repo.list_events_for_job("job-9", limit=10)[0]
    assert event.reason == JobClosureReason.DEAD_END_REDIRECT


def test_insert_events_with_an_empty_list_is_a_no_op():
    repo = _repo()
    repo.insert_events(None, [])
    assert repo.list_events_for_job("job-1", limit=10) == []


def test_list_runs_returns_newest_first_with_counts():
    repo = _repo()
    old_run = repo.start_run("fetch", NOW - timedelta(days=1))
    new_run = repo.start_run("scheduler", NOW)
    repo.insert_events(new_run, [_event("a", JobHistoryEventType.INSERTED)])

    runs = repo.list_runs(limit=10, offset=0)
    assert [r.id for r in runs] == [new_run, old_run]
    assert runs[0].inserted == 1
    assert runs[1].inserted == 0


def test_prune_removes_events_past_the_cutoff_and_keeps_recent_ones():
    repo = _repo()
    repo.insert_events(
        None,
        [
            _event("old", JobHistoryEventType.CLOSED, at=NOW - timedelta(days=200)),
            _event("new", JobHistoryEventType.CLOSED, at=NOW),
        ],
    )
    deleted = repo.prune_events_older_than(NOW - timedelta(days=90))
    assert deleted == 1
    assert repo.list_events_for_job("old", limit=10) == []
    assert len(repo.list_events_for_job("new", limit=10)) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/ingestion/test_job_history_repository.py -v`
Expected: FAIL with `ImportError: cannot import name 'JobHistoryRepository'`

- [ ] **Step 3: Write the port**

Create `backend/src/hiresense/ingestion/ports/job_history.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from hiresense.ingestion.domain.ingestion_run_summary import IngestionRunSummary
from hiresense.ingestion.domain.job_history_event import JobHistoryEvent


class JobHistoryPort(Protocol):
    """Persistence for the per-job audit trail and its run headers."""

    def start_run(self, trigger: str, started_at: datetime) -> str:
        """Open a run row with status 'running'. Returns its id."""
        ...

    def finish_run(self, run_id: str, status: str, finished_at: datetime) -> None:
        """Stamp a run's terminal status ('completed' or 'failed')."""
        ...

    def insert_events(self, run_id: str | None, events: list[JobHistoryEvent]) -> None:
        """Persist a batch of events in ONE bulk insert.

        `run_id` is None for closures produced outside an ingestion run (the
        URL-probe sweep). An empty list is a no-op that touches no store.
        """
        ...

    def list_events_for_job(self, job_id: str, limit: int) -> list[JobHistoryEvent]:
        """One job's events, newest first."""
        ...

    def list_events_for_run(self, run_id: str, limit: int) -> list[JobHistoryEvent]:
        """One run's events, newest first."""
        ...

    def list_runs(self, limit: int, offset: int) -> list[IngestionRunSummary]:
        """Runs newest first, each with its per-event-type totals."""
        ...

    def get_run(self, run_id: str) -> IngestionRunSummary | None: ...

    def prune_events_older_than(self, cutoff: datetime) -> int:
        """Delete events with occurred_at < cutoff. Returns the row count."""
        ...
```

Re-export `JobHistoryPort` from `backend/src/hiresense/ingestion/ports/__init__.py`.

- [ ] **Step 4: Write the repository**

Create `backend/src/hiresense/ingestion/infrastructure/job_history_repository.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select

from hiresense.ingestion.domain.ingestion_run_summary import IngestionRunSummary
from hiresense.ingestion.domain.job_history_event import JobHistoryEvent
from hiresense.ingestion.infrastructure.ingestion_run_orm import IngestionRunOrm
from hiresense.ingestion.infrastructure.job_history_event_orm import JobHistoryEventOrm
from hiresense.shared.infrastructure.sql_repository import SqlRepository


def _to_domain(row: JobHistoryEventOrm) -> JobHistoryEvent:
    return JobHistoryEvent(
        job_id=row.job_id,
        event=row.event,
        changed_fields=row.changed_fields or {},
        reason=row.reason,
        occurred_at=row.occurred_at,
    )


class JobHistoryRepository(SqlRepository):
    """The only SQL for the audit trail.

    Run totals are aggregated from job_history_events at read time rather than
    denormalised onto the run row, so a run's counts can never disagree with
    the events that actually landed.
    """

    def start_run(self, trigger: str, started_at: datetime) -> str:
        run_id = uuid_mod.uuid4()
        with self._session_factory() as session:
            session.add(
                IngestionRunOrm(
                    id=run_id, started_at=started_at, trigger=trigger, status="running"
                )
            )
            session.commit()
        return str(run_id)

    def finish_run(self, run_id: str, status: str, finished_at: datetime) -> None:
        with self._session_factory() as session:
            row = session.get(IngestionRunOrm, uuid_mod.UUID(run_id))
            if row is None:
                return
            row.status = status
            row.finished_at = finished_at
            session.commit()

    def insert_events(self, run_id: str | None, events: list[JobHistoryEvent]) -> None:
        if not events:
            return
        resolved = uuid_mod.UUID(run_id) if run_id else None
        with self._session_factory() as session:
            # One executemany for the whole batch: a fetch produces ~1,000+
            # events per cycle and per-row inserts would dominate the pass.
            session.execute(
                JobHistoryEventOrm.__table__.insert(),
                [
                    {
                        "id": uuid_mod.uuid4(),
                        "job_id": e.job_id,
                        "run_id": resolved,
                        "event": e.event.value,
                        "changed_fields": e.changed_fields,
                        "reason": e.reason.value if e.reason else None,
                        "occurred_at": e.occurred_at,
                    }
                    for e in events
                ],
            )
            session.commit()

    def list_events_for_job(self, job_id: str, limit: int) -> list[JobHistoryEvent]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(JobHistoryEventOrm)
                .where(JobHistoryEventOrm.job_id == job_id)
                .order_by(JobHistoryEventOrm.occurred_at.desc())
                .limit(limit)
            ).all()
            return [_to_domain(r) for r in rows]

    def list_events_for_run(self, run_id: str, limit: int) -> list[JobHistoryEvent]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(JobHistoryEventOrm)
                .where(JobHistoryEventOrm.run_id == uuid_mod.UUID(run_id))
                .order_by(JobHistoryEventOrm.occurred_at.desc())
                .limit(limit)
            ).all()
            return [_to_domain(r) for r in rows]

    def list_runs(self, limit: int, offset: int) -> list[IngestionRunSummary]:
        with self._session_factory() as session:
            runs = session.scalars(
                select(IngestionRunOrm)
                .order_by(IngestionRunOrm.started_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
            if not runs:
                return []
            # One grouped count for the whole page instead of a query per run.
            counts = self._counts_for(session, [r.id for r in runs])
            return [self._summary(r, counts.get(r.id, {})) for r in runs]

    def get_run(self, run_id: str) -> IngestionRunSummary | None:
        resolved = uuid_mod.UUID(run_id)
        with self._session_factory() as session:
            row = session.get(IngestionRunOrm, resolved)
            if row is None:
                return None
            counts = self._counts_for(session, [resolved])
            return self._summary(row, counts.get(resolved, {}))

    def prune_events_older_than(self, cutoff: datetime) -> int:
        with self._session_factory() as session:
            result = session.execute(
                delete(JobHistoryEventOrm).where(JobHistoryEventOrm.occurred_at < cutoff)
            )
            session.commit()
            return int(result.rowcount or 0)

    @staticmethod
    def _counts_for(session: Any, run_ids: list[uuid_mod.UUID]) -> dict[Any, dict[str, int]]:
        rows = session.execute(
            select(
                JobHistoryEventOrm.run_id,
                JobHistoryEventOrm.event,
                func.count().label("total"),
            )
            .where(JobHistoryEventOrm.run_id.in_(run_ids))
            .group_by(JobHistoryEventOrm.run_id, JobHistoryEventOrm.event)
        ).all()
        counts: dict[Any, dict[str, int]] = {}
        for run_id, event, total in rows:
            counts.setdefault(run_id, {})[event] = total
        return counts

    @staticmethod
    def _summary(row: IngestionRunOrm, counts: dict[str, int]) -> IngestionRunSummary:
        return IngestionRunSummary(
            id=str(row.id),
            started_at=row.started_at,
            finished_at=row.finished_at,
            trigger=row.trigger,
            status=row.status,
            inserted=counts.get("inserted", 0),
            updated=counts.get("updated", 0),
            reopened=counts.get("reopened", 0),
            closed=counts.get("closed", 0),
        )
```

Re-export `JobHistoryRepository` from `backend/src/hiresense/ingestion/infrastructure/__init__.py`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/ingestion/test_job_history_repository.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Lint and commit**

```bash
cd backend && uv run ruff format src/hiresense/ingestion tests/unit/ingestion && uv run ruff check .
cd .. && git add backend/src/hiresense/ingestion/ backend/tests/unit/ingestion/test_job_history_repository.py
git commit -m "feat(ingestion): add job history repository and port"
```

---

### Task 6: `JobHistoryRecorder`

The failure boundary. Every caller goes through this; nothing else touches `JobHistoryPort` directly. History must never be able to fail an ingestion pass, so every method swallows and counts its own failures.

**Files:**
- Create: `backend/src/hiresense/ingestion/domain/job_history_recorder.py`
- Modify: `backend/src/hiresense/ingestion/domain/__init__.py`
- Test: `backend/tests/unit/ingestion/test_job_history_recorder.py`

**Interfaces:**
- Consumes: `JobHistoryPort` (Task 5); `UpsertOutcome` (Task 4); `JobHistoryEvent`, `JobHistoryEventType`, `JobClosureReason` (Task 2)
- Produces: `JobHistoryRecorder(store: JobHistoryPort, clock: Callable[[], datetime] | None = None)` with:
  - `start_run(trigger: str) -> str | None` — None if the store failed
  - `finish_run(run_id: str | None, status: str) -> None`
  - `record_outcomes(run_id: str | None, outcomes: list[UpsertOutcome]) -> None`
  - `record_closures(job_ids: list[str], reason: JobClosureReason, run_id: str | None = None) -> None`
  - `prune(cutoff: datetime) -> None`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_job_history_recorder.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

from hiresense.ingestion.domain import (
    JobClosureReason,
    JobHistoryEventType,
    JobHistoryRecorder,
)
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.upsert_result import UpsertResult
from hiresense.ingestion.ports.jobs_repository import UpsertOutcome

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


class FakeStore:
    def __init__(self) -> None:
        self.runs: list[tuple[str, datetime]] = []
        self.finished: list[tuple[str, str]] = []
        self.batches: list[tuple[str | None, list]] = []
        self.pruned: list[datetime] = []

    def start_run(self, trigger, started_at):
        self.runs.append((trigger, started_at))
        return "run-1"

    def finish_run(self, run_id, status, finished_at):
        self.finished.append((run_id, status))

    def insert_events(self, run_id, events):
        self.batches.append((run_id, events))

    def prune_events_older_than(self, cutoff):
        self.pruned.append(cutoff)
        return 0


class ExplodingStore(FakeStore):
    def start_run(self, trigger, started_at):
        raise RuntimeError("db down")

    def insert_events(self, run_id, events):
        raise RuntimeError("db down")


def _job(job_id: str) -> NormalizedJob:
    return NormalizedJob(
        id=job_id,
        source="remotive",
        source_type="feed",
        source_id=job_id,
        title="Engineer",
        company="Acme",
        description="Build things.",
        url=f"https://example.com/{job_id}",
    )


def _recorder(store):
    return JobHistoryRecorder(store=store, clock=lambda: NOW)


def test_unchanged_outcomes_are_skipped():
    store = FakeStore()
    _recorder(store).record_outcomes(
        "run-1",
        [
            UpsertOutcome(job=_job("a"), result=UpsertResult.UNCHANGED),
            UpsertOutcome(job=_job("b"), result=UpsertResult.INSERTED),
        ],
    )
    (_, events) = store.batches[0]
    assert [e.job_id for e in events] == ["b"]


def test_all_outcomes_unchanged_writes_nothing_at_all():
    store = FakeStore()
    _recorder(store).record_outcomes(
        "run-1", [UpsertOutcome(job=_job("a"), result=UpsertResult.UNCHANGED)]
    )
    assert store.batches == []


def test_outcomes_are_written_in_one_batch_carrying_the_diff():
    store = FakeStore()
    _recorder(store).record_outcomes(
        "run-1",
        [
            UpsertOutcome(job=_job("a"), result=UpsertResult.INSERTED),
            UpsertOutcome(
                job=_job("b"),
                result=UpsertResult.UPDATED,
                changed_fields={"title": {"old": "x", "new": "y"}},
            ),
            UpsertOutcome(job=_job("c"), result=UpsertResult.REOPENED),
        ],
    )
    assert len(store.batches) == 1
    run_id, events = store.batches[0]
    assert run_id == "run-1"
    assert [e.event for e in events] == [
        JobHistoryEventType.INSERTED,
        JobHistoryEventType.UPDATED,
        JobHistoryEventType.REOPENED,
    ]
    assert events[1].changed_fields == {"title": {"old": "x", "new": "y"}}
    assert all(e.occurred_at == NOW for e in events)


def test_closures_carry_their_reason_and_no_run_by_default():
    store = FakeStore()
    _recorder(store).record_closures(["a", "b"], JobClosureReason.PROBE_404)
    run_id, events = store.batches[0]
    assert run_id is None
    assert [e.event for e in events] == [JobHistoryEventType.CLOSED] * 2
    assert all(e.reason == JobClosureReason.PROBE_404 for e in events)


def test_closures_can_be_attributed_to_a_run():
    store = FakeStore()
    _recorder(store).record_closures(
        ["a"], JobClosureReason.SNAPSHOT_DISAPPEARANCE, run_id="run-1"
    )
    assert store.batches[0][0] == "run-1"


def test_empty_closure_list_writes_nothing():
    store = FakeStore()
    _recorder(store).record_closures([], JobClosureReason.EXPIRY)
    assert store.batches == []


def test_a_failing_store_is_swallowed_and_never_raises():
    recorder = _recorder(ExplodingStore())
    assert recorder.start_run("fetch") is None
    recorder.record_outcomes(
        "run-1", [UpsertOutcome(job=_job("a"), result=UpsertResult.INSERTED)]
    )
    recorder.record_closures(["a"], JobClosureReason.EXPIRY)


def test_start_and_finish_run_pass_through_the_clock():
    store = FakeStore()
    recorder = _recorder(store)
    run_id = recorder.start_run("scheduler")
    recorder.finish_run(run_id, "completed")
    assert store.runs == [("scheduler", NOW)]
    assert store.finished == [("run-1", "completed")]


def test_finish_run_with_no_run_id_is_a_no_op():
    store = FakeStore()
    _recorder(store).finish_run(None, "failed")
    assert store.finished == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/ingestion/test_job_history_recorder.py -v`
Expected: FAIL with `ImportError: cannot import name 'JobHistoryRecorder'`

- [ ] **Step 3: Write the recorder**

Create `backend/src/hiresense/ingestion/domain/job_history_recorder.py`:

```python
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from hiresense.ingestion.domain.job_closure_reason import JobClosureReason
from hiresense.ingestion.domain.job_history_event import JobHistoryEvent
from hiresense.ingestion.domain.job_history_event_type import JobHistoryEventType
from hiresense.ingestion.domain.upsert_result import UpsertResult
from hiresense.ingestion.ports.job_history import JobHistoryPort
from hiresense.ingestion.ports.jobs_repository import UpsertOutcome
from hiresense.shared.observability import get_domain_metrics

logger = logging.getLogger(__name__)

_RESULT_TO_EVENT: dict[UpsertResult, JobHistoryEventType] = {
    UpsertResult.INSERTED: JobHistoryEventType.INSERTED,
    UpsertResult.UPDATED: JobHistoryEventType.UPDATED,
    UpsertResult.REOPENED: JobHistoryEventType.REOPENED,
}


class JobHistoryRecorder:
    """Turns upsert outcomes and closures into persisted history.

    Every method swallows its own failures and increments
    automation_failures_total{component=job_history_record}. An audit trail
    that can fail an ingestion pass is worse than a gap in the audit trail —
    the job table, not this, is the source of truth.
    """

    def __init__(
        self,
        store: JobHistoryPort,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def start_run(self, trigger: str) -> str | None:
        try:
            return self._store.start_run(trigger, self._clock())
        except Exception:
            self._fail("start_run")
            return None

    def finish_run(self, run_id: str | None, status: str) -> None:
        if run_id is None:
            return
        try:
            self._store.finish_run(run_id, status, self._clock())
        except Exception:
            self._fail("finish_run")

    def record_outcomes(self, run_id: str | None, outcomes: list[UpsertOutcome]) -> None:
        now = self._clock()
        events = [
            JobHistoryEvent(
                job_id=outcome.job.id,
                event=_RESULT_TO_EVENT[outcome.result],
                changed_fields=outcome.changed_fields,
                occurred_at=now,
            )
            for outcome in outcomes
            # UNCHANGED is a no-op, not history.
            if outcome.result in _RESULT_TO_EVENT
        ]
        self._write(run_id, events)

    def record_closures(
        self,
        job_ids: list[str],
        reason: JobClosureReason,
        run_id: str | None = None,
    ) -> None:
        now = self._clock()
        self._write(
            run_id,
            [
                JobHistoryEvent(
                    job_id=job_id,
                    event=JobHistoryEventType.CLOSED,
                    reason=reason,
                    occurred_at=now,
                )
                for job_id in job_ids
            ],
        )

    def prune(self, cutoff: datetime) -> None:
        try:
            deleted = self._store.prune_events_older_than(cutoff)
            if deleted:
                logger.info("Pruned %d job history events older than %s", deleted, cutoff)
        except Exception:
            self._fail("prune")

    def _write(self, run_id: str | None, events: list[JobHistoryEvent]) -> None:
        if not events:
            return
        try:
            self._store.insert_events(run_id, events)
        except Exception:
            self._fail("insert_events")

    @staticmethod
    def _fail(operation: str) -> None:
        logger.exception("Job history %s failed", operation)
        get_domain_metrics().automation_failures_total.add(
            1, {"component": "job_history_record"}
        )
```

Re-export `JobHistoryRecorder` from `backend/src/hiresense/ingestion/domain/__init__.py`.

**Note:** confirm the metrics import path with `grep -rn "get_domain_metrics" src/hiresense/autohunt/domain/autohunt_service.py` and use whatever that file uses — it is the reference for this pattern.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/ingestion/test_job_history_recorder.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Lint and commit**

```bash
cd backend && uv run ruff format src/hiresense/ingestion tests/unit/ingestion && uv run ruff check .
cd .. && git add backend/src/hiresense/ingestion/ backend/tests/unit/ingestion/test_job_history_recorder.py
git commit -m "feat(ingestion): add failure-swallowing job history recorder"
```

---

### Task 7: Wire the recorder into `IngestionOrchestrator`

The run is opened before the source loop and closed in `finally`, so a crashed pass is recorded `failed` rather than left `running` forever.

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/services.py` (ctor ~line 37; `run` ~line 77; the outcome loop ~line 184; snapshot closure ~line 214; `_prune_expired` ~line 319)
- Test: `backend/tests/unit/ingestion/test_orchestrator_history.py`

**Interfaces:**
- Consumes: `JobHistoryRecorder` (Task 6), `JobClosureReason` (Task 2)
- Produces: `IngestionOrchestrator(..., history: JobHistoryRecorder | None = None, history_retention_days: int | None = None)`; `run(filters=None, trigger: str = "fetch")`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_orchestrator_history.py`. Build the orchestrator the same way `tests/unit/ingestion/test_orchestrator.py` already does — **read that file first and reuse its fakes and fixtures rather than inventing new ones.** The assertions to add:

```python
async def test_run_opens_and_completes_a_run(...):
    """A successful pass calls start_run once with trigger='fetch' and
    finish_run once with status='completed'."""


async def test_a_crashed_pass_marks_the_run_failed(...):
    """When a source loop raises, finish_run is still called, with
    status='failed' — the run is never left 'running'."""


async def test_outcomes_are_recorded_with_the_run_id(...):
    """record_outcomes receives the run id returned by start_run, and the
    outcomes of every source in the pass."""


async def test_snapshot_closures_are_recorded_with_the_disappearance_reason(...):
    """A source with supports_snapshot_closure() closing jobs produces a
    record_closures call with JobClosureReason.SNAPSHOT_DISAPPEARANCE and the
    run id attached."""


async def test_scheduler_trigger_is_passed_through(...):
    """run(trigger='scheduler') opens the run with trigger='scheduler'."""


async def test_orchestrator_without_a_recorder_still_runs(...):
    """history=None is a fully supported wiring (tests, bare apps): the pass
    completes and returns jobs with no history calls."""


async def test_history_is_pruned_with_its_own_retention_window(...):
    """_prune_expired calls history.prune with a cutoff derived from
    history_retention_days, independent of ingestion_job_retention_days."""
```

Use a `FakeRecorder` capturing `start_run`/`finish_run`/`record_outcomes`/`record_closures`/`prune` calls, modelled on the `FakeStore` in Task 6.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/ingestion/test_orchestrator_history.py -v`
Expected: FAIL — `IngestionOrchestrator` has no `history` parameter

- [ ] **Step 3: Extend the constructor**

In `backend/src/hiresense/ingestion/domain/services.py`, add two parameters after `source_concurrency` and store them:

```python
        source_concurrency: int = 8,
        history: JobHistoryRecorder | None = None,
        history_retention_days: int | None = None,
    ) -> None:
        ...
        self._source_concurrency = max(1, source_concurrency)
        # None in tests and bare apps: every call site below is guarded, so a
        # missing recorder degrades to "no history", never to an error.
        self._history = history
        self._history_retention_days = history_retention_days
```

Import `JobHistoryRecorder` and `JobClosureReason` at the top of the file.

- [ ] **Step 4: Open and close the run**

Change the signature at line 77:

```python
    async def run(
        self,
        filters: dict[str, Any] | None = None,
        trigger: str = "fetch",
    ) -> list[NormalizedJob]:
```

Immediately after `claimed = True` (before `await self._prune_expired()`), open the run:

```python
                run_id = self._history.start_run(trigger) if self._history else None
```

Declare `run_id: str | None = None` alongside `pending` **before** the `try` so the `finally` can always see it. In the existing `finally` block, after the task-draining code, close it:

```python
                if self._history is not None and run_id is not None:
                    # 'failed' whenever we leave via an exception; the flag is
                    # set on the success path just before returning.
                    self._history.finish_run(run_id, "completed" if completed else "failed")
```

Introduce `completed = False` next to `claimed = False` and set `completed = True` on the last line before the successful `return`.

- [ ] **Step 5: Record outcomes and snapshot closures**

In the per-source block, immediately after the `for outcome in outcomes:` loop finishes (before `indexed_count = len(touched)`):

```python
                    if self._history is not None:
                        self._history.record_outcomes(run_id, outcomes)
```

In the `supports_snapshot_closure()` block, after `closed_ids` is obtained:

```python
                        if closed_ids and self._history is not None:
                            self._history.record_closures(
                                closed_ids,
                                JobClosureReason.SNAPSHOT_DISAPPEARANCE,
                                run_id=run_id,
                            )
```

- [ ] **Step 6: Prune history alongside jobs**

At the end of `_prune_expired`, add an independent block. Note the early `return` at the top of that method guards on `self._retention_days`; history pruning must not be skipped just because job pruning is disabled, so **restructure so the history branch runs regardless**:

```python
    async def _prune_expired(self) -> None:
        await self._prune_jobs()
        await self._prune_history()

    async def _prune_history(self) -> None:
        if self._history is None or not self._history_retention_days:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._history_retention_days)
        await asyncio.to_thread(self._history.prune, cutoff)
```

Rename the existing body of `_prune_expired` to `_prune_jobs` unchanged.

- [ ] **Step 7: Run the tests**

Run: `uv run python -m pytest tests/unit/ingestion/ -v`
Expected: PASS — both the new file and the existing `test_orchestrator.py`

- [ ] **Step 8: Full suite and lint**

Run: `uv run python -m pytest -q && uv run ruff format src/hiresense/ingestion tests/unit/ingestion && uv run ruff check .`
Expected: PASS except the two known `.env` failures

- [ ] **Step 9: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/services.py backend/tests/unit/ingestion/test_orchestrator_history.py
git commit -m "feat(ingestion): record job history for each ingestion run"
```

---

### Task 8: Closure reasons in `JobRevalidationService`

The sweep currently knows *that* it closed a job but throws away *why*. Carrying the reason is the point of the whole feature — "is the sweep over-closing?" is only answerable if `probe_404` and `dead_end_redirect` are distinguishable after the fact.

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/closed_listing_classifier.py`
- Modify: `backend/src/hiresense/ingestion/domain/job_revalidation_service.py` (ctor ~line 51; `_close_expired` ~line 165; `_probe_and_close` ~line 210; `_probe_counted` ~line 223; `_probe` ~line 235)
- Test: `backend/tests/unit/ingestion/test_revalidation_history.py`

**Interfaces:**
- Consumes: `JobHistoryRecorder`, `JobClosureReason`
- Produces: `closure_reason(status_code: int) -> JobClosureReason` in `closed_listing_classifier`; `JobRevalidationService(..., history: JobHistoryRecorder | None = None)`; `_probe` returns `tuple[Verdict, JobClosureReason | None]`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_revalidation_history.py`. **Read `tests/unit/ingestion/test_job_revalidation_service.py` first** and reuse its fake HTTP client, fake repository and construction helper. Cases:

```python
def test_closure_reason_maps_404_and_410_to_probe_404(): ...
def test_closure_reason_maps_a_200_marker_hit_to_closed_marker(): ...

async def test_a_404_probe_records_probe_404(): ...
async def test_a_dead_end_redirect_records_dead_end_redirect(): ...
async def test_a_200_closed_marker_records_closed_marker(): ...
async def test_expiry_closures_record_expiry(): ...
async def test_sweep_closures_are_recorded_with_no_run_id(): ...
async def test_an_open_verdict_records_nothing(): ...
async def test_service_without_a_recorder_still_sweeps(): ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/ingestion/test_revalidation_history.py -v`
Expected: FAIL with `ImportError: cannot import name 'closure_reason'`

- [ ] **Step 3: Add `closure_reason` to the classifier**

Append to `backend/src/hiresense/ingestion/domain/closed_listing_classifier.py`:

```python
def closure_reason(status_code: int) -> JobClosureReason:
    """Which signal a CLOSED verdict rested on.

    Only meaningful when classify_listing already returned CLOSED. 404/410 is
    the listing being gone; anything else reaching here is a 200 page whose
    body matched a closed-marker phrase.
    """
    if status_code in (404, 410):
        return JobClosureReason.PROBE_404
    return JobClosureReason.CLOSED_MARKER
```

with `from hiresense.ingestion.domain.job_closure_reason import JobClosureReason` at the top. Leave `classify_listing` itself untouched — its existing tests pin its signature.

- [ ] **Step 4: Carry the reason through the probe path**

In `backend/src/hiresense/ingestion/domain/job_revalidation_service.py`:

Add `history: JobHistoryRecorder | None = None` to `__init__` and store as `self._history`.

Change `_probe` to return the reason alongside the verdict:

```python
    async def _probe(self, job: Any) -> tuple[Verdict, JobClosureReason | None]:
        probe_url = self._probe_url(job)
        async with self._sem:
            try:
                status_code, body = await self._fetch_capped(probe_url)
            except _DeadEndRedirect as exc:
                logger.info("Revalidation: dead-end redirect for %s (%s)", probe_url, exc)
                return Verdict.CLOSED, JobClosureReason.DEAD_END_REDIRECT
            except _ProbeBlocked as exc:
                logger.warning("Revalidation probe blocked for %s: %s", probe_url, exc)
                return Verdict.UNKNOWN, None
            except Exception as exc:
                logger.warning("Revalidation probe failed for %s: %s", probe_url, exc)
                return Verdict.UNKNOWN, None
            verdict = classify_listing(
                status_code=status_code,
                body=body,
                markers=self._markers,
            )
            reason = closure_reason(status_code) if verdict == Verdict.CLOSED else None
            return verdict, reason
```

Update `_probe_counted` to match:

```python
    async def _probe_counted(self, job: Any) -> tuple[Verdict, JobClosureReason | None]:
        result = await self._probe(job)
        self._checked_count += 1
        return result
```

Update `_probe_and_close` to group closures by reason — one `record_closures` call per reason rather than one per job:

```python
    async def _probe_and_close(self, jobs: list[Any]) -> list[str]:
        if not jobs:
            return []
        results = await asyncio.gather(*(self._probe_counted(j) for j in jobs))
        by_reason: dict[JobClosureReason, list[str]] = {}
        to_close: list[str] = []
        for job, (verdict, reason) in zip(jobs, results):
            if verdict != Verdict.CLOSED:
                continue
            to_close.append(job.id)
            # reason is always set on a CLOSED verdict; the fallback keeps a
            # future classifier path from silently dropping the closure.
            by_reason.setdefault(reason or JobClosureReason.PROBE_404, []).append(job.id)
        await asyncio.to_thread(self._repo.mark_checked, [j.id for j in jobs])
        if to_close:
            await asyncio.to_thread(self._repo.mark_closed, to_close)
            if self._indexer is not None:
                await self._indexer.remove(to_close)
            if self._history is not None:
                for reason, ids in by_reason.items():
                    # run_id stays None: the sweep is not an ingestion run.
                    self._history.record_closures(ids, reason)
        logger.info("Revalidation: probed %d, closed %d", len(jobs), len(to_close))
        return to_close
```

In `_close_expired`, after `expired` is obtained and the jobs are closed:

```python
        if expired and self._history is not None:
            self._history.record_closures(expired, JobClosureReason.EXPIRY)
```

- [ ] **Step 5: Run the tests**

Run: `uv run python -m pytest tests/unit/ingestion/ -v`
Expected: PASS — including the existing `test_job_revalidation_service.py`. `_probe` changed its return type; if an existing test patches or asserts on it, that is a **real contract change** — update it and note it in the commit body.

- [ ] **Step 6: Full suite, lint, commit**

```bash
cd backend && uv run python -m pytest -q && uv run ruff format src/hiresense/ingestion tests/unit/ingestion && uv run ruff check .
cd .. && git add backend/src/hiresense/ingestion/domain/ backend/tests/unit/ingestion/test_revalidation_history.py
git commit -m "feat(ingestion): record closure reasons from the revalidation sweep"
```

---

### Task 9: Configuration and composition wiring

Nothing above is reachable from the running app until this lands. This is the task that makes the feature real.

**Files:**
- Modify: `backend/src/hiresense/shared/config/groups/ingestion.py`
- Modify: `backend/.env.example`
- Modify: `backend/src/hiresense/composition/ingestion.py` (~line 254 and ~line 276 and ~line 316)
- Modify: `backend/src/hiresense/composition/scheduler.py` (~line 62)
- Modify: `backend/src/hiresense/ingestion/api/provider.py`, `backend/src/hiresense/ingestion/api/dependencies.py`
- Test: `backend/tests/unit/shared/test_config_job_history.py`

**Interfaces:**
- Consumes: everything from Tasks 5–8
- Produces: `settings.job_history_retention_days`; `IngestionProvider.get_job_history()` returning `JobHistoryPort | None`; `get_job_history(request)` FastAPI dependency

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/shared/test_config_job_history.py`:

```python
from __future__ import annotations

from hiresense.shared.config.groups.ingestion import IngestionSettings


def test_job_history_retention_defaults_to_90_days():
    assert IngestionSettings().job_history_retention_days == 90


def test_job_history_retention_can_be_disabled_with_zero():
    assert IngestionSettings(job_history_retention_days=0).job_history_retention_days == 0
```

Confirm the group class's real name with `grep -n "^class" src/hiresense/shared/config/groups/ingestion.py` and use that; the assertions stay the same.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/shared/test_config_job_history.py -v`
Expected: FAIL — no such field

- [ ] **Step 3: Add the setting**

In `backend/src/hiresense/shared/config/groups/ingestion.py`, directly below `ingestion_job_retention_days`:

```python
    # Days to retain per-job history events before pruning, on the same pass
    # that prunes jobs. Independent of ingestion_job_retention_days: history is
    # small per row and is the only record of what a past run did, so it is
    # worth keeping at least as long as the jobs it describes. 0 disables
    # pruning entirely. The FK cascade is a second, independent bound —
    # deleting a job removes its history regardless of age.
    job_history_retention_days: int = Field(default=90, ge=0, le=3650)
```

In `backend/.env.example`, next to `INGESTION_JOB_RETENTION_DAYS`:

```
# Days of per-job audit-trail history to keep (0 = keep forever).
# Pruned on the same pass that prunes jobs.
JOB_HISTORY_RETENTION_DAYS=90
```

- [ ] **Step 4: Wire the recorder**

In `backend/src/hiresense/composition/ingestion.py`, after the two `JobsRepository` constructions (~line 255):

```python
    # One history store shared by the orchestrator and the sweep: the audit
    # trail spans both, and a job's timeline interleaves their events.
    job_history_repo = JobHistoryRepository(session_factory=infra.sync_session_factory)
    job_history_recorder = JobHistoryRecorder(store=job_history_repo)
```

Add to the `IngestionOrchestrator(...)` call:

```python
        history=job_history_recorder,
        history_retention_days=s.job_history_retention_days,
```

Add to the `JobRevalidationService(...)` call:

```python
        history=job_history_recorder,
```

Pass `job_history_repo` into `IngestionProvider(...)` as `job_history=job_history_repo` (the API reads through the port directly; the recorder is a write-side concern).

Add the imports: `JobHistoryRecorder` from `hiresense.ingestion.domain`, `JobHistoryRepository` from `hiresense.ingestion.infrastructure`.

- [ ] **Step 5: Distinguish the scheduler trigger**

In `backend/src/hiresense/composition/scheduler.py` line ~62, replace the bare method reference so scheduled passes are attributable:

```python
            # Bare `ingestion_orchestrator.run` would record every scheduled
            # pass as a manual fetch; the lambda is what makes the two
            # distinguishable in the run history.
            run=lambda: ingestion_orchestrator.run(trigger="scheduler"),
```

- [ ] **Step 6: Expose it to the API layer**

In `backend/src/hiresense/ingestion/api/provider.py`, add a `job_history: JobHistoryPort | None = None` constructor parameter, store it, and add:

```python
    def get_job_history(self) -> JobHistoryPort | None:
        return self._job_history
```

In `backend/src/hiresense/ingestion/api/dependencies.py`, following the defensive pattern already used by `get_semantic_scoring`:

```python
def get_job_history(request: Request) -> JobHistoryPort | None:
    ingestion = getattr(request.app.state, "ingestion", None)
    return ingestion.get_job_history() if ingestion is not None else None
```

- [ ] **Step 7: Run test and verify the app still builds**

Run: `uv run python -m pytest tests/unit/shared/test_config_job_history.py -v && uv run python -c "from hiresense.app import create_app; create_app(); print('app builds')"`
Expected: PASS, then `app builds`

If `create_app` is not the right factory, find it with `grep -rn "def create_app" src/hiresense/`.

- [ ] **Step 8: Full suite, lint, commit**

```bash
cd backend && uv run python -m pytest -q && uv run ruff format src/hiresense tests && uv run ruff check .
cd .. && git add backend/src/hiresense backend/.env.example backend/tests/unit/shared/test_config_job_history.py
git commit -m "feat(ingestion): wire job history recorder and retention setting"
```

---

### Task 10: Three read endpoints

**Files:**
- Modify: `backend/src/hiresense/ingestion/api/routes.py`
- Test: `backend/tests/integration/test_job_history_endpoints.py`

**Interfaces:**
- Consumes: `get_job_history` (Task 9), `JobHistoryPort` (Task 5)
- Produces:
  - `GET /ingestion/jobs/{job_id}/history?limit=50` → `JobHistoryResponse{events: list[JobHistoryEvent]}`
  - `GET /ingestion/runs?limit=25&offset=0` → `IngestionRunsResponse{runs: list[IngestionRunSummary]}`
  - `GET /ingestion/runs/{run_id}` → `IngestionRunDetailResponse{run: IngestionRunSummary, events: list[JobHistoryEvent]}`
  - All on the existing `require_auth` router; all 503 when no history store is wired.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/integration/test_job_history_endpoints.py`. **Read `tests/integration/test_routes.py` first** for the app-building fixture, the `require_auth` override and the SQLite `StaticPool` setup, and reuse them. Cases:

```python
def test_job_history_returns_events_newest_first(): ...
def test_job_history_for_an_unknown_job_returns_an_empty_list(): ...
def test_job_history_respects_the_limit_parameter(): ...
def test_runs_list_returns_newest_first_with_counts(): ...
def test_run_detail_returns_the_run_and_its_events(): ...
def test_run_detail_for_an_unknown_id_returns_404(): ...
def test_all_three_endpoints_require_auth(): ...
def test_endpoints_return_503_when_no_history_store_is_wired(): ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/integration/test_job_history_endpoints.py -v`
Expected: FAIL with 404s — the routes do not exist

- [ ] **Step 3: Add the response models and routes**

In `backend/src/hiresense/ingestion/api/routes.py`, near the other `BaseModel` declarations:

```python
class JobHistoryResponse(BaseModel):
    events: list[JobHistoryEvent]


class IngestionRunsResponse(BaseModel):
    runs: list[IngestionRunSummary]


class IngestionRunDetailResponse(BaseModel):
    run: IngestionRunSummary
    events: list[JobHistoryEvent]
```

Then the endpoints:

```python
def _require_history(history: JobHistoryPort | None) -> JobHistoryPort:
    if history is None:
        raise HTTPException(status_code=503, detail="Job history is not configured")
    return history


@router.get("/jobs/{job_id}/history", response_model=JobHistoryResponse)
async def get_job_history_events(
    job_id: str,
    history: Annotated[JobHistoryPort | None, Depends(get_job_history)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> JobHistoryResponse:
    store = _require_history(history)
    events = await asyncio.to_thread(store.list_events_for_job, job_id, limit)
    return JobHistoryResponse(events=events)


@router.get("/runs", response_model=IngestionRunsResponse)
async def list_ingestion_runs(
    history: Annotated[JobHistoryPort | None, Depends(get_job_history)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> IngestionRunsResponse:
    store = _require_history(history)
    runs = await asyncio.to_thread(store.list_runs, limit, offset)
    return IngestionRunsResponse(runs=runs)


@router.get("/runs/{run_id}", response_model=IngestionRunDetailResponse)
async def get_ingestion_run(
    run_id: str,
    history: Annotated[JobHistoryPort | None, Depends(get_job_history)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> IngestionRunDetailResponse:
    store = _require_history(history)
    run = await asyncio.to_thread(store.get_run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    events = await asyncio.to_thread(store.list_events_for_run, run_id, limit)
    return IngestionRunDetailResponse(run=run, events=events)
```

Add the needed imports: `asyncio`, `get_job_history`, `JobHistoryPort`, `JobHistoryEvent`, `IngestionRunSummary`.

**Ordering note:** `/runs/{run_id}` must be declared *after* `/runs`, or the literal path is shadowed by the parameterised one.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/integration/test_job_history_endpoints.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Full suite, lint, commit**

```bash
cd backend && uv run python -m pytest -q && uv run ruff format src/hiresense tests && uv run ruff check .
cd .. && git add backend/src/hiresense/ingestion/api/routes.py backend/tests/integration/test_job_history_endpoints.py
git commit -m "feat(ingestion): expose job history and ingestion run endpoints"
```

---

### Task 11: Frontend — contracts, routes and service methods

The data layer only. No UI yet, so this task is reviewable on its own.

**Files:**
- Create: `frontend/src/app/core/contracts/job-history-event.model.ts`
- Create: `frontend/src/app/core/contracts/ingestion-run.model.ts`
- Modify: `frontend/src/app/core/contracts/index.ts`
- Modify: `frontend/src/app/core/api/api-routes.ts`
- Modify: `frontend/src/app/core/services/ingestion.service.ts`
- Test: `frontend/src/app/core/services/ingestion.service.spec.ts` (extend)

**Interfaces:**
- Consumes: the three endpoints from Task 10
- Produces:
  - `JobHistoryEvent { jobId: string; event: 'inserted'|'updated'|'reopened'|'closed'; changedFields: Record<string, ChangedValue>; reason: string | null; occurredAt: string }`
  - `ChangedValue = { old: string | null; new: string | null } | { changed: true }`
  - `IngestionRunSummary { id, startedAt, finishedAt, trigger, status, inserted, updated, reopened, closed }`
  - `IngestionRunDetail { run: IngestionRunSummary; events: JobHistoryEvent[] }`
  - `IngestionService.getJobHistory(jobId, limit?)`, `.listRuns(limit?, offset?)`, `.getRun(runId)`

**Naming note:** the backend serialises snake_case (`job_id`, `occurred_at`, `changed_fields`). Check whether the app has a camelCase interceptor — `grep -rn "camel" frontend/src/app/core/interceptors/`. If it does not, declare the interfaces in **snake_case** to match the wire format, and follow whatever the neighbouring contracts in `core/contracts/` already do. Do not introduce a converter for this feature alone.

- [ ] **Step 1: Write the failing test**

Extend `frontend/src/app/core/services/ingestion.service.spec.ts`, following its existing `HttpTestingController` pattern:

```typescript
it('requests job history for a job id', () => {
  service.getJobHistory('job-1').subscribe();
  const req = httpMock.expectOne((r) => r.url.endsWith('/ingestion/jobs/job-1/history'));
  expect(req.request.method).toBe('GET');
  req.flush({ events: [] });
});

it('passes the limit through as a query param', () => {
  service.getJobHistory('job-1', 10).subscribe();
  const req = httpMock.expectOne((r) => r.url.endsWith('/ingestion/jobs/job-1/history'));
  expect(req.request.params.get('limit')).toBe('10');
  req.flush({ events: [] });
});

it('requests the run list with limit and offset', () => {
  service.listRuns(5, 10).subscribe();
  const req = httpMock.expectOne((r) => r.url.endsWith('/ingestion/runs'));
  expect(req.request.params.get('limit')).toBe('5');
  expect(req.request.params.get('offset')).toBe('10');
  req.flush({ runs: [] });
});

it('requests one run by id', () => {
  service.getRun('run-1').subscribe();
  const req = httpMock.expectOne((r) => r.url.endsWith('/ingestion/runs/run-1'));
  expect(req.request.method).toBe('GET');
  req.flush({ run: {}, events: [] });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
export PATH="$HOME/AppData/Roaming/fnm/node-versions/v22.23.1/installation:$PATH"
npm test -- --include "**/ingestion.service.spec.ts"
```
Expected: FAIL — `service.getJobHistory is not a function`

- [ ] **Step 3: Add the routes**

In `frontend/src/app/core/api/api-routes.ts`, inside the `ingestion:` block (line ~79), keeping the existing style:

```typescript
    jobHistory: defineRoute('/ingestion/jobs/:jobId/history'),
    runs: defineRoute('/ingestion/runs'),
    run: defineRoute('/ingestion/runs/:runId'),
```

- [ ] **Step 4: Add the contracts**

Create `frontend/src/app/core/contracts/job-history-event.model.ts`:

```typescript
/** A tracked field's before/after values, or a bare changed flag for large
 *  fields (description) that are recorded as a flag only. */
export type ChangedValue = { old: string | null; new: string | null } | { changed: true };

export type JobHistoryEventType = 'inserted' | 'updated' | 'reopened' | 'closed';

export interface JobHistoryEvent {
  job_id: string;
  event: JobHistoryEventType;
  changed_fields: Record<string, ChangedValue>;
  reason: string | null;
  occurred_at: string;
}
```

Create `frontend/src/app/core/contracts/ingestion-run.model.ts`:

```typescript
import { JobHistoryEvent } from './job-history-event.model';

export interface IngestionRunSummary {
  id: string;
  started_at: string;
  finished_at: string | null;
  trigger: string;
  status: string;
  inserted: number;
  updated: number;
  reopened: number;
  closed: number;
}

export interface IngestionRunDetail {
  run: IngestionRunSummary;
  events: JobHistoryEvent[];
}
```

Re-export both from `frontend/src/app/core/contracts/index.ts`.

- [ ] **Step 5: Add the service methods**

In `frontend/src/app/core/services/ingestion.service.ts`, next to `getJobAnalysis`:

```typescript
  getJobHistory(jobId: string, limit?: number): Observable<{ events: JobHistoryEvent[] }> {
    let params = new HttpParams();
    if (limit !== undefined) params = params.set('limit', String(limit));
    return this.api.get<{ events: JobHistoryEvent[] }>(
      API_ROUTES.ingestion.jobHistory({ jobId }),
      { params },
    );
  }

  listRuns(limit?: number, offset?: number): Observable<{ runs: IngestionRunSummary[] }> {
    let params = new HttpParams();
    if (limit !== undefined) params = params.set('limit', String(limit));
    if (offset !== undefined) params = params.set('offset', String(offset));
    return this.api.get<{ runs: IngestionRunSummary[] }>(API_ROUTES.ingestion.runs(), { params });
  }

  getRun(runId: string): Observable<IngestionRunDetail> {
    return this.api.get<IngestionRunDetail>(API_ROUTES.ingestion.run({ runId }));
  }
```

- [ ] **Step 6: Run test to verify it passes**

Run: `npm test -- --include "**/ingestion.service.spec.ts"`
Expected: PASS

- [ ] **Step 7: Lint, format, commit**

```bash
cd frontend
npx ng lint
npx prettier --write --end-of-line auto "src/app/core/**/*.ts"
cd .. && git add frontend/src/app/core/
git commit -m "feat(ingestion): add job history and run API client"
```

---

### Task 12: Frontend — per-job history timeline

**Files:**
- Create: `frontend/src/app/pages/job/job-history-timeline/job-history-timeline.component.{ts,html,scss,spec.ts}`
- Modify: `frontend/src/app/pages/job/job.component.html`, `job.component.ts`
- Test: the component's own `.spec.ts`

**Interfaces:**
- Consumes: `IngestionService.getJobHistory`, `JobHistoryEvent` (Task 11)
- Produces: `<app-job-history-timeline [jobId]="…" />`

**Empty-state copy (from the spec's open question, which resolved as "do not backfill"):** when a job has no events, render *"No recorded history — this job predates the audit trail, which begins 19 Aug 2026."* Existing jobs get no synthetic events; the empty state has to say so honestly rather than implying nothing ever happened.

- [ ] **Step 1: Write the failing test**

Create the spec with these cases, following the existing standalone-component test setup in `frontend/src/app/pages/admin/scheduler/scheduler.component.spec.ts`:

```typescript
it('renders one entry per event, newest first', () => {});
it('renders an inserted event as "Ingested"', () => {});
it('renders a reopened event as "Reopened"', () => {});
it('renders a closed event with its reason in human words', () => {});
it('renders a tracked field change as "was X, now Y"', () => {});
it('renders a description change as "Description updated" with no values', () => {});
it('renders the predates-the-audit-trail empty state when there are no events', () => {});
it('renders an error state when the request fails', () => {});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --include "**/job-history-timeline.component.spec.ts"`
Expected: FAIL — the component file does not exist

- [ ] **Step 3: Write the component**

Standalone, `ChangeDetectionStrategy.OnPush`, all state in signals — match `scheduler.component.ts`. Requirements:

- `jobId = input.required<string>()`
- `events = signal<JobHistoryEvent[]>([])`, `loading = signal(true)`, `error = signal<string | null>(null)`
- Loads on init via `IngestionService.getJobHistory(this.jobId())`
- A `label(event)` method mapping event type → `Ingested` / `Updated` / `Reopened` / `Closed`
- A `reasonLabel(reason)` method mapping the five reason strings → human words: `probe_404` → "listing returned 404", `closed_marker` → "page says the role is closed", `dead_end_redirect` → "redirected to a generic page", `expiry` → "listing expiry date passed", `snapshot_disappearance` → "disappeared from the source feed"
- A `changes(event)` method turning `changed_fields` into display strings: a `{old,new}` entry → `Salary: was blank, now $180-200K` (empty/null renders as "blank"); a `{changed:true}` entry → `Description updated`

Mount it in `job.component.html` under the existing detail panel.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- --include "**/job-history-timeline.component.spec.ts"`
Expected: PASS (8 tests)

- [ ] **Step 5: Full frontend suite, lint, format, commit**

```bash
cd frontend
npm test && npx ng lint && npx prettier --check --end-of-line auto $(git diff --name-only origin/main...HEAD -- 'frontend/src/**')
cd .. && git add frontend/src/app/pages/job/
git commit -m "feat(ingestion): add per-job history timeline"
```

---

### Task 13: Frontend — ingestion runs page

**Files:**
- Create: `frontend/src/app/pages/admin/runs/runs.component.{ts,html,scss,spec.ts}`
- Modify: `frontend/src/app/app.routes.ts`
- Modify: the admin nav (find it with `grep -rn "admin/scheduler" frontend/src/app --include=*.ts --include=*.html`)

**Interfaces:**
- Consumes: `IngestionService.listRuns` / `.getRun`, `IngestionRunSummary`, `IngestionRunDetail` (Task 11)
- Produces: route `admin/runs` behind `adminGuard`, lazy-loaded, exporting `RunsComponent`

- [ ] **Step 1: Write the failing test**

```typescript
it('renders one row per run with its totals', () => {});
it('shows a running run with no duration', () => {});
it('formats a finished run duration from started_at and finished_at', () => {});
it('labels the trigger as Manual fetch or Scheduled', () => {});
it('expands a row to load and show that run events', () => {});
it('renders an empty state when there are no runs yet', () => {});
it('renders an error state when the request fails', () => {});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --include "**/runs.component.spec.ts"`
Expected: FAIL — the component file does not exist

- [ ] **Step 3: Write the component and register the route**

Standalone + signals + OnPush, modelled on `scheduler.component.ts`. Table columns: Started, Duration, Trigger, Status, Inserted, Updated, Reopened, Closed. A row expands to fetch `getRun(id)` lazily and list that run's events. Wrap the table in an `overflow-x: auto` container.

In `app.routes.ts`, beside the other admin entries:

```typescript
      {
        path: 'admin/runs',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./pages/admin/runs/runs.component').then((m) => m.RunsComponent),
      },
```

Add the nav link next to the existing "Scheduler" entry.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- --include "**/runs.component.spec.ts"`
Expected: PASS (7 tests)

- [ ] **Step 5: Full frontend gates**

```bash
cd frontend
npm test && npm run build && npx ng lint && npx prettier --check --end-of-line auto $(git diff --name-only origin/main...HEAD -- 'frontend/src/**')
```
Expected: all PASS. `ng lint` and `prettier --check` are CI-enforced and are **not** run by `npm test` or `npm run build` — do not skip them.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/pages/admin/runs/ frontend/src/app/app.routes.ts
git commit -m "feat(ingestion): add ingestion run history page"
```

---

### Task 14: Apply the migrations to the dev database and verify end to end

Merged migrations do not auto-upgrade the developer's database — CI runs on SQLite. Skipping this means the app 500s on the first history read with `UndefinedTable`.

**Files:** none — verification only.

- [ ] **Step 1: Confirm the database is reachable**

Run: `docker compose ps db`
Expected: the `db` service is up. If not: `docker compose up -d db`, then wait for it to report healthy.

- [ ] **Step 2: Apply the migrations**

Run: `cd backend && uv run python -m alembic upgrade head`
Expected: `045` and `046` apply cleanly, ending at head `046`

- [ ] **Step 3: Verify the tables and indexes exist**

Run:
```bash
docker compose exec db psql -U hiresense -d hiresense -c "\d job_history_events" -c "\d ingestion_runs"
```
Expected: both tables, the FK to `ingested_jobs` with `ON DELETE CASCADE`, and the three indexes

- [ ] **Step 4: Exercise a real fetch**

Start the backend (`uv run app`) and the frontend, trigger **Fetch jobs**, and confirm:
- `GET /ingestion/runs` returns a run whose totals are non-zero and whose status becomes `completed`
- opening a job that the run touched shows its timeline
- a job the run did not touch shows the predates-the-audit-trail empty state

- [ ] **Step 5: Confirm sweep closures land with reasons**

After the background revalidation sweep finishes, run:
```bash
docker compose exec db psql -U hiresense -d hiresense -c "SELECT reason, count(*) FROM job_history_events WHERE event='closed' GROUP BY reason;"
```
Expected: rows grouped by reason, all with `run_id IS NULL`. **This is the payoff:** the split between `probe_404`, `dead_end_redirect` and `closed_marker` is the first direct evidence of whether the sweep's dead-end-redirect heuristic is over-closing. Report the numbers — do not just note that the query ran.

- [ ] **Step 6: Cross-check the reopen hypothesis**

Run:
```bash
docker compose exec db psql -U hiresense -d hiresense -c "SELECT event, count(*) FROM job_history_events GROUP BY event;"
```
Compare `reopened` against `inserted`. A large `reopened` count confirms the long-standing suspicion that the sweep closes jobs the next fetch immediately reopens — the original question that motivated this feature. Report it either way.

---

## Follow-ups (explicitly NOT in this plan)

- **`PortalScanner` produces no history.** ATS portal scans upsert jobs through the same repository but are not wired to a run or a recorder. Adding them is a self-contained follow-up.
- **No backfill for existing jobs.** Per the spec's resolved open question, the ~4,500 pre-existing jobs get no synthetic `inserted` events; the timeline empty state says so.
- **Run detail has no per-source breakdown.** The spec's API section mentions "per-source counts" on `GET /ingestion/runs/{id}`. `job_history_events` has no `source` column, so per-source totals would require either denormalising `source` onto the event or joining `ingested_jobs`. The run detail ships with per-event-type totals only; per-source is a follow-up that should decide the denormalisation question deliberately.

## Self-Review

Run against the spec after the plan is written:

**Spec coverage** — Schema → Task 1. Capturing the diff → Tasks 3–4. Recording → Tasks 6–8. Retention → Tasks 7, 9. API → Task 10. Frontend (job timeline, runs page) → Tasks 11–13. Open question (backfill) → resolved as "do not backfill", surfaced as the Task 12 empty state. **Gap found and recorded:** the spec's "per-source counts" on run detail has no schema support; captured as an explicit follow-up above rather than silently dropped.

**Placeholder scan** — No TBDs. Tasks 7, 8, 12 and 13 specify test *cases* by name rather than full bodies, because each must reuse an existing fixture (`test_orchestrator.py`, `test_job_revalidation_service.py`, `scheduler.component.spec.ts`) that would be wrong to duplicate blind; each says which file to read first.

**Type consistency** — `changed_fields` is `dict[str, Any]` everywhere (port, ORM, domain model, recorder) and `Record<string, ChangedValue>` on the frontend. `run_id` is `str | None` across the recorder and port, `uuid.UUID` only inside the repository, which converts at both boundaries. `_apply_to_row` returns `tuple[UpsertResult, dict[str, Any]]` in Task 4 and is unpacked at both call sites. `JobHistoryRecorder.record_closures(job_ids, reason, run_id=None)` has the same signature in Tasks 6, 7 and 8.
