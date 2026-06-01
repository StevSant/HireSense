# Proactive Auto-Hunt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new read-only `autohunt` bounded context whose `POST /autohunt/run` (external-cron-triggered) computes the top-N new, taste-ranked, above-floor job matches since the last run and persists a `Digest`; `GET /autohunt/digests` + `/latest` serve them in-app.

**Architecture:** `AutoHuntService.run()` orchestrates existing ports — ingestion's bucket-scoped jobs repo (new `list_since` method), the shared taste-aware `SemanticPreRanker`, and the profile — then persists a `Digest` via a new `DigestRepository`. Each run persists exactly one digest row whose `created_at` is the watermark for the next run. Wired as a new context built after ingestion + profile.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy (sync session factory), Alembic, Pydantic v2, pytest (`asyncio_mode=auto`), `uv`.

**Spec:** `docs/superpowers/specs/2026-05-31-proactive-auto-hunt-design.md`. Scope is **digest only** (pre-drafted applications, email, and the frontend view are out of scope / future specs).

**Tooling (this machine):** pytest = `uv run python -m pytest ...` (NOT bare); from `backend/`. Ruff: `uv run python -m ruff check <paths>`.

**Verified integration facts:**
- `JobsRepository(session_factory, *, bucket)` is **bucket-scoped**; `_to_domain(row) -> NormalizedJob` converter exists; `list_all` does `select(IngestedJob).where(IngestedJob.bucket == self._bucket)` → `[_to_domain(r) ...]`. `IngestedJob` has `fetched_at` (immutable, indexed via `ix_ingested_jobs_bucket_fetched_at`), `status` ("open"/"closed"). `NormalizedJob` has `.id, .title, .company, .url, .match_score` (match_score set by the pre-ranker).
- `SemanticPreRanker.rerank(jobs, skill_by_id, candidate_skills, candidate_summary, bucket) -> list[NormalizedJob]` (async); falls back to passthrough when the vector store/embedding is unavailable; already applies `preference.query_vector`.
- `ProfileService.get_for_language(language) -> ProfileLanguageView | None` with `.skills: list[str]`, `.summary: str`. `Settings.default_language = "en"`.
- `IngestionBuild` (frozen dataclass) currently exposes `provider`, `orchestrator`. The builder has locals `boards_jobs_repo` (a `JobsRepository` bucket="boards") and `pre_ranker` (a `SemanticPreRanker`).
- Bootstrap/API patterns: provider holds the service; `dependencies.py` reads `request.app.state.autohunt.get_autohunt_service()`; router `APIRouter(prefix="/autohunt", tags=["autohunt"], dependencies=[Depends(require_auth)])`; builder returns a frozen `AutoHuntBuild(provider, service)`; wired in `main.create_app()`.
- Alembic head is `017` → new migration `018`. Preference/tracking contexts are the persistence-stack template (domain model + ORM + repository + port). Integration tests: in-memory SQLite + `StaticPool` + `Base.metadata.create_all`, override `require_auth` → `"test-user"`, `AsyncClient(transport=ASGITransport(app=app))`.

---

## File Structure

**Create (`backend/src/hiresense/autohunt/`):**
- `domain/digest_entry.py` — `DigestEntry`.
- `domain/digest.py` — `Digest`.
- `domain/autohunt_service.py` — `AutoHuntService`.
- `domain/__init__.py` — re-exports.
- `infrastructure/orm.py` — `DigestOrm`.
- `infrastructure/repository.py` — `DigestRepository`.
- `infrastructure/__init__.py` — re-export.
- `ports/repository.py` — `DigestRepositoryPort`.
- `ports/__init__.py` — re-export.
- `api/provider.py`, `api/dependencies.py`, `api/routes.py`, `api/schemas.py`, `api/__init__.py`.
- `__init__.py`.
- `backend/alembic/versions/018_create_digests.py`.
- `backend/src/hiresense/bootstrap/autohunt.py`.

**Modify:**
- `backend/src/hiresense/config.py` + `backend/.env.example` — autohunt settings.
- `backend/src/hiresense/ingestion/infrastructure/jobs_repository.py` — add `list_since`.
- `backend/src/hiresense/bootstrap/ingestion.py` — expose `boards_jobs_repo` + `pre_ranker` on `IngestionBuild`.
- `backend/src/hiresense/bootstrap/__init__.py` — export `build_autohunt`, `AutoHuntBuild`.
- `backend/src/hiresense/main.py` — build + register autohunt.

**Tests:** `backend/tests/unit/autohunt/` (service), `backend/tests/integration/test_autohunt.py` (repo + endpoints).

---

## Task 1: Settings

**Files:** Modify `backend/src/hiresense/config.py`, `backend/.env.example`.

