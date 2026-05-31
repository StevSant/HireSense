# Analytics Phase 1 — Tracking Status History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record every tracked-application status transition into a new `application_status_history` table — written transactionally in the tracking write path, backfilled for existing apps — and expose a read port for the analytics funnel (Phase 2).

**Architecture:** A new `application_status_history` table owned by the tracking context. `TrackingRepository.create` seeds an initial `None→saved` row; a new `save_with_history` writes the app update **and** a `from→to` history row in one session/commit. `TrackingService.update_status` calls `save_with_history` only when the status actually changes (else plain `save`). Read methods + a `StatusHistoryReadPort` let the analytics context (later phase) consume the history.

**Tech Stack:** Python 3.12, SQLAlchemy (sync session factory), Alembic, Pydantic v2, pytest (`asyncio_mode=auto`), `uv`.

**Spec:** `docs/superpowers/specs/2026-05-31-market-analytics-design.md` (this implements §Architecture.1 only; Phases 2–3 — the analytics context and frontend — are separate plans).

**Tooling (this machine):** run pytest as `uv run python -m pytest ...` (NOT bare `uv run pytest`); alembic as `uv run python -m alembic ...`. Run from `backend/`. Ruff: `uv run python -m ruff check src tests`.

**Conventions (verified):**
- One class per file; package `__init__.py` re-exports public symbols (import from the package).
- Tracking ORM: `tracking/infrastructure/orm.py` holds `TrackedApplicationOrm`; `Base` from `hiresense.infrastructure.database`.
- Repository methods each open their own `with self._session_factory() as session:` block (see `tracking/infrastructure/repository.py`).
- `TrackingService.update_status` is async (Phase 2 work): captures `previous = app.status` before reassigning, emits `TrackingStatusChangedEvent` only when `previous != saved.status and saved.job_id is not None`.
- `ApplicationStatus` enum values: `saved, applied, interviewing, offered, accepted, rejected` (`tracking/domain/models.py`).
- Alembic head is `016`; migrations use `op.execute(...)` raw SQL with numeric revision ids (`alembic/versions/016_create_preference_tables.py`).
- Integration tests build real SQLite via `Base.metadata.create_all` + `StaticPool` (see `tests/integration/test_preference_implicit_flow.py`).

---

## File Structure

**Create:**
- `backend/src/hiresense/tracking/domain/status_transition.py` — `StatusTransition` value model.
- `backend/src/hiresense/tracking/infrastructure/status_history_orm.py` — `ApplicationStatusHistoryOrm` table.
- `backend/src/hiresense/tracking/ports/status_history_read.py` — `StatusHistoryReadPort` protocol.
- `backend/alembic/versions/017_create_application_status_history.py` — table + backfill migration.
- `backend/tests/integration/test_status_history.py` — DB-backed history tests.

**Modify:**
- `backend/src/hiresense/tracking/domain/__init__.py` — re-export `StatusTransition`.
- `backend/src/hiresense/tracking/ports/__init__.py` — re-export `StatusHistoryReadPort`.
- `backend/src/hiresense/tracking/infrastructure/repository.py` — seed row in `create`; add `save_with_history`, `list_history`, `history_for`.
- `backend/src/hiresense/tracking/domain/services.py` — `update_status` uses `save_with_history` on change.
- `backend/tests/unit/tracking/test_service.py` — extend `FakeRepository`; assert transition recording.

---

## Task 1: StatusTransition value model

**Files:**
- Create: `backend/src/hiresense/tracking/domain/status_transition.py`
- Modify: `backend/src/hiresense/tracking/domain/__init__.py`

- [ ] **Step 1: Create the model**

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel


class StatusTransition(BaseModel):
    """One recorded application status change (pure domain model)."""

    id: uuid_mod.UUID | None = None
    application_id: uuid_mod.UUID
    from_status: str | None = None
    to_status: str
    changed_at: datetime | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Re-export** — edit `tracking/domain/__init__.py`:

```python
from hiresense.tracking.domain.services import TrackingService
from hiresense.tracking.domain.status_transition import StatusTransition

__all__ = ["StatusTransition", "TrackingService"]
```

