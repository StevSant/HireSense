# Application Pipeline Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `tracking` module with PostgreSQL persistence for tracking job applications through a saved → applied → interviewing → offered → accepted/rejected pipeline.

**Architecture:** New `tracking/` bounded context following the existing hexagonal pattern. First ORM model in the project, backed by async SQLAlchemy + Alembic migration. Repository pattern for DB access, service layer for business logic, FastAPI routes for REST API. Frontend gets a dedicated Pipeline page and a "Track" button on the ingestion page.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, asyncpg, PostgreSQL, Pydantic v2, Angular 21, pytest-asyncio

---

## File Map

### New Files

| File | Responsibility |
|---|---|
| `backend/src/hiresense/tracking/__init__.py` | Package marker |
| `backend/src/hiresense/tracking/domain/__init__.py` | Package marker |
| `backend/src/hiresense/tracking/domain/models.py` | `ApplicationStatus` enum + `TrackedApplication` ORM model |
| `backend/src/hiresense/tracking/domain/services.py` | `TrackingService` business logic |
| `backend/src/hiresense/tracking/infrastructure/__init__.py` | Package marker |
| `backend/src/hiresense/tracking/infrastructure/repository.py` | `TrackingRepository` async SQLAlchemy |
| `backend/src/hiresense/tracking/api/__init__.py` | Package marker |
| `backend/src/hiresense/tracking/api/schemas.py` | Pydantic request/response models |
| `backend/src/hiresense/tracking/api/routes.py` | REST endpoints |
| `backend/src/hiresense/tracking/api/dependencies.py` | DI stubs |
| `backend/alembic/script.py.mako` | Alembic migration template |
| `backend/alembic/versions/001_create_tracked_applications.py` | First migration |
| `backend/tests/unit/tracking/__init__.py` | Package marker |
| `backend/tests/unit/tracking/test_models.py` | ORM model tests |
| `backend/tests/unit/tracking/test_schemas.py` | Schema validation tests |
| `backend/tests/unit/tracking/test_repository.py` | Repository tests (with in-memory SQLite) |
| `backend/tests/unit/tracking/test_service.py` | Service tests (mocked repository) |
| `backend/tests/unit/tracking/test_routes.py` | API route tests |
| `frontend/src/app/core/models/tracked-application.model.ts` | TypeScript model |
| `frontend/src/app/core/models/create-application-request.model.ts` | Request model |
| `frontend/src/app/core/models/update-application-request.model.ts` | Request model |
| `frontend/src/app/pages/tracking/tracking.component.ts` | Pipeline page component |
| `frontend/src/app/pages/tracking/tracking.component.html` | Pipeline page template |
| `frontend/src/app/pages/tracking/tracking.component.scss` | Pipeline page styles |

### Modified Files

| File | Change |
|---|---|
| `backend/src/hiresense/infrastructure/database.py` | Import TrackedApplication so Base.metadata sees it |
| `backend/src/hiresense/main.py` | Wire TrackingService, repository, session factory, routes |
| `frontend/src/app/app.routes.ts` | Add tracking child route |
| `frontend/src/app/pages/dashboard/dashboard.component.html` | Add Pipeline link to sidebar |
| `frontend/src/app/pages/ingestion/ingestion.component.ts` | Add "Track" button logic |
| `frontend/src/app/pages/ingestion/ingestion.component.html` | Add "Track" button to job rows |

---

## Task 1: Initialize Alembic versions directory and migration template

**Files:**
- Create: `backend/alembic/versions/` (directory)
- Create: `backend/alembic/script.py.mako`

- [ ] **Step 1: Create versions directory**

```bash
mkdir -p backend/alembic/versions
```

- [ ] **Step 2: Create Alembic script template**

Create `backend/alembic/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/script.py.mako backend/alembic/versions/
git commit -m "chore(alembic): add migration template and versions directory"
```

---

## Task 2: ApplicationStatus enum and TrackedApplication ORM model

**Files:**
- Create: `backend/src/hiresense/tracking/__init__.py`
- Create: `backend/src/hiresense/tracking/domain/__init__.py`
- Create: `backend/src/hiresense/tracking/domain/models.py`
- Create: `backend/tests/unit/tracking/__init__.py`
- Create: `backend/tests/unit/tracking/test_models.py`

- [ ] **Step 1: Create package init files**

Create empty `__init__.py` files:
- `backend/src/hiresense/tracking/__init__.py`
- `backend/src/hiresense/tracking/domain/__init__.py`
- `backend/tests/unit/tracking/__init__.py`

- [ ] **Step 2: Write the failing test**

Create `backend/tests/unit/tracking/test_models.py`:

```python
import uuid
from datetime import datetime, timezone

from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


def test_application_status_values() -> None:
    assert ApplicationStatus.SAVED == "saved"
    assert ApplicationStatus.APPLIED == "applied"
    assert ApplicationStatus.INTERVIEWING == "interviewing"
    assert ApplicationStatus.OFFERED == "offered"
    assert ApplicationStatus.ACCEPTED == "accepted"
    assert ApplicationStatus.REJECTED == "rejected"


def test_tracked_application_creation() -> None:
    app = TrackedApplication(
        title="Backend Engineer",
        company="Anthropic",
        url="https://example.com/job",
        status=ApplicationStatus.SAVED,
    )
    assert app.title == "Backend Engineer"
    assert app.company == "Anthropic"
    assert app.status == ApplicationStatus.SAVED
    assert app.job_id is None
    assert app.notes is None
    assert app.applied_at is None


def test_tracked_application_with_job_id() -> None:
    job_id = uuid.uuid4()
    app = TrackedApplication(
        job_id=job_id,
        title="ML Engineer",
        company="OpenAI",
        status=ApplicationStatus.APPLIED,
    )
    assert app.job_id == job_id


def test_tracked_application_default_status() -> None:
    app = TrackedApplication(title="SWE", company="Acme")
    assert app.status == ApplicationStatus.SAVED
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/tracking/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write implementation**

Create `backend/src/hiresense/tracking/domain/models.py`:

```python
from __future__ import annotations

import enum
import uuid as uuid_mod