- [ ] **Step 1: Add settings** (after the analytics block in `config.py`):

```python
    # --- Proactive Auto-Hunt (scheduled digest of new taste-ranked matches) ---
    # Top-N new matches per digest, and the minimum match score (0-1) to qualify.
    autohunt_top_n: int = 5
    autohunt_min_score: float = 0.6
    # First-run lookback window (no prior digest to anchor the watermark).
    autohunt_initial_lookback_days: int = 7
    # Digests older than this are pruned at the end of each run.
    autohunt_digest_retention_days: int = 90
    # Intended cron cadence — INFORMATIONAL ONLY; the app never self-schedules.
    autohunt_schedule: str = "0 9 * * *"
```

- [ ] **Step 2: `.env.example`** (after the analytics block):

```
# --- Proactive Auto-Hunt ---
AUTOHUNT_TOP_N=5
AUTOHUNT_MIN_SCORE=0.6
AUTOHUNT_INITIAL_LOOKBACK_DAYS=7
AUTOHUNT_DIGEST_RETENTION_DAYS=90
AUTOHUNT_SCHEDULE=0 9 * * *
```

- [ ] **Step 3: Verify + commit**

Run: `cd backend && uv run python -c "from hiresense.config import Settings; s=Settings(); print(s.autohunt_top_n, s.autohunt_min_score, s.autohunt_initial_lookback_days)"`
Expected: `5 0.6 7`

```bash
git add backend/src/hiresense/config.py backend/.env.example
git commit -m "feat(autohunt): add auto-hunt settings"
```

---

## Task 2: Digest domain models

**Files:** Create `backend/src/hiresense/autohunt/domain/digest_entry.py`, `digest.py`, `__init__.py`, and the package `backend/src/hiresense/autohunt/__init__.py`.

- [ ] **Step 1: `digest_entry.py`**

```python
from __future__ import annotations

from pydantic import BaseModel


class DigestEntry(BaseModel):
    """One job in a digest — a denormalized snapshot, stable after the job closes."""

    job_id: str
    title: str
    company: str
    url: str | None = None
    score: float

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: `digest.py`**

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel, Field

from hiresense.autohunt.domain.digest_entry import DigestEntry


class Digest(BaseModel):
    """One auto-hunt run: top new matches above the floor (may be empty).

    `created_at` doubles as the watermark for the next run; `cutoff_at` is the
    "new since" lower bound this run used.
    """

    id: uuid_mod.UUID | None = None
    created_at: datetime | None = None
    cutoff_at: datetime
    entries: list[DigestEntry] = Field(default_factory=list)
    job_count: int = 0

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: `autohunt/__init__.py`** — empty package marker:

```python
```

- [ ] **Step 4: `autohunt/domain/__init__.py`**

```python
from hiresense.autohunt.domain.digest import Digest
from hiresense.autohunt.domain.digest_entry import DigestEntry

__all__ = ["Digest", "DigestEntry"]
```

- [ ] **Step 5: Verify + commit**

Run: `cd backend && uv run python -c "from hiresense.autohunt.domain import Digest, DigestEntry; from datetime import datetime, timezone; print(Digest(cutoff_at=datetime.now(timezone.utc)).job_count)"`
Expected: `0`

```bash
git add backend/src/hiresense/autohunt/__init__.py backend/src/hiresense/autohunt/domain/digest_entry.py backend/src/hiresense/autohunt/domain/digest.py backend/src/hiresense/autohunt/domain/__init__.py
git commit -m "feat(autohunt): add Digest + DigestEntry domain models"
```

---

## Task 3: Digest ORM + migration

**Files:** Create `backend/src/hiresense/autohunt/infrastructure/orm.py`, `backend/alembic/versions/018_create_digests.py`.

- [ ] **Step 1: `orm.py`**

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class DigestOrm(Base):
    """One auto-hunt run. `created_at` is the watermark for the next run;
    `entries` is a denormalized JSON snapshot of the qualifying matches."""

    __tablename__ = "digests"

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entries: Mapped[list] = mapped_column(JSON, default=list)
    job_count: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 2: Verify the ORM imports + registers**

Run: `cd backend && uv run python -c "from hiresense.autohunt.infrastructure.orm import DigestOrm; print(DigestOrm.__tablename__)"`
Expected: `digests`

- [ ] **Step 3: Migration `018_create_digests.py`**

```python
"""create digests (auto-hunt run log + top-N new-match snapshots)

Revision ID: 018
Revises: 017
Create Date: 2026-05-31
"""
from typing import Sequence, Union