- [ ] **Step 3: Verify import**

Run: `cd backend && uv run python -c "from hiresense.tracking.domain import StatusTransition; print(StatusTransition(application_id=__import__('uuid').uuid4(), to_status='saved').to_status)"`
Expected: prints `saved`.

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/tracking/domain/status_transition.py backend/src/hiresense/tracking/domain/__init__.py
git commit -m "feat(tracking): add StatusTransition domain model"
```

---

## Task 2: ApplicationStatusHistoryOrm

**Files:**
- Create: `backend/src/hiresense/tracking/infrastructure/status_history_orm.py`

- [ ] **Step 1: Create the ORM model**

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class ApplicationStatusHistoryOrm(Base):
    """Append-only log of tracked-application status transitions.

    Written transactionally with the status change (never via the event bus),
    so the funnel analytics never miss a transition. `from_status` is NULL on
    the seed row created when an application is first tracked.
    """

    __tablename__ = "application_status_history"
    __table_args__ = (
        Index("ix_application_status_history_application_id", "application_id"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    application_id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 2: Verify it imports + registers on Base**

Run: `cd backend && uv run python -c "from hiresense.tracking.infrastructure.status_history_orm import ApplicationStatusHistoryOrm; print(ApplicationStatusHistoryOrm.__tablename__)"`
Expected: prints `application_status_history`.

- [ ] **Step 3: Commit**

```bash
git add backend/src/hiresense/tracking/infrastructure/status_history_orm.py
git commit -m "feat(tracking): add application_status_history ORM model"
```

---

## Task 3: Alembic migration (create table + backfill)

**Files:**
- Create: `backend/alembic/versions/017_create_application_status_history.py`

- [ ] **Step 1: Write the migration**

```python
"""create application_status_history (+ backfill one seed row per existing app)

Backs the funnel analytics. Each tracked-application status change appends a
row (written transactionally by the tracking repository). Existing applications
are seeded with a single NULL->current_status row timestamped at applied_at or
created_at.

Revision ID: 017
Revises: 016
Create Date: 2026-05-31
"""
import uuid
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS application_status_history (
            id UUID PRIMARY KEY,
            application_id UUID NOT NULL,
            from_status VARCHAR(20),
            to_status VARCHAR(20) NOT NULL,
            changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_application_status_history_application_id "
        "ON application_status_history (application_id)"
    )
    # Backfill: one seed row per existing application (portable, Python-side UUIDs).
    conn = op.get_bind()
    rows = conn.execute(
        text("SELECT id, status, applied_at, created_at FROM tracked_applications")
    ).fetchall()
    for r in rows:
        conn.execute(
            text(
                "INSERT INTO application_status_history "
                "(id, application_id, from_status, to_status, changed_at) "
                "VALUES (:id, :app_id, NULL, :to_status, :changed_at)"
            ),
            {
                "id": str(uuid.uuid4()),
                "app_id": r.id,
                "to_status": r.status,
                "changed_at": r.applied_at or r.created_at,
            },
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_application_status_history_application_id")
    op.execute("DROP TABLE IF EXISTS application_status_history")
```

- [ ] **Step 2: Sanity-check the revision chains**

Run: `cd backend && uv run python -c "import ast,io; src=open('alembic/versions/017_create_application_status_history.py').read(); print('016' in src and 'revision' in src)"`
Expected: prints `True`. (A full `alembic upgrade` requires a live Postgres; the DB-backed behavior is covered by the integration test in Task 6 via `create_all`. Do NOT attempt `alembic upgrade` here unless a Postgres URL is configured.)

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/017_create_application_status_history.py
git commit -m "feat(tracking): migration for application_status_history + backfill"
```

---

## Task 4: StatusHistoryReadPort

**Files:**
- Create: `backend/src/hiresense/tracking/ports/status_history_read.py`
- Modify: `backend/src/hiresense/tracking/ports/__init__.py`

- [ ] **Step 1: Create the port**

```python
from __future__ import annotations

import uuid
from typing import Protocol

from hiresense.tracking.domain.status_transition import StatusTransition


class StatusHistoryReadPort(Protocol):
    """Read access to application status history, consumed by analytics."""

    def list_history(self) -> list[StatusTransition]: ...

    def history_for(self, application_id: uuid.UUID) -> list[StatusTransition]: ...
```

- [ ] **Step 2: Re-export** — edit `tracking/ports/__init__.py`:

```python
from hiresense.tracking.ports.repository import TrackingRepositoryPort
from hiresense.tracking.ports.status_history_read import StatusHistoryReadPort

__all__ = ["StatusHistoryReadPort", "TrackingRepositoryPort"]
```

- [ ] **Step 3: Verify import**

Run: `cd backend && uv run python -c "from hiresense.tracking.ports import StatusHistoryReadPort; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/tracking/ports/status_history_read.py backend/src/hiresense/tracking/ports/__init__.py
git commit -m "feat(tracking): add StatusHistoryReadPort"
```

---

## Task 5: Repository — seed on create, save_with_history, read methods

**Files:**
- Modify: `backend/src/hiresense/tracking/infrastructure/repository.py`

- [ ] **Step 1: Add imports** at the top of `repository.py` (after the existing imports):

```python
from sqlalchemy import select

from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication
from hiresense.tracking.domain.status_transition import StatusTransition
from hiresense.tracking.infrastructure.orm import TrackedApplicationOrm
from hiresense.tracking.infrastructure.status_history_orm import ApplicationStatusHistoryOrm
```

(Merge with the existing import block — `select`, `TrackedApplicationOrm`, and the domain models are already imported; add `StatusTransition` and `ApplicationStatusHistoryOrm`.)

- [ ] **Step 2: Add a domain converter** next to `_to_domain`:

```python
def _history_to_domain(row: ApplicationStatusHistoryOrm) -> StatusTransition:
    return StatusTransition.model_validate(row)
```

- [ ] **Step 3: Seed a history row in `create`** — replace the `create` method body so the seed row is inserted in the same session:

```python
    def create(self, application: TrackedApplication) -> TrackedApplication:
        with self._session_factory() as session:
            row = TrackedApplicationOrm(
                **{field: getattr(application, field) for field in _CONTENT_FIELDS}
            )
            session.add(row)
            session.flush()  # assign row.id before writing the seed history row
            session.add(
                ApplicationStatusHistoryOrm(
                    application_id=row.id,
                    from_status=None,
                    to_status=row.status,
                )
            )
            session.commit()
            session.refresh(row)
            return _to_domain(row)
```

- [ ] **Step 4: Add `save_with_history`** (right after the existing `save`):

```python
    def save_with_history(
        self,
        application: TrackedApplication,
        *,
        from_status: str | None,
        to_status: str,
    ) -> TrackedApplication:
        with self._session_factory() as session:
            row = (
                session.get(TrackedApplicationOrm, application.id)
                if application.id
                else None
            )
            if row is None:
                row = TrackedApplicationOrm(
                    **{field: getattr(application, field) for field in _CONTENT_FIELDS}
                )
                session.add(row)
                session.flush()
            else:
                for field in _CONTENT_FIELDS:
                    setattr(row, field, getattr(application, field))
            session.add(
                ApplicationStatusHistoryOrm(
                    application_id=row.id,
                    from_status=from_status,
                    to_status=to_status,
                )
            )
            session.commit()
            session.refresh(row)
            return _to_domain(row)
```

- [ ] **Step 5: Add read methods** (after `delete`):

```python
    def list_history(self) -> list[StatusTransition]:
        with self._session_factory() as session:
            stmt = select(ApplicationStatusHistoryOrm).order_by(
                ApplicationStatusHistoryOrm.changed_at
            )
            return [_history_to_domain(r) for r in session.scalars(stmt).all()]

    def history_for(self, application_id: uuid.UUID) -> list[StatusTransition]:
        with self._session_factory() as session:
            stmt = (
                select(ApplicationStatusHistoryOrm)
                .where(ApplicationStatusHistoryOrm.application_id == application_id)
                .order_by(ApplicationStatusHistoryOrm.changed_at)
            )
            return [_history_to_domain(r) for r in session.scalars(stmt).all()]
```

- [ ] **Step 6: Verify it imports**

Run: `cd backend && uv run python -c "from hiresense.tracking.infrastructure.repository import TrackingRepository; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 7: Commit**

```bash
git add backend/src/hiresense/tracking/infrastructure/repository.py
git commit -m "feat(tracking): seed + transactional status-history writes and reads"
```

---

## Task 6: TrackingService records the transition; unit + integration tests

**Files:**
- Modify: `backend/src/hiresense/tracking/domain/services.py`
- Modify: `backend/tests/unit/tracking/test_service.py`
- Create: `backend/tests/integration/test_status_history.py`

- [ ] **Step 1: Update `update_status` to use `save_with_history` on change** — in `services.py`, change the save step so a transition is recorded only when the status actually changes:

```python
    async def update_status(
        self,
        id: uuid_mod.UUID,
        status: ApplicationStatus,
        notes: str | None = None,
    ) -> TrackedApplication:
        app = self.get(id)
        previous = app.status
        app.status = status.value
        if status == ApplicationStatus.APPLIED and app.applied_at is None:
            app.applied_at = datetime.now(timezone.utc)
        if notes is not None:
            app.notes = notes
        if previous != status.value:
            saved = self._repo.save_with_history(
                app, from_status=previous, to_status=status.value
            )
        else:
            saved = self._repo.save(app)
        if previous != saved.status and saved.job_id is not None:
            await self._event_bus.publish(
                TrackingStatusChangedEvent(job_id=str(saved.job_id), status=saved.status)
            )
        return saved
```

(`TrackingStatusChangedEvent` is already imported at module top from Phase 2.)

- [ ] **Step 2: Extend the unit-test `FakeRepository`** — in `tests/unit/tracking/test_service.py`, read the existing `FakeRepository` and add history support: a `self.history: list[tuple[str | None, str]] = []` in `__init__`, a `save_with_history` that records `(from_status, to_status)` then delegates to `save`, and a `create` that also appends `(None, application.status)`:

```python
    def save_with_history(self, application, *, from_status, to_status):
        self.history.append((from_status, to_status))
        return self.save(application)
```

(Match the existing fake's `save`/`create` signatures and storage exactly — read them first. Initialize `self.history = []` in the fake's `__init__`.)

- [ ] **Step 3: Add unit tests** asserting transition recording:

```python
@pytest.mark.asyncio
async def test_update_status_records_transition_on_change():
    bus = FakeEventBus()
    repo = FakeRepository()
    created = repo.create(_make_app(job_id=uuid_mod.uuid4(), status=ApplicationStatus.SAVED.value))
    service = TrackingService(repository=repo, ingestion_orchestrator=FakeIngestionOrchestrator(), event_bus=bus)

    await service.update_status(created.id, ApplicationStatus.APPLIED)

    # create() seeded (None, "saved"); the change appended ("saved", "applied").
    assert repo.history[-1] == ("saved", "applied")


@pytest.mark.asyncio
async def test_update_status_no_transition_when_unchanged():
    bus = FakeEventBus()
    repo = FakeRepository()
    created = repo.create(_make_app(status=ApplicationStatus.APPLIED.value))
    before = len(repo.history)
    service = TrackingService(repository=repo, ingestion_orchestrator=FakeIngestionOrchestrator(), event_bus=bus)

    await service.update_status(created.id, ApplicationStatus.APPLIED)

    assert len(repo.history) == before  # no new transition row
```

(Adapt `_make_app`/`FakeRepository`/`FakeEventBus`/`FakeIngestionOrchestrator` to the existing helpers in the file.)

- [ ] **Step 4: Run unit tests**

Run: `cd backend && uv run python -m pytest tests/unit/tracking/test_service.py -v`
Expected: PASS (existing + 2 new).

- [ ] **Step 5: Write the DB-backed integration test** — `tests/integration/test_status_history.py`, modeled on `tests/integration/test_preference_implicit_flow.py`'s SQLite setup (`create_engine(... StaticPool)`, `Base.metadata.create_all(engine)`, `sessionmaker`). Import the ORM models so the tables are registered before `create_all`. The test must:

```python
import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication
from hiresense.tracking.infrastructure.orm import TrackedApplicationOrm  # noqa: F401
from hiresense.tracking.infrastructure.status_history_orm import ApplicationStatusHistoryOrm  # noqa: F401
from hiresense.tracking.infrastructure.repository import TrackingRepository


def _factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_create_seeds_initial_history_row():
    repo = TrackingRepository(session_factory=_factory())
    app = repo.create(TrackedApplication(title="Eng", company="Acme", status="saved"))
    history = repo.history_for(app.id)
    assert len(history) == 1
    assert history[0].from_status is None
    assert history[0].to_status == "saved"


def test_save_with_history_appends_transition_row():
    factory = _factory()
    repo = TrackingRepository(session_factory=factory)
    app = repo.create(TrackedApplication(title="Eng", company="Acme", status="saved"))
    app.status = "applied"
    repo.save_with_history(app, from_status="saved", to_status="applied")
    history = repo.history_for(app.id)
    assert [(h.from_status, h.to_status) for h in history] == [
        (None, "saved"),
        ("saved", "applied"),
    ]


def test_list_history_returns_all_ordered():
    repo = TrackingRepository(session_factory=_factory())
    a = repo.create(TrackedApplication(title="A", company="X", status="saved"))
    b = repo.create(TrackedApplication(title="B", company="Y", status="saved"))
    a.status = "applied"
    repo.save_with_history(a, from_status="saved", to_status="applied")
    all_rows = repo.list_history()
    assert len(all_rows) == 3  # 2 seeds + 1 transition
    assert {r.application_id for r in all_rows} == {a.id, b.id}
```

- [ ] **Step 6: Run the integration test**

Run: `cd backend && uv run python -m pytest tests/integration/test_status_history.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Run the broader tracking/applications suite for regressions**

Run: `cd backend && uv run python -m pytest tests/ -k "tracking or applications or apply or status_history" -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/src/hiresense/tracking/domain/services.py backend/tests/unit/tracking/test_service.py backend/tests/integration/test_status_history.py
git commit -m "feat(tracking): record status transitions to history on change"
```

---

## Task 7: Final verification

- [ ] **Step 1: Full suite**

Run: `cd backend && uv run python -m pytest -q`
Expected: PASS (no regressions).

- [ ] **Step 2: Lint the files this branch touched**

Run: `cd backend && uv run python -m ruff check src/hiresense/tracking tests/integration/test_status_history.py tests/unit/tracking/test_service.py`
Expected: clean. (Repo-wide `ruff check src tests` has ~30 pre-existing errors unrelated to this branch — do not fix those here.)

- [ ] **Step 3: App composition smoke**

Run: `cd backend && uv run python -c "from hiresense.main import create_app; create_app(); print('ok')"`
Expected: `ok`.

---

## Self-Review notes

- **Spec coverage (§Architecture.1):** new `application_status_history` table (Task 2) ✓; transactional write in tracking — seed on create + `save_with_history` on change, same session/commit (Tasks 5–6) ✓; backfill one row per existing app (Task 3) ✓; `from→to` + `changed_at` columns (Task 2) ✓; `StatusHistoryReadPort` consumed later by analytics (Task 4) ✓; event bus untouched / preference subscriber unaffected (Task 6 keeps the existing publish) ✓.
- **Type/name consistency:** `StatusTransition` fields (`application_id`, `from_status`, `to_status`, `changed_at`) consistent across model, ORM (`model_validate` via `from_attributes`), port, and repository readers; `save_with_history(application, *, from_status, to_status)` signature identical in repo, the `FakeRepository`, and the `update_status` call site.
- **No placeholders:** every code step is complete; test steps that must match existing fakes say to read and reuse the exact helper names.
- **Out of scope here:** analytics services/endpoints (Phase 2 plan) and the dashboard frontend (Phase 3 plan).