from sqlalchemy import DateTime, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class ApplicationStatus(str, enum.Enum):
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class TrackedApplication(Base):
    __tablename__ = "tracked_applications"
    __table_args__ = (
        Index("ix_tracked_applications_status", "status"),
        Index("ix_tracked_applications_job_id", "job_id"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid_mod.uuid4
    )
    job_id: Mapped[uuid_mod.UUID | None] = mapped_column(Uuid, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=ApplicationStatus.SAVED.value
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/tracking/test_models.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/tracking/ backend/tests/unit/tracking/
git commit -m "feat(tracking): add ApplicationStatus enum and TrackedApplication ORM model"
```

---

## Task 3: Alembic migration for tracked_applications table

**Files:**
- Create: `backend/alembic/versions/001_create_tracked_applications.py`
- Modify: `backend/src/hiresense/infrastructure/database.py`

- [ ] **Step 1: Register model with Base metadata**

Add this import to `backend/src/hiresense/infrastructure/database.py` at the bottom of the file, after the `build_session_factory` function:

```python
# Import models so Base.metadata registers them for Alembic autogenerate
from hiresense.tracking.domain.models import TrackedApplication  # noqa: E402, F401
```

- [ ] **Step 2: Create the migration file manually**

Create `backend/alembic/versions/001_create_tracked_applications.py`:

```python
"""create tracked_applications table

Revision ID: 001
Revises:
Create Date: 2026-04-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tracked_applications",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="saved"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tracked_applications_status", "tracked_applications", ["status"])
    op.create_index("ix_tracked_applications_job_id", "tracked_applications", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_tracked_applications_job_id", table_name="tracked_applications")
    op.drop_index("ix_tracked_applications_status", table_name="tracked_applications")
    op.drop_table("tracked_applications")
```

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/001_create_tracked_applications.py backend/src/hiresense/infrastructure/database.py
git commit -m "feat(tracking): add Alembic migration for tracked_applications table"
```

---

## Task 4: Pydantic API schemas

**Files:**
- Create: `backend/src/hiresense/tracking/api/__init__.py`
- Create: `backend/src/hiresense/tracking/api/schemas.py`
- Create: `backend/tests/unit/tracking/test_schemas.py`

- [ ] **Step 1: Create api package init**

Create empty `backend/src/hiresense/tracking/api/__init__.py`.

- [ ] **Step 2: Write the failing test**

Create `backend/tests/unit/tracking/test_schemas.py`:

```python
import uuid
from datetime import datetime, timezone

import pytest

from hiresense.tracking.api.schemas import (
    CreateApplicationRequest,
    TrackedApplicationResponse,
    UpdateApplicationRequest,
)
from hiresense.tracking.domain.models import ApplicationStatus


def test_create_request_with_job_id() -> None:
    req = CreateApplicationRequest(job_id=uuid.uuid4())
    assert req.job_id is not None
    assert req.title is None


def test_create_request_manual() -> None:
    req = CreateApplicationRequest(title="SWE", company="Acme", url="https://example.com")
    assert req.title == "SWE"
    assert req.company == "Acme"
    assert req.job_id is None


def test_update_request_status_only() -> None:
    req = UpdateApplicationRequest(status=ApplicationStatus.APPLIED)
    assert req.status == ApplicationStatus.APPLIED
    assert req.notes is None


def test_update_request_notes_only() -> None:
    req = UpdateApplicationRequest(notes="Great interview")
    assert req.notes == "Great interview"
    assert req.status is None


def test_response_model() -> None:
    now = datetime.now(timezone.utc)
    resp = TrackedApplicationResponse(
        id=uuid.uuid4(),
        job_id=None,
        title="SWE",
        company="Acme",
        url=None,
        status=ApplicationStatus.SAVED,
        notes=None,
        applied_at=None,
        created_at=now,
        updated_at=now,
    )
    assert resp.status == ApplicationStatus.SAVED
    assert resp.job_id is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/tracking/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write implementation**

Create `backend/src/hiresense/tracking/api/schemas.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from hiresense.tracking.domain.models import ApplicationStatus


class CreateApplicationRequest(BaseModel):
    job_id: uuid.UUID | None = None
    title: str | None = None
    company: str | None = None
    url: str | None = None
    notes: str | None = None


class UpdateApplicationRequest(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = None


class TrackedApplicationResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID | None
    title: str
    company: str
    url: str | None
    status: ApplicationStatus
    notes: str | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/tracking/test_schemas.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/tracking/api/ backend/tests/unit/tracking/test_schemas.py
git commit -m "feat(tracking): add Pydantic API schemas for tracking endpoints"
```

---

## Task 5: TrackingRepository

**Files:**
- Create: `backend/src/hiresense/tracking/infrastructure/__init__.py`
- Create: `backend/src/hiresense/tracking/infrastructure/repository.py`
- Create: `backend/tests/unit/tracking/test_repository.py`

- [ ] **Step 1: Create infrastructure package init**

Create empty `backend/src/hiresense/tracking/infrastructure/__init__.py`.

- [ ] **Step 2: Write the failing test**

Create `backend/tests/unit/tracking/test_repository.py`:

```python
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from hiresense.infrastructure.database import Base
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication
from hiresense.tracking.infrastructure.repository import TrackingRepository


@pytest.fixture
def sync_session_factory():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    Base.metadata.drop_all(engine)


@pytest.fixture
def repo(sync_session_factory):
    return TrackingRepository(session_factory=sync_session_factory)


def test_create_and_get_by_id(repo, sync_session_factory) -> None:
    app = TrackedApplication(
        title="SWE",
        company="Acme",
        status=ApplicationStatus.SAVED.value,
    )
    with sync_session_factory() as session:
        session.add(app)
        session.commit()
        created_id = app.id

    result = repo.get_by_id(created_id)
    assert result is not None
    assert result.title == "SWE"
    assert result.company == "Acme"


def test_get_by_id_not_found(repo) -> None:
    result = repo.get_by_id(uuid.uuid4())
    assert result is None


def test_get_by_job_id(repo, sync_session_factory) -> None:
    job_id = uuid.uuid4()
    app = TrackedApplication(
        job_id=job_id,
        title="ML Eng",
        company="OpenAI",
        status=ApplicationStatus.SAVED.value,
    )
    with sync_session_factory() as session:
        session.add(app)
        session.commit()

    result = repo.get_by_job_id(job_id)
    assert result is not None
    assert result.title == "ML Eng"


def test_get_by_job_id_not_found(repo) -> None:
    result = repo.get_by_job_id(uuid.uuid4())
    assert result is None


def test_list_all(repo, sync_session_factory) -> None:
    with sync_session_factory() as session:
        session.add(TrackedApplication(title="A", company="X", status=ApplicationStatus.SAVED.value))
        session.add(TrackedApplication(title="B", company="Y", status=ApplicationStatus.APPLIED.value))
        session.commit()

    results = repo.list_all()
    assert len(results) == 2


def test_list_all_filter_by_status(repo, sync_session_factory) -> None:
    with sync_session_factory() as session:
        session.add(TrackedApplication(title="A", company="X", status=ApplicationStatus.SAVED.value))
        session.add(TrackedApplication(title="B", company="Y", status=ApplicationStatus.APPLIED.value))
        session.commit()

    results = repo.list_all(status=ApplicationStatus.APPLIED)
    assert len(results) == 1
    assert results[0].title == "B"


def test_update(repo, sync_session_factory) -> None:
    app = TrackedApplication(title="SWE", company="Acme", status=ApplicationStatus.SAVED.value)
    with sync_session_factory() as session:
        session.add(app)
        session.commit()
        app_id = app.id

    updated = repo.get_by_id(app_id)
    updated.status = ApplicationStatus.APPLIED.value
    repo.save(updated)

    result = repo.get_by_id(app_id)
    assert result.status == ApplicationStatus.APPLIED.value


def test_delete(repo, sync_session_factory) -> None:
    app = TrackedApplication(title="SWE", company="Acme", status=ApplicationStatus.SAVED.value)
    with sync_session_factory() as session:
        session.add(app)
        session.commit()
        app_id = app.id

    deleted = repo.delete(app_id)
    assert deleted is True
    assert repo.get_by_id(app_id) is None


def test_delete_not_found(repo) -> None:
    deleted = repo.delete(uuid.uuid4())
    assert deleted is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/tracking/test_repository.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write implementation**

Create `backend/src/hiresense/tracking/infrastructure/repository.py`:

```python
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


class TrackingRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def get_by_id(self, id: uuid.UUID) -> TrackedApplication | None:
        with self._session_factory() as session:
            return session.get(TrackedApplication, id)

    def get_by_job_id(self, job_id: uuid.UUID) -> TrackedApplication | None:
        with self._session_factory() as session:
            stmt = select(TrackedApplication).where(
                TrackedApplication.job_id == job_id
            )
            return session.scalars(stmt).first()

    def list_all(
        self, status: ApplicationStatus | None = None
    ) -> list[TrackedApplication]:
        with self._session_factory() as session:
            stmt = select(TrackedApplication)
            if status is not None:
                stmt = stmt.where(TrackedApplication.status == status.value)
            return list(session.scalars(stmt).all())

    def save(self, application: TrackedApplication) -> TrackedApplication:
        with self._session_factory() as session:
            application = session.merge(application)
            session.commit()
            return application

    def create(self, application: TrackedApplication) -> TrackedApplication:
        with self._session_factory() as session:
            session.add(application)
            session.commit()
            session.refresh(application)
            return application

    def delete(self, id: uuid.UUID) -> bool:
        with self._session_factory() as session:
            app = session.get(TrackedApplication, id)
            if app is None:
                return False
            session.delete(app)
            session.commit()
            return True
```

**Note:** This uses synchronous SQLAlchemy sessions for simplicity in unit tests with SQLite. In production, `main.py` will pass the async session factory. For the async production path, a thin async wrapper can be added later when integrating — the sync repository works for all unit testing and the core logic is the same.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/tracking/test_repository.py -v`
Expected: All 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/tracking/infrastructure/ backend/tests/unit/tracking/test_repository.py
git commit -m "feat(tracking): add TrackingRepository with sync SQLAlchemy sessions"
```

---

## Task 6: TrackingService

**Files:**
- Create: `backend/src/hiresense/tracking/domain/services.py`
- Create: `backend/tests/unit/tracking/test_service.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/tracking/test_service.py`:

```python
import uuid
from datetime import datetime, timezone

import pytest

from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication
from hiresense.tracking.domain.services import TrackingService


class FakeRepository:
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, TrackedApplication] = {}

    def create(self, application: TrackedApplication) -> TrackedApplication:
        if application.id is None:
            application.id = uuid.uuid4()
        application.created_at = datetime.now(timezone.utc)
        application.updated_at = datetime.now(timezone.utc)
        self._store[application.id] = application
        return application

    def get_by_id(self, id: uuid.UUID) -> TrackedApplication | None:
        return self._store.get(id)

    def get_by_job_id(self, job_id: uuid.UUID) -> TrackedApplication | None:
        for app in self._store.values():
            if app.job_id == job_id:
                return app
        return None

    def list_all(self, status: ApplicationStatus | None = None) -> list[TrackedApplication]:
        apps = list(self._store.values())
        if status is not None:
            apps = [a for a in apps if a.status == status.value]
        return apps

    def save(self, application: TrackedApplication) -> TrackedApplication:
        application.updated_at = datetime.now(timezone.utc)
        self._store[application.id] = application
        return application

    def delete(self, id: uuid.UUID) -> bool:
        if id in self._store:
            del self._store[id]
            return True
        return False


class FakeIngestionOrchestrator:
    def __init__(self, jobs: dict[str, object] | None = None) -> None:
        self._jobs = jobs or {}

    def get_job_by_id(self, job_id: str) -> object | None:
        return self._jobs.get(job_id)


class FakeJob:
    def __init__(self, id: str, title: str, company: str, url: str) -> None:
        self.id = id
        self.title = title
        self.company = company
        self.url = url


def test_track_manual_job() -> None:
    repo = FakeRepository()
    service = TrackingService(repository=repo, ingestion_orchestrator=None)

    result = service.track_job(title="SWE", company="Acme", url="https://example.com")
    assert result.title == "SWE"
    assert result.company == "Acme"
    assert result.status == ApplicationStatus.SAVED.value
    assert result.job_id is None


def test_track_from_ingestion() -> None:
    job_id = str(uuid.uuid4())
    fake_job = FakeJob(id=job_id, title="ML Eng", company="OpenAI", url="https://openai.com/job")
    orchestrator = FakeIngestionOrchestrator(jobs={job_id: fake_job})
    repo = FakeRepository()
    service = TrackingService(repository=repo, ingestion_orchestrator=orchestrator)

    result = service.track_from_ingestion(job_id=job_id)
    assert result.title == "ML Eng"
    assert result.company == "OpenAI"
    assert result.url == "https://openai.com/job"
    assert str(result.job_id) == job_id


def test_track_from_ingestion_not_found() -> None:
    orchestrator = FakeIngestionOrchestrator(jobs={})
    repo = FakeRepository()
    service = TrackingService(repository=repo, ingestion_orchestrator=orchestrator)

    with pytest.raises(ValueError, match="not found"):
        service.track_from_ingestion(job_id=str(uuid.uuid4()))


def test_track_from_ingestion_already_tracked() -> None:
    job_id = str(uuid.uuid4())
    fake_job = FakeJob(id=job_id, title="ML Eng", company="OpenAI", url="https://openai.com/job")
    orchestrator = FakeIngestionOrchestrator(jobs={job_id: fake_job})
    repo = FakeRepository()
    service = TrackingService(repository=repo, ingestion_orchestrator=orchestrator)

    service.track_from_ingestion(job_id=job_id)
    with pytest.raises(ValueError, match="already tracked"):
        service.track_from_ingestion(job_id=job_id)


def test_get_application() -> None:
    repo = FakeRepository()
    service = TrackingService(repository=repo, ingestion_orchestrator=None)

    created = service.track_job(title="SWE", company="Acme")
    result = service.get(created.id)
    assert result.title == "SWE"


def test_get_application_not_found() -> None:
    repo = FakeRepository()
    service = TrackingService(repository=repo, ingestion_orchestrator=None)

    with pytest.raises(ValueError, match="not found"):
        service.get(uuid.uuid4())


def test_list_applications() -> None:
    repo = FakeRepository()
    service = TrackingService(repository=repo, ingestion_orchestrator=None)

    service.track_job(title="A", company="X")
    service.track_job(title="B", company="Y")
    results = service.list()
    assert len(results) == 2


def test_list_filter_by_status() -> None:
    repo = FakeRepository()
    service = TrackingService(repository=repo, ingestion_orchestrator=None)

    app = service.track_job(title="A", company="X")
    service.update_status(app.id, ApplicationStatus.APPLIED)
    service.track_job(title="B", company="Y")

    results = service.list(status=ApplicationStatus.APPLIED)
    assert len(results) == 1
    assert results[0].title == "A"


def test_update_status() -> None:
    repo = FakeRepository()
    service = TrackingService(repository=repo, ingestion_orchestrator=None)

    app = service.track_job(title="SWE", company="Acme")
    updated = service.update_status(app.id, ApplicationStatus.INTERVIEWING)
    assert updated.status == ApplicationStatus.INTERVIEWING.value


def test_update_status_to_applied_sets_applied_at() -> None:
    repo = FakeRepository()
    service = TrackingService(repository=repo, ingestion_orchestrator=None)

    app = service.track_job(title="SWE", company="Acme")
    assert app.applied_at is None

    updated = service.update_status(app.id, ApplicationStatus.APPLIED)
    assert updated.applied_at is not None


def test_update_status_to_applied_does_not_overwrite_applied_at() -> None:
    repo = FakeRepository()
    service = TrackingService(repository=repo, ingestion_orchestrator=None)

    app = service.track_job(title="SWE", company="Acme")
    updated = service.update_status(app.id, ApplicationStatus.APPLIED)
    original_applied_at = updated.applied_at

    updated2 = service.update_status(app.id, ApplicationStatus.INTERVIEWING)
    updated3 = service.update_status(app.id, ApplicationStatus.APPLIED)
    assert updated3.applied_at == original_applied_at


def test_update_notes() -> None:
    repo = FakeRepository()
    service = TrackingService(repository=repo, ingestion_orchestrator=None)

    app = service.track_job(title="SWE", company="Acme")
    updated = service.update_notes(app.id, "Great company")
    assert updated.notes == "Great company"


def test_remove() -> None:
    repo = FakeRepository()
    service = TrackingService(repository=repo, ingestion_orchestrator=None)

    app = service.track_job(title="SWE", company="Acme")
    service.remove(app.id)
    with pytest.raises(ValueError, match="not found"):
        service.get(app.id)


def test_remove_not_found() -> None:
    repo = FakeRepository()
    service = TrackingService(repository=repo, ingestion_orchestrator=None)

    with pytest.raises(ValueError, match="not found"):
        service.remove(uuid.uuid4())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/tracking/test_service.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/hiresense/tracking/domain/services.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


class TrackingService:
    def __init__(self, repository: Any, ingestion_orchestrator: Any) -> None:
        self._repo = repository
        self._ingestion = ingestion_orchestrator

    def track_job(
        self,
        title: str,
        company: str,
        url: str | None = None,
        notes: str | None = None,
    ) -> TrackedApplication:
        app = TrackedApplication(
            title=title,
            company=company,
            url=url,
            notes=notes,
            status=ApplicationStatus.SAVED.value,
        )
        return self._repo.create(app)

    def track_from_ingestion(self, job_id: str) -> TrackedApplication:
        job = self._ingestion.get_job_by_id(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        job_uuid = uuid_mod.UUID(job_id)
        existing = self._repo.get_by_job_id(job_uuid)
        if existing is not None:
            raise ValueError(f"Job {job_id} already tracked")

        app = TrackedApplication(
            job_id=job_uuid,
            title=job.title,
            company=job.company,
            url=getattr(job, "url", None),
            status=ApplicationStatus.SAVED.value,
        )
        return self._repo.create(app)

    def get(self, id: uuid_mod.UUID) -> TrackedApplication:
        app = self._repo.get_by_id(id)
        if app is None:
            raise ValueError(f"Application {id} not found")
        return app

    def list(
        self, status: ApplicationStatus | None = None
    ) -> list[TrackedApplication]:
        return self._repo.list_all(status=status)

    def update_status(
        self,
        id: uuid_mod.UUID,
        status: ApplicationStatus,
        notes: str | None = None,
    ) -> TrackedApplication:
        app = self.get(id)
        app.status = status.value

        if status == ApplicationStatus.APPLIED and app.applied_at is None:
            app.applied_at = datetime.now(timezone.utc)

        if notes is not None:
            app.notes = notes

        return self._repo.save(app)

    def update_notes(self, id: uuid_mod.UUID, notes: str) -> TrackedApplication:
        app = self.get(id)
        app.notes = notes
        return self._repo.save(app)

    def remove(self, id: uuid_mod.UUID) -> None:
        deleted = self._repo.delete(id)
        if not deleted:
            raise ValueError(f"Application {id} not found")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/tracking/test_service.py -v`
Expected: All 15 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/tracking/domain/services.py backend/tests/unit/tracking/test_service.py
git commit -m "feat(tracking): add TrackingService with CRUD and status transitions"
```

---

## Task 7: Add `get_job_by_id` to IngestionOrchestrator

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/services.py`
- Create: `backend/tests/unit/ingestion/test_job_lookup.py`

The `TrackingService.track_from_ingestion()` calls `orchestrator.get_job_by_id(job_id)`. The `IngestionOrchestrator` currently runs ingestion and returns jobs but doesn't store them for later lookup. We need to add a simple in-memory cache and lookup method.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/ingestion/test_job_lookup.py`:

```python
import uuid

import pytest

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.services import IngestionOrchestrator


def _make_job(title: str = "SWE", company: str = "Acme") -> NormalizedJob:
    return NormalizedJob(
        id=str(uuid.uuid4()),
        title=title,
        company=company,
        description="desc",
        source="test",
        source_type="api",
        url="https://example.com",
    )


class FakeEventBus:
    async def publish(self, event) -> None:
        pass


def test_get_job_by_id_returns_none_initially() -> None:
    orchestrator = IngestionOrchestrator(sources=[], normalizers={}, event_bus=FakeEventBus())
    assert orchestrator.get_job_by_id("nonexistent") is None


def test_store_and_retrieve_job() -> None:
    orchestrator = IngestionOrchestrator(sources=[], normalizers={}, event_bus=FakeEventBus())
    job = _make_job()
    orchestrator.store_job(job)
    result = orchestrator.get_job_by_id(job.id)
    assert result is not None
    assert result.title == "SWE"


def test_store_multiple_and_retrieve() -> None:
    orchestrator = IngestionOrchestrator(sources=[], normalizers={}, event_bus=FakeEventBus())
    job1 = _make_job("A", "X")
    job2 = _make_job("B", "Y")
    orchestrator.store_job(job1)
    orchestrator.store_job(job2)

    assert orchestrator.get_job_by_id(job1.id).title == "A"
    assert orchestrator.get_job_by_id(job2.id).title == "B"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_job_lookup.py -v`
Expected: FAIL — `AttributeError: 'IngestionOrchestrator' object has no attribute 'get_job_by_id'`

- [ ] **Step 3: Add store and lookup to IngestionOrchestrator**

Modify `backend/src/hiresense/ingestion/domain/services.py`:

Add a `_jobs` dict to `__init__`:

```python
    def __init__(
        self,
        sources: list[Any],
        normalizers: dict[str, JobNormalizer],
        event_bus: Any,
    ) -> None:
        self._sources = sources
        self._normalizers = normalizers
        self._event_bus = event_bus
        self._jobs: dict[str, NormalizedJob] = {}
```

Add two methods after the `run` method:

```python
    def store_job(self, job: NormalizedJob) -> None:
        self._jobs[job.id] = job

    def get_job_by_id(self, job_id: str) -> NormalizedJob | None:
        return self._jobs.get(job_id)
```

Also update the `run` method to store each job after dedup:

After the line `all_jobs.append(job)`, add:
```python
                    self._jobs[job.id] = job
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/ingestion/test_job_lookup.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Run all ingestion tests to check for regressions**

Run: `cd backend && uv run pytest tests/unit/ingestion/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/services.py backend/tests/unit/ingestion/test_job_lookup.py
git commit -m "feat(ingestion): add in-memory job store and get_job_by_id lookup"
```

---

## Task 8: API routes and DI stubs

**Files:**
- Create: `backend/src/hiresense/tracking/api/dependencies.py`
- Create: `backend/src/hiresense/tracking/api/routes.py`
- Create: `backend/tests/unit/tracking/test_routes.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/tracking/test_routes.py`:

```python
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.tracking.api.dependencies import get_tracking_service
from hiresense.tracking.api.routes import router
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


class FakeTrackingService:
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, TrackedApplication] = {}

    def track_job(self, title, company, url=None, notes=None):
        app = TrackedApplication(
            id=uuid.uuid4(),
            title=title,
            company=company,
            url=url,
            notes=notes,
            status=ApplicationStatus.SAVED.value,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._store[app.id] = app
        return app

    def track_from_ingestion(self, job_id):
        raise ValueError(f"Job {job_id} not found")

    def get(self, id):
        app = self._store.get(id)
        if app is None:
            raise ValueError(f"Application {id} not found")
        return app

    def list(self, status=None):
        apps = list(self._store.values())
        if status is not None:
            apps = [a for a in apps if a.status == status.value]
        return apps

    def update_status(self, id, status, notes=None):
        app = self.get(id)
        app.status = status.value
        if notes:
            app.notes = notes
        return app

    def update_notes(self, id, notes):
        app = self.get(id)
        app.notes = notes
        return app

    def remove(self, id):
        if id not in self._store:
            raise ValueError(f"Application {id} not found")
        del self._store[id]


def _make_app(service: FakeTrackingService) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_tracking_service] = lambda: service
    return app


def test_create_manual_application() -> None:
    service = FakeTrackingService()
    client = TestClient(_make_app(service))

    response = client.post("/tracking", json={"title": "SWE", "company": "Acme"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "SWE"
    assert data["company"] == "Acme"
    assert data["status"] == "saved"


def test_create_from_ingestion_not_found() -> None:
    service = FakeTrackingService()
    client = TestClient(_make_app(service))

    response = client.post("/tracking", json={"job_id": str(uuid.uuid4())})
    assert response.status_code == 404


def test_list_applications() -> None:
    service = FakeTrackingService()
    service.track_job(title="A", company="X")
    service.track_job(title="B", company="Y")
    client = TestClient(_make_app(service))

    response = client.get("/tracking")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_application() -> None:
    service = FakeTrackingService()
    app = service.track_job(title="SWE", company="Acme")
    client = TestClient(_make_app(service))

    response = client.get(f"/tracking/{app.id}")
    assert response.status_code == 200
    assert response.json()["title"] == "SWE"


def test_get_application_not_found() -> None:
    service = FakeTrackingService()
    client = TestClient(_make_app(service))

    response = client.get(f"/tracking/{uuid.uuid4()}")
    assert response.status_code == 404


def test_update_application() -> None:
    service = FakeTrackingService()
    app = service.track_job(title="SWE", company="Acme")
    client = TestClient(_make_app(service))

    response = client.patch(f"/tracking/{app.id}", json={"status": "applied"})
    assert response.status_code == 200
    assert response.json()["status"] == "applied"


def test_update_application_not_found() -> None:
    service = FakeTrackingService()
    client = TestClient(_make_app(service))

    response = client.patch(f"/tracking/{uuid.uuid4()}", json={"status": "applied"})
    assert response.status_code == 404


def test_delete_application() -> None:
    service = FakeTrackingService()
    app = service.track_job(title="SWE", company="Acme")
    client = TestClient(_make_app(service))

    response = client.delete(f"/tracking/{app.id}")
    assert response.status_code == 204


def test_delete_application_not_found() -> None:
    service = FakeTrackingService()
    client = TestClient(_make_app(service))

    response = client.delete(f"/tracking/{uuid.uuid4()}")
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/tracking/test_routes.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create DI stubs**

Create `backend/src/hiresense/tracking/api/dependencies.py`:

```python
from hiresense.tracking.domain.services import TrackingService


def get_tracking_service() -> TrackingService:
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")
```

- [ ] **Step 4: Create routes**

Create `backend/src/hiresense/tracking/api/routes.py`:

```python
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from hiresense.tracking.api.dependencies import get_tracking_service
from hiresense.tracking.api.schemas import (
    CreateApplicationRequest,
    TrackedApplicationResponse,
    UpdateApplicationRequest,
)
from hiresense.tracking.domain.models import ApplicationStatus
from hiresense.tracking.domain.services import TrackingService

router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.post("", response_model=TrackedApplicationResponse, status_code=201)
def create_application(
    request: CreateApplicationRequest,
    service: Annotated[TrackingService, Depends(get_tracking_service)],
) -> TrackedApplicationResponse:
    try:
        if request.job_id is not None:
            app = service.track_from_ingestion(job_id=str(request.job_id))
        else:
            if not request.title or not request.company:
                raise HTTPException(
                    status_code=422,
                    detail="title and company are required for manual entries",
                )
            app = service.track_job(
                title=request.title,
                company=request.company,
                url=request.url,
                notes=request.notes,
            )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        if "already tracked" in msg:
            raise HTTPException(status_code=409, detail=msg)
        raise
    return TrackedApplicationResponse.model_validate(app)


@router.get("", response_model=list[TrackedApplicationResponse])
def list_applications(
    service: Annotated[TrackingService, Depends(get_tracking_service)],
    status: ApplicationStatus | None = None,
) -> list[TrackedApplicationResponse]:
    apps = service.list(status=status)
    return [TrackedApplicationResponse.model_validate(a) for a in apps]


@router.get("/{id}", response_model=TrackedApplicationResponse)
def get_application(
    id: uuid.UUID,
    service: Annotated[TrackingService, Depends(get_tracking_service)],
) -> TrackedApplicationResponse:
    try:
        app = service.get(id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Application {id} not found")
    return TrackedApplicationResponse.model_validate(app)


@router.patch("/{id}", response_model=TrackedApplicationResponse)
def update_application(
    id: uuid.UUID,
    request: UpdateApplicationRequest,
    service: Annotated[TrackingService, Depends(get_tracking_service)],
) -> TrackedApplicationResponse:
    try:
        if request.status is not None:
            app = service.update_status(id, request.status, notes=request.notes)
        elif request.notes is not None:
            app = service.update_notes(id, request.notes)
        else:
            app = service.get(id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Application {id} not found")
    return TrackedApplicationResponse.model_validate(app)


@router.delete("/{id}", status_code=204)
def delete_application(
    id: uuid.UUID,
    service: Annotated[TrackingService, Depends(get_tracking_service)],
) -> Response:
    try:
        service.remove(id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Application {id} not found")
    return Response(status_code=204)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/tracking/test_routes.py -v`
Expected: All 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/tracking/api/ backend/tests/unit/tracking/test_routes.py
git commit -m "feat(tracking): add REST API routes with CRUD endpoints"
```

---

## Task 9: Wire tracking module into app factory

**Files:**
- Modify: `backend/src/hiresense/main.py`

- [ ] **Step 1: Add imports to main.py**

```python
from hiresense.infrastructure.database import build_session_factory
from sqlalchemy.orm import sessionmaker, Session
from hiresense.tracking.api.dependencies import get_tracking_service
from hiresense.tracking.api.routes import router as tracking_router
from hiresense.tracking.domain.services import TrackingService
from hiresense.tracking.infrastructure.repository import TrackingRepository
```

- [ ] **Step 2: Add tracking wiring after optimization module**

Add this block before the health check in `create_app()`:

```python
    # --- Tracking module ---
    sync_session_factory = sessionmaker(
        bind=build_engine(settings),
        expire_on_commit=False,
    )
    tracking_repo = TrackingRepository(session_factory=sync_session_factory)
    tracking_service = TrackingService(
        repository=tracking_repo,
        ingestion_orchestrator=ingestion_orchestrator,
    )
    app.dependency_overrides[get_tracking_service] = lambda: tracking_service
    app.include_router(tracking_router)
```

Also add this import at the top:
```python
from hiresense.infrastructure.database import build_engine
```

Note: `build_engine` is already defined in `database.py`. We use a sync `sessionmaker` here because the routes are synchronous (no `async def`). This matches the repository's sync session usage.

- [ ] **Step 3: Run all tests**

Run: `cd backend && uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/main.py
git commit -m "feat(app): wire tracking module with repository, service, and routes"
```

---

## Task 10: Frontend TypeScript models

**Files:**
- Create: `frontend/src/app/core/models/tracked-application.model.ts`
- Create: `frontend/src/app/core/models/create-application-request.model.ts`
- Create: `frontend/src/app/core/models/update-application-request.model.ts`

- [ ] **Step 1: Create TrackedApplication model**

Create `frontend/src/app/core/models/tracked-application.model.ts`:

```typescript
export type ApplicationStatus = 'saved' | 'applied' | 'interviewing' | 'offered' | 'accepted' | 'rejected';

export interface TrackedApplication {
  id: string;
  job_id: string | null;
  title: string;
  company: string;
  url: string | null;
  status: ApplicationStatus;
  notes: string | null;
  applied_at: string | null;
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: Create CreateApplicationRequest model**

Create `frontend/src/app/core/models/create-application-request.model.ts`:

```typescript
export interface CreateApplicationRequest {
  job_id?: string;
  title?: string;
  company?: string;
  url?: string;
  notes?: string;
}
```

- [ ] **Step 3: Create UpdateApplicationRequest model**

Create `frontend/src/app/core/models/update-application-request.model.ts`:

```typescript
import { ApplicationStatus } from './tracked-application.model';

export interface UpdateApplicationRequest {
  status?: ApplicationStatus;
  notes?: string;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/core/models/tracked-application.model.ts frontend/src/app/core/models/create-application-request.model.ts frontend/src/app/core/models/update-application-request.model.ts
git commit -m "feat(frontend): add tracking TypeScript models"
```

---

## Task 11: Frontend Pipeline page

**Files:**
- Create: `frontend/src/app/pages/tracking/tracking.component.ts`
- Create: `frontend/src/app/pages/tracking/tracking.component.html`
- Create: `frontend/src/app/pages/tracking/tracking.component.scss`
- Modify: `frontend/src/app/app.routes.ts`
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.html`

- [ ] **Step 1: Create component TypeScript**

Create `frontend/src/app/pages/tracking/tracking.component.ts`:

```typescript
import { Component, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { environment } from '../../../environments/environment';
import { TrackedApplication, ApplicationStatus } from '../../core/models/tracked-application.model';
import { CreateApplicationRequest } from '../../core/models/create-application-request.model';
import { UpdateApplicationRequest } from '../../core/models/update-application-request.model';

@Component({
  selector: 'app-tracking',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './tracking.component.html',
  styleUrl: './tracking.component.scss',
})
export class TrackingComponent implements OnInit {
  applications = signal<TrackedApplication[]>([]);
  loading = signal(false);
  error = signal('');
  statusFilter = signal<string>('');
  showAddForm = signal(false);

  // Add form fields
  newTitle = '';
  newCompany = '';
  newUrl = '';
  newNotes = '';

  readonly statuses: ApplicationStatus[] = [
    'saved', 'applied', 'interviewing', 'offered', 'accepted', 'rejected'
  ];

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadApplications();
  }

  loadApplications(): void {
    this.loading.set(true);
    let url = `${environment.apiUrl}/tracking`;
    if (this.statusFilter()) {
      url += `?status=${this.statusFilter()}`;
    }
    this.http.get<TrackedApplication[]>(url).subscribe({
      next: (apps) => {
        this.applications.set(apps);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to load applications');
        this.loading.set(false);
      },
    });
  }

  onStatusFilterChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.statusFilter.set(select.value);
    this.loadApplications();
  }

  addApplication(): void {
    const req: CreateApplicationRequest = {
      title: this.newTitle,
      company: this.newCompany,
      url: this.newUrl || undefined,
      notes: this.newNotes || undefined,
    };
    this.http.post<TrackedApplication>(`${environment.apiUrl}/tracking`, req).subscribe({
      next: () => {
        this.showAddForm.set(false);
        this.newTitle = '';
        this.newCompany = '';
        this.newUrl = '';
        this.newNotes = '';
        this.loadApplications();
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to add application');
      },
    });
  }

  updateStatus(app: TrackedApplication, event: Event): void {
    const select = event.target as HTMLSelectElement;
    const req: UpdateApplicationRequest = { status: select.value as ApplicationStatus };
    this.http.patch<TrackedApplication>(`${environment.apiUrl}/tracking/${app.id}`, req).subscribe({
      next: () => this.loadApplications(),
      error: (err) => this.error.set(err.error?.detail || 'Failed to update status'),
    });
  }

  deleteApplication(app: TrackedApplication): void {
    this.http.delete(`${environment.apiUrl}/tracking/${app.id}`).subscribe({
      next: () => this.loadApplications(),
      error: (err) => this.error.set(err.error?.detail || 'Failed to delete'),
    });
  }

  toggleAddForm(): void {
    this.showAddForm.update(v => !v);
  }
}
```

- [ ] **Step 2: Create component template**

Create `frontend/src/app/pages/tracking/tracking.component.html`:

```html
<div class="tracking-page">
  <header class="page-header">
    <h1>Application Pipeline</h1>
    <div class="header-actions">
      <select (change)="onStatusFilterChange($event)">
        <option value="">All Statuses</option>
        @for (status of statuses; track status) {
          <option [value]="status">{{ status }}</option>
        }
      </select>
      <button (click)="toggleAddForm()" class="add-btn">
        {{ showAddForm() ? 'Cancel' : 'Add Application' }}
      </button>
    </div>
  </header>

  @if (error()) {
    <div class="error-banner">{{ error() }}</div>
  }

  @if (showAddForm()) {
    <form class="add-form" (ngSubmit)="addApplication()">
      <input type="text" [(ngModel)]="newTitle" name="title" placeholder="Job Title" required />
      <input type="text" [(ngModel)]="newCompany" name="company" placeholder="Company" required />
      <input type="text" [(ngModel)]="newUrl" name="url" placeholder="URL (optional)" />
      <textarea [(ngModel)]="newNotes" name="notes" placeholder="Notes (optional)"></textarea>
      <button type="submit">Save</button>
    </form>
  }

  @if (loading()) {
    <p class="loading">Loading...</p>
  } @else {
    <table class="applications-table">
      <thead>
        <tr>
          <th>Company</th>
          <th>Title</th>
          <th>Status</th>
          <th>Applied</th>
          <th>Notes</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        @for (app of applications(); track app.id) {
          <tr>
            <td>{{ app.company }}</td>
            <td>
              @if (app.url) {
                <a [href]="app.url" target="_blank">{{ app.title }}</a>
              } @else {
                {{ app.title }}
              }
            </td>
            <td>
              <select [value]="app.status" (change)="updateStatus(app, $event)">
                @for (status of statuses; track status) {
                  <option [value]="status" [selected]="status === app.status">{{ status }}</option>
                }
              </select>
            </td>
            <td>{{ app.applied_at ? (app.applied_at | slice:0:10) : '-' }}</td>
            <td class="notes-cell">{{ app.notes || '-' }}</td>
            <td>
              <button (click)="deleteApplication(app)" class="delete-btn">Remove</button>
            </td>
          </tr>
        } @empty {
          <tr>
            <td colspan="6" class="empty-state">No applications tracked yet</td>
          </tr>
        }
      </tbody>
    </table>
  }
</div>
```

- [ ] **Step 3: Create component styles**

Create `frontend/src/app/pages/tracking/tracking.component.scss`:

```scss
.tracking-page {
  padding: 1.5rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.header-actions {
  display: flex;
  gap: 0.75rem;
}

.add-form {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-width: 400px;
  margin-bottom: 1.5rem;
  padding: 1rem;
  border: 1px solid #ddd;
  border-radius: 6px;
}

.applications-table {
  width: 100%;
  border-collapse: collapse;

  th, td {
    padding: 0.75rem;
    text-align: left;
    border-bottom: 1px solid #eee;
  }

  th {
    font-weight: 600;
    border-bottom: 2px solid #ddd;
  }
}

.notes-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-state {
  text-align: center;
  color: #999;
  padding: 2rem;
}

.error-banner {
  background: #fee;
  color: #c00;
  padding: 0.75rem;
  border-radius: 4px;
  margin-bottom: 1rem;
}

.delete-btn {
  color: #c00;
  background: none;
  border: 1px solid #c00;
  border-radius: 4px;
  padding: 0.25rem 0.5rem;
  cursor: pointer;
}

.add-btn {
  padding: 0.5rem 1rem;
}

.loading {
  color: #666;
}
```

- [ ] **Step 4: Add route to app.routes.ts**

Add this child route inside the `children` array of the dashboard route in `frontend/src/app/app.routes.ts`, after the optimization route:

```typescript
      { path: 'tracking', loadComponent: () => import('./pages/tracking/tracking.component').then(m => m.TrackingComponent) },
```

- [ ] **Step 5: Add sidebar link**

In `frontend/src/app/pages/dashboard/dashboard.component.html`, add this nav link after the Optimization link:

```html
      <a routerLink="tracking" routerLinkActive="active">
        <span class="icon">&#128203;</span>
        <span>Pipeline</span>
      </a>
```

- [ ] **Step 6: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/pages/tracking/ frontend/src/app/app.routes.ts frontend/src/app/pages/dashboard/dashboard.component.html
git commit -m "feat(frontend): add Pipeline page with tracking UI and sidebar navigation"
```

---

## Task 12: Add "Track" button to ingestion page

**Files:**
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.ts`
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.html`

- [ ] **Step 1: Add tracking state and method to component**

Add these to `frontend/src/app/pages/ingestion/ingestion.component.ts`:

Import:
```typescript
import { CreateApplicationRequest } from '../../core/models/create-application-request.model';
```

Add signal:
```typescript
  trackedJobIds = signal<Set<string>>(new Set());
```

Add method:
```typescript
  trackJob(jobId: string): void {
    const req: CreateApplicationRequest = { job_id: jobId };
    this.http.post(`${environment.apiUrl}/tracking`, req).subscribe({
      next: () => {
        this.trackedJobIds.update(ids => {
          const newSet = new Set(ids);
          newSet.add(jobId);
          return newSet;
        });
      },
      error: (err) => {
        if (err.status === 409) {
          this.trackedJobIds.update(ids => {
            const newSet = new Set(ids);
            newSet.add(jobId);
            return newSet;
          });
        }
      },
    });
  }

  isTracked(jobId: string): boolean {
    return this.trackedJobIds().has(jobId);
  }
```

- [ ] **Step 2: Add Track button to job table rows**

In `frontend/src/app/pages/ingestion/ingestion.component.html`, add a "Track" button column to the jobs table. In the `<thead>`, add:
```html
<th>Actions</th>
```

In each job row `<tr>`, add:
```html
<td>
  <button
    (click)="trackJob(job.id)"
    [disabled]="isTracked(job.id)"
  >
    {{ isTracked(job.id) ? 'Tracked' : 'Track' }}
  </button>
</td>
```

- [ ] **Step 3: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pages/ingestion/ingestion.component.ts frontend/src/app/pages/ingestion/ingestion.component.html
git commit -m "feat(frontend): add Track button to ingestion job table"
```

---

## Task 13: Run full test suite and verify

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Run linter**

Run: `cd backend && uv run ruff check src/ tests/`
Expected: No errors (or only pre-existing ones)

- [ ] **Step 4: Final commit if any lint fixes needed**

```bash
git add -A
git commit -m "fix: address lint issues from tracking module implementation"
```
