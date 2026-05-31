# Preference Phase 2 — Implicit Signals + Explanation v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Feed tracking-status outcomes back into the taste vector as *implicit* feedback signals (event-driven), and layer an optional LLM-phrased natural-language summary over the deterministic preference explanation.

**Architecture:** A tracking status change publishes a new `TrackingStatusChangedEvent` on the existing in-memory event bus; a subscriber registered in the preference bootstrap maps the status to a `FeedbackKind` and records an *implicit* `FeedbackSignal` (identical pipeline to explicit feedback, `source=IMPLICIT`). Because the bus `publish` is async (`asyncio.create_task`), the status-change path is made async end-to-end. Separately, `PreferenceService.explain()` becomes async and, when enabled and an LLM + job-title lookup are attached, asks the tracked LLM to phrase a one/two-sentence drift summary over the deterministic counts, falling back to `summary=None` on any failure.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy (sync session factory), Pydantic v2, pytest (`asyncio_mode=auto`), `uv`.

**Spec:** `docs/superpowers/specs/2026-05-31-preference-learning-loop-phase2-design.md` (Phase 2). **Scope note:** this plan implements **Part 1 (implicit signals)** and **Part 3 (explanation v2)** ONLY. **Part 2 (dimension-weight nudging) is explicitly deferred** to its own spec — it requires persisting the 6 weighted `DimensionResult` scores per job and threading `job_id` through `MatchingOrchestrator.evaluate()` and both its call sites (the orchestrator currently receives a job dict with no id), which is a matching API-contract change warranting a dedicated design pass.

**No DB migration is required:** new `FeedbackKind` values (`applied`, `interviewing`, `offered`, `accepted`, `rejected`) all fit the existing `feedback_signals.kind VARCHAR(32)` column; `source` already supports `implicit`; the explanation `summary` is an API-only field.

**Tooling note (known trampoline workaround on this machine):** run pytest as `uv run python -m pytest ...` (NOT bare `uv run pytest`). Run from `backend/`. Ruff: `uv run python -m ruff check src tests`.

**Conventions observed (follow exactly):**
- One class/function per file where practical; package `__init__.py` re-exports public symbols (import from the package, not the file).
- Domain events: Pydantic `DomainEvent` subclass with a fixed `event_type` string + fields (see `kernel/events/match_completed.py`). Re-export from `kernel/events/__init__.py`.
- Event bus: `await bus.publish(event)`; `bus.subscribe(event_type, async_handler)` (see `adapters/event_bus/in_memory_bus.py`, `ports/event_bus.py`).
- Bootstrap builders construct services from `SharedInfra` and wire cross-context deps in `main.create_app()`.
- Tests: preference tests are async with inline `FakeRepo`/`FakeVectorStore` (`tests/unit/preference/`); tracking tests use inline `FakeRepository`/`FakeIngestionOrchestrator` (`tests/unit/tracking/`); integration tests use real SQLite + in-process FastAPI (`tests/integration/`).

---

## Current-state reference (verified)

- `FeedbackKind` (`preference/domain/feedback_kind.py`): members THUMBS_UP/THUMBS_DOWN/NOT_INTERESTED/MORE_LIKE_THIS; `_NEGATIVE = frozenset({"thumbs_down", "not_interested", "rejected"})` (already lists `rejected`); `.polarity` (-1 if value in `_NEGATIVE` else +1); `.weight_key` → `f"preference_weight_{self.value}"`.
- `build_preference` (`bootstrap/preference.py`): `weights = {kind: float(getattr(s, kind.weight_key)) for kind in FeedbackKind}` — picks up new weight settings automatically once enum members + settings exist.
- `PreferenceService` (`preference/domain/services.py`): `record_signal(self, job_id: UUID, kind)` is **async**, hardcodes `source=FeedbackSource.EXPLICIT`, snapshots embedding via `self._vector_store.get_vector(str(job_id))`, then `self._recompute()`. `explain(self)` is **sync** today.
- `TrackingService` (`tracking/domain/services.py`): `__init__(self, repository, ingestion_orchestrator)`; `update_status(self, id, status, notes=None)` is **sync**, sets `app.status = status.value`, returns `self._repo.save(app)`. `TrackedApplication.job_id: UUID | None`.
- Event bus `publish` is **async** and dispatches handlers via `asyncio.create_task` (needs a running loop → callers must be async).
- `update_status` callers: `tracking/api/routes.py:100` (PATCH `update_application`, sync), `applications/domain/apply_service.py:163` (`mark_applied`, sync) ← called by `applications/api/routes.py:299` (`mark_applied` route, sync).
- Composition root `main.create_app()`: `tracked = admin.tracked` (line 64, available before preference); `build_preference(infra)` (73); `build_ingestion(infra, tracked, preference_query=preference.service)` (78); `build_tracking(infra, ingestion.orchestrator)` (98). `SharedInfra.event_bus` always present.
- Ingestion orchestrator getter: `IngestionOrchestrator.get_job_by_id(job_id: str) -> NormalizedJob | None` (`ingestion/domain/services.py:130`); `NormalizedJob` has `.title`, `.company`, `.skills`.
- Tracked LLM call interface: `await llm.complete(prompt: str, system: str) -> str` (`matching/domain/scorers/llm_scorer.py:46`).