from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS digests (
            id UUID PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            cutoff_at TIMESTAMPTZ NOT NULL,
            entries JSONB NOT NULL DEFAULT '[]'::jsonb,
            job_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_digests_created_at ON digests (created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_digests_created_at")
    op.execute("DROP TABLE IF EXISTS digests")
```

- [ ] **Step 4: Sanity-check the migration parses** (do NOT run `alembic upgrade` — needs live Postgres; the DB behavior is covered by the SQLite repo test in Task 4 via `create_all`):

Run: `cd backend && uv run python -c "import ast; ast.parse(open('alembic/versions/018_create_digests.py').read()); print('parses')"`
Expected: `parses`

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/autohunt/infrastructure/orm.py backend/alembic/versions/018_create_digests.py
git commit -m "feat(autohunt): add digests ORM + migration"
```

---

## Task 4: DigestRepository + port

**Files:** Create `backend/src/hiresense/autohunt/infrastructure/repository.py`, `infrastructure/__init__.py`, `ports/repository.py`, `ports/__init__.py`; Test `backend/tests/integration/test_autohunt_repository.py`.

- [ ] **Step 1: Write the failing DB-backed test**

```python
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.autohunt.domain import Digest, DigestEntry
from hiresense.autohunt.infrastructure import DigestRepository
from hiresense.autohunt.infrastructure.orm import DigestOrm  # noqa: F401
from hiresense.infrastructure.database import Base


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _digest(cutoff, entries=None):
    entries = entries or []
    return Digest(cutoff_at=cutoff, entries=entries, job_count=len(entries))


def test_add_and_latest_roundtrip():
    repo = DigestRepository(session_factory=_factory())
    now = datetime.now(timezone.utc)
    e = DigestEntry(job_id="j1", title="Eng", company="Acme", url="http://x", score=0.8)
    saved = repo.add(_digest(now, [e]))
    assert saved.id is not None and saved.created_at is not None
    latest = repo.latest()
    assert latest is not None
    assert latest.job_count == 1
    assert latest.entries[0].job_id == "j1"


def test_latest_is_most_recent():
    factory = _factory()
    repo = DigestRepository(session_factory=factory)
    old = datetime.now(timezone.utc) - timedelta(days=2)
    repo.add(_digest(old))
    repo.add(_digest(datetime.now(timezone.utc)))
    assert len(repo.list_recent(10)) == 2
    # latest() returns the most-recently-created row.
    assert repo.latest() is not None


def test_prune_older_than():
    repo = DigestRepository(session_factory=_factory())
    repo.add(_digest(datetime.now(timezone.utc)))
    removed = repo.prune_older_than(datetime.now(timezone.utc) + timedelta(days=1))
    assert removed == 1
    assert repo.latest() is None
```

- [ ] **Step 2: Run → FAIL** (`cd backend && uv run python -m pytest tests/integration/test_autohunt_repository.py -v`).

- [ ] **Step 3: Port** `ports/repository.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from hiresense.autohunt.domain import Digest


class DigestRepositoryPort(Protocol):
    def add(self, digest: Digest) -> Digest: ...

    def latest(self) -> Digest | None: ...

    def list_recent(self, limit: int) -> list[Digest]: ...

    def prune_older_than(self, cutoff: datetime) -> int: ...
```

`ports/__init__.py`:

```python
from hiresense.autohunt.ports.repository import DigestRepositoryPort

__all__ = ["DigestRepositoryPort"]
```

- [ ] **Step 4: Repository** `infrastructure/repository.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from hiresense.autohunt.domain import Digest, DigestEntry
from hiresense.autohunt.infrastructure.orm import DigestOrm


def _to_domain(row: DigestOrm) -> Digest:
    return Digest(
        id=row.id,
        created_at=row.created_at,
        cutoff_at=row.cutoff_at,
        entries=[DigestEntry.model_validate(e) for e in (row.entries or [])],
        job_count=row.job_count,
    )


class DigestRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def add(self, digest: Digest) -> Digest:
        with self._session_factory() as session:
            row = DigestOrm(
                cutoff_at=digest.cutoff_at,
                entries=[e.model_dump() for e in digest.entries],
                job_count=digest.job_count,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def latest(self) -> Digest | None:
        with self._session_factory() as session:
            stmt = select(DigestOrm).order_by(DigestOrm.created_at.desc()).limit(1)
            row = session.scalars(stmt).first()
            return _to_domain(row) if row is not None else None

    def list_recent(self, limit: int) -> list[Digest]:
        with self._session_factory() as session:
            stmt = select(DigestOrm).order_by(DigestOrm.created_at.desc()).limit(limit)
            return [_to_domain(r) for r in session.scalars(stmt).all()]

    def prune_older_than(self, cutoff: datetime) -> int:
        with self._session_factory() as session:
            ids = session.scalars(
                select(DigestOrm.id).where(DigestOrm.created_at < cutoff)
            ).all()
            if ids:
                session.execute(delete(DigestOrm).where(DigestOrm.id.in_(ids)))
                session.commit()
            return len(ids)
```

`infrastructure/__init__.py`:

```python
from hiresense.autohunt.infrastructure.repository import DigestRepository

__all__ = ["DigestRepository"]
```

- [ ] **Step 5: Run → PASS** (3 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/autohunt/ports/ backend/src/hiresense/autohunt/infrastructure/repository.py backend/src/hiresense/autohunt/infrastructure/__init__.py backend/tests/integration/test_autohunt_repository.py
git commit -m "feat(autohunt): add DigestRepository + port"
```

---

## Task 5: jobs_repo.list_since + expose repo/pre-ranker on IngestionBuild

**Files:** Modify `backend/src/hiresense/ingestion/infrastructure/jobs_repository.py`, `backend/src/hiresense/bootstrap/ingestion.py`; Test `backend/tests/integration/test_jobs_list_since.py`.

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.ingestion.infrastructure.models import IngestedJob
from hiresense.ingestion.infrastructure.jobs_repository import JobsRepository


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_list_since_filters_by_fetched_at_status_and_bucket():
    factory = _factory()
    now = datetime.now(timezone.utc)
    with factory() as s:
        s.add_all([
            IngestedJob(id="new", bucket="boards", source="x", source_type="board", title="New",
                        identity_key="k1", status="open", fetched_at=now),
            IngestedJob(id="old", bucket="boards", source="x", source_type="board", title="Old",
                        identity_key="k2", status="open", fetched_at=now - timedelta(days=10)),
            IngestedJob(id="closed", bucket="boards", source="x", source_type="board", title="Closed",
                        identity_key="k3", status="closed", fetched_at=now),
            IngestedJob(id="portal", bucket="portals", source="y", source_type="portal", title="Portal",
                        identity_key="k4", status="open", fetched_at=now),
        ])
        s.commit()
    repo = JobsRepository(session_factory=factory, bucket="boards")
    cutoff = now - timedelta(days=1)
    ids = [j.id for j in repo.list_since(cutoff)]
    assert ids == ["new"]  # old (before cutoff), closed (status), portal (bucket) all excluded
```

- [ ] **Step 2: Run → FAIL** (no `list_since`).

- [ ] **Step 3: Add `list_since`** to `JobsRepository` (after `list_all`):

```python
    def list_since(self, cutoff: datetime, *, status: str = "open") -> list[NormalizedJob]:
        with self._session_factory() as session:
            stmt = (
                select(IngestedJob)
                .where(
                    IngestedJob.bucket == self._bucket,
                    IngestedJob.status == status,
                    IngestedJob.fetched_at >= cutoff,
                )
                .order_by(IngestedJob.fetched_at.desc())
            )
            return [_to_domain(r) for r in session.scalars(stmt).all()]
```

(`select`, `datetime`, `_to_domain`, `IngestedJob`, `NormalizedJob` are already imported in this module.)

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: Expose repo + pre-ranker on `IngestionBuild`** — in `bootstrap/ingestion.py`:

Add fields to the dataclass:

```python
@dataclass(frozen=True)
class IngestionBuild:
    provider: IngestionProvider
    orchestrator: IngestionOrchestrator
    boards_jobs_repo: Any
    pre_ranker: Any
```

(Ensure `from typing import Any` is imported — it is used elsewhere in bootstrap; add if missing.) Update the return at the end of `build_ingestion`:

```python
    return IngestionBuild(
        provider=provider,
        orchestrator=ingestion_orchestrator,
        boards_jobs_repo=boards_jobs_repo,
        pre_ranker=pre_ranker,
    )
```

- [ ] **Step 6: Verify the app still builds**

Run: `cd backend && uv run python -c "from hiresense.main import create_app; create_app(); print('ok')"`
Expected: `ok`.

- [ ] **Step 7: Commit**

```bash
git add backend/src/hiresense/ingestion/infrastructure/jobs_repository.py backend/src/hiresense/bootstrap/ingestion.py backend/tests/integration/test_jobs_list_since.py
git commit -m "feat(ingestion): add list_since + expose boards repo/pre-ranker on IngestionBuild"
```

---

## Task 6: AutoHuntService

**Files:** Create `backend/src/hiresense/autohunt/domain/autohunt_service.py`; update `autohunt/domain/__init__.py`; Test `backend/tests/unit/autohunt/test_autohunt_service.py` (+ `backend/tests/unit/autohunt/__init__.py` if the project's other unit dirs have one — match convention).

- [ ] **Step 1: Write the failing unit test** (fakes for every port)

```python
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

import pytest

from hiresense.autohunt.domain import Digest
from hiresense.autohunt.domain.autohunt_service import AutoHuntService


class _Job:
    def __init__(self, id, score):
        self.id = id
        self.title = f"Title {id}"
        self.company = "Acme"
        self.url = f"http://x/{id}"
        self.match_score = score


class _FakeJobsRepo:
    def __init__(self, jobs):
        self._jobs = jobs
        self.since_called_with = None

    def list_since(self, cutoff, *, status="open"):
        self.since_called_with = cutoff
        return self._jobs


class _FakePreRanker:
    async def rerank(self, jobs, skill_by_id, candidate_skills, candidate_summary, bucket):
        # Pass through already-scored jobs (sorted desc by score).
        return sorted(jobs, key=lambda j: (j.match_score or 0), reverse=True)


class _FakeProfile:
    def __init__(self, view):
        self._view = view

    def get_for_language(self, language):
        return self._view


class _View:
    skills = ["python"]
    summary = "backend engineer"


class _FakeDigestRepo:
    def __init__(self, latest=None):
        self._latest = latest
        self.added = []
        self.pruned_at = None

    def add(self, digest):
        saved = digest.model_copy(update={"id": uuid_mod.uuid4(), "created_at": datetime.now(timezone.utc)})
        self.added.append(saved)
        self._latest = saved
        return saved

    def latest(self):
        return self._latest

    def prune_older_than(self, cutoff):
        self.pruned_at = cutoff
        return 0


def _service(jobs_repo, digest_repo, profile=_FakeProfile(_View())):
    return AutoHuntService(
        jobs_repo=jobs_repo, pre_ranker=_FakePreRanker(), profile_service=profile,
        digest_repo=digest_repo, top_n=5, min_score=0.6,
        initial_lookback_days=7, retention_days=90, language="en",
    )


@pytest.mark.asyncio
async def test_run_filters_floor_and_caps_top_n():
    jobs = [_Job("a", 0.9), _Job("b", 0.7), _Job("c", 0.5), _Job("d", None)]
    digest_repo = _FakeDigestRepo()
    svc = _service(_FakeJobsRepo(jobs), digest_repo)
    d = await svc.run()
    ids = [e.job_id for e in d.entries]
    assert ids == ["a", "b"]  # c below 0.6, d None → excluded
    assert d.job_count == 2


@pytest.mark.asyncio
async def test_run_top_n_cap():
    jobs = [_Job(c, 0.9) for c in "abcdefg"]
    svc = _service(_FakeJobsRepo(jobs), _FakeDigestRepo())
    svc._top_n = 3  # or rebuild; simplest to assert via a fresh service
    d = await svc.run()
    assert d.job_count == 3


@pytest.mark.asyncio
async def test_run_uses_latest_created_at_as_cutoff():
    prev = Digest(id=uuid_mod.uuid4(), created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
                  cutoff_at=datetime(2026, 5, 19, tzinfo=timezone.utc))
    jobs_repo = _FakeJobsRepo([])
    svc = _service(jobs_repo, _FakeDigestRepo(latest=prev))
    await svc.run()
    assert jobs_repo.since_called_with == prev.created_at


@pytest.mark.asyncio
async def test_run_no_profile_persists_empty_digest():
    jobs_repo = _FakeJobsRepo([_Job("a", 0.9)])
    digest_repo = _FakeDigestRepo()
    svc = _service(jobs_repo, digest_repo, profile=_FakeProfile(None))
    d = await svc.run()
    assert d.job_count == 0 and d.entries == []
```

(Adapt `test_run_top_n_cap` to construct a service with `top_n=3` via the `_service` builder rather than mutating a private — pass an override. If `_service` doesn't parameterize top_n, build `AutoHuntService(...)` directly with `top_n=3`.)

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `autohunt_service.py`:

```python
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from hiresense.autohunt.domain.digest import Digest
from hiresense.autohunt.domain.digest_entry import DigestEntry

logger = logging.getLogger(__name__)


class AutoHuntService:
    """Orchestrates one auto-hunt run: new-since jobs → taste-rank → floor →
    top-N → persist a Digest. Pure orchestration over injected ports."""

    def __init__(
        self,
        *,
        jobs_repo: Any,
        pre_ranker: Any,
        profile_service: Any,
        digest_repo: Any,
        top_n: int,
        min_score: float,
        initial_lookback_days: int,
        retention_days: int,
        language: str,
    ) -> None:
        self._jobs_repo = jobs_repo
        self._pre_ranker = pre_ranker
        self._profile = profile_service
        self._digest_repo = digest_repo
        self._top_n = top_n
        self._min_score = min_score
        self._initial_lookback_days = initial_lookback_days
        self._retention_days = retention_days
        self._language = language

    async def run(self) -> Digest:
        now = datetime.now(timezone.utc)
        latest = self._digest_repo.latest()
        cutoff = (
            latest.created_at
            if latest is not None and latest.created_at is not None
            else now - timedelta(days=self._initial_lookback_days)
        )

        view = self._profile.get_for_language(self._language)
        if view is None:
            return self._persist([], cutoff, now)

        new_jobs = self._jobs_repo.list_since(cutoff, status="open")
        candidate_skills = list(view.skills or [])
        candidate_summary = view.summary or ""
        try:
            ranked = await self._pre_ranker.rerank(
                new_jobs, {}, candidate_skills, candidate_summary, "boards"
            )
        except Exception:
            logger.exception("autohunt: rerank failed — persisting empty digest")
            return self._persist([], cutoff, now)

        qualified = [
            j for j in ranked
            if getattr(j, "match_score", None) is not None and j.match_score >= self._min_score
        ][: self._top_n]
        entries = [
            DigestEntry(
                job_id=j.id, title=j.title, company=j.company,
                url=getattr(j, "url", None), score=j.match_score,
            )
            for j in qualified
        ]
        return self._persist(entries, cutoff, now)

    def _persist(self, entries: list[DigestEntry], cutoff: datetime, now: datetime) -> Digest:
        digest = self._digest_repo.add(
            Digest(cutoff_at=cutoff, entries=entries, job_count=len(entries))
        )
        try:
            self._digest_repo.prune_older_than(now - timedelta(days=self._retention_days))
        except Exception:
            logger.exception("autohunt: digest prune failed (non-fatal)")
        return digest
```

- [ ] **Step 4: Re-export** — add `AutoHuntService` to `autohunt/domain/__init__.py`:

```python
from hiresense.autohunt.domain.autohunt_service import AutoHuntService
from hiresense.autohunt.domain.digest import Digest
from hiresense.autohunt.domain.digest_entry import DigestEntry

__all__ = ["AutoHuntService", "Digest", "DigestEntry"]
```

- [ ] **Step 5: Run → PASS.**

Run: `cd backend && uv run python -m pytest tests/unit/autohunt -v`

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/autohunt/domain/autohunt_service.py backend/src/hiresense/autohunt/domain/__init__.py backend/tests/unit/autohunt/
git commit -m "feat(autohunt): add AutoHuntService run orchestrator"
```

---

## Task 7: API layer

**Files:** Create `backend/src/hiresense/autohunt/api/{schemas.py,provider.py,dependencies.py,routes.py,__init__.py}`.

- [ ] **Step 1: `schemas.py`** (re-export the domain model as the response model):

```python
from __future__ import annotations

from hiresense.autohunt.domain import Digest

__all__ = ["Digest"]
```

- [ ] **Step 2: `provider.py`**

```python
from __future__ import annotations

from hiresense.autohunt.domain import AutoHuntService


class AutoHuntProvider:
    def __init__(self, autohunt_service: AutoHuntService) -> None:
        self._autohunt_service = autohunt_service

    def get_autohunt_service(self) -> AutoHuntService:
        return self._autohunt_service
```

- [ ] **Step 3: `dependencies.py`**

```python
from __future__ import annotations

from fastapi import Request

from hiresense.autohunt.domain import AutoHuntService


def get_autohunt_service(request: Request) -> AutoHuntService:
    return request.app.state.autohunt.get_autohunt_service()
```

- [ ] **Step 4: `routes.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from hiresense.autohunt.api.dependencies import get_autohunt_service
from hiresense.autohunt.domain import AutoHuntService, Digest
from hiresense.identity.api.dependencies import require_auth

router = APIRouter(prefix="/autohunt", tags=["autohunt"], dependencies=[Depends(require_auth)])


@router.post("/run", response_model=Digest)
async def run(service: AutoHuntService = Depends(get_autohunt_service)) -> Digest:
    return await service.run()


@router.get("/digests", response_model=list[Digest])
def list_digests(
    limit: int = 20, service: AutoHuntService = Depends(get_autohunt_service)
) -> list[Digest]:
    return service.list_recent(limit)


@router.get("/digests/latest")
def latest_digest(
    service: AutoHuntService = Depends(get_autohunt_service),
) -> Digest | Response:
    digest = service.latest()
    if digest is None:
        return Response(status_code=204)
    return digest
```

NOTE: `list_digests` and `latest_digest` call `service.list_recent(...)` / `service.latest()` — add thin pass-throughs to `AutoHuntService` (Step 5) so the API depends only on the service, not the repo.

- [ ] **Step 5: Add read pass-throughs to `AutoHuntService`** (in `autohunt_service.py`, after `run`):

```python
    def latest(self) -> Digest | None:
        return self._digest_repo.latest()

    def list_recent(self, limit: int) -> list[Digest]:
        return self._digest_repo.list_recent(limit)
```

(The `/digests/latest` route returns `Digest | Response`; FastAPI serializes the `Digest` via its model and passes the 204 `Response` through. To keep the `response_model` typing clean, the route omits `response_model` and returns the model/Response directly — acceptable and mirrors other 204-returning routes like preference `/reset`.)

- [ ] **Step 6: `__init__.py`**

```python
from hiresense.autohunt.api.routes import router

__all__ = ["router"]
```

- [ ] **Step 7: Verify import + commit**

Run: `cd backend && uv run python -c "from hiresense.autohunt.api import router; print(len(router.routes))"`
Expected: `3`.

```bash
git add backend/src/hiresense/autohunt/api/ backend/src/hiresense/autohunt/domain/autohunt_service.py
git commit -m "feat(autohunt): add API provider, dependencies, routes"
```

---

## Task 8: Bootstrap + main wiring

**Files:** Create `backend/src/hiresense/bootstrap/autohunt.py`; Modify `bootstrap/__init__.py`, `main.py`.

- [ ] **Step 1: `bootstrap/autohunt.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hiresense.autohunt.api.provider import AutoHuntProvider
from hiresense.autohunt.domain import AutoHuntService
from hiresense.autohunt.infrastructure import DigestRepository
from hiresense.bootstrap.shared_infra import SharedInfra


@dataclass(frozen=True)
class AutoHuntBuild:
    provider: AutoHuntProvider
    service: AutoHuntService


def build_autohunt(
    infra: SharedInfra, jobs_repo: Any, pre_ranker: Any, profile_service: Any
) -> AutoHuntBuild:
    s = infra.settings
    service = AutoHuntService(
        jobs_repo=jobs_repo,
        pre_ranker=pre_ranker,
        profile_service=profile_service,
        digest_repo=DigestRepository(session_factory=infra.sync_session_factory),
        top_n=s.autohunt_top_n,
        min_score=s.autohunt_min_score,
        initial_lookback_days=s.autohunt_initial_lookback_days,
        retention_days=s.autohunt_digest_retention_days,
        language=s.default_language,
    )
    return AutoHuntBuild(provider=AutoHuntProvider(autohunt_service=service), service=service)
```

- [ ] **Step 2: `bootstrap/__init__.py`** — add the import + `__all__` entries (mirror existing):

```python
from hiresense.bootstrap.autohunt import AutoHuntBuild, build_autohunt
```
(add `"AutoHuntBuild"`, `"build_autohunt"` to `__all__`.)

- [ ] **Step 3: `main.py`** — router import near the others:

```python
from hiresense.autohunt.api import router as autohunt_router
```
Add `build_autohunt` to the `from hiresense.bootstrap import (...)` block. After the `--- Tracking ---` block (ingestion + profile are already built above), add:

```python
    # --- Auto-Hunt (scheduled digest of new taste-ranked matches) ---
    autohunt = build_autohunt(infra, ingestion.boards_jobs_repo, ingestion.pre_ranker, profile.service)
    app.state.autohunt = autohunt.provider
    app.include_router(autohunt_router)
```

- [ ] **Step 4: Verify the app builds**

Run: `cd backend && uv run python -c "from hiresense.main import create_app; create_app(); print('ok')"`
Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/bootstrap/autohunt.py backend/src/hiresense/bootstrap/__init__.py backend/src/hiresense/main.py
git commit -m "feat(autohunt): wire auto-hunt context into the app"
```

---

## Task 9: Endpoint integration tests

**Files:** Create `backend/tests/integration/test_autohunt_endpoints.py`.

- [ ] **Step 1: Write the integration test** (in-process FastAPI, real SQLite, fake pre-ranker/profile, auth overridden)

```python
import uuid as uuid_mod
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.autohunt.api import router as autohunt_router
from hiresense.autohunt.api.dependencies import get_autohunt_service
from hiresense.autohunt.domain import AutoHuntService
from hiresense.autohunt.infrastructure import DigestRepository
from hiresense.autohunt.infrastructure.orm import DigestOrm  # noqa: F401
from hiresense.identity.api.dependencies import require_auth
from hiresense.infrastructure.database import Base
from hiresense.ingestion.infrastructure.models import IngestedJob  # noqa: F401
from hiresense.ingestion.infrastructure.jobs_repository import JobsRepository


class _PreRanker:
    async def rerank(self, jobs, skill_by_id, candidate_skills, candidate_summary, bucket):
        return sorted(jobs, key=lambda j: (j.match_score or 0), reverse=True)


class _Profile:
    def get_for_language(self, language):
        return type("V", (), {"skills": ["python"], "summary": "backend"})()


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _seed_jobs(factory):
    now = datetime.now(timezone.utc)
    with factory() as s:
        s.add_all([
            IngestedJob(id="hi", bucket="boards", source="x", source_type="board", title="High",
                        company="Acme", url="http://x/hi", identity_key="k1", status="open",
                        fetched_at=now, match_score=0.9),
            IngestedJob(id="lo", bucket="boards", source="x", source_type="board", title="Low",
                        company="Acme", url="http://x/lo", identity_key="k2", status="open",
                        fetched_at=now, match_score=0.2),
        ])
        s.commit()


def _build_app(factory):
    jobs_repo = JobsRepository(session_factory=factory, bucket="boards")
    service = AutoHuntService(
        jobs_repo=jobs_repo, pre_ranker=_PreRanker(), profile_service=_Profile(),
        digest_repo=DigestRepository(session_factory=factory),
        top_n=5, min_score=0.6, initial_lookback_days=7, retention_days=90, language="en",
    )
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_autohunt_service] = lambda: service
    app.include_router(autohunt_router)
    return app


@pytest.mark.asyncio
async def test_run_creates_digest_above_floor():
    factory = _factory()
    _seed_jobs(factory)
    app = _build_app(factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/autohunt/run")
        assert r.status_code == 200
        data = r.json()
        assert data["job_count"] == 1  # only the 0.9 job clears the 0.6 floor
        assert data["entries"][0]["job_id"] == "hi"


@pytest.mark.asyncio
async def test_second_run_empty_and_watermark_chains():
    factory = _factory()
    _seed_jobs(factory)
    app = _build_app(factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        first = (await c.post("/autohunt/run")).json()
        # No jobs newer than the first run's created_at → empty digest.
        second = (await c.post("/autohunt/run")).json()
        assert second["job_count"] == 0
        assert second["cutoff_at"][:19] == first["created_at"][:19]  # watermark chains
        latest = (await c.get("/autohunt/digests/latest")).json()
        assert latest["job_count"] == 0
        listed = (await c.get("/autohunt/digests?limit=10")).json()
        assert len(listed) == 2
```

- [ ] **Step 2: Run → PASS**

Run: `cd backend && uv run python -m pytest tests/integration/test_autohunt_endpoints.py -v`
Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_autohunt_endpoints.py
git commit -m "test(autohunt): integration tests for run + read endpoints"
```

---

## Task 10: Final verification

- [ ] **Step 1: Full suite** — `cd backend && uv run python -m pytest -q` → PASS.
- [ ] **Step 2: Lint** — `cd backend && uv run python -m ruff check src/hiresense/autohunt src/hiresense/bootstrap/autohunt.py tests/unit/autohunt tests/integration/test_autohunt_repository.py tests/integration/test_autohunt_endpoints.py tests/integration/test_jobs_list_since.py` → clean (fix with `--fix`; pre-existing repo-wide debt out of scope).
- [ ] **Step 3: App smoke** — `cd backend && uv run python -c "from hiresense.main import create_app; create_app(); print('ok')"` → `ok`.

---

## Self-Review notes

- **Spec coverage:** `digests` table + always-persist watermark (T3) ✓; domain models incl. denormalized entries (T2) ✓; `DigestRepository` add/latest/list_recent/prune (T4) ✓; `jobs_repo.list_since` new-since query (T5) ✓; `IngestionBuild` exposes repo+pre-ranker so the shared taste-aware pre-ranker is reused (T5, T8) ✓; `AutoHuntService.run` — cutoff-from-latest-else-lookback, floor, top-N, empty-profile/empty paths, retention (T6) ✓; three auth-gated endpoints, `/run` for external cron (T7) ✓; bootstrap after ingestion/profile (T8) ✓; integration tests incl. watermark-chaining (T9) ✓.
- **Type/name consistency:** `Digest{id,created_at,cutoff_at,entries,job_count}` and `DigestEntry{job_id,title,company,url,score}` consistent across model/ORM/repo/service/tests; `AutoHuntService.run/latest/list_recent` match the routes; `jobs_repo.list_since(cutoff, *, status="open")` consistent between repo, service, and tests; `build_autohunt(infra, jobs_repo, pre_ranker, profile_service)` matches `IngestionBuild.boards_jobs_repo`/`.pre_ranker` exposed in T5 and the main wiring in T8.
- **No placeholders:** every code step complete; the one note (top_n=3 test) instructs constructing the service directly with the override.
- **Out of scope:** pre-drafted applications, email/push, frontend digest view, portals bucket, company-diversity cap.