---

# PART 1 — Implicit signals

## Task 1: Add implicit members to FeedbackKind

**Files:**
- Modify: `backend/src/hiresense/preference/domain/feedback_kind.py`
- Test: `backend/tests/unit/preference/test_feedback_kind.py`

- [ ] **Step 1: Write the failing test** (append to the existing test file)

```python
def test_implicit_kinds_exist_and_have_expected_polarity():
    assert FeedbackKind.APPLIED.value == "applied"
    assert FeedbackKind.INTERVIEWING.value == "interviewing"
    assert FeedbackKind.OFFERED.value == "offered"
    assert FeedbackKind.ACCEPTED.value == "accepted"
    assert FeedbackKind.REJECTED.value == "rejected"
    # Only rejection is negative.
    assert FeedbackKind.APPLIED.polarity == 1
    assert FeedbackKind.INTERVIEWING.polarity == 1
    assert FeedbackKind.OFFERED.polarity == 1
    assert FeedbackKind.ACCEPTED.polarity == 1
    assert FeedbackKind.REJECTED.polarity == -1


def test_implicit_kinds_weight_keys():
    assert FeedbackKind.OFFERED.weight_key == "preference_weight_offered"
    assert FeedbackKind.REJECTED.weight_key == "preference_weight_rejected"
```

(The test file already imports `FeedbackKind`; if not, add `from hiresense.preference.domain import FeedbackKind`.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_feedback_kind.py -v`
Expected: FAIL — `AttributeError: APPLIED`.

- [ ] **Step 3: Add the members** (in `feedback_kind.py`, inside the enum, after the explicit members)

```python
class FeedbackKind(str, enum.Enum):
    # Explicit (Phase 1)
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    NOT_INTERESTED = "not_interested"
    MORE_LIKE_THIS = "more_like_this"

    # Implicit (Phase 2) — emitted from tracking status transitions.
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
```

(`_NEGATIVE` already contains `"rejected"`; do not change it. `polarity`/`weight_key` are unchanged.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_feedback_kind.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/preference/domain/feedback_kind.py backend/tests/unit/preference/test_feedback_kind.py
git commit -m "feat(preference): add implicit FeedbackKind members"
```

---

## Task 2: Add implicit per-kind weight settings

**Files:**
- Modify: `backend/src/hiresense/config.py`
- Modify: `backend/.env.example`

No new test: `build_preference` already maps `{kind: getattr(s, kind.weight_key)}` over all `FeedbackKind`, so missing settings would raise at startup — Task 8's integration test exercises this path.

- [ ] **Step 1: Add settings** — in `config.py`, in the preference block (after `preference_weight_not_interested`), add the tiered implicit magnitudes (polarity is derived from the kind; only `rejected` is negative):

```python
    # Implicit (Phase 2) per-kind magnitudes — outcomes from the tracking pipeline.
    # Tiered: stronger ground-truth outcomes weigh more than a thumbs-up.
    preference_weight_applied: float = 1.0
    preference_weight_interviewing: float = 1.5
    preference_weight_offered: float = 2.5
    preference_weight_accepted: float = 3.0
    preference_weight_rejected: float = 1.5
```

- [ ] **Step 2: Mirror in `.env.example`** — after the existing `PREFERENCE_WEIGHT_NOT_INTERESTED=1.5` line:

```
# Implicit (Phase 2) per-kind magnitudes (tracking outcomes feed the taste vector).
PREFERENCE_WEIGHT_APPLIED=1.0
PREFERENCE_WEIGHT_INTERVIEWING=1.5
PREFERENCE_WEIGHT_OFFERED=2.5
PREFERENCE_WEIGHT_ACCEPTED=3.0
PREFERENCE_WEIGHT_REJECTED=1.5
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/hiresense/config.py backend/.env.example
git commit -m "feat(preference): add implicit-signal weight settings"
```

---

## Task 3: TrackingStatusChangedEvent

**Files:**
- Create: `backend/src/hiresense/kernel/events/tracking_status_changed.py`
- Modify: `backend/src/hiresense/kernel/events/__init__.py`

- [ ] **Step 1: Create the event** (mirror `match_completed.py`)

```python
from __future__ import annotations

from hiresense.kernel.events.base import DomainEvent


class TrackingStatusChangedEvent(DomainEvent):
    """Emitted when a tracked application's status actually changes.

    ``job_id`` is the ingestion job id as a string (None when the tracked
    application is not linked to an ingested job — such events carry no
    embedding-mappable target and are ignored by the preference subscriber).
    """

    event_type: str = "tracking.status_changed"
    job_id: str | None
    status: str
```

- [ ] **Step 2: Re-export** — in `kernel/events/__init__.py`:

```python
from hiresense.kernel.events.base import DomainEvent
from hiresense.kernel.events.jobs_ingested import JobsIngestedEvent
from hiresense.kernel.events.match_completed import MatchCompletedEvent
from hiresense.kernel.events.tracking_status_changed import TrackingStatusChangedEvent

__all__ = [
    "DomainEvent",
    "JobsIngestedEvent",
    "MatchCompletedEvent",
    "TrackingStatusChangedEvent",
]
```

- [ ] **Step 3: Verify import**

Run: `cd backend && uv run python -c "from hiresense.kernel.events import TrackingStatusChangedEvent; print(TrackingStatusChangedEvent(job_id=None, status='applied').event_type)"`
Expected: prints `tracking.status_changed`.

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/kernel/events/tracking_status_changed.py backend/src/hiresense/kernel/events/__init__.py
git commit -m "feat(kernel): add TrackingStatusChangedEvent"
```

---

## Task 4: TrackingService emits the event (async, only on actual change)

**Files:**
- Modify: `backend/src/hiresense/tracking/domain/services.py`
- Test: `backend/tests/unit/tracking/test_service.py`

- [ ] **Step 1: Update the unit test** — add a `FakeEventBus` and assert emission. At the top of `test_service.py`, add:

```python
class FakeEventBus:
    def __init__(self) -> None:
        self.published: list = []

    async def publish(self, event) -> None:
        self.published.append(event)

    def subscribe(self, event_type, handler) -> None:  # not used in these tests
        pass
```

Update the helper that builds the service so it passes a `FakeEventBus` (store it on the test so assertions can read `.published`). Then add:

```python
import pytest
from hiresense.tracking.domain.models import ApplicationStatus


@pytest.mark.asyncio
async def test_update_status_emits_event_on_actual_change():
    bus = FakeEventBus()
    repo = FakeRepository()
    job_id = uuid_mod.uuid4()
    created = repo.create(_make_app(job_id=job_id, status=ApplicationStatus.SAVED.value))
    service = TrackingService(repository=repo, ingestion_orchestrator=FakeIngestionOrchestrator(), event_bus=bus)

    await service.update_status(created.id, ApplicationStatus.APPLIED)

    assert len(bus.published) == 1
    evt = bus.published[0]
    assert evt.event_type == "tracking.status_changed"
    assert evt.status == "applied"
    assert evt.job_id == str(job_id)


@pytest.mark.asyncio
async def test_update_status_no_event_when_status_unchanged():
    bus = FakeEventBus()
    repo = FakeRepository()
    created = repo.create(_make_app(status=ApplicationStatus.APPLIED.value))
    service = TrackingService(repository=repo, ingestion_orchestrator=FakeIngestionOrchestrator(), event_bus=bus)

    await service.update_status(created.id, ApplicationStatus.APPLIED)

    assert bus.published == []


@pytest.mark.asyncio
async def test_update_status_no_event_when_job_id_none():
    bus = FakeEventBus()
    repo = FakeRepository()
    created = repo.create(_make_app(job_id=None, status=ApplicationStatus.SAVED.value))
    service = TrackingService(repository=repo, ingestion_orchestrator=FakeIngestionOrchestrator(), event_bus=bus)

    await service.update_status(created.id, ApplicationStatus.OFFERED)

    assert bus.published == []
```

NOTE: adapt `_make_app(...)`/`FakeRepository.create(...)` to the existing test helpers in this file — read them first. Any existing test that calls `service.update_status(...)` synchronously MUST be converted to `async def` + `await` (and the service constructor call updated to pass `event_bus=FakeEventBus()`). `asyncio_mode=auto` means an `async def test_` needs no decorator, but keep `@pytest.mark.asyncio` consistent with the file's existing style if present.

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run python -m pytest tests/unit/tracking/test_service.py -v`
Expected: FAIL — `TrackingService.__init__` got an unexpected keyword `event_bus` / `update_status` not awaitable.

- [ ] **Step 3: Implement** — edit `tracking/domain/services.py`:

Add `event_bus` to `__init__`:

```python
    def __init__(self, repository: TrackingRepositoryPort, ingestion_orchestrator: Any, event_bus: Any) -> None:
        self._repo = repository
        self._ingestion = ingestion_orchestrator
        self._event_bus = event_bus
```

Make `update_status` async, detect the actual change, save, then emit:

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
        saved = self._repo.save(app)
        if previous != saved.status and saved.job_id is not None:
            from hiresense.kernel.events import TrackingStatusChangedEvent

            await self._event_bus.publish(
                TrackingStatusChangedEvent(job_id=str(saved.job_id), status=saved.status)
            )
        return saved
```

(Import `TrackingStatusChangedEvent` locally inside the method to avoid a module-level import cycle; this mirrors how other domain services reference kernel events at call time.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/tracking/test_service.py -v`
Expected: PASS (all, including the three new tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/tracking/domain/services.py backend/tests/unit/tracking/test_service.py
git commit -m "feat(tracking): emit TrackingStatusChangedEvent on real status change"
```

---

## Task 5: Propagate async to update_status callers

**Files:**
- Modify: `backend/src/hiresense/tracking/api/routes.py`
- Modify: `backend/src/hiresense/applications/domain/apply_service.py`
- Modify: `backend/src/hiresense/applications/api/routes.py`

- [ ] **Step 1: Tracking PATCH route → async** — in `tracking/api/routes.py`, change `update_application` to `async def` and `await` the status call:

```python
@router.patch("/{id}", response_model=TrackedApplicationResponse)
async def update_application(
    id: uuid_mod.UUID,
    request: UpdateApplicationRequest,
    service: TrackingService = Depends(get_tracking_service),
    orchestrator: IngestionOrchestrator = Depends(get_ingestion_orchestrator),
) -> TrackedApplicationResponse:
    try:
        if request.status is not None:
            app = await service.update_status(id, request.status, notes=request.notes)
        elif request.notes is not None:
            app = service.update_notes(id, request.notes)
        else:
            app = service.get(id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _enrich(app, orchestrator)
```

- [ ] **Step 2: `mark_applied` service → async** — in `applications/domain/apply_service.py`:

```python
    async def mark_applied(self, application_id: uuid.UUID) -> None:
        # Idempotent: set status=APPLIED, set applied_at if not already set.
        await self._tracking.update_status(
            application_id,
            ApplicationStatus.APPLIED,
        )
```

- [ ] **Step 3: `mark_applied` route → async** — in `applications/api/routes.py` (the `@router.post("/{application_id}/mark-applied")` handler):

```python
@router.post("/{application_id}/mark-applied", response_model=ApplicationAggregate)
async def mark_applied(
    application_id: uuid_mod.UUID,
    apply_service: ApplyService = Depends(get_apply_service),
    app_service: ApplicationService = Depends(get_application_service),
) -> ApplicationAggregate:
    try:
        await apply_service.mark_applied(application_id)
        return app_service.get(application_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 4: Verify no other sync caller remains**

Run: `cd backend && uv run python -m pytest tests/ -k "tracking or applications or apply" -q`
Expected: PASS (fix any test that calls `update_status`/`mark_applied` synchronously by awaiting it in an async test). Also grep to be safe: `grep -rn "update_status(\|mark_applied(" backend/src backend/tests` and confirm every call site is awaited.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/tracking/api/routes.py backend/src/hiresense/applications/domain/apply_service.py backend/src/hiresense/applications/api/routes.py
git commit -m "refactor(tracking,applications): await async update_status across call sites"
```

---

## Task 6: Inject the event bus in bootstrap/tracking.py

**Files:**
- Modify: `backend/src/hiresense/bootstrap/tracking.py`

- [ ] **Step 1: Pass `infra.event_bus`**

```python
def build_tracking(infra: SharedInfra, ingestion_orchestrator: Any) -> TrackingBuild:
    tracking_repo = TrackingRepository(session_factory=infra.sync_session_factory)
    tracking_service = TrackingService(
        repository=tracking_repo,
        ingestion_orchestrator=ingestion_orchestrator,
        event_bus=infra.event_bus,
    )
    provider = TrackingProvider(tracking_service=tracking_service)
    return TrackingBuild(provider=provider, service=tracking_service)
```

- [ ] **Step 2: Verify the app still builds**

Run: `cd backend && uv run python -c "from hiresense.main import create_app; create_app(); print('ok')"`
Expected: prints `ok` (no wiring errors). If the model loads slowly, that's fine — success is the `ok` line.

- [ ] **Step 3: Commit**

```bash
git add backend/src/hiresense/bootstrap/tracking.py
git commit -m "feat(tracking): wire event bus into TrackingService"
```

---

## Task 7: PreferenceService.record_implicit_signal (factor shared body)

**Files:**
- Modify: `backend/src/hiresense/preference/domain/services.py`
- Test: `backend/tests/unit/preference/test_preference_service.py`

- [ ] **Step 1: Write the failing test** (append; mirror the existing async style + `FakeRepo`/`FakeVectorStore`)

```python
@pytest.mark.asyncio
async def test_record_implicit_signal_sets_source_implicit():
    repo = FakeRepo()
    store = FakeVectorStore({str(JOB_ID): [0.1, 0.2, 0.3]})  # adapt to existing fake ctor
    service = _build_service(repo=repo, store=store)  # adapt to existing builder/fixture

    signal = await service.record_implicit_signal(JOB_ID, FeedbackKind.OFFERED)

    assert signal.source == FeedbackSource.IMPLICIT
    assert signal.kind == FeedbackKind.OFFERED
    stored = repo.list_signals()
    assert any(s.source == FeedbackSource.IMPLICIT for s in stored)


@pytest.mark.asyncio
async def test_record_signal_still_explicit():
    repo = FakeRepo()
    store = FakeVectorStore({str(JOB_ID): [0.1, 0.2, 0.3]})
    service = _build_service(repo=repo, store=store)

    signal = await service.record_signal(JOB_ID, FeedbackKind.THUMBS_UP)

    assert signal.source == FeedbackSource.EXPLICIT
```

(Read the existing tests to reuse their `FakeRepo`, `FakeVectorStore`, `JOB_ID`, and service-construction helper; match names exactly. Import `FeedbackSource` from `hiresense.preference.domain`.)

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_preference_service.py -v`
Expected: FAIL — `PreferenceService` has no `record_implicit_signal`.

- [ ] **Step 3: Factor the shared body** — in `preference/domain/services.py`, replace `record_signal` with a private `_record` + two thin public methods:

```python
    async def _record(
        self, job_id: uuid_mod.UUID, kind: FeedbackKind, source: FeedbackSource
    ) -> FeedbackSignal:
        embedding: list[float] | None = None
        if self._vector_store is not None:
            try:
                embedding = await self._vector_store.get_vector(str(job_id))
            except Exception:
                logger.exception("preference: get_vector failed for %s", job_id)
        if embedding is None:
            logger.debug(
                "preference: no embedding for job %s (not indexed yet?) — "
                "signal stored, no contribution",
                job_id,
            )
        signal = self._repo.add_signal(
            FeedbackSignal(
                job_id=job_id,
                kind=kind,
                source=source,
                job_embedding=embedding,
            )
        )
        self._recompute()
        return signal

    async def record_signal(self, job_id: uuid_mod.UUID, kind: FeedbackKind) -> FeedbackSignal:
        return await self._record(job_id, kind, FeedbackSource.EXPLICIT)

    async def record_implicit_signal(
        self, job_id: uuid_mod.UUID, kind: FeedbackKind
    ) -> FeedbackSignal:
        return await self._record(job_id, kind, FeedbackSource.IMPLICIT)
```

(Keep all existing imports; `FeedbackSource` is already imported in this module.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_preference_service.py -v`
Expected: PASS (existing + new). The existing API route `submit_feedback` already does `await service.record_signal(...)` — unchanged.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/preference/domain/services.py backend/tests/unit/preference/test_preference_service.py
git commit -m "feat(preference): add record_implicit_signal via shared _record"
```

---

## Task 8: Status→kind mapping + subscriber, registered in bootstrap

**Files:**
- Create: `backend/src/hiresense/preference/domain/implicit_signal_mapping.py`
- Modify: `backend/src/hiresense/preference/domain/__init__.py` (re-export the mapping fn)
- Modify: `backend/src/hiresense/bootstrap/preference.py` (register subscriber)
- Test (unit): `backend/tests/unit/preference/test_implicit_signal_mapping.py`
- Test (integration): `backend/tests/integration/test_preference_implicit_flow.py`

- [ ] **Step 1: Write the mapping unit test**

```python
from hiresense.preference.domain import FeedbackKind, status_to_feedback_kind


def test_status_to_feedback_kind_mapping():
    assert status_to_feedback_kind("applied") == FeedbackKind.APPLIED
    assert status_to_feedback_kind("interviewing") == FeedbackKind.INTERVIEWING
    assert status_to_feedback_kind("offered") == FeedbackKind.OFFERED
    assert status_to_feedback_kind("accepted") == FeedbackKind.ACCEPTED
    assert status_to_feedback_kind("rejected") == FeedbackKind.REJECTED


def test_saved_status_has_no_signal():
    assert status_to_feedback_kind("saved") is None
    assert status_to_feedback_kind("unknown") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_implicit_signal_mapping.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Implement the mapping** — `preference/domain/implicit_signal_mapping.py`:

```python
from __future__ import annotations

from hiresense.preference.domain.feedback_kind import FeedbackKind

# Tracking status string -> implicit FeedbackKind. SAVED (and anything unknown)
# produces no signal: saving a job is not yet an outcome.
_STATUS_TO_KIND: dict[str, FeedbackKind] = {
    "applied": FeedbackKind.APPLIED,
    "interviewing": FeedbackKind.INTERVIEWING,
    "offered": FeedbackKind.OFFERED,
    "accepted": FeedbackKind.ACCEPTED,
    "rejected": FeedbackKind.REJECTED,
}


def status_to_feedback_kind(status: str) -> FeedbackKind | None:
    return _STATUS_TO_KIND.get(status)
```

- [ ] **Step 4: Re-export** — in `preference/domain/__init__.py`, add `status_to_feedback_kind` to the imports and `__all__`:

```python
from hiresense.preference.domain.implicit_signal_mapping import status_to_feedback_kind
```
(and add `"status_to_feedback_kind"` to `__all__`).

- [ ] **Step 5: Run the mapping test → PASS**

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_implicit_signal_mapping.py -v`
Expected: PASS.

- [ ] **Step 6: Register the subscriber** — in `bootstrap/preference.py`, after the `service` is constructed and before returning, subscribe a handler on the bus:

```python
import logging
import uuid as uuid_mod

from hiresense.kernel.events import TrackingStatusChangedEvent
from hiresense.preference.domain import status_to_feedback_kind

logger = logging.getLogger(__name__)
```

Inside `build_preference`, after building `service`:

```python
    async def _on_status_changed(event: TrackingStatusChangedEvent) -> None:
        kind = status_to_feedback_kind(event.status)
        if kind is None or event.job_id is None:
            return
        try:
            await service.record_implicit_signal(uuid_mod.UUID(event.job_id), kind)
        except Exception:
            logger.exception("preference: implicit signal failed for job %s", event.job_id)

    infra.event_bus.subscribe(TrackingStatusChangedEvent().event_type, _on_status_changed)
```

NOTE: `TrackingStatusChangedEvent().event_type` requires the event to be constructible with no args — but it has required fields. Instead subscribe with the literal class default: use `TrackingStatusChangedEvent.model_fields["event_type"].default` OR simply the string `"tracking.status_changed"`. Use the string constant to avoid constructing an event:

```python
    infra.event_bus.subscribe("tracking.status_changed", _on_status_changed)
```

- [ ] **Step 7: Write the integration test** — `tests/integration/test_preference_implicit_flow.py`, modeled on `tests/integration/test_preference_flow.py` (real SQLite, in-process FastAPI, fake vector store, auth override). It must:
  1. Build the app (or wire `build_preference` + `build_tracking` against a shared `InMemoryEventBus` and a real preference repo + fake vector store).
  2. Create a tracked application linked to a `job_id` for which the fake vector store returns an embedding.
  3. PATCH the tracked application status to `offered`.
  4. Because the bus dispatches via `asyncio.create_task`, `await asyncio.sleep(0)` (or a short poll) after the PATCH so the handler runs.
  5. Assert a `FeedbackSignal` now exists with `source=IMPLICIT`, `kind=offered`, and that `GET /preference/explain` reflects `total_signals >= 1` / a non-zero positive count.

Use the existing integration test's helpers/fixtures as the template; match its app-construction and auth-override approach exactly. Keep the fake vector store returning a fixed-dim vector for the linked job id.

- [ ] **Step 8: Run the integration test**

Run: `cd backend && uv run python -m pytest tests/integration/test_preference_implicit_flow.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/src/hiresense/preference/domain/implicit_signal_mapping.py backend/src/hiresense/preference/domain/__init__.py backend/src/hiresense/bootstrap/preference.py backend/tests/unit/preference/test_implicit_signal_mapping.py backend/tests/integration/test_preference_implicit_flow.py
git commit -m "feat(preference): subscribe to tracking events and record implicit signals"
```

---

# PART 3 — Explanation v2 (LLM phrasing)

## Task 9: Add the explanation-enabled setting

**Files:**
- Modify: `backend/src/hiresense/config.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Add the setting** (in the preference block of `config.py`):

```python
    # Phase 2: layer an LLM-phrased natural-language drift summary over the
    # deterministic explanation. Falls back to summary=None on any LLM failure.
    preference_explanation_enabled: bool = True
```

- [ ] **Step 2: `.env.example`**:

```
# Phase 2: enable the LLM-phrased preference drift summary (true/false).
PREFERENCE_EXPLANATION_ENABLED=true
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/hiresense/config.py backend/.env.example
git commit -m "feat(preference): add preference_explanation_enabled setting"
```

---

## Task 10: Add `summary` to PreferenceExplanation

**Files:**
- Modify: `backend/src/hiresense/preference/domain/explanation.py`
- Test: `backend/tests/unit/preference/test_explanation.py`

- [ ] **Step 1: Add the field + assert deterministic builder leaves it None** — add to `test_explanation.py`:

```python
def test_build_explanation_summary_defaults_none():
    exp = build_explanation([], delta_vector=None)
    assert exp.summary is None
```

- [ ] **Step 2: Run → FAIL** (`summary` not a field).

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_explanation.py -v`

- [ ] **Step 3: Add the field** — in `explanation.py`, on `PreferenceExplanation`:

```python
class PreferenceExplanation(BaseModel):
    active: bool
    total_signals: int
    positive_count: int
    negative_count: int
    counts_by_kind: dict[str, int]
    drift_magnitude: float
    summary: str | None = None
```

(`build_explanation` is unchanged — it never sets `summary`, so it stays `None`.)

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/preference/domain/explanation.py backend/tests/unit/preference/test_explanation.py
git commit -m "feat(preference): add optional summary field to PreferenceExplanation"
```

---

## Task 11: Async explain() with optional LLM summary

**Files:**
- Modify: `backend/src/hiresense/preference/domain/services.py`
- Test: `backend/tests/unit/preference/test_preference_service.py`

The service gains optional, late-bindable explanation dependencies. Construction stays backward-compatible (defaults make explain() purely deterministic).

- [ ] **Step 1: Write the failing tests** (append)

```python
class _FakeLLM:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[tuple[str, str]] = []

    async def complete(self, prompt: str, system: str) -> str:
        self.calls.append((prompt, system))
        return self._text


class _FakeJobLookup:
    def __init__(self, titles: dict[str, str]) -> None:
        self._titles = titles

    def get_job_by_id(self, job_id: str):
        title = self._titles.get(job_id)
        if title is None:
            return None
        return type("J", (), {"title": title, "company": "Acme", "skills": []})()


@pytest.mark.asyncio
async def test_explain_is_deterministic_when_llm_not_attached():
    service = _build_service()  # no explainer attached
    exp = await service.explain()
    assert exp.summary is None


@pytest.mark.asyncio
async def test_explain_adds_llm_summary_when_enabled_and_attached():
    repo = FakeRepo()
    store = FakeVectorStore({str(JOB_ID): [0.1, 0.2, 0.3]})
    service = _build_service(repo=repo, store=store, explanation_enabled=True)
    await service.record_signal(JOB_ID, FeedbackKind.THUMBS_UP)
    llm = _FakeLLM("Leaning toward remote backend roles.")
    service.attach_explainer(llm=llm, job_lookup=_FakeJobLookup({str(JOB_ID): "Backend Engineer"}))

    exp = await service.explain()

    assert exp.summary == "Leaning toward remote backend roles."
    assert llm.calls  # the LLM was actually consulted


@pytest.mark.asyncio
async def test_explain_falls_back_when_llm_raises():
    repo = FakeRepo()
    store = FakeVectorStore({str(JOB_ID): [0.1, 0.2, 0.3]})
    service = _build_service(repo=repo, store=store, explanation_enabled=True)
    await service.record_signal(JOB_ID, FeedbackKind.THUMBS_UP)

    class _BoomLLM:
        async def complete(self, prompt: str, system: str) -> str:
            raise RuntimeError("llm down")

    service.attach_explainer(llm=_BoomLLM(), job_lookup=_FakeJobLookup({str(JOB_ID): "Backend Engineer"}))

    exp = await service.explain()
    assert exp.summary is None  # graceful fallback; deterministic fields intact
    assert exp.total_signals == 1
```

(Adapt `_build_service` to accept an `explanation_enabled` kwarg if the existing helper doesn't already pass through to the constructor; if there is no helper, construct `PreferenceService(...)` directly with the existing required args plus the new optional ones.)

- [ ] **Step 2: Run → FAIL** (no `attach_explainer`; `explain` not awaitable).

- [ ] **Step 3: Implement** — in `PreferenceService`:

Extend `__init__` to accept the new optional deps (add params with defaults at the END so existing positional/keyword construction is unaffected; all current call sites use keyword args):

```python
    def __init__(
        self,
        *,
        repository: Any,
        vector_store: Any,
        calculator: TasteVectorCalculator,
        weights: dict[FeedbackKind, float],
        enabled: bool,
        llm: Any | None = None,
        explanation_enabled: bool = False,
    ) -> None:
        self._repo = repository
        self._vector_store = vector_store
        self._calc = calculator
        self._weights = weights
        self._enabled = enabled
        self._llm = llm
        self._explanation_enabled = explanation_enabled
        self._job_lookup: Any | None = None
```

Add the late-binding setter:

```python
    def attach_explainer(self, *, llm: Any, job_lookup: Any) -> None:
        """Late-bind the explanation LLM + job-title lookup (two-phase wiring:
        the ingestion orchestrator is built after the preference service)."""
        self._llm = llm
        self._job_lookup = job_lookup
```

Make `explain` async and layer the summary:

```python
    async def explain(self) -> PreferenceExplanation:
        model = self._repo.get_model()
        delta = model.delta_vector if model is not None else None
        signals = self._repo.list_signals()
        explanation = build_explanation(signals, delta_vector=delta)
        if self._explanation_enabled and self._llm is not None:
            summary = await self._build_summary(signals, explanation)
            if summary:
                explanation = explanation.model_copy(update={"summary": summary})
        return explanation

    async def _build_summary(
        self, signals: list[FeedbackSignal], explanation: PreferenceExplanation
    ) -> str | None:
        try:
            pos_titles = self._titles_for([s for s in signals if s.kind.polarity > 0])
            neg_titles = self._titles_for([s for s in signals if s.kind.polarity < 0])
            if not pos_titles and not neg_titles:
                return None
            prompt = (
                "Summarize the candidate's evolving job preferences in one or two "
                "short sentences, plain and specific.\n"
                f"Liked/positively-signaled roles: {', '.join(pos_titles) or 'none'}.\n"
                f"Disliked/negatively-signaled roles: {', '.join(neg_titles) or 'none'}.\n"
                f"Total signals: {explanation.total_signals} "
                f"({explanation.positive_count} positive, {explanation.negative_count} negative)."
            )
            system = (
                "You phrase a concise preference drift summary. One or two sentences. "
                "No preamble, no JSON, no bullet points."
            )
            text = await self._llm.complete(prompt, system=system)
            text = (text or "").strip()
            return text or None
        except Exception:
            logger.exception("preference: LLM explanation failed — using deterministic only")
            return None

    def _titles_for(self, signals: list[FeedbackSignal]) -> list[str]:
        if self._job_lookup is None:
            return []
        titles: list[str] = []
        for s in signals:
            try:
                job = self._job_lookup.get_job_by_id(str(s.job_id))
            except Exception:
                job = None
            if job is not None and getattr(job, "title", None):
                titles.append(job.title)
        return titles[:10]  # cap prompt size; dedup-free is fine for a summary
```

- [ ] **Step 4: Run → PASS** (the new tests + existing).

Run: `cd backend && uv run python -m pytest tests/unit/preference/test_preference_service.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/preference/domain/services.py backend/tests/unit/preference/test_preference_service.py
git commit -m "feat(preference): async explain with optional LLM-phrased summary"
```

---

## Task 12: Wire explain route + bootstrap + two-phase attach

**Files:**
- Modify: `backend/src/hiresense/preference/api/routes.py`
- Modify: `backend/src/hiresense/bootstrap/preference.py`
- Modify: `backend/src/hiresense/main.py`

- [ ] **Step 1: Make the explain route async** — in `preference/api/routes.py`:

```python
@router.get("/explain", response_model=PreferenceExplanation)
async def explain(
    service: PreferenceService = Depends(get_preference_service),
) -> PreferenceExplanation:
    return await service.explain()
```

- [ ] **Step 2: bootstrap/preference.py — accept `tracked`, pass LLM + enabled flag** — change the signature and construction:

```python
from collections.abc import Callable
from typing import Any


def build_preference(infra: SharedInfra, tracked: Callable[[str], Any]) -> PreferenceBuild:
    s = infra.settings
    calculator = TasteVectorCalculator(
        alpha=s.preference_alpha,
        beta=s.preference_beta,
        gamma=s.preference_gamma,
        tau_days=s.preference_decay_tau_days,
    )
    weights = {kind: float(getattr(s, kind.weight_key)) for kind in FeedbackKind}
    service = PreferenceService(
        repository=PreferenceRepository(session_factory=infra.sync_session_factory),
        vector_store=infra.vector_store,
        calculator=calculator,
        weights=weights,
        enabled=s.preference_enabled,
        llm=tracked("preference_explanation") if s.preference_explanation_enabled else None,
        explanation_enabled=s.preference_explanation_enabled,
    )
    # (subscriber registration from Task 8 stays here)
    ...
    return PreferenceBuild(provider=PreferenceProvider(preference_service=service), service=service)
```

- [ ] **Step 3: main.py — pass `tracked` and late-bind the job lookup** — `tracked` is defined at line 64 (before preference). Update the preference build call and, after ingestion is built, attach the job lookup:

```python
    # --- Preference (taste-vector learning; consumed by ingestion pre-ranking) ---
    preference = build_preference(infra, tracked)
    app.state.preference = preference.provider
    app.include_router(preference_router)

    # --- Ingestion (uses the tracked-LLM factory for match scoring) ---
    ingestion = build_ingestion(infra, tracked, preference_query=preference.service)
    app.state.ingestion = ingestion.provider
    app.include_router(ingestion_router)
    # Two-phase wiring: ingestion is built after preference, so attach the
    # job-title lookup used by the LLM explanation summary now.
    preference.service.attach_explainer(
        llm=preference.service._llm, job_lookup=ingestion.orchestrator
    )
```

NOTE: reaching `preference.service._llm` is awkward. Cleaner: have `attach_explainer` accept only `job_lookup` and keep the already-set `llm` from construction. Adjust the Task 11 setter to:

```python
    def attach_job_lookup(self, job_lookup: Any) -> None:
        self._job_lookup = job_lookup
```

and in Task 11's tests use `attach_explainer(llm=..., job_lookup=...)`. To satisfy BOTH the unit tests (which set the llm) and the two-phase wiring (which only needs the lookup), provide both methods:

```python
    def attach_explainer(self, *, llm: Any, job_lookup: Any) -> None:
        self._llm = llm
        self._job_lookup = job_lookup

    def attach_job_lookup(self, job_lookup: Any) -> None:
        self._job_lookup = job_lookup
```

Then main.py uses the clean call:

```python
    preference.service.attach_job_lookup(ingestion.orchestrator)
```

(Implementer: add `attach_job_lookup` to the Task 11 implementation as well — update Task 11's service code to include both setters before this task runs, or add it here and re-run Task 11's tests.)

- [ ] **Step 4: Verify app builds + explain works end-to-end**

Run: `cd backend && uv run python -c "from hiresense.main import create_app; create_app(); print('ok')"`
Expected: prints `ok`.

Run the preference integration tests:
`cd backend && uv run python -m pytest tests/integration/test_preference_flow.py tests/integration/test_preference_implicit_flow.py -v`
Expected: PASS (explain still returns; summary is None unless an LLM is wired in the test).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/preference/api/routes.py backend/src/hiresense/bootstrap/preference.py backend/src/hiresense/main.py backend/src/hiresense/preference/domain/services.py
git commit -m "feat(preference): wire async explain + two-phase LLM explainer attach"
```

---

## Task 13: Final verification

- [ ] **Step 1: Full backend test suite**

Run: `cd backend && uv run python -m pytest -q`
Expected: PASS (no regressions across tracking, applications, preference, matching, ingestion).

- [ ] **Step 2: Lint**

Run: `cd backend && uv run python -m ruff check src tests`
Expected: clean (no errors).

- [ ] **Step 3: App composition smoke**

Run: `cd backend && uv run python -c "from hiresense.main import create_app; create_app(); print('ok')"`
Expected: `ok`.

---

## Self-Review notes

- **Spec coverage (Parts 1 & 3):** implicit signal capture via a tracking event the preference context subscribes to (Tasks 3–8) ✓; the five implicit `FeedbackKind` members with config-driven tiered weights, `rejected` negative (Tasks 1–2) ✓; `record_implicit_signal` reusing the explicit pipeline with `source=IMPLICIT` (Task 7) ✓; emit only on actual status change, skip `job_id is None` (Task 4) ✓; explanation v2 LLM phrasing over the deterministic summary with graceful fallback + enable setting (Tasks 9–12) ✓; Phase 1 safety preserved — defaults make explain() deterministic, no behavior change without an LLM (Tasks 10–12) ✓.
- **Part 2 (weight nudging) deferred** with a documented reason (needs dimension-score persistence + `job_id` threading through the matching contract) — out of scope here, its own spec.
- **Type/name consistency:** `status_to_feedback_kind` used in mapping test + subscriber; `record_implicit_signal`/`record_signal` both async via `_record`; `attach_explainer`/`attach_job_lookup` both provided so Task 11 tests and Task 12 wiring agree; event subscribed by the literal `"tracking.status_changed"` matching the event's `event_type`.
- **Async propagation:** `update_status` → tracking PATCH route, `apply_service.mark_applied` → applications mark-applied route, plus existing tests, all awaited (Tasks 4–5).
- **No placeholders:** every code step contains complete code; where a fake/fixture must match existing test scaffolding, the step says to read and reuse the existing helper names.
