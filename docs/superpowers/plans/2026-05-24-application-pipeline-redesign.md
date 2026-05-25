# Application Pipeline Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `TrackedApplication` the spine of the pipeline — every match, CV optimization, and interview prep hangs off an application, and the user navigates them via a single unified detail view that pulls upstream data automatically.

**Architecture:** New `hiresense/applications/` bounded context (clean-architecture, mirrors existing `tracking/`, `matching/`, etc.). Four new child tables FK→`tracked_applications` for snapshots and artifacts. The new `ApplicationService` orchestrates the existing `MatchingOrchestrator`, `CvOptimizer`, and `InterviewPrepService` instead of replacing them. Frontend gets a new `/dashboard/applications/:id` detail view with four tabs; the Tracking page is renamed to Applications and the Optimization / Interview pages are restructured to flow through the application.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.x / Alembic / pytest. Angular 20 (signals API) / TypeScript. PostgreSQL (with pgvector for matching).

**Spec:** `docs/superpowers/specs/2026-05-24-application-pipeline-redesign-design.md`

**Phase markers (checkpoint between phases):**
- **Phase A** — Backend foundation (data model, repository, migration)
- **Phase B** — Backend services (ApplicationService, SkillExtractor, ArtifactService)
- **Phase C** — Backend API (schemas, routes, DI wiring)
- **CHECKPOINT 1** — `curl` the API end-to-end before frontend work
- **Phase D** — Frontend foundation (models, service, applications list page)
- **Phase E** — Frontend detail view (4 tabs + create dialog)
- **Phase F** — Frontend restructure (Interview page, Optimization redirect, nav update)

---

## Phase A — Backend foundation

### Task A1: SQLAlchemy ORM models for the four artifact tables

**Files:**
- Create: `backend/src/hiresense/applications/__init__.py`
- Create: `backend/src/hiresense/applications/domain/__init__.py`
- Create: `backend/src/hiresense/applications/domain/models.py`
- Create: `backend/tests/unit/applications/__init__.py`
- Test: `backend/tests/unit/applications/test_models.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/unit/applications/test_models.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from hiresense.applications.domain.models import (
    ApplicationCvOptimization,
    ApplicationInterviewPrep,
    ApplicationJobSnapshot,
    ApplicationMatch,
    JobSnapshotSource,
)


def test_job_snapshot_defaults_and_required_fields() -> None:
    snap = ApplicationJobSnapshot(
        application_id=uuid.uuid4(),
        description="some description",
        required_skills=["python", "fastapi"],
        source=JobSnapshotSource.MANUAL.value,
    )
    assert snap.description == "some description"
    assert snap.required_skills == ["python", "fastapi"]
    assert snap.source == "manual"


def test_application_match_all_score_fields() -> None:
    match = ApplicationMatch(
        application_id=uuid.uuid4(),
        overall_score=0.82,
        semantic_score=0.7,
        skill_score=0.9,
        experience_score=0.8,
        language_score=0.85,
        matched_skills=["python"],
        missing_skills=["k8s"],
        pros=["good fit"],
        cons=["missing k8s"],
        recommendations=["learn k8s"],
        cv_language="en",
    )
    assert match.overall_score == 0.82
    assert "python" in match.matched_skills


def test_application_cv_optimization_links_to_match() -> None:
    opt = ApplicationCvOptimization(
        application_id=uuid.uuid4(),
        match_id=uuid.uuid4(),
        cv_language="en",
        original_tex=r"\documentclass{article}",
        optimized_tex=r"\documentclass{article}\begin{document}\end{document}",
        improvement_summary="tightened skills section",
        changes=[{"section": "skills", "before": "", "after": "python, k8s"}],
    )
    assert opt.cv_language == "en"
    assert opt.match_id is not None


def test_application_interview_prep_lists() -> None:
    prep = ApplicationInterviewPrep(
        application_id=uuid.uuid4(),
        competencies_to_probe=["leadership"],
        technical_topics=["distributed systems"],
        negotiation_points=["remote-first"],
        matched_stories=[{"story_id": str(uuid.uuid4()), "story_title": "led migration", "relevance": "high"}],
    )
    assert prep.competencies_to_probe == ["leadership"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/applications/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hiresense.applications'`

- [ ] **Step 3: Create the package skeleton and ORM models**

`backend/src/hiresense/applications/__init__.py`:

```python
```

`backend/src/hiresense/applications/domain/__init__.py`:

```python
from hiresense.applications.domain.models import (
    ApplicationCvOptimization,
    ApplicationInterviewPrep,
    ApplicationJobSnapshot,
    ApplicationMatch,
    JobSnapshotSource,
)

__all__ = [
    "ApplicationCvOptimization",
    "ApplicationInterviewPrep",
    "ApplicationJobSnapshot",
    "ApplicationMatch",
    "JobSnapshotSource",
]
```

`backend/src/hiresense/applications/domain/models.py`:

```python
from __future__ import annotations

import enum
import uuid as uuid_mod
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class JobSnapshotSource(str, enum.Enum):
    INGESTED = "ingested"
    MANUAL = "manual"
    LLM_EXTRACTED = "llm_extracted"


class ApplicationJobSnapshot(Base):
    __tablename__ = "application_job_snapshots"

    id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid_mod.uuid4
    )
    application_id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid,
        ForeignKey("tracked_applications.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    required_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ApplicationMatch(Base):
    __tablename__ = "application_matches"
    __table_args__ = (
        Index("ix_application_matches_app_created", "application_id", "created_at"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid_mod.uuid4
    )
    application_id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, ForeignKey("tracked_applications.id", ondelete="CASCADE"), nullable=False
    )
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    semantic_score: Mapped[float] = mapped_column(Float, nullable=False)
    skill_score: Mapped[float] = mapped_column(Float, nullable=False)
    experience_score: Mapped[float] = mapped_column(Float, nullable=False)
    language_score: Mapped[float] = mapped_column(Float, nullable=False)
    matched_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    pros: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    cons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    recommendations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    cv_language: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ApplicationCvOptimization(Base):
    __tablename__ = "application_cv_optimizations"
    __table_args__ = (
        Index("ix_application_cv_opts_app_created", "application_id", "created_at"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid_mod.uuid4
    )
    application_id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, ForeignKey("tracked_applications.id", ondelete="CASCADE"), nullable=False
    )
    match_id: Mapped[uuid_mod.UUID | None] = mapped_column(
        Uuid, ForeignKey("application_matches.id", ondelete="SET NULL"), nullable=True
    )
    cv_language: Mapped[str] = mapped_column(String(10), nullable=False)
    original_tex: Mapped[str] = mapped_column(Text, nullable=False)
    optimized_tex: Mapped[str] = mapped_column(Text, nullable=False)
    improvement_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    changes: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ApplicationInterviewPrep(Base):
    __tablename__ = "application_interview_preps"
    __table_args__ = (
        Index("ix_application_interview_preps_app_created", "application_id", "created_at"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid_mod.uuid4
    )
    application_id: Mapped[uuid_mod.UUID] = mapped_column(
        Uuid, ForeignKey("tracked_applications.id", ondelete="CASCADE"), nullable=False
    )
    competencies_to_probe: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    technical_topics: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    negotiation_points: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    matched_stories: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/applications/test_models.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/applications/__init__.py \
        backend/src/hiresense/applications/domain/__init__.py \
        backend/src/hiresense/applications/domain/models.py \
        backend/tests/unit/applications/__init__.py \
        backend/tests/unit/applications/test_models.py
git commit -m "feat(applications): add ORM models for application artifacts"
```

---

### Task A2: Alembic migration for the four tables + backfill snapshot data

**Files:**
- Create: `backend/alembic/versions/005_create_application_artifacts.py`

- [ ] **Step 1: Find the current latest revision**

Run: `cd backend && uv run alembic heads`
Expected: prints the most recent revision id (likely `004`).

- [ ] **Step 2: Write the migration**

`backend/alembic/versions/005_create_application_artifacts.py`:

```python
"""create application artifact tables and backfill snapshots

Revision ID: 005
Revises: 004
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_job_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("tracked_applications.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("required_skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "application_matches",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("tracked_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("semantic_score", sa.Float(), nullable=False),
        sa.Column("skill_score", sa.Float(), nullable=False),
        sa.Column("experience_score", sa.Float(), nullable=False),
        sa.Column("language_score", sa.Float(), nullable=False),
        sa.Column("matched_skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("missing_skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("pros", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("cons", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("recommendations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("cv_language", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_application_matches_app_created",
        "application_matches",
        ["application_id", "created_at"],
    )

    op.create_table(
        "application_cv_optimizations",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("tracked_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "match_id",
            sa.Uuid(),
            sa.ForeignKey("application_matches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("cv_language", sa.String(10), nullable=False),
        sa.Column("original_tex", sa.Text(), nullable=False),
        sa.Column("optimized_tex", sa.Text(), nullable=False),
        sa.Column("improvement_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("changes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_application_cv_opts_app_created",
        "application_cv_optimizations",
        ["application_id", "created_at"],
    )

    op.create_table(
        "application_interview_preps",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("tracked_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("competencies_to_probe", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("technical_topics", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("negotiation_points", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("matched_stories", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_application_interview_preps_app_created",
        "application_interview_preps",
        ["application_id", "created_at"],
    )

    # Backfill: each existing tracked_application gets an empty job snapshot.
    # Source is 'manual' because we cannot reliably reconstruct ingested-job
    # description/skills here (the normalized_jobs table may have changed).
    op.execute(
        """
        INSERT INTO application_job_snapshots (id, application_id, description, required_skills, source)
        SELECT gen_random_uuid(), ta.id, '', '[]'::json, 'manual'
        FROM tracked_applications ta
        LEFT JOIN application_job_snapshots ajs ON ajs.application_id = ta.id
        WHERE ajs.id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_application_interview_preps_app_created", table_name="application_interview_preps")
    op.drop_table("application_interview_preps")
    op.drop_index("ix_application_cv_opts_app_created", table_name="application_cv_optimizations")
    op.drop_table("application_cv_optimizations")
    op.drop_index("ix_application_matches_app_created", table_name="application_matches")
    op.drop_table("application_matches")
    op.drop_table("application_job_snapshots")
```

- [ ] **Step 3: Apply the migration and check schema**

Run: `cd backend && uv run alembic upgrade head`
Expected: log line "Running upgrade 004 -> 005, create application artifact tables and backfill snapshots"

Verify tables exist:
```bash
docker compose exec postgres psql -U hiresense -d hiresense -c '\dt application_*'
```
Expected: lists `application_job_snapshots`, `application_matches`, `application_cv_optimizations`, `application_interview_preps`.

If any existing `tracked_applications` rows are in the DB, verify they got backfill snapshots:
```bash
docker compose exec postgres psql -U hiresense -d hiresense -c \
  "SELECT count(*) FROM application_job_snapshots; SELECT count(*) FROM tracked_applications;"
```
Expected: equal counts.

- [ ] **Step 4: Verify downgrade works**

Run: `cd backend && uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: drops the four tables, recreates them, completes cleanly.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/005_create_application_artifacts.py
git commit -m "feat(applications): add migration for artifact tables with snapshot backfill"
```

---

### Task A3: Repository port (Protocol)

**Files:**
- Create: `backend/src/hiresense/applications/ports/__init__.py`
- Create: `backend/src/hiresense/applications/ports/repository.py`

- [ ] **Step 1: Define the port**

`backend/src/hiresense/applications/ports/repository.py`:

```python
from __future__ import annotations

import uuid
from typing import Protocol

from hiresense.applications.domain.models import (
    ApplicationCvOptimization,
    ApplicationInterviewPrep,
    ApplicationJobSnapshot,
    ApplicationMatch,
)
from hiresense.tracking.domain.models import TrackedApplication


class ApplicationRepositoryPort(Protocol):
    # Job snapshot (1:1)
    def create_snapshot(self, snapshot: ApplicationJobSnapshot) -> ApplicationJobSnapshot: ...
    def get_snapshot(self, application_id: uuid.UUID) -> ApplicationJobSnapshot | None: ...
    def save_snapshot(self, snapshot: ApplicationJobSnapshot) -> ApplicationJobSnapshot: ...

    # Matches (1:N)
    def create_match(self, match: ApplicationMatch) -> ApplicationMatch: ...
    def list_matches(self, application_id: uuid.UUID) -> list[ApplicationMatch]: ...
    def get_latest_match(self, application_id: uuid.UUID) -> ApplicationMatch | None: ...
    def get_match(self, match_id: uuid.UUID) -> ApplicationMatch | None: ...

    # CV optimizations (1:N)
    def create_optimization(self, opt: ApplicationCvOptimization) -> ApplicationCvOptimization: ...
    def list_optimizations(self, application_id: uuid.UUID) -> list[ApplicationCvOptimization]: ...
    def get_latest_optimization(self, application_id: uuid.UUID) -> ApplicationCvOptimization | None: ...

    # Interview preps (1:N)
    def create_interview_prep(self, prep: ApplicationInterviewPrep) -> ApplicationInterviewPrep: ...
    def list_interview_preps(self, application_id: uuid.UUID) -> list[ApplicationInterviewPrep]: ...
    def get_latest_interview_prep(self, application_id: uuid.UUID) -> ApplicationInterviewPrep | None: ...
```

`backend/src/hiresense/applications/ports/__init__.py`:

```python
from hiresense.applications.ports.repository import ApplicationRepositoryPort

__all__ = ["ApplicationRepositoryPort"]
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/hiresense/applications/ports/
git commit -m "feat(applications): add repository port"
```

---

### Task A4: SQLAlchemy repository implementation

**Files:**
- Create: `backend/src/hiresense/applications/infrastructure/__init__.py`
- Create: `backend/src/hiresense/applications/infrastructure/repository.py`
- Test: `backend/tests/unit/applications/test_repository.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/unit/applications/test_repository.py`:

```python
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.applications.domain.models import (
    ApplicationCvOptimization,
    ApplicationInterviewPrep,
    ApplicationJobSnapshot,
    ApplicationMatch,
    JobSnapshotSource,
)
from hiresense.applications.infrastructure.repository import ApplicationRepository
from hiresense.infrastructure.database import Base
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture()
def repo(session_factory):
    return ApplicationRepository(session_factory=session_factory)


@pytest.fixture()
def tracked_app(session_factory) -> TrackedApplication:
    with session_factory() as session:
        app = TrackedApplication(
            title="Software Engineer",
            company="Fieldguide",
            status=ApplicationStatus.SAVED.value,
        )
        session.add(app)
        session.commit()
        session.refresh(app)
        return app


def test_create_and_get_snapshot(repo, tracked_app):
    snap = ApplicationJobSnapshot(
        application_id=tracked_app.id,
        description="job desc",
        required_skills=["python"],
        source=JobSnapshotSource.MANUAL.value,
    )
    created = repo.create_snapshot(snap)
    fetched = repo.get_snapshot(tracked_app.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.required_skills == ["python"]


def test_create_and_get_latest_match(repo, tracked_app):
    m1 = ApplicationMatch(
        application_id=tracked_app.id,
        overall_score=0.5, semantic_score=0.5, skill_score=0.5,
        experience_score=0.5, language_score=0.5, cv_language="en",
    )
    m2 = ApplicationMatch(
        application_id=tracked_app.id,
        overall_score=0.8, semantic_score=0.8, skill_score=0.8,
        experience_score=0.8, language_score=0.8, cv_language="en",
    )
    repo.create_match(m1)
    repo.create_match(m2)
    latest = repo.get_latest_match(tracked_app.id)
    assert latest is not None
    assert latest.overall_score == 0.8
    assert len(repo.list_matches(tracked_app.id)) == 2


def test_create_and_get_latest_optimization(repo, tracked_app):
    opt = ApplicationCvOptimization(
        application_id=tracked_app.id,
        cv_language="en",
        original_tex="orig",
        optimized_tex="opt",
        improvement_summary="summary",
        changes=[],
    )
    repo.create_optimization(opt)
    latest = repo.get_latest_optimization(tracked_app.id)
    assert latest is not None
    assert latest.optimized_tex == "opt"


def test_create_and_get_latest_interview_prep(repo, tracked_app):
    prep = ApplicationInterviewPrep(
        application_id=tracked_app.id,
        competencies_to_probe=["leadership"],
    )
    repo.create_interview_prep(prep)
    latest = repo.get_latest_interview_prep(tracked_app.id)
    assert latest is not None
    assert latest.competencies_to_probe == ["leadership"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/applications/test_repository.py -v`
Expected: FAIL with import error for `ApplicationRepository`.

- [ ] **Step 3: Implement the repository**

`backend/src/hiresense/applications/infrastructure/__init__.py`:

```python
from hiresense.applications.infrastructure.repository import ApplicationRepository

__all__ = ["ApplicationRepository"]
```

`backend/src/hiresense/applications/infrastructure/repository.py`:

```python
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.applications.domain.models import (
    ApplicationCvOptimization,
    ApplicationInterviewPrep,
    ApplicationJobSnapshot,
    ApplicationMatch,
)


class ApplicationRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    # ---- snapshots ----------------------------------------------------

    def create_snapshot(self, snapshot: ApplicationJobSnapshot) -> ApplicationJobSnapshot:
        with self._session_factory() as session:
            session.add(snapshot)
            session.commit()
            session.refresh(snapshot)
            return snapshot

    def get_snapshot(self, application_id: uuid.UUID) -> ApplicationJobSnapshot | None:
        with self._session_factory() as session:
            stmt = select(ApplicationJobSnapshot).where(
                ApplicationJobSnapshot.application_id == application_id
            )
            return session.scalars(stmt).first()

    def save_snapshot(self, snapshot: ApplicationJobSnapshot) -> ApplicationJobSnapshot:
        with self._session_factory() as session:
            merged = session.merge(snapshot)
            session.commit()
            session.refresh(merged)
            return merged

    # ---- matches ------------------------------------------------------

    def create_match(self, match: ApplicationMatch) -> ApplicationMatch:
        with self._session_factory() as session:
            session.add(match)
            session.commit()
            session.refresh(match)
            return match

    def list_matches(self, application_id: uuid.UUID) -> list[ApplicationMatch]:
        with self._session_factory() as session:
            stmt = (
                select(ApplicationMatch)
                .where(ApplicationMatch.application_id == application_id)
                .order_by(ApplicationMatch.created_at.desc())
            )
            return list(session.scalars(stmt).all())

    def get_latest_match(self, application_id: uuid.UUID) -> ApplicationMatch | None:
        matches = self.list_matches(application_id)
        return matches[0] if matches else None

    def get_match(self, match_id: uuid.UUID) -> ApplicationMatch | None:
        with self._session_factory() as session:
            return session.get(ApplicationMatch, match_id)

    # ---- optimizations -----------------------------------------------

    def create_optimization(
        self, opt: ApplicationCvOptimization
    ) -> ApplicationCvOptimization:
        with self._session_factory() as session:
            session.add(opt)
            session.commit()
            session.refresh(opt)
            return opt

    def list_optimizations(
        self, application_id: uuid.UUID
    ) -> list[ApplicationCvOptimization]:
        with self._session_factory() as session:
            stmt = (
                select(ApplicationCvOptimization)
                .where(ApplicationCvOptimization.application_id == application_id)
                .order_by(ApplicationCvOptimization.created_at.desc())
            )
            return list(session.scalars(stmt).all())

    def get_latest_optimization(
        self, application_id: uuid.UUID
    ) -> ApplicationCvOptimization | None:
        opts = self.list_optimizations(application_id)
        return opts[0] if opts else None

    # ---- interview preps ---------------------------------------------

    def create_interview_prep(
        self, prep: ApplicationInterviewPrep
    ) -> ApplicationInterviewPrep:
        with self._session_factory() as session:
            session.add(prep)
            session.commit()
            session.refresh(prep)
            return prep

    def list_interview_preps(
        self, application_id: uuid.UUID
    ) -> list[ApplicationInterviewPrep]:
        with self._session_factory() as session:
            stmt = (
                select(ApplicationInterviewPrep)
                .where(ApplicationInterviewPrep.application_id == application_id)
                .order_by(ApplicationInterviewPrep.created_at.desc())
            )
            return list(session.scalars(stmt).all())

    def get_latest_interview_prep(
        self, application_id: uuid.UUID
    ) -> ApplicationInterviewPrep | None:
        preps = self.list_interview_preps(application_id)
        return preps[0] if preps else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/applications/test_repository.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/applications/infrastructure/ \
        backend/tests/unit/applications/test_repository.py
git commit -m "feat(applications): add SQLAlchemy repository for artifact tables"
```

---

## Phase B — Backend services

### Task B1: SkillExtractor (LLM-backed required-skill extraction)

**Files:**
- Create: `backend/src/hiresense/applications/domain/skill_extractor.py`
- Test: `backend/tests/unit/applications/test_skill_extractor.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/unit/applications/test_skill_extractor.py`:

```python
from __future__ import annotations

import pytest

from hiresense.applications.domain.skill_extractor import SkillExtractor


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.last_prompt: str | None = None

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.last_prompt = prompt
        return self.response


@pytest.mark.asyncio
async def test_returns_skills_from_clean_json_response() -> None:
    llm = FakeLLM(response='["python", "fastapi", "kubernetes"]')
    extractor = SkillExtractor(llm=llm)
    skills = await extractor.extract("Backend engineer job at a remote startup.")
    assert skills == ["python", "fastapi", "kubernetes"]


@pytest.mark.asyncio
async def test_strips_markdown_code_fence() -> None:
    llm = FakeLLM(response='```json\n["python", "django"]\n```')
    extractor = SkillExtractor(llm=llm)
    skills = await extractor.extract("Some job desc.")
    assert skills == ["python", "django"]


@pytest.mark.asyncio
async def test_returns_empty_list_on_invalid_json() -> None:
    llm = FakeLLM(response="not valid JSON at all")
    extractor = SkillExtractor(llm=llm)
    skills = await extractor.extract("Some job desc.")
    assert skills == []


@pytest.mark.asyncio
async def test_returns_empty_list_when_llm_is_none() -> None:
    extractor = SkillExtractor(llm=None)
    skills = await extractor.extract("Some job desc.")
    assert skills == []


@pytest.mark.asyncio
async def test_normalizes_skills_to_lowercase_and_dedupes() -> None:
    llm = FakeLLM(response='["Python", "PYTHON", "FastAPI", " python "]')
    extractor = SkillExtractor(llm=llm)
    skills = await extractor.extract("desc")
    assert skills == ["python", "fastapi"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/applications/test_skill_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the extractor**

`backend/src/hiresense/applications/domain/skill_extractor.py`:

```python
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "You extract required technical skills from job descriptions. Return only a JSON array."
USER_PROMPT_TEMPLATE = (
    "Extract the required technical skills from the following job description. "
    "Return a JSON array of short lowercase strings (no commentary, no markdown, no explanation). "
    "Skills are libraries, languages, frameworks, tools, databases, cloud providers, "
    "and other technical competencies. Exclude soft skills.\n\n"
    "Job description:\n{description}"
)


class SkillExtractor:
    def __init__(self, llm: Any | None) -> None:
        self._llm = llm

    async def extract(self, description: str) -> list[str]:
        if self._llm is None or not description.strip():
            return []

        prompt = USER_PROMPT_TEMPLATE.format(description=description)
        try:
            response = await self._llm.complete(prompt, system=SYSTEM_PROMPT)
        except Exception:
            logger.exception("Skill extraction LLM call failed")
            return []

        raw = self._strip_markdown_fence(response)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Skill extractor got non-JSON response: %r", raw[:200])
            return []

        if not isinstance(parsed, list):
            return []

        return self._normalize(parsed)

    @staticmethod
    def _strip_markdown_fence(text: str) -> str:
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        return match.group(1).strip() if match else text.strip()

    @staticmethod
    def _normalize(skills: list[Any]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for s in skills:
            if not isinstance(s, str):
                continue
            normalized = s.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/applications/test_skill_extractor.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/applications/domain/skill_extractor.py \
        backend/tests/unit/applications/test_skill_extractor.py
git commit -m "feat(applications): add LLM-backed skill extractor"
```

---

### Task B2: ApplicationService (create / get / list / delete / edit snapshot)

**Files:**
- Create: `backend/src/hiresense/applications/domain/aggregate.py`
- Create: `backend/src/hiresense/applications/domain/application_service.py`
- Test: `backend/tests/unit/applications/test_application_service.py`

- [ ] **Step 1: Define the aggregate response model**

`backend/src/hiresense/applications/domain/aggregate.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class JobSnapshotView(BaseModel):
    id: uuid.UUID
    description: str
    required_skills: list[str]
    source: str
    updated_at: datetime | None = None


class MatchView(BaseModel):
    id: uuid.UUID
    overall_score: float
    semantic_score: float
    skill_score: float
    experience_score: float
    language_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    pros: list[str]
    cons: list[str]
    recommendations: list[str]
    cv_language: str
    created_at: datetime | None = None


class CvOptimizationView(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID | None
    cv_language: str
    original_tex: str
    optimized_tex: str
    improvement_summary: str
    changes: list[dict]
    created_at: datetime | None = None


class InterviewPrepView(BaseModel):
    id: uuid.UUID
    competencies_to_probe: list[str]
    technical_topics: list[str]
    negotiation_points: list[str]
    matched_stories: list[dict]
    created_at: datetime | None = None


class ApplicationAggregate(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID | None
    title: str
    company: str
    url: str | None
    status: str
    notes: str | None
    applied_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    job_snapshot: JobSnapshotView | None
    latest_match: MatchView | None
    latest_optimization: CvOptimizationView | None
    latest_interview_prep: InterviewPrepView | None
    match_count: int
    optimization_count: int
    interview_prep_count: int
```

- [ ] **Step 2: Write the failing test**

`backend/tests/unit/applications/test_application_service.py`:

```python
from __future__ import annotations

import uuid

import pytest

from hiresense.applications.domain.application_service import ApplicationService
from hiresense.applications.domain.models import ApplicationJobSnapshot, JobSnapshotSource


class FakeNormalizedJob:
    def __init__(self, id_: str, title: str, company: str, description: str, skills: list[str], url: str | None = None) -> None:
        self.id = id_
        self.title = title
        self.company = company
        self.description = description
        self.skills = skills
        self.url = url


class FakeIngestionOrchestrator:
    def __init__(self, jobs: dict[str, FakeNormalizedJob] | None = None) -> None:
        self._jobs = jobs or {}

    def get_job_by_id(self, job_id: str):
        return self._jobs.get(job_id)


class FakeTrackingService:
    def __init__(self) -> None:
        self.tracked: dict[uuid.UUID, object] = {}

    def track_from_ingestion(self, job_id: str):
        from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication
        job_uuid = uuid.UUID(job_id)
        app = TrackedApplication(
            id=uuid.uuid4(),
            job_id=job_uuid,
            title="Software Engineer",
            company="Fieldguide",
            status=ApplicationStatus.SAVED.value,
        )
        self.tracked[app.id] = app
        return app

    def track_job(self, title: str, company: str, url=None, notes=None):
        from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication
        app = TrackedApplication(
            id=uuid.uuid4(),
            title=title,
            company=company,
            url=url,
            notes=notes,
            status=ApplicationStatus.SAVED.value,
        )
        self.tracked[app.id] = app
        return app

    def get(self, id_):
        if id_ not in self.tracked:
            raise ValueError(f"Application {id_} not found")
        return self.tracked[id_]

    def list(self, status=None):
        return list(self.tracked.values())

    def remove(self, id_):
        if id_ not in self.tracked:
            raise ValueError(f"Application {id_} not found")
        del self.tracked[id_]


class FakeRepo:
    def __init__(self) -> None:
        self.snapshots: dict[uuid.UUID, ApplicationJobSnapshot] = {}

    def create_snapshot(self, snap):
        snap.id = snap.id or uuid.uuid4()
        self.snapshots[snap.application_id] = snap
        return snap

    def get_snapshot(self, application_id):
        return self.snapshots.get(application_id)

    def save_snapshot(self, snap):
        self.snapshots[snap.application_id] = snap
        return snap

    def list_matches(self, application_id):
        return []

    def get_latest_match(self, application_id):
        return None

    def list_optimizations(self, application_id):
        return []

    def get_latest_optimization(self, application_id):
        return None

    def list_interview_preps(self, application_id):
        return []

    def get_latest_interview_prep(self, application_id):
        return None


class FakeSkillExtractor:
    def __init__(self, skills: list[str]) -> None:
        self.skills = skills
        self.called_with: str | None = None

    async def extract(self, description: str) -> list[str]:
        self.called_with = description
        return self.skills


@pytest.mark.asyncio
async def test_create_from_ingested_job_copies_skills_without_llm() -> None:
    job_id = str(uuid.uuid4())
    ingestion = FakeIngestionOrchestrator({
        job_id: FakeNormalizedJob(
            job_id, "Software Engineer", "Fieldguide",
            "Build cool stuff", ["python", "fastapi"]
        )
    })
    tracking = FakeTrackingService()
    repo = FakeRepo()
    extractor = FakeSkillExtractor(skills=["should_not_be_called"])

    service = ApplicationService(
        repository=repo,
        tracking_service=tracking,
        ingestion_orchestrator=ingestion,
        skill_extractor=extractor,
    )

    agg = await service.create_from_ingested(job_id)

    assert agg.job_snapshot is not None
    assert agg.job_snapshot.required_skills == ["python", "fastapi"]
    assert agg.job_snapshot.source == JobSnapshotSource.INGESTED.value
    assert extractor.called_with is None  # LLM not called for ingested jobs


@pytest.mark.asyncio
async def test_create_from_manual_calls_llm_extractor() -> None:
    ingestion = FakeIngestionOrchestrator()
    tracking = FakeTrackingService()
    repo = FakeRepo()
    extractor = FakeSkillExtractor(skills=["python", "kubernetes"])

    service = ApplicationService(
        repository=repo,
        tracking_service=tracking,
        ingestion_orchestrator=ingestion,
        skill_extractor=extractor,
    )

    agg = await service.create_from_manual(
        title="SRE", company="Acme", description="Run k8s clusters", url=None
    )

    assert agg.job_snapshot is not None
    assert agg.job_snapshot.required_skills == ["python", "kubernetes"]
    assert agg.job_snapshot.source == JobSnapshotSource.LLM_EXTRACTED.value
    assert extractor.called_with == "Run k8s clusters"


@pytest.mark.asyncio
async def test_create_from_manual_with_empty_extraction_uses_manual_source() -> None:
    ingestion = FakeIngestionOrchestrator()
    tracking = FakeTrackingService()
    repo = FakeRepo()
    extractor = FakeSkillExtractor(skills=[])

    service = ApplicationService(
        repository=repo,
        tracking_service=tracking,
        ingestion_orchestrator=ingestion,
        skill_extractor=extractor,
    )

    agg = await service.create_from_manual(
        title="X", company="Y", description="job desc", url=None
    )
    assert agg.job_snapshot is not None
    assert agg.job_snapshot.required_skills == []
    assert agg.job_snapshot.source == JobSnapshotSource.MANUAL.value


@pytest.mark.asyncio
async def test_update_snapshot_in_place() -> None:
    ingestion = FakeIngestionOrchestrator()
    tracking = FakeTrackingService()
    repo = FakeRepo()
    extractor = FakeSkillExtractor(skills=[])

    service = ApplicationService(
        repository=repo,
        tracking_service=tracking,
        ingestion_orchestrator=ingestion,
        skill_extractor=extractor,
    )

    agg = await service.create_from_manual("X", "Y", "desc", url=None)
    updated = service.update_snapshot(
        agg.id, description="new desc", required_skills=["docker"]
    )
    assert updated.job_snapshot is not None
    assert updated.job_snapshot.description == "new desc"
    assert updated.job_snapshot.required_skills == ["docker"]


@pytest.mark.asyncio
async def test_regenerate_skills_calls_extractor() -> None:
    ingestion = FakeIngestionOrchestrator()
    tracking = FakeTrackingService()
    repo = FakeRepo()
    extractor = FakeSkillExtractor(skills=["aws"])

    service = ApplicationService(
        repository=repo,
        tracking_service=tracking,
        ingestion_orchestrator=ingestion,
        skill_extractor=extractor,
    )
    agg = await service.create_from_manual("X", "Y", "desc", url=None)
    extractor.skills = ["docker", "k8s"]  # change return
    extractor.called_with = None

    refreshed = await service.regenerate_skills(agg.id)
    assert refreshed.job_snapshot is not None
    assert refreshed.job_snapshot.required_skills == ["docker", "k8s"]
    assert extractor.called_with == "desc"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/applications/test_application_service.py -v`
Expected: FAIL with import error.

- [ ] **Step 4: Implement `ApplicationService`**

`backend/src/hiresense/applications/domain/application_service.py`:

```python
from __future__ import annotations

import uuid
from typing import Any

from hiresense.applications.domain.aggregate import (
    ApplicationAggregate,
    CvOptimizationView,
    InterviewPrepView,
    JobSnapshotView,
    MatchView,
)
from hiresense.applications.domain.models import ApplicationJobSnapshot, JobSnapshotSource
from hiresense.applications.domain.skill_extractor import SkillExtractor
from hiresense.applications.ports import ApplicationRepositoryPort
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


class ApplicationService:
    def __init__(
        self,
        repository: ApplicationRepositoryPort,
        tracking_service: Any,
        ingestion_orchestrator: Any,
        skill_extractor: SkillExtractor,
    ) -> None:
        self._repo = repository
        self._tracking = tracking_service
        self._ingestion = ingestion_orchestrator
        self._extractor = skill_extractor

    async def create_from_ingested(self, job_id: str) -> ApplicationAggregate:
        job = self._ingestion.get_job_by_id(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        tracked = self._tracking.track_from_ingestion(job_id)
        snapshot = ApplicationJobSnapshot(
            application_id=tracked.id,
            description=getattr(job, "description", "") or "",
            required_skills=list(getattr(job, "skills", []) or []),
            source=JobSnapshotSource.INGESTED.value,
        )
        self._repo.create_snapshot(snapshot)
        return self._build_aggregate(tracked)

    async def create_from_manual(
        self,
        title: str,
        company: str,
        description: str,
        url: str | None,
        notes: str | None = None,
    ) -> ApplicationAggregate:
        tracked = self._tracking.track_job(title=title, company=company, url=url, notes=notes)
        skills = await self._extractor.extract(description)
        source = (
            JobSnapshotSource.LLM_EXTRACTED.value
            if skills
            else JobSnapshotSource.MANUAL.value
        )
        snapshot = ApplicationJobSnapshot(
            application_id=tracked.id,
            description=description,
            required_skills=skills,
            source=source,
        )
        self._repo.create_snapshot(snapshot)
        return self._build_aggregate(tracked)

    def get(self, application_id: uuid.UUID) -> ApplicationAggregate:
        tracked = self._tracking.get(application_id)
        return self._build_aggregate(tracked)

    def list(self, status: ApplicationStatus | None = None) -> list[ApplicationAggregate]:
        tracked_list = self._tracking.list(status=status)
        return [self._build_aggregate(t) for t in tracked_list]

    def remove(self, application_id: uuid.UUID) -> None:
        self._tracking.remove(application_id)

    def update_snapshot(
        self,
        application_id: uuid.UUID,
        description: str | None = None,
        required_skills: list[str] | None = None,
    ) -> ApplicationAggregate:
        snap = self._repo.get_snapshot(application_id)
        if snap is None:
            raise ValueError(f"Snapshot for {application_id} not found")
        if description is not None:
            snap.description = description
        if required_skills is not None:
            snap.required_skills = required_skills
        self._repo.save_snapshot(snap)
        tracked = self._tracking.get(application_id)
        return self._build_aggregate(tracked)

    async def regenerate_skills(self, application_id: uuid.UUID) -> ApplicationAggregate:
        snap = self._repo.get_snapshot(application_id)
        if snap is None:
            raise ValueError(f"Snapshot for {application_id} not found")
        snap.required_skills = await self._extractor.extract(snap.description)
        if snap.required_skills:
            snap.source = JobSnapshotSource.LLM_EXTRACTED.value
        self._repo.save_snapshot(snap)
        tracked = self._tracking.get(application_id)
        return self._build_aggregate(tracked)

    # ----- internal ----------------------------------------------------

    def _build_aggregate(self, tracked: TrackedApplication) -> ApplicationAggregate:
        snap_orm = self._repo.get_snapshot(tracked.id)
        snap_view = (
            JobSnapshotView(
                id=snap_orm.id,
                description=snap_orm.description,
                required_skills=list(snap_orm.required_skills or []),
                source=snap_orm.source,
                updated_at=snap_orm.updated_at,
            )
            if snap_orm is not None
            else None
        )

        latest_match = self._repo.get_latest_match(tracked.id)
        match_view = (
            MatchView(
                id=latest_match.id,
                overall_score=latest_match.overall_score,
                semantic_score=latest_match.semantic_score,
                skill_score=latest_match.skill_score,
                experience_score=latest_match.experience_score,
                language_score=latest_match.language_score,
                matched_skills=list(latest_match.matched_skills or []),
                missing_skills=list(latest_match.missing_skills or []),
                pros=list(latest_match.pros or []),
                cons=list(latest_match.cons or []),
                recommendations=list(latest_match.recommendations or []),
                cv_language=latest_match.cv_language,
                created_at=latest_match.created_at,
            )
            if latest_match is not None
            else None
        )

        latest_opt = self._repo.get_latest_optimization(tracked.id)
        opt_view = (
            CvOptimizationView(
                id=latest_opt.id,
                match_id=latest_opt.match_id,
                cv_language=latest_opt.cv_language,
                original_tex=latest_opt.original_tex,
                optimized_tex=latest_opt.optimized_tex,
                improvement_summary=latest_opt.improvement_summary,
                changes=list(latest_opt.changes or []),
                created_at=latest_opt.created_at,
            )
            if latest_opt is not None
            else None
        )

        latest_prep = self._repo.get_latest_interview_prep(tracked.id)
        prep_view = (
            InterviewPrepView(
                id=latest_prep.id,
                competencies_to_probe=list(latest_prep.competencies_to_probe or []),
                technical_topics=list(latest_prep.technical_topics or []),
                negotiation_points=list(latest_prep.negotiation_points or []),
                matched_stories=list(latest_prep.matched_stories or []),
                created_at=latest_prep.created_at,
            )
            if latest_prep is not None
            else None
        )

        return ApplicationAggregate(
            id=tracked.id,
            job_id=tracked.job_id,
            title=tracked.title,
            company=tracked.company,
            url=tracked.url,
            status=tracked.status,
            notes=tracked.notes,
            applied_at=tracked.applied_at,
            created_at=tracked.created_at,
            updated_at=tracked.updated_at,
            job_snapshot=snap_view,
            latest_match=match_view,
            latest_optimization=opt_view,
            latest_interview_prep=prep_view,
            match_count=len(self._repo.list_matches(tracked.id)),
            optimization_count=len(self._repo.list_optimizations(tracked.id)),
            interview_prep_count=len(self._repo.list_interview_preps(tracked.id)),
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/applications/test_application_service.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/applications/domain/aggregate.py \
        backend/src/hiresense/applications/domain/application_service.py \
        backend/tests/unit/applications/test_application_service.py
git commit -m "feat(applications): add ApplicationService and aggregate views"
```

---

### Task B3: ArtifactService (orchestrates match / optimize / interview-prep)

**Files:**
- Create: `backend/src/hiresense/applications/domain/artifact_service.py`
- Test: `backend/tests/unit/applications/test_artifact_service.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/unit/applications/test_artifact_service.py`:

```python
from __future__ import annotations

import uuid

import pytest

from hiresense.applications.domain.artifact_service import ArtifactService
from hiresense.applications.domain.models import (
    ApplicationCvOptimization,
    ApplicationInterviewPrep,
    ApplicationJobSnapshot,
    ApplicationMatch,
    JobSnapshotSource,
)


class FakeRepo:
    def __init__(self, snapshot: ApplicationJobSnapshot | None = None) -> None:
        self._snapshot = snapshot
        self.matches: list[ApplicationMatch] = []
        self.opts: list[ApplicationCvOptimization] = []
        self.preps: list[ApplicationInterviewPrep] = []

    def get_snapshot(self, application_id):
        return self._snapshot

    def create_match(self, match):
        match.id = match.id or uuid.uuid4()
        self.matches.append(match)
        return match

    def get_latest_match(self, application_id):
        return self.matches[-1] if self.matches else None

    def get_match(self, match_id):
        return next((m for m in self.matches if m.id == match_id), None)

    def create_optimization(self, opt):
        opt.id = opt.id or uuid.uuid4()
        self.opts.append(opt)
        return opt

    def create_interview_prep(self, prep):
        prep.id = prep.id or uuid.uuid4()
        self.preps.append(prep)
        return prep


class FakeMatchResult:
    def __init__(self) -> None:
        from hiresense.matching.domain.models import ScoreBreakdown
        self.overall_score = 0.75
        self.breakdown = ScoreBreakdown(
            semantic_score=0.8, skill_score=0.7, experience_score=0.75, language_score=0.7,
        )
        self.matched_skills = ["python"]
        self.missing_skills = ["k8s"]
        self.pros = ["good"]
        self.cons = ["short on infra"]
        self.recommendations = ["learn k8s"]


class FakeMatchingOrchestrator:
    def __init__(self) -> None:
        self.last_args: dict | None = None

    async def analyze(self, *, job_id, cv_id, job_description, job_skills, cv_summary, cv_skills, **kwargs):
        self.last_args = {
            "job_description": job_description,
            "job_skills": job_skills,
            "cv_summary": cv_summary,
            "cv_skills": cv_skills,
        }
        return FakeMatchResult()


class FakeProfile:
    def __init__(self, language: str, summary: str, skills: list[str], raw_tex: str = "") -> None:
        self.language = language
        self.summary = summary
        self.skills = skills
        self.raw_tex = raw_tex


class FakeProfileService:
    def __init__(self, profile: FakeProfile | None) -> None:
        self._profile = profile

    def get_for_language(self, language: str) -> FakeProfile | None:
        return self._profile


class FakeOptimizerResult:
    def __init__(self) -> None:
        self.optimized_tex = "OPT_TEX"
        self.improvement_summary = "tightened skills"
        self.changes = [{"section": "skills", "before": "x", "after": "y"}]


class FakeOptimizer:
    def __init__(self) -> None:
        self.last_args: dict | None = None

    async def optimize(self, *, match_id, job_id, cv_id, original_tex, job_description, job_skills, missing_skills, recommendations):
        self.last_args = {
            "original_tex": original_tex,
            "job_skills": job_skills,
            "missing_skills": missing_skills,
        }
        return FakeOptimizerResult()


class FakePrepResult:
    def __init__(self) -> None:
        self.job_title = "X"
        self.company = "Y"
        self.matched_stories = []
        self.competencies_to_probe = ["leadership"]
        self.technical_topics = ["k8s"]
        self.negotiation_points = ["remote"]


class FakeInterviewPrepService:
    def __init__(self) -> None:
        self.last_job: dict | None = None

    async def prepare(self, job: dict):
        self.last_job = job
        return FakePrepResult()


@pytest.mark.asyncio
async def test_generate_match_uses_snapshot_and_profile() -> None:
    app_id = uuid.uuid4()
    snap = ApplicationJobSnapshot(
        application_id=app_id,
        description="job desc",
        required_skills=["python", "k8s"],
        source=JobSnapshotSource.MANUAL.value,
    )
    repo = FakeRepo(snapshot=snap)
    matching = FakeMatchingOrchestrator()
    profiles = FakeProfileService(FakeProfile("en", "I am a senior engineer.", ["python"]))

    service = ArtifactService(
        repository=repo,
        matching_orchestrator=matching,
        cv_optimizer=None,
        interview_prep_service=None,
        profile_service=profiles,
    )

    result = await service.generate_match(app_id, cv_language="en")
    assert result.overall_score == 0.75
    assert result.matched_skills == ["python"]
    assert matching.last_args["job_description"] == "job desc"
    assert matching.last_args["job_skills"] == ["python", "k8s"]
    assert matching.last_args["cv_skills"] == ["python"]


@pytest.mark.asyncio
async def test_generate_match_raises_when_no_snapshot() -> None:
    repo = FakeRepo(snapshot=None)
    service = ArtifactService(
        repository=repo,
        matching_orchestrator=FakeMatchingOrchestrator(),
        cv_optimizer=None,
        interview_prep_service=None,
        profile_service=FakeProfileService(FakeProfile("en", "s", [])),
    )
    with pytest.raises(ValueError, match="Snapshot"):
        await service.generate_match(uuid.uuid4(), cv_language="en")


@pytest.mark.asyncio
async def test_generate_match_raises_when_no_profile() -> None:
    snap = ApplicationJobSnapshot(
        application_id=uuid.uuid4(), description="d", required_skills=[], source="manual",
    )
    repo = FakeRepo(snapshot=snap)
    service = ArtifactService(
        repository=repo,
        matching_orchestrator=FakeMatchingOrchestrator(),
        cv_optimizer=None,
        interview_prep_service=None,
        profile_service=FakeProfileService(None),
    )
    with pytest.raises(ValueError, match="Profile"):
        await service.generate_match(uuid.uuid4(), cv_language="en")


@pytest.mark.asyncio
async def test_generate_optimization_pulls_missing_skills_from_match() -> None:
    app_id = uuid.uuid4()
    snap = ApplicationJobSnapshot(
        application_id=app_id, description="desc", required_skills=["python", "k8s"], source="manual",
    )
    repo = FakeRepo(snapshot=snap)
    # Pre-populate a match
    match = ApplicationMatch(
        id=uuid.uuid4(),
        application_id=app_id,
        overall_score=0.7, semantic_score=0.7, skill_score=0.5,
        experience_score=0.8, language_score=0.8,
        matched_skills=["python"], missing_skills=["k8s"],
        pros=[], cons=[], recommendations=["learn k8s"],
        cv_language="en",
    )
    repo.matches.append(match)

    profiles = FakeProfileService(FakeProfile("en", "summary", ["python"], raw_tex=r"\documentclass{}"))
    optimizer = FakeOptimizer()

    service = ArtifactService(
        repository=repo,
        matching_orchestrator=FakeMatchingOrchestrator(),
        cv_optimizer=optimizer,
        interview_prep_service=None,
        profile_service=profiles,
    )

    result = await service.generate_optimization(app_id, cv_language="en", match_id=None)
    assert result.optimized_tex == "OPT_TEX"
    assert optimizer.last_args["job_skills"] == ["python", "k8s"]
    assert optimizer.last_args["missing_skills"] == ["k8s"]


@pytest.mark.asyncio
async def test_generate_optimization_raises_without_match() -> None:
    snap = ApplicationJobSnapshot(
        application_id=uuid.uuid4(), description="d", required_skills=["x"], source="manual",
    )
    repo = FakeRepo(snapshot=snap)
    profiles = FakeProfileService(FakeProfile("en", "s", ["x"], raw_tex=r"\documentclass{}"))
    service = ArtifactService(
        repository=repo,
        matching_orchestrator=FakeMatchingOrchestrator(),
        cv_optimizer=FakeOptimizer(),
        interview_prep_service=None,
        profile_service=profiles,
    )
    with pytest.raises(ValueError, match="match"):
        await service.generate_optimization(uuid.uuid4(), cv_language="en", match_id=None)


@pytest.mark.asyncio
async def test_generate_interview_prep_uses_snapshot() -> None:
    app_id = uuid.uuid4()
    snap = ApplicationJobSnapshot(
        application_id=app_id, description="desc", required_skills=["x"], source="manual",
    )
    repo = FakeRepo(snapshot=snap)
    prep_service = FakeInterviewPrepService()

    # We also need the tracked application title/company; use a fake injected via _build_job_dict.
    # For this unit test we pass them in via a helper-friendly seam:
    class FakeTracked:
        title = "Software Engineer"
        company = "Fieldguide"

    class FakeTrackingForPrep:
        def get(self, _):
            return FakeTracked()

    service = ArtifactService(
        repository=repo,
        matching_orchestrator=FakeMatchingOrchestrator(),
        cv_optimizer=None,
        interview_prep_service=prep_service,
        profile_service=FakeProfileService(FakeProfile("en", "s", [])),
        tracking_service=FakeTrackingForPrep(),
    )

    result = await service.generate_interview_prep(app_id)
    assert result.competencies_to_probe == ["leadership"]
    assert prep_service.last_job["title"] == "Software Engineer"
    assert prep_service.last_job["company"] == "Fieldguide"
    assert prep_service.last_job["description"] == "desc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/applications/test_artifact_service.py -v`
Expected: FAIL with import error.

- [ ] **Step 3: Implement `ArtifactService`**

`backend/src/hiresense/applications/domain/artifact_service.py`:

```python
from __future__ import annotations

import uuid
from typing import Any

from hiresense.applications.domain.aggregate import (
    CvOptimizationView,
    InterviewPrepView,
    MatchView,
)
from hiresense.applications.domain.models import (
    ApplicationCvOptimization,
    ApplicationInterviewPrep,
    ApplicationMatch,
)
from hiresense.applications.ports import ApplicationRepositoryPort


class ArtifactService:
    def __init__(
        self,
        repository: ApplicationRepositoryPort,
        matching_orchestrator: Any,
        cv_optimizer: Any,
        interview_prep_service: Any,
        profile_service: Any,
        tracking_service: Any | None = None,
    ) -> None:
        self._repo = repository
        self._matching = matching_orchestrator
        self._optimizer = cv_optimizer
        self._prep = interview_prep_service
        self._profiles = profile_service
        self._tracking = tracking_service

    async def generate_match(
        self,
        application_id: uuid.UUID,
        cv_language: str,
    ) -> MatchView:
        snapshot = self._repo.get_snapshot(application_id)
        if snapshot is None:
            raise ValueError(f"Snapshot for {application_id} not found")

        profile = self._profiles.get_for_language(cv_language)
        if profile is None:
            raise ValueError(f"Profile for language '{cv_language}' not found")

        cv_summary = getattr(profile, "summary", "") or ""
        cv_skills = list(getattr(profile, "skills", []) or [])

        result = await self._matching.analyze(
            job_id=str(application_id),
            cv_id=cv_language,
            job_description=snapshot.description,
            job_skills=list(snapshot.required_skills or []),
            cv_summary=cv_summary,
            cv_skills=cv_skills,
        )

        # Re-compute missing skills server-side from snapshot vs profile (case-insensitive)
        required_lower = {s.lower() for s in (snapshot.required_skills or [])}
        cv_skills_lower = {s.lower() for s in cv_skills}
        missing = sorted(required_lower - cv_skills_lower)
        matched = sorted(required_lower & cv_skills_lower)

        row = ApplicationMatch(
            application_id=application_id,
            overall_score=result.overall_score,
            semantic_score=result.breakdown.semantic_score,
            skill_score=result.breakdown.skill_score,
            experience_score=result.breakdown.experience_score,
            language_score=result.breakdown.language_score,
            matched_skills=list(result.matched_skills) if result.matched_skills else matched,
            missing_skills=list(result.missing_skills) if result.missing_skills else missing,
            pros=list(result.pros or []),
            cons=list(result.cons or []),
            recommendations=list(result.recommendations or []),
            cv_language=cv_language,
        )
        saved = self._repo.create_match(row)
        return MatchView(
            id=saved.id,
            overall_score=saved.overall_score,
            semantic_score=saved.semantic_score,
            skill_score=saved.skill_score,
            experience_score=saved.experience_score,
            language_score=saved.language_score,
            matched_skills=list(saved.matched_skills or []),
            missing_skills=list(saved.missing_skills or []),
            pros=list(saved.pros or []),
            cons=list(saved.cons or []),
            recommendations=list(saved.recommendations or []),
            cv_language=saved.cv_language,
            created_at=saved.created_at,
        )

    async def generate_optimization(
        self,
        application_id: uuid.UUID,
        cv_language: str,
        match_id: uuid.UUID | None,
    ) -> CvOptimizationView:
        snapshot = self._repo.get_snapshot(application_id)
        if snapshot is None:
            raise ValueError(f"Snapshot for {application_id} not found")

        if match_id is None:
            match = self._repo.get_latest_match(application_id)
        else:
            match = self._repo.get_match(match_id)
        if match is None:
            raise ValueError("No match found — run a match before optimizing")

        profile = self._profiles.get_for_language(cv_language)
        if profile is None:
            raise ValueError(f"Profile for language '{cv_language}' not found")

        original_tex = getattr(profile, "raw_tex", "") or ""

        result = await self._optimizer.optimize(
            match_id=str(match.id),
            job_id=str(application_id),
            cv_id=cv_language,
            original_tex=original_tex,
            job_description=snapshot.description,
            job_skills=list(snapshot.required_skills or []),
            missing_skills=list(match.missing_skills or []),
            recommendations=list(match.recommendations or []),
        )

        row = ApplicationCvOptimization(
            application_id=application_id,
            match_id=match.id,
            cv_language=cv_language,
            original_tex=original_tex,
            optimized_tex=result.optimized_tex,
            improvement_summary=getattr(result, "improvement_summary", "") or "",
            changes=[
                c.model_dump() if hasattr(c, "model_dump") else dict(c)
                for c in getattr(result, "changes", []) or []
            ],
        )
        saved = self._repo.create_optimization(row)
        return CvOptimizationView(
            id=saved.id,
            match_id=saved.match_id,
            cv_language=saved.cv_language,
            original_tex=saved.original_tex,
            optimized_tex=saved.optimized_tex,
            improvement_summary=saved.improvement_summary,
            changes=list(saved.changes or []),
            created_at=saved.created_at,
        )

    async def generate_interview_prep(
        self,
        application_id: uuid.UUID,
    ) -> InterviewPrepView:
        snapshot = self._repo.get_snapshot(application_id)
        if snapshot is None:
            raise ValueError(f"Snapshot for {application_id} not found")
        if self._tracking is None:
            raise RuntimeError("tracking_service not wired into ArtifactService")
        tracked = self._tracking.get(application_id)

        prep = await self._prep.prepare({
            "title": tracked.title,
            "company": tracked.company,
            "description": snapshot.description,
        })

        row = ApplicationInterviewPrep(
            application_id=application_id,
            competencies_to_probe=list(prep.competencies_to_probe or []),
            technical_topics=list(prep.technical_topics or []),
            negotiation_points=list(prep.negotiation_points or []),
            matched_stories=[
                {
                    "story_id": str(m.story_id),
                    "story_title": m.story_title,
                    "relevance": m.relevance,
                }
                for m in prep.matched_stories or []
            ],
        )
        saved = self._repo.create_interview_prep(row)
        return InterviewPrepView(
            id=saved.id,
            competencies_to_probe=list(saved.competencies_to_probe or []),
            technical_topics=list(saved.technical_topics or []),
            negotiation_points=list(saved.negotiation_points or []),
            matched_stories=list(saved.matched_stories or []),
            created_at=saved.created_at,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/applications/test_artifact_service.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/applications/domain/artifact_service.py \
        backend/tests/unit/applications/test_artifact_service.py
git commit -m "feat(applications): add ArtifactService for match/optimize/interview-prep generation"
```

---

### Task B4: Add a profile lookup helper (`ProfileService.get_for_language`)

The existing `ProfileService` exposes per-language data but not via a single `get_for_language(lang)` accessor that returns a uniform object with `.summary`, `.skills`, `.raw_tex`. Add a thin wrapper if it doesn't already exist.

**Files:**
- Modify: `backend/src/hiresense/profile/domain/services.py` (add `get_for_language`)
- Test: `backend/tests/unit/profile/test_services_get_for_language.py`

- [ ] **Step 1: Read the existing service**

Run: `cat backend/src/hiresense/profile/domain/services.py` — locate the class and inspect how profiles are stored / what fields they have.

- [ ] **Step 2: Write the failing test**

`backend/tests/unit/profile/test_services_get_for_language.py`:

```python
from __future__ import annotations

# (Test details depend on actual ProfileService API — read Step 1 output first.
# If get_for_language already exists in some form, skip Step 3 and add a thin alias.)

def test_get_for_language_returns_uniform_view() -> None:
    # Construct service with a stub repo containing an "en" profile having
    # summary, skills, and raw_tex. Assert .get_for_language("en") returns
    # an object exposing those three attributes; .get_for_language("fr") returns None.
    pass  # Replace with concrete asserts after reading services.py.
```

- [ ] **Step 3: Implement**

Add a method to `ProfileService`:

```python
class ProfileLanguageView:
    def __init__(self, language: str, summary: str, skills: list[str], raw_tex: str) -> None:
        self.language = language
        self.summary = summary
        self.skills = skills
        self.raw_tex = raw_tex


class ProfileService:
    # ... existing code ...

    def get_for_language(self, language: str) -> ProfileLanguageView | None:
        profile = self._repo.get_by_language(language)  # or however the repo exposes it
        if profile is None:
            return None
        # Adapt the existing profile fields to the uniform view.
        summary = self._build_summary(profile)
        return ProfileLanguageView(
            language=profile.language,
            summary=summary,
            skills=list(profile.skills or []),
            raw_tex=profile.raw_tex or "",
        )
```

(Concrete implementation depends on what's already in `services.py`. If the repo already exposes per-language profiles via another method, alias it. If multiple profiles per language exist, return the most recent.)

- [ ] **Step 4: Run test**

Run: `cd backend && uv run pytest tests/unit/profile/test_services_get_for_language.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/profile/domain/services.py \
        backend/tests/unit/profile/test_services_get_for_language.py
git commit -m "feat(profile): add get_for_language uniform-view accessor"
```

---

## Phase C — Backend API

### Task C1: Pydantic schemas

**Files:**
- Create: `backend/src/hiresense/applications/api/__init__.py`
- Create: `backend/src/hiresense/applications/api/schemas.py`

- [ ] **Step 1: Define schemas**

`backend/src/hiresense/applications/api/schemas.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator


class CreateApplicationRequest(BaseModel):
    """Either job_id (from ingested job) OR title+company+description (manual)."""
    job_id: uuid.UUID | None = None
    title: str | None = None
    company: str | None = None
    description: str | None = None
    url: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def check_one_of(self) -> "CreateApplicationRequest":
        if self.job_id is None:
            if not self.title or not self.company:
                raise ValueError("title and company are required when job_id is not given")
            if self.description is None:
                raise ValueError("description is required when job_id is not given")
        return self


class UpdateApplicationRequest(BaseModel):
    status: str | None = None
    notes: str | None = None


class UpdateJobSnapshotRequest(BaseModel):
    description: str | None = None
    required_skills: list[str] | None = None


class GenerateMatchRequest(BaseModel):
    cv_language: str = "en"


class GenerateOptimizationRequest(BaseModel):
    cv_language: str = "en"
    match_id: uuid.UUID | None = None


class ApplicationListItemResponse(BaseModel):
    id: uuid.UUID
    title: str
    company: str
    status: str
    url: str | None
    created_at: datetime | None
    has_match: bool
    has_optimization: bool
    has_prep: bool
    latest_match_score: float | None
```

(The full aggregate response is `ApplicationAggregate` from `domain/aggregate.py` — re-exported in `api/__init__.py` so route handlers can use it directly.)

`backend/src/hiresense/applications/api/__init__.py`:

```python
from hiresense.applications.api.schemas import (
    ApplicationListItemResponse,
    CreateApplicationRequest,
    GenerateMatchRequest,
    GenerateOptimizationRequest,
    UpdateApplicationRequest,
    UpdateJobSnapshotRequest,
)

__all__ = [
    "ApplicationListItemResponse",
    "CreateApplicationRequest",
    "GenerateMatchRequest",
    "GenerateOptimizationRequest",
    "UpdateApplicationRequest",
    "UpdateJobSnapshotRequest",
]
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/hiresense/applications/api/
git commit -m "feat(applications): add API request/response schemas"
```

---

### Task C2: DI provider and dependencies

**Files:**
- Create: `backend/src/hiresense/applications/api/provider.py`
- Create: `backend/src/hiresense/applications/api/dependencies.py`

- [ ] **Step 1: Provider**

`backend/src/hiresense/applications/api/provider.py`:

```python
from __future__ import annotations

from hiresense.applications.domain.application_service import ApplicationService
from hiresense.applications.domain.artifact_service import ArtifactService


class ApplicationsProvider:
    def __init__(
        self,
        application_service: ApplicationService,
        artifact_service: ArtifactService,
    ) -> None:
        self._application_service = application_service
        self._artifact_service = artifact_service

    def get_application_service(self) -> ApplicationService:
        return self._application_service

    def get_artifact_service(self) -> ArtifactService:
        return self._artifact_service
```

- [ ] **Step 2: Dependencies**

`backend/src/hiresense/applications/api/dependencies.py`:

```python
from __future__ import annotations

from fastapi import Depends, Request

from hiresense.applications.domain.application_service import ApplicationService
from hiresense.applications.domain.artifact_service import ArtifactService
from hiresense.applications.api.provider import ApplicationsProvider


def _get_provider(request: Request) -> ApplicationsProvider:
    provider = getattr(request.app.state, "applications_provider", None)
    if provider is None:
        raise RuntimeError("applications_provider not configured in app.state")
    return provider


def get_application_service(
    provider: ApplicationsProvider = Depends(_get_provider),
) -> ApplicationService:
    return provider.get_application_service()


def get_artifact_service(
    provider: ApplicationsProvider = Depends(_get_provider),
) -> ArtifactService:
    return provider.get_artifact_service()
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/hiresense/applications/api/provider.py \
        backend/src/hiresense/applications/api/dependencies.py
git commit -m "feat(applications): add DI provider and FastAPI dependencies"
```

---

### Task C3: Routes — application CRUD + snapshot edit

**Files:**
- Create: `backend/src/hiresense/applications/api/routes.py`
- Test: `backend/tests/integration/applications/__init__.py`
- Test: `backend/tests/integration/applications/test_routes_crud.py`

- [ ] **Step 1: Write the failing integration test**

`backend/tests/integration/applications/test_routes_crud.py`:

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hiresense.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_create_manual_application_and_get_aggregate(client):
    resp = client.post(
        "/applications",
        json={"title": "SRE", "company": "Acme", "description": "Run k8s"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    app_id = data["id"]

    resp = client.get(f"/applications/{app_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "SRE"
    assert body["job_snapshot"] is not None
    assert body["job_snapshot"]["description"] == "Run k8s"


def test_create_requires_description_when_no_job_id(client):
    resp = client.post("/applications", json={"title": "SRE", "company": "Acme"})
    assert resp.status_code == 422


def test_list_returns_has_artifact_flags(client):
    client.post("/applications", json={"title": "X", "company": "Y", "description": "Z"})
    resp = client.get("/applications")
    assert resp.status_code == 200
    rows = resp.json()
    assert all("has_match" in r and "has_optimization" in r and "has_prep" in r for r in rows)


def test_update_job_snapshot(client):
    resp = client.post(
        "/applications",
        json={"title": "X", "company": "Y", "description": "old desc"},
    )
    app_id = resp.json()["id"]

    resp = client.put(
        f"/applications/{app_id}/job-snapshot",
        json={"description": "new desc", "required_skills": ["python"]},
    )
    assert resp.status_code == 200
    assert resp.json()["job_snapshot"]["description"] == "new desc"
    assert resp.json()["job_snapshot"]["required_skills"] == ["python"]


def test_delete_application(client):
    resp = client.post(
        "/applications",
        json={"title": "X", "company": "Y", "description": "Z"},
    )
    app_id = resp.json()["id"]
    resp = client.delete(f"/applications/{app_id}")
    assert resp.status_code == 204
    resp = client.get(f"/applications/{app_id}")
    assert resp.status_code == 404
```

`backend/tests/integration/applications/__init__.py`:

```python
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/integration/applications/test_routes_crud.py -v`
Expected: FAIL — route 404s on POST /applications.

- [ ] **Step 3: Implement the routes**

`backend/src/hiresense/applications/api/routes.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from hiresense.applications.api.dependencies import (
    get_application_service,
    get_artifact_service,
)
from hiresense.applications.api.schemas import (
    ApplicationListItemResponse,
    CreateApplicationRequest,
    GenerateMatchRequest,
    GenerateOptimizationRequest,
    UpdateApplicationRequest,
    UpdateJobSnapshotRequest,
)
from hiresense.applications.domain.aggregate import (
    ApplicationAggregate,
    CvOptimizationView,
    InterviewPrepView,
    MatchView,
)
from hiresense.applications.domain.application_service import ApplicationService
from hiresense.applications.domain.artifact_service import ArtifactService
from hiresense.identity.api.dependencies import require_auth

router = APIRouter(
    prefix="/applications",
    tags=["applications"],
    dependencies=[Depends(require_auth)],
)


# -------- application CRUD --------------------------------------------

@router.post("", response_model=ApplicationAggregate, status_code=201)
async def create_application(
    request: CreateApplicationRequest,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationAggregate:
    try:
        if request.job_id is not None:
            return await service.create_from_ingested(str(request.job_id))
        return await service.create_from_manual(
            title=request.title or "",
            company=request.company or "",
            description=request.description or "",
            url=request.url,
            notes=request.notes,
        )
    except ValueError as exc:
        msg = str(exc).lower()
        status_code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("", response_model=list[ApplicationListItemResponse])
def list_applications(
    service: ApplicationService = Depends(get_application_service),
) -> list[ApplicationListItemResponse]:
    aggregates = service.list()
    return [
        ApplicationListItemResponse(
            id=a.id,
            title=a.title,
            company=a.company,
            status=a.status,
            url=a.url,
            created_at=a.created_at,
            has_match=a.match_count > 0,
            has_optimization=a.optimization_count > 0,
            has_prep=a.interview_prep_count > 0,
            latest_match_score=a.latest_match.overall_score if a.latest_match else None,
        )
        for a in aggregates
    ]


@router.get("/{application_id}", response_model=ApplicationAggregate)
def get_application(
    application_id: uuid_mod.UUID,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationAggregate:
    try:
        return service.get(application_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{application_id}", status_code=204)
def delete_application(
    application_id: uuid_mod.UUID,
    service: ApplicationService = Depends(get_application_service),
) -> Response:
    try:
        service.remove(application_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


# -------- job snapshot edits ------------------------------------------

@router.put("/{application_id}/job-snapshot", response_model=ApplicationAggregate)
def update_snapshot(
    application_id: uuid_mod.UUID,
    request: UpdateJobSnapshotRequest,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationAggregate:
    try:
        return service.update_snapshot(
            application_id,
            description=request.description,
            required_skills=request.required_skills,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{application_id}/job-snapshot/regenerate-skills", response_model=ApplicationAggregate)
async def regenerate_skills(
    application_id: uuid_mod.UUID,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationAggregate:
    try:
        return await service.regenerate_skills(application_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# -------- artifact generation -----------------------------------------

@router.post("/{application_id}/match", response_model=MatchView, status_code=201)
async def generate_match(
    application_id: uuid_mod.UUID,
    request: GenerateMatchRequest,
    service: ArtifactService = Depends(get_artifact_service),
) -> MatchView:
    try:
        return await service.generate_match(application_id, cv_language=request.cv_language)
    except ValueError as exc:
        msg = str(exc).lower()
        status_code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/{application_id}/optimize", response_model=CvOptimizationView, status_code=201)
async def generate_optimization(
    application_id: uuid_mod.UUID,
    request: GenerateOptimizationRequest,
    service: ArtifactService = Depends(get_artifact_service),
) -> CvOptimizationView:
    try:
        return await service.generate_optimization(
            application_id,
            cv_language=request.cv_language,
            match_id=request.match_id,
        )
    except ValueError as exc:
        msg = str(exc).lower()
        status_code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/{application_id}/interview-prep", response_model=InterviewPrepView, status_code=201)
async def generate_interview_prep(
    application_id: uuid_mod.UUID,
    service: ArtifactService = Depends(get_artifact_service),
) -> InterviewPrepView:
    try:
        return await service.generate_interview_prep(application_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 4: Wire the provider into `main.py`**

Modify: `backend/src/hiresense/main.py`

Add imports near the top with the other context imports:

```python
from hiresense.applications.api.provider import ApplicationsProvider
from hiresense.applications.api.routes import router as applications_router
from hiresense.applications.domain.application_service import ApplicationService
from hiresense.applications.domain.artifact_service import ArtifactService
from hiresense.applications.domain.skill_extractor import SkillExtractor
from hiresense.applications.infrastructure.repository import ApplicationRepository
```

In the lifespan / startup section where other providers are built (find `tracking_provider = ...` for a sibling pattern), add:

```python
application_repo = ApplicationRepository(session_factory=sync_session_factory)
skill_extractor = SkillExtractor(llm=llm_client)
application_service = ApplicationService(
    repository=application_repo,
    tracking_service=tracking_service,
    ingestion_orchestrator=ingestion_orchestrator,
    skill_extractor=skill_extractor,
)
artifact_service = ArtifactService(
    repository=application_repo,
    matching_orchestrator=matching_orchestrator,
    cv_optimizer=cv_optimizer,
    interview_prep_service=interview_prep_service,
    profile_service=profile_service,
    tracking_service=tracking_service,
)
app.state.applications_provider = ApplicationsProvider(
    application_service=application_service,
    artifact_service=artifact_service,
)
```

Where routers are registered (find `app.include_router(tracking_router)` for the sibling pattern), add:

```python
app.include_router(applications_router)
```

(Variable names like `sync_session_factory`, `llm_client`, `tracking_service`, `ingestion_orchestrator`, `matching_orchestrator`, `cv_optimizer`, `interview_prep_service`, `profile_service` reflect what's already in `main.py`. Read the file first and adapt the actual identifiers — search for `TrackingService` to find the right block.)

- [ ] **Step 5: Run integration test to verify it passes**

Run: `cd backend && uv run pytest tests/integration/applications/test_routes_crud.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/applications/api/routes.py \
        backend/src/hiresense/main.py \
        backend/tests/integration/applications/
git commit -m "feat(applications): wire up application CRUD routes"
```

---

### Task C4: Integration tests for artifact generation routes

**Files:**
- Test: `backend/tests/integration/applications/test_routes_artifacts.py`

- [ ] **Step 1: Write the integration test**

`backend/tests/integration/applications/test_routes_artifacts.py`:

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hiresense.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def application_with_snapshot(client) -> str:
    resp = client.post(
        "/applications",
        json={
            "title": "Backend Engineer",
            "company": "TestCo",
            "description": "Python and FastAPI required. Kubernetes a plus.",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_generate_match_persists_row(client, application_with_snapshot):
    # Requires a default profile to be set up. If the test env doesn't have
    # one, this test will get a 400 — the assertion verifies the contract,
    # not the LLM result. Skip with a clear marker if profile is missing.
    resp = client.post(
        f"/applications/{application_with_snapshot}/match",
        json={"cv_language": "en"},
    )
    if resp.status_code == 400 and "profile" in resp.text.lower():
        pytest.skip("No active profile in test env")
    assert resp.status_code == 201, resp.text
    assert "overall_score" in resp.json()

    # Verify it shows up in the aggregate
    resp = client.get(f"/applications/{application_with_snapshot}")
    assert resp.json()["match_count"] == 1


def test_generate_optimization_requires_match(client, application_with_snapshot):
    resp = client.post(
        f"/applications/{application_with_snapshot}/optimize",
        json={"cv_language": "en"},
    )
    # Either 400 (no match yet) or 400 (no profile) — both acceptable here.
    assert resp.status_code == 400


def test_generate_interview_prep(client, application_with_snapshot):
    resp = client.post(
        f"/applications/{application_with_snapshot}/interview-prep",
    )
    # InterviewPrepService returns gracefully even when LLM is not configured
    # (negotiation_points carries a placeholder string), so this should always 201.
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "competencies_to_probe" in body
```

- [ ] **Step 2: Run test**

Run: `cd backend && uv run pytest tests/integration/applications/test_routes_artifacts.py -v`
Expected: PASS (3 tests; one may be `SKIPPED` if no profile fixture is loaded).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/applications/test_routes_artifacts.py
git commit -m "test(applications): integration tests for artifact generation routes"
```

---

## CHECKPOINT 1 — Verify the backend end-to-end via curl

Before starting the frontend, run the app and walk through the pipeline:

- [ ] **Start the stack:** `docker compose up -d`
- [ ] **Run migrations:** `cd backend && uv run alembic upgrade head`
- [ ] **Boot backend:** `cd backend && uv run uvicorn hiresense.main:app --reload --port 8000`
- [ ] **Create an application from a manual description:**
  ```bash
  curl -X POST http://localhost:8000/applications \
    -H 'Content-Type: application/json' \
    -d '{"title": "SRE", "company": "TestCo", "description": "Python and Kubernetes required."}'
  ```
  Expect: 201 with a snapshot whose `required_skills` is non-empty (LLM extraction).
- [ ] **Run a match:** `curl -X POST .../applications/<id>/match -d '{"cv_language":"en"}'` — expect score breakdown back.
- [ ] **Run an optimization:** `curl -X POST .../applications/<id>/optimize -d '{"cv_language":"en"}'` — expect optimized_tex.
- [ ] **Run prep:** `curl -X POST .../applications/<id>/interview-prep` — expect competencies + topics.
- [ ] **Open `/applications/<id>` in the browser** (FastAPI Swagger at `/docs`) and verify the aggregate has all four sections populated.

Any failure here is a Phase A–C bug — fix before moving to Phase D.

---

## Phase D — Frontend foundation

### Task D1: Angular models for the application aggregate

**Files:**
- Create: `frontend/src/app/pages/applications/models/job-snapshot.model.ts`
- Create: `frontend/src/app/pages/applications/models/application-match.model.ts`
- Create: `frontend/src/app/pages/applications/models/cv-optimization.model.ts`
- Create: `frontend/src/app/pages/applications/models/application-interview-prep.model.ts`
- Create: `frontend/src/app/pages/applications/models/application-aggregate.model.ts`
- Create: `frontend/src/app/pages/applications/models/application-list-item.model.ts`

- [ ] **Step 1: Write the models** (one type per file per project code-style rule)

`job-snapshot.model.ts`:

```typescript
export interface JobSnapshot {
  id: string;
  description: string;
  required_skills: string[];
  source: 'ingested' | 'manual' | 'llm_extracted';
  updated_at: string | null;
}
```

`application-match.model.ts`:

```typescript
export interface ApplicationMatch {
  id: string;
  overall_score: number;
  semantic_score: number;
  skill_score: number;
  experience_score: number;
  language_score: number;
  matched_skills: string[];
  missing_skills: string[];
  pros: string[];
  cons: string[];
  recommendations: string[];
  cv_language: string;
  created_at: string | null;
}
```

`cv-optimization.model.ts`:

```typescript
export interface CvOptimization {
  id: string;
  match_id: string | null;
  cv_language: string;
  original_tex: string;
  optimized_tex: string;
  improvement_summary: string;
  changes: Array<{ section_name?: string; section?: string; original?: string; optimized?: string; reason?: string; before?: string; after?: string }>;
  created_at: string | null;
}
```

`application-interview-prep.model.ts`:

```typescript
export interface ApplicationInterviewPrep {
  id: string;
  competencies_to_probe: string[];
  technical_topics: string[];
  negotiation_points: string[];
  matched_stories: Array<{ story_id: string; story_title: string; relevance: string }>;
  created_at: string | null;
}
```

`application-aggregate.model.ts`:

```typescript
import { JobSnapshot } from './job-snapshot.model';
import { ApplicationMatch } from './application-match.model';
import { CvOptimization } from './cv-optimization.model';
import { ApplicationInterviewPrep } from './application-interview-prep.model';

export interface ApplicationAggregate {
  id: string;
  job_id: string | null;
  title: string;
  company: string;
  url: string | null;
  status: string;
  notes: string | null;
  applied_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  job_snapshot: JobSnapshot | null;
  latest_match: ApplicationMatch | null;
  latest_optimization: CvOptimization | null;
  latest_interview_prep: ApplicationInterviewPrep | null;
  match_count: number;
  optimization_count: number;
  interview_prep_count: number;
}
```

`application-list-item.model.ts`:

```typescript
export interface ApplicationListItem {
  id: string;
  title: string;
  company: string;
  status: string;
  url: string | null;
  created_at: string | null;
  has_match: boolean;
  has_optimization: boolean;
  has_prep: boolean;
  latest_match_score: number | null;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/pages/applications/models/
git commit -m "feat(applications-fe): add aggregate and list-item models"
```

---

### Task D2: ApplicationsService (HTTP client)

**Files:**
- Create: `frontend/src/app/core/services/applications.service.ts`

- [ ] **Step 1: Implement the service**

`frontend/src/app/core/services/applications.service.ts`:

```typescript
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ApplicationAggregate } from '../../pages/applications/models/application-aggregate.model';
import { ApplicationListItem } from '../../pages/applications/models/application-list-item.model';
import { ApplicationMatch } from '../../pages/applications/models/application-match.model';
import { CvOptimization } from '../../pages/applications/models/cv-optimization.model';
import { ApplicationInterviewPrep } from '../../pages/applications/models/application-interview-prep.model';

@Injectable({ providedIn: 'root' })
export class ApplicationsService {
  private http = inject(HttpClient);
  private base = `${environment.apiUrl}/applications`;

  list(): Observable<ApplicationListItem[]> {
    return this.http.get<ApplicationListItem[]>(this.base);
  }

  get(id: string): Observable<ApplicationAggregate> {
    return this.http.get<ApplicationAggregate>(`${this.base}/${id}`);
  }

  createFromJob(jobId: string): Observable<ApplicationAggregate> {
    return this.http.post<ApplicationAggregate>(this.base, { job_id: jobId });
  }

  createManual(payload: {
    title: string;
    company: string;
    description: string;
    url?: string;
    notes?: string;
  }): Observable<ApplicationAggregate> {
    return this.http.post<ApplicationAggregate>(this.base, payload);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }

  updateSnapshot(id: string, payload: {
    description?: string;
    required_skills?: string[];
  }): Observable<ApplicationAggregate> {
    return this.http.put<ApplicationAggregate>(`${this.base}/${id}/job-snapshot`, payload);
  }

  regenerateSkills(id: string): Observable<ApplicationAggregate> {
    return this.http.post<ApplicationAggregate>(`${this.base}/${id}/job-snapshot/regenerate-skills`, {});
  }

  generateMatch(id: string, cvLanguage: string): Observable<ApplicationMatch> {
    return this.http.post<ApplicationMatch>(`${this.base}/${id}/match`, { cv_language: cvLanguage });
  }

  generateOptimization(id: string, payload: { cv_language: string; match_id?: string }): Observable<CvOptimization> {
    return this.http.post<CvOptimization>(`${this.base}/${id}/optimize`, payload);
  }

  generateInterviewPrep(id: string): Observable<ApplicationInterviewPrep> {
    return this.http.post<ApplicationInterviewPrep>(`${this.base}/${id}/interview-prep`, {});
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/core/services/applications.service.ts
git commit -m "feat(applications-fe): add ApplicationsService HTTP client"
```

---

### Task D3: Applications list page (replaces the Tracking page)

**Files:**
- Create: `frontend/src/app/pages/applications/applications.component.ts`
- Create: `frontend/src/app/pages/applications/applications.component.html`
- Create: `frontend/src/app/pages/applications/applications.component.scss`

- [ ] **Step 1: Implement the list component**

`applications.component.ts`:

```typescript
import { Component, OnInit, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { DatePipe, TitleCasePipe } from '@angular/common';
import { ApplicationsService } from '../../core/services/applications.service';
import { ApplicationListItem } from './models/application-list-item.model';

@Component({
  selector: 'app-applications',
  standalone: true,
  imports: [DatePipe, TitleCasePipe],
  templateUrl: './applications.component.html',
  styleUrl: './applications.component.scss',
})
export class ApplicationsComponent implements OnInit {
  private service = inject(ApplicationsService);
  private router = inject(Router);

  applications = signal<ApplicationListItem[]>([]);
  loading = signal(false);
  error = signal('');

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.service.list().subscribe({
      next: (rows) => {
        this.applications.set(rows);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Failed to load applications');
        this.loading.set(false);
      },
    });
  }

  open(id: string): void {
    this.router.navigate(['/dashboard/applications', id]);
  }

  scoreColor(score: number | null): string {
    if (score === null) return '#9ca3af';
    if (score >= 0.7) return '#16a34a';
    if (score >= 0.4) return '#ca8a04';
    return '#dc2626';
  }
}
```

`applications.component.html`:

```html
<div class="page">
  <div class="page-header">
    <h1>Applications</h1>
    <button class="btn-primary" (click)="router.navigate(['/dashboard/applications', 'new'])">+ New application</button>
  </div>

  @if (loading()) {
    <p>Loading...</p>
  } @else if (error()) {
    <div class="alert alert-error">{{ error() }}</div>
  } @else {
    <table class="apps-table">
      <thead>
        <tr>
          <th>Title</th>
          <th>Company</th>
          <th>Status</th>
          <th>Match</th>
          <th>Artifacts</th>
          <th>Created</th>
        </tr>
      </thead>
      <tbody>
        @for (app of applications(); track app.id) {
          <tr (click)="open(app.id)" class="row">
            <td>{{ app.title }}</td>
            <td>{{ app.company }}</td>
            <td>{{ app.status | titlecase }}</td>
            <td>
              @if (app.latest_match_score !== null) {
                <span class="score-pill" [style.background]="scoreColor(app.latest_match_score)">
                  {{ (app.latest_match_score * 100).toFixed(0) }}%
                </span>
              } @else {
                <span class="muted">—</span>
              }
            </td>
            <td>
              <span class="badge" [class.on]="app.has_match">match</span>
              <span class="badge" [class.on]="app.has_optimization">cv</span>
              <span class="badge" [class.on]="app.has_prep">prep</span>
            </td>
            <td>{{ app.created_at | date:'mediumDate' }}</td>
          </tr>
        }
      </tbody>
    </table>
  }
</div>
```

`applications.component.scss`:

```scss
.page-header { display: flex; justify-content: space-between; align-items: center; }
.apps-table { width: 100%; border-collapse: collapse; }
.apps-table th, .apps-table td { padding: 0.5rem; border-bottom: 1px solid #e5e7eb; }
.row { cursor: pointer; }
.row:hover { background: #f9fafb; }
.score-pill { color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.85em; }
.badge { padding: 2px 6px; border-radius: 4px; margin-right: 4px; background: #e5e7eb; color: #9ca3af; font-size: 0.8em; }
.badge.on { background: #10b981; color: white; }
.muted { color: #9ca3af; }
```

Wait — the component template references `router.navigate` but `router` isn't exposed publicly. Fix the component to expose it or add a method.

In `applications.component.ts` change the private `router` to public:

```typescript
constructor(public router: Router) {}
```

Or add a method `newApplication() { this.router.navigate(['/dashboard/applications', 'new']); }` and call it from the template. Use the method approach (cleaner):

In `applications.component.ts` add:

```typescript
newApplication(): void {
  this.router.navigate(['/dashboard/applications', 'new']);
}
```

In `applications.component.html` change the button click to:

```html
<button class="btn-primary" (click)="newApplication()">+ New application</button>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/pages/applications/applications.component.*
git commit -m "feat(applications-fe): add Applications list page"
```

---

### Task D4: Register the new route and update nav

**Files:**
- Modify: `frontend/src/app/app.routes.ts`
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.html` (or wherever the nav lives — find it first)

- [ ] **Step 1: Add the route**

Modify `frontend/src/app/app.routes.ts` — under the dashboard children, add **before** the existing `tracking` route:

```typescript
{
  path: 'applications',
  loadComponent: () =>
    import('./pages/applications/applications.component').then(m => m.ApplicationsComponent),
},
{
  path: 'applications/:id',
  loadComponent: () =>
    import('./pages/applications/application-detail.component').then(m => m.ApplicationDetailComponent),
},
```

(The detail component is built in Phase E. For now this route entry exists ahead of the file; you can stub the file with an empty exported class so this commit compiles.)

- [ ] **Step 2: Stub the detail component**

`frontend/src/app/pages/applications/application-detail.component.ts`:

```typescript
import { Component } from '@angular/core';

@Component({
  selector: 'app-application-detail',
  standalone: true,
  template: '<p>Loading...</p>',
})
export class ApplicationDetailComponent {}
```

- [ ] **Step 3: Update the nav**

Read `frontend/src/app/pages/dashboard/dashboard.component.html` to find the nav links. Add an "Applications" link pointing to `/dashboard/applications` next to the existing "Tracking" link. Don't remove "Tracking" yet — that happens in Phase F.

- [ ] **Step 4: Smoke test**

Run: `cd frontend && npm start` and navigate to `/dashboard/applications`. The page loads, shows the empty state or existing tracked rows.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/app.routes.ts \
        frontend/src/app/pages/applications/application-detail.component.ts \
        frontend/src/app/pages/dashboard/dashboard.component.html
git commit -m "feat(applications-fe): register applications routes and nav entry"
```

---

## Phase E — Frontend detail view

### Task E1: SkillChips reusable component

**Files:**
- Create: `frontend/src/app/pages/applications/components/skill-chips.component.ts`
- Create: `frontend/src/app/pages/applications/components/skill-chips.component.html`
- Create: `frontend/src/app/pages/applications/components/skill-chips.component.scss`

- [ ] **Step 1: Implement**

`skill-chips.component.ts`:

```typescript
import { Component, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-skill-chips',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './skill-chips.component.html',
  styleUrl: './skill-chips.component.scss',
})
export class SkillChipsComponent {
  skills = input<string[]>([]);
  editable = input<boolean>(false);
  add = output<string>();
  remove = output<string>();

  draft = signal('');

  onAdd(): void {
    const value = this.draft().trim().toLowerCase();
    if (!value) return;
    if (this.skills().includes(value)) {
      this.draft.set('');
      return;
    }
    this.add.emit(value);
    this.draft.set('');
  }

  onRemove(skill: string): void {
    this.remove.emit(skill);
  }
}
```

`skill-chips.component.html`:

```html
<div class="chips">
  @for (skill of skills(); track skill) {
    <span class="chip">
      {{ skill }}
      @if (editable()) {
        <button type="button" (click)="onRemove(skill)" class="chip-remove">✕</button>
      }
    </span>
  }
  @if (editable()) {
    <input
      class="chip-input"
      [ngModel]="draft()"
      (ngModelChange)="draft.set($event)"
      (keyup.enter)="onAdd()"
      placeholder="+ add skill"
    />
  }
</div>
```

`skill-chips.component.scss`:

```scss
.chips { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.chip { padding: 2px 8px; border-radius: 12px; background: #e0f2fe; color: #0369a1; font-size: 0.9em; display: inline-flex; align-items: center; gap: 4px; }
.chip-remove { background: none; border: none; color: inherit; cursor: pointer; padding: 0; font-size: 0.9em; }
.chip-input { border: 1px dashed #cbd5e1; border-radius: 12px; padding: 2px 8px; font-size: 0.9em; min-width: 120px; }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/pages/applications/components/skill-chips.component.*
git commit -m "feat(applications-fe): add SkillChips reusable component"
```

---

### Task E2: ApplicationDetailComponent shell with tabs

**Files:**
- Replace stub: `frontend/src/app/pages/applications/application-detail.component.ts`
- Create: `frontend/src/app/pages/applications/application-detail.component.html`
- Create: `frontend/src/app/pages/applications/application-detail.component.scss`

- [ ] **Step 1: Implement the shell**

`application-detail.component.ts`:

```typescript
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { TitleCasePipe } from '@angular/common';
import { ApplicationsService } from '../../core/services/applications.service';
import { ApplicationAggregate } from './models/application-aggregate.model';

type TabKey = 'job' | 'match' | 'cv' | 'interview';

@Component({
  selector: 'app-application-detail',
  standalone: true,
  imports: [TitleCasePipe],
  templateUrl: './application-detail.component.html',
  styleUrl: './application-detail.component.scss',
})
export class ApplicationDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private service = inject(ApplicationsService);

  aggregate = signal<ApplicationAggregate | null>(null);
  loading = signal(true);
  error = signal('');
  activeTab = signal<TabKey>('job');

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id || id === 'new') {
      // 'new' is the create-dialog path — open it inline. For now, navigate back to list.
      this.router.navigate(['/dashboard/applications']);
      return;
    }
    this.load(id);
  }

  load(id: string): void {
    this.loading.set(true);
    this.service.get(id).subscribe({
      next: (agg) => {
        this.aggregate.set(agg);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Failed to load application');
        this.loading.set(false);
      },
    });
  }

  setTab(tab: TabKey): void {
    this.activeTab.set(tab);
  }

  reload(): void {
    const agg = this.aggregate();
    if (agg) this.load(agg.id);
  }
}
```

`application-detail.component.html`:

```html
@if (loading()) {
  <p>Loading...</p>
} @else if (error()) {
  <div class="alert alert-error">{{ error() }}</div>
} @else if (aggregate(); as agg) {
  <div class="detail-page">
    <header class="detail-header">
      <div>
        <h1>{{ agg.title }}</h1>
        <p class="company">{{ agg.company }} · <span class="status">{{ agg.status | titlecase }}</span></p>
      </div>
      @if (agg.url) {
        <a [href]="agg.url" target="_blank" rel="noopener" class="btn-secondary">Open job ↗</a>
      }
    </header>

    <nav class="tabs">
      <button [class.active]="activeTab() === 'job'" (click)="setTab('job')">Job</button>
      <button [class.active]="activeTab() === 'match'" (click)="setTab('match')">
        Match @if (agg.match_count) { <span class="badge">{{ agg.match_count }}</span> }
      </button>
      <button [class.active]="activeTab() === 'cv'" (click)="setTab('cv')">
        CV @if (agg.optimization_count) { <span class="badge">{{ agg.optimization_count }}</span> }
      </button>
      <button [class.active]="activeTab() === 'interview'" (click)="setTab('interview')">
        Interview @if (agg.interview_prep_count) { <span class="badge">{{ agg.interview_prep_count }}</span> }
      </button>
    </nav>

    <section class="tab-body">
      @switch (activeTab()) {
        @case ('job')       { <p>Job tab placeholder. Snapshot description: {{ agg.job_snapshot?.description }}</p> }
        @case ('match')     { <p>Match tab placeholder.</p> }
        @case ('cv')        { <p>CV tab placeholder.</p> }
        @case ('interview') { <p>Interview tab placeholder.</p> }
      }
    </section>
  </div>
}
```

`application-detail.component.scss`:

```scss
.detail-header { display: flex; justify-content: space-between; align-items: flex-start; }
.company { color: #6b7280; }
.tabs { display: flex; gap: 4px; border-bottom: 1px solid #e5e7eb; margin: 1rem 0; }
.tabs button { padding: 8px 16px; background: none; border: none; cursor: pointer; border-bottom: 2px solid transparent; }
.tabs button.active { border-bottom-color: #2563eb; color: #2563eb; }
.badge { background: #e5e7eb; padding: 1px 6px; border-radius: 8px; font-size: 0.75em; margin-left: 4px; }
.tab-body { padding: 1rem 0; }
```

- [ ] **Step 2: Smoke test**

Run: `cd frontend && npm start`, visit `/dashboard/applications/<some-id>`. Tab switching works; placeholders render.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pages/applications/application-detail.component.*
git commit -m "feat(applications-fe): add detail-view shell with tabs"
```

---

### Task E3: Job tab (snapshot description + skills edit)

**Files:**
- Create: `frontend/src/app/pages/applications/components/job-tab.component.ts`
- Create: `frontend/src/app/pages/applications/components/job-tab.component.html`
- Create: `frontend/src/app/pages/applications/components/job-tab.component.scss`
- Modify: `frontend/src/app/pages/applications/application-detail.component.ts` and `.html` to use the new tab.

- [ ] **Step 1: Implement the tab component**

`job-tab.component.ts`:

```typescript
import { Component, OnChanges, SimpleChanges, computed, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';
import { SkillChipsComponent } from './skill-chips.component';

@Component({
  selector: 'app-job-tab',
  standalone: true,
  imports: [FormsModule, SkillChipsComponent],
  templateUrl: './job-tab.component.html',
  styleUrl: './job-tab.component.scss',
})
export class JobTabComponent implements OnChanges {
  private service = inject(ApplicationsService);

  aggregate = input.required<ApplicationAggregate>();
  changed = output<void>();

  description = signal('');
  skills = signal<string[]>([]);
  saving = signal(false);
  regenerating = signal(false);
  error = signal('');

  ngOnChanges(_changes: SimpleChanges): void {
    const snap = this.aggregate().job_snapshot;
    this.description.set(snap?.description ?? '');
    this.skills.set(snap?.required_skills ?? []);
  }

  source = computed(() => this.aggregate().job_snapshot?.source ?? 'manual');

  save(): void {
    this.saving.set(true);
    this.error.set('');
    this.service
      .updateSnapshot(this.aggregate().id, {
        description: this.description(),
        required_skills: this.skills(),
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.changed.emit();
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Save failed');
          this.saving.set(false);
        },
      });
  }

  regenerate(): void {
    this.regenerating.set(true);
    this.error.set('');
    this.service.regenerateSkills(this.aggregate().id).subscribe({
      next: (agg) => {
        this.skills.set(agg.job_snapshot?.required_skills ?? []);
        this.regenerating.set(false);
        this.changed.emit();
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Regenerate failed');
        this.regenerating.set(false);
      },
    });
  }

  addSkill(skill: string): void {
    this.skills.update((arr) => [...arr, skill]);
  }

  removeSkill(skill: string): void {
    this.skills.update((arr) => arr.filter((s) => s !== skill));
  }
}
```

`job-tab.component.html`:

```html
<div class="job-tab">
  <div class="row">
    <label>Description</label>
    <textarea rows="8" [ngModel]="description()" (ngModelChange)="description.set($event)"></textarea>
  </div>

  <div class="row">
    <div class="row-header">
      <label>Required skills</label>
      <span class="source-badge">source: {{ source() }}</span>
      <button class="btn-secondary btn-sm" (click)="regenerate()" [disabled]="regenerating()">
        @if (regenerating()) { Regenerating... } @else { Regenerate from description }
      </button>
    </div>
    <app-skill-chips
      [skills]="skills()"
      [editable]="true"
      (add)="addSkill($event)"
      (remove)="removeSkill($event)" />
  </div>

  @if (error()) {
    <div class="alert alert-error">{{ error() }}</div>
  }

  <div class="actions">
    <button class="btn-primary" (click)="save()" [disabled]="saving()">
      @if (saving()) { Saving... } @else { Save snapshot }
    </button>
  </div>
</div>
```

`job-tab.component.scss`:

```scss
.row { margin-bottom: 1rem; }
.row-header { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem; }
.source-badge { font-size: 0.8em; color: #6b7280; }
textarea { width: 100%; font-family: inherit; padding: 8px; }
.btn-sm { font-size: 0.85em; padding: 4px 10px; }
.actions { display: flex; gap: 8px; }
```

- [ ] **Step 2: Wire into the detail component**

In `application-detail.component.ts`:

```typescript
import { JobTabComponent } from './components/job-tab.component';
```

Add to `imports: [TitleCasePipe, JobTabComponent]`.

In `application-detail.component.html` replace the `@case ('job')` block with:

```html
@case ('job') {
  <app-job-tab [aggregate]="agg" (changed)="reload()" />
}
```

- [ ] **Step 3: Smoke test**

Run: edit a description + skills, click Save → page reloads with new values. Click Regenerate → skills update from LLM.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pages/applications/components/job-tab.component.* \
        frontend/src/app/pages/applications/application-detail.component.*
git commit -m "feat(applications-fe): add Job tab with snapshot edit and skill regeneration"
```

---

### Task E4: Match tab

**Files:**
- Create: `frontend/src/app/pages/applications/components/match-tab.component.ts`
- Create: `frontend/src/app/pages/applications/components/match-tab.component.html`
- Create: `frontend/src/app/pages/applications/components/match-tab.component.scss`
- Modify: `application-detail.component.{ts,html}`

- [ ] **Step 1: Implement**

`match-tab.component.ts`:

```typescript
import { Component, computed, inject, input, output, signal } from '@angular/core';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';
import { SkillChipsComponent } from './skill-chips.component';

@Component({
  selector: 'app-match-tab',
  standalone: true,
  imports: [SkillChipsComponent],
  templateUrl: './match-tab.component.html',
  styleUrl: './match-tab.component.scss',
})
export class MatchTabComponent {
  private service = inject(ApplicationsService);

  aggregate = input.required<ApplicationAggregate>();
  changed = output<void>();

  cvLanguage = signal<'en' | 'es'>('en');
  running = signal(false);
  error = signal('');

  match = computed(() => this.aggregate().latest_match);

  pct(score: number): string {
    return (score * 100).toFixed(0);
  }

  color(score: number): string {
    if (score >= 0.7) return '#16a34a';
    if (score >= 0.4) return '#ca8a04';
    return '#dc2626';
  }

  run(): void {
    this.running.set(true);
    this.error.set('');
    this.service.generateMatch(this.aggregate().id, this.cvLanguage()).subscribe({
      next: () => {
        this.running.set(false);
        this.changed.emit();
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Match failed');
        this.running.set(false);
      },
    });
  }
}
```

`match-tab.component.html`:

```html
<div class="match-tab">
  <div class="controls">
    <label>CV language:</label>
    <select [value]="cvLanguage()" (change)="cvLanguage.set($any($event.target).value)">
      <option value="en">English</option>
      <option value="es">Spanish</option>
    </select>
    <button class="btn-primary" (click)="run()" [disabled]="running()">
      @if (running()) { Running... } @else { @if (match()) { Re-run match } @else { Run match } }
    </button>
  </div>

  @if (error()) {
    <div class="alert alert-error">{{ error() }}</div>
  }

  @if (match(); as m) {
    <div class="score-grid">
      <div class="score-card">
        <span class="label">Overall</span>
        <span class="value" [style.color]="color(m.overall_score)">{{ pct(m.overall_score) }}%</span>
      </div>
      <div class="score-card"><span class="label">Semantic</span><span class="value">{{ pct(m.semantic_score) }}%</span></div>
      <div class="score-card"><span class="label">Skills</span><span class="value">{{ pct(m.skill_score) }}%</span></div>
      <div class="score-card"><span class="label">Experience</span><span class="value">{{ pct(m.experience_score) }}%</span></div>
      <div class="score-card"><span class="label">Language</span><span class="value">{{ pct(m.language_score) }}%</span></div>
    </div>

    <div class="row">
      <h3>Matched skills</h3>
      <app-skill-chips [skills]="m.matched_skills" />
    </div>
    <div class="row">
      <h3>Missing skills</h3>
      <app-skill-chips [skills]="m.missing_skills" />
    </div>

    @if (m.pros.length) {
      <div class="row"><h3>Pros</h3><ul>@for (p of m.pros; track p) { <li>{{ p }}</li> }</ul></div>
    }
    @if (m.cons.length) {
      <div class="row"><h3>Cons</h3><ul>@for (c of m.cons; track c) { <li>{{ c }}</li> }</ul></div>
    }
    @if (m.recommendations.length) {
      <div class="row"><h3>Recommendations</h3><ul>@for (r of m.recommendations; track r) { <li>{{ r }}</li> }</ul></div>
    }
  } @else {
    <p class="muted">No match yet. Run one to see the score breakdown.</p>
  }
</div>
```

`match-tab.component.scss`:

```scss
.controls { display: flex; gap: 8px; align-items: center; margin-bottom: 1rem; }
.score-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 1rem; }
.score-card { padding: 12px; border: 1px solid #e5e7eb; border-radius: 6px; text-align: center; }
.score-card .label { display: block; color: #6b7280; font-size: 0.85em; }
.score-card .value { font-size: 1.5em; font-weight: 600; }
.row { margin-bottom: 1rem; }
.muted { color: #9ca3af; }
```

- [ ] **Step 2: Wire it in**

`application-detail.component.ts`: add `import { MatchTabComponent } from './components/match-tab.component';` and add `MatchTabComponent` to imports.

`application-detail.component.html`: replace the `@case ('match')` block with:

```html
@case ('match') { <app-match-tab [aggregate]="agg" (changed)="reload()" /> }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pages/applications/components/match-tab.component.* \
        frontend/src/app/pages/applications/application-detail.component.*
git commit -m "feat(applications-fe): add Match tab with score breakdown and re-run"
```

---

### Task E5: CV tab

**Files:**
- Create: `frontend/src/app/pages/applications/components/cv-tab.component.ts`
- Create: `frontend/src/app/pages/applications/components/cv-tab.component.html`
- Create: `frontend/src/app/pages/applications/components/cv-tab.component.scss`
- Modify: `application-detail.component.{ts,html}`

- [ ] **Step 1: Implement**

`cv-tab.component.ts`:

```typescript
import { Component, computed, inject, input, output, signal } from '@angular/core';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';

@Component({
  selector: 'app-cv-tab',
  standalone: true,
  templateUrl: './cv-tab.component.html',
  styleUrl: './cv-tab.component.scss',
})
export class CvTabComponent {
  private service = inject(ApplicationsService);

  aggregate = input.required<ApplicationAggregate>();
  changed = output<void>();

  cvLanguage = signal<'en' | 'es'>('en');
  running = signal(false);
  error = signal('');

  optimization = computed(() => this.aggregate().latest_optimization);
  hasMatch = computed(() => this.aggregate().latest_match !== null);

  run(): void {
    this.running.set(true);
    this.error.set('');
    this.service
      .generateOptimization(this.aggregate().id, { cv_language: this.cvLanguage() })
      .subscribe({
        next: () => {
          this.running.set(false);
          this.changed.emit();
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Optimization failed');
          this.running.set(false);
        },
      });
  }

  download(): void {
    const opt = this.optimization();
    if (!opt) return;
    const blob = new Blob([opt.optimized_tex], { type: 'application/x-tex' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cv_${opt.cv_language}.tex`;
    a.click();
    URL.revokeObjectURL(url);
  }
}
```

`cv-tab.component.html`:

```html
<div class="cv-tab">
  <div class="controls">
    <label>CV language:</label>
    <select [value]="cvLanguage()" (change)="cvLanguage.set($any($event.target).value)">
      <option value="en">English</option>
      <option value="es">Spanish</option>
    </select>
    <button class="btn-primary" (click)="run()" [disabled]="running() || !hasMatch()">
      @if (running()) { Optimizing... } @else { @if (optimization()) { Re-run optimization } @else { Generate optimization } }
    </button>
    @if (optimization()) {
      <button class="btn-secondary" (click)="download()">Download .tex</button>
    }
  </div>

  @if (!hasMatch()) {
    <div class="alert">Run a match first — optimization uses the missing-skills list from the latest match.</div>
  }
  @if (error()) {
    <div class="alert alert-error">{{ error() }}</div>
  }

  @if (optimization(); as opt) {
    @if (opt.improvement_summary) {
      <div class="summary-card">
        <h3>Summary</h3>
        <p>{{ opt.improvement_summary }}</p>
      </div>
    }
    @if (opt.changes.length) {
      <h3>Changes</h3>
      @for (c of opt.changes; track $index) {
        <div class="change-card">
          <div class="change-header">{{ c.section_name ?? c.section ?? 'section' }}</div>
          <div class="diff">
            <div class="diff-side">
              <span class="diff-label">Original</span>
              <pre>{{ c.original ?? c.before ?? '' }}</pre>
            </div>
            <div class="diff-side">
              <span class="diff-label">Optimized</span>
              <pre>{{ c.optimized ?? c.after ?? '' }}</pre>
            </div>
          </div>
          @if (c.reason) { <div class="change-reason">{{ c.reason }}</div> }
        </div>
      }
    }
  } @else {
    <p class="muted">No optimization yet.</p>
  }
</div>
```

`cv-tab.component.scss`:

```scss
.controls { display: flex; gap: 8px; align-items: center; margin-bottom: 1rem; }
.summary-card, .change-card { border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px; margin-bottom: 12px; }
.change-header { font-weight: 600; margin-bottom: 8px; }
.diff { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.diff-side pre { background: #f9fafb; padding: 8px; border-radius: 4px; white-space: pre-wrap; }
.diff-label { font-size: 0.85em; color: #6b7280; }
.change-reason { margin-top: 6px; font-size: 0.9em; color: #6b7280; }
.muted { color: #9ca3af; }
.alert { padding: 8px 12px; background: #fef3c7; border-radius: 4px; margin-bottom: 12px; }
```

- [ ] **Step 2: Wire in**

Update `application-detail.component.ts` imports and the `@case ('cv')` block to:

```html
@case ('cv') { <app-cv-tab [aggregate]="agg" (changed)="reload()" /> }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pages/applications/components/cv-tab.component.* \
        frontend/src/app/pages/applications/application-detail.component.*
git commit -m "feat(applications-fe): add CV tab with optimization generation and download"
```

---

### Task E6: Interview tab

**Files:**
- Create: `frontend/src/app/pages/applications/components/interview-tab.component.ts`
- Create: `frontend/src/app/pages/applications/components/interview-tab.component.html`
- Create: `frontend/src/app/pages/applications/components/interview-tab.component.scss`
- Modify: `application-detail.component.{ts,html}`

- [ ] **Step 1: Implement**

`interview-tab.component.ts`:

```typescript
import { Component, computed, inject, input, output, signal } from '@angular/core';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationAggregate } from '../models/application-aggregate.model';

@Component({
  selector: 'app-interview-tab',
  standalone: true,
  templateUrl: './interview-tab.component.html',
  styleUrl: './interview-tab.component.scss',
})
export class InterviewTabComponent {
  private service = inject(ApplicationsService);

  aggregate = input.required<ApplicationAggregate>();
  changed = output<void>();

  running = signal(false);
  error = signal('');

  prep = computed(() => this.aggregate().latest_interview_prep);

  run(): void {
    this.running.set(true);
    this.error.set('');
    this.service.generateInterviewPrep(this.aggregate().id).subscribe({
      next: () => {
        this.running.set(false);
        this.changed.emit();
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Prep generation failed');
        this.running.set(false);
      },
    });
  }
}
```

`interview-tab.component.html`:

```html
<div class="interview-tab">
  <button class="btn-primary" (click)="run()" [disabled]="running()">
    @if (running()) { Generating... } @else { @if (prep()) { Re-run prep } @else { Generate prep } }
  </button>

  @if (error()) {
    <div class="alert alert-error">{{ error() }}</div>
  }

  @if (prep(); as p) {
    <div class="cols">
      <section>
        <h3>Competencies to probe</h3>
        <ul>@for (c of p.competencies_to_probe; track c) { <li>{{ c }}</li> }</ul>
      </section>
      <section>
        <h3>Technical topics</h3>
        <ul>@for (t of p.technical_topics; track t) { <li>{{ t }}</li> }</ul>
      </section>
      <section>
        <h3>Negotiation points</h3>
        <ul>@for (n of p.negotiation_points; track n) { <li>{{ n }}</li> }</ul>
      </section>
    </div>
    @if (p.matched_stories.length) {
      <h3>Matched stories</h3>
      @for (s of p.matched_stories; track s.story_id) {
        <div class="story-card">
          <div class="story-title">{{ s.story_title }}</div>
          <div class="story-relevance">{{ s.relevance }}</div>
        </div>
      }
    }
  } @else {
    <p class="muted">No prep yet.</p>
  }
</div>
```

`interview-tab.component.scss`:

```scss
.cols { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-top: 1rem; }
.story-card { padding: 12px; border: 1px solid #e5e7eb; border-radius: 6px; margin-bottom: 8px; }
.story-title { font-weight: 600; }
.story-relevance { font-size: 0.9em; color: #6b7280; margin-top: 4px; }
.muted { color: #9ca3af; }
```

- [ ] **Step 2: Wire in**

Same pattern as previous tabs — add the import, register in `imports`, replace the `@case ('interview')` block.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pages/applications/components/interview-tab.component.* \
        frontend/src/app/pages/applications/application-detail.component.*
git commit -m "feat(applications-fe): add Interview tab"
```

---

### Task E7: Create-application dialog

**Files:**
- Create: `frontend/src/app/pages/applications/components/application-create-dialog.component.ts`
- Create: `frontend/src/app/pages/applications/components/application-create-dialog.component.html`
- Create: `frontend/src/app/pages/applications/components/application-create-dialog.component.scss`
- Modify: `applications.component.{ts,html}` — open the dialog instead of navigating to `applications/new`.

- [ ] **Step 1: Implement**

`application-create-dialog.component.ts`:

```typescript
import { Component, inject, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApplicationsService } from '../../../core/services/applications.service';

@Component({
  selector: 'app-application-create-dialog',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './application-create-dialog.component.html',
  styleUrl: './application-create-dialog.component.scss',
})
export class ApplicationCreateDialogComponent {
  private service = inject(ApplicationsService);

  closed = output<void>();
  created = output<string>();

  title = signal('');
  company = signal('');
  description = signal('');
  url = signal('');
  saving = signal(false);
  error = signal('');

  submit(): void {
    if (!this.title().trim() || !this.company().trim() || !this.description().trim()) {
      this.error.set('Title, company, and description are required');
      return;
    }
    this.saving.set(true);
    this.error.set('');
    this.service
      .createManual({
        title: this.title().trim(),
        company: this.company().trim(),
        description: this.description().trim(),
        url: this.url().trim() || undefined,
      })
      .subscribe({
        next: (agg) => {
          this.saving.set(false);
          this.created.emit(agg.id);
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Create failed');
          this.saving.set(false);
        },
      });
  }

  onOverlay(ev: MouseEvent): void {
    if ((ev.target as HTMLElement).classList.contains('overlay')) {
      this.closed.emit();
    }
  }
}
```

`application-create-dialog.component.html`:

```html
<div class="overlay" (click)="onOverlay($event)">
  <div class="dialog">
    <h2>New application</h2>
    <p class="hint">Paste a job description below. Skills will be extracted automatically.</p>

    <div class="field">
      <label>Title</label>
      <input [ngModel]="title()" (ngModelChange)="title.set($event)" />
    </div>
    <div class="field">
      <label>Company</label>
      <input [ngModel]="company()" (ngModelChange)="company.set($event)" />
    </div>
    <div class="field">
      <label>URL (optional)</label>
      <input [ngModel]="url()" (ngModelChange)="url.set($event)" />
    </div>
    <div class="field">
      <label>Job description</label>
      <textarea rows="8" [ngModel]="description()" (ngModelChange)="description.set($event)"></textarea>
    </div>

    @if (error()) {
      <div class="alert alert-error">{{ error() }}</div>
    }

    <div class="actions">
      <button class="btn-secondary" (click)="closed.emit()">Cancel</button>
      <button class="btn-primary" (click)="submit()" [disabled]="saving()">
        @if (saving()) { Creating... } @else { Create }
      </button>
    </div>
  </div>
</div>
```

`application-create-dialog.component.scss`:

```scss
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 100; }
.dialog { background: white; border-radius: 8px; padding: 24px; width: min(600px, 90vw); max-height: 90vh; overflow-y: auto; }
.hint { color: #6b7280; font-size: 0.9em; }
.field { margin-bottom: 12px; }
.field label { display: block; font-weight: 600; margin-bottom: 4px; }
.field input, .field textarea { width: 100%; padding: 8px; font-family: inherit; }
.actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 1rem; }
```

- [ ] **Step 2: Wire into the list page**

Modify `applications.component.ts`:

```typescript
import { ApplicationCreateDialogComponent } from './components/application-create-dialog.component';

// ... in the @Component decorator:
imports: [DatePipe, TitleCasePipe, ApplicationCreateDialogComponent],

// Add field:
showCreateDialog = signal(false);

// Replace newApplication():
openCreate(): void {
  this.showCreateDialog.set(true);
}

onCreated(id: string): void {
  this.showCreateDialog.set(false);
  this.router.navigate(['/dashboard/applications', id]);
}
```

In `applications.component.html`:
- Change the button click from `newApplication()` to `openCreate()`.
- Add at the bottom of the page:

```html
@if (showCreateDialog()) {
  <app-application-create-dialog
    (closed)="showCreateDialog.set(false)"
    (created)="onCreated($event)" />
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pages/applications/components/application-create-dialog.component.* \
        frontend/src/app/pages/applications/applications.component.*
git commit -m "feat(applications-fe): add create-application dialog"
```

---

### Task E8: "Track" button on ingestion job-detail panel creates an application

**Files:**
- Modify: `frontend/src/app/pages/ingestion/ingestion.component.ts` — change the track handler to call `ApplicationsService.createFromJob()` instead of `TrackingService.create()`, and on success navigate to `/dashboard/applications/:id`.

- [ ] **Step 1: Read the current track handler**

Run: `cat frontend/src/app/pages/ingestion/ingestion.component.ts` — locate the method bound to `(track)="..."` on `app-job-detail-panel`.

- [ ] **Step 2: Replace the implementation**

Change the imports to add `ApplicationsService` and `Router`, then change the track handler to:

```typescript
onTrack(jobId: string): void {
  this.applicationsService.createFromJob(jobId).subscribe({
    next: (agg) => {
      this.router.navigate(['/dashboard/applications', agg.id]);
    },
    error: (err) => {
      this.error.set(err?.error?.detail ?? 'Failed to create application');
    },
  });
}
```

(Keep the existing TrackingService import for now — Phase F removes it.)

- [ ] **Step 3: Smoke test**

Click Track on an ingestion job — verify it lands on the application detail view with a snapshot pre-populated from the ingested job.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/pages/ingestion/ingestion.component.ts
git commit -m "feat(ingestion-fe): Track button creates an application and routes to detail"
```

---

## Phase F — Frontend restructure

### Task F1: Restructure Interview page (applications list at top + stories below)

**Files:**
- Modify: `frontend/src/app/pages/interview/interview.component.ts`
- Modify: `frontend/src/app/pages/interview/interview.component.html`
- Create: `frontend/src/app/pages/interview/components/applications-prep-list.component.ts`
- Create: `frontend/src/app/pages/interview/components/applications-prep-list.component.html`
- Create: `frontend/src/app/pages/interview/components/applications-prep-list.component.scss`

- [ ] **Step 1: Implement the applications-prep list**

`applications-prep-list.component.ts`:

```typescript
import { Component, OnInit, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { DatePipe, TitleCasePipe } from '@angular/common';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationListItem } from '../../applications/models/application-list-item.model';

@Component({
  selector: 'app-applications-prep-list',
  standalone: true,
  imports: [DatePipe, TitleCasePipe],
  templateUrl: './applications-prep-list.component.html',
  styleUrl: './applications-prep-list.component.scss',
})
export class ApplicationsPrepListComponent implements OnInit {
  private service = inject(ApplicationsService);
  private router = inject(Router);

  applications = signal<ApplicationListItem[]>([]);
  loading = signal(false);

  ngOnInit(): void {
    this.loading.set(true);
    this.service.list().subscribe({
      next: (rows) => {
        this.applications.set(rows);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  openPrep(id: string): void {
    this.router.navigate(['/dashboard/applications', id], { queryParams: { tab: 'interview' } });
  }
}
```

`applications-prep-list.component.html`:

```html
<section class="prep-list">
  <h2>Interview prep — your applications</h2>
  @if (loading()) {
    <p>Loading...</p>
  } @else if (applications().length === 0) {
    <p class="muted">No applications yet. Track a job or create one to start preparing.</p>
  } @else {
    <table>
      <thead>
        <tr><th>Title</th><th>Company</th><th>Status</th><th>Prep</th><th></th></tr>
      </thead>
      <tbody>
        @for (a of applications(); track a.id) {
          <tr>
            <td>{{ a.title }}</td>
            <td>{{ a.company }}</td>
            <td>{{ a.status | titlecase }}</td>
            <td>@if (a.has_prep) { <span class="badge on">ready</span> } @else { <span class="badge">none</span> }</td>
            <td><button class="btn-primary btn-sm" (click)="openPrep(a.id)">Open prep</button></td>
          </tr>
        }
      </tbody>
    </table>
  }
</section>
```

`applications-prep-list.component.scss`:

```scss
.prep-list { margin-bottom: 2rem; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 0.5rem; border-bottom: 1px solid #e5e7eb; }
.badge { padding: 2px 8px; border-radius: 4px; background: #e5e7eb; }
.badge.on { background: #10b981; color: white; }
.muted { color: #9ca3af; }
.btn-sm { font-size: 0.85em; padding: 4px 10px; }
```

- [ ] **Step 2: Update detail component to honour `tab` query param**

Modify `application-detail.component.ts`:

In `ngOnInit`:

```typescript
const tab = this.route.snapshot.queryParamMap.get('tab') as TabKey | null;
if (tab && ['job', 'match', 'cv', 'interview'].includes(tab)) {
  this.activeTab.set(tab);
}
```

- [ ] **Step 3: Restructure the Interview page**

In `interview.component.ts`:
- Remove all `prep*` state and the `generatePrep()` method, plus the related signals (`prepJobTitle`, `prepCompany`, etc.).
- Add `ApplicationsPrepListComponent` to imports.

In `interview.component.html` replace the standalone "Prepare for interview" form section with:

```html
<app-applications-prep-list />
```

Keep the story-bank section (the part that lists stories + the add-story form) — that stays.

- [ ] **Step 4: Smoke test**

Navigate to `/dashboard/interview`. See the applications list at top + story bank below. Click "Open prep" on a row → land on detail view, Interview tab active.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/interview/ \
        frontend/src/app/pages/applications/application-detail.component.ts
git commit -m "feat(interview-fe): show applications list at top, remove free-form prep form"
```

---

### Task F2: Replace Optimization page with a thin redirect form

**Files:**
- Modify: `frontend/src/app/pages/optimization/optimization.component.ts`
- Modify: `frontend/src/app/pages/optimization/optimization.component.html`

- [ ] **Step 1: Replace the component**

`optimization.component.ts`:

```typescript
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApplicationsService } from '../../core/services/applications.service';

@Component({
  selector: 'app-optimization',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './optimization.component.html',
  styleUrl: './optimization.component.scss',
})
export class OptimizationComponent {
  private service = inject(ApplicationsService);
  private router = inject(Router);

  title = signal('');
  company = signal('');
  description = signal('');
  saving = signal(false);
  error = signal('');

  submit(): void {
    if (!this.title().trim() || !this.company().trim() || !this.description().trim()) {
      this.error.set('All fields required');
      return;
    }
    this.saving.set(true);
    this.error.set('');
    this.service
      .createManual({
        title: this.title().trim(),
        company: this.company().trim(),
        description: this.description().trim(),
      })
      .subscribe({
        next: (agg) => {
          this.router.navigate(['/dashboard/applications', agg.id], { queryParams: { tab: 'cv' } });
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Create failed');
          this.saving.set(false);
        },
      });
  }
}
```

`optimization.component.html`:

```html
<div class="page">
  <h1>CV Optimization</h1>
  <p>Paste a job description below. We'll create an application, extract required skills automatically, and take you to the CV tab to run the optimization.</p>

  <div class="form">
    <div class="field">
      <label>Title</label>
      <input [ngModel]="title()" (ngModelChange)="title.set($event)" />
    </div>
    <div class="field">
      <label>Company</label>
      <input [ngModel]="company()" (ngModelChange)="company.set($event)" />
    </div>
    <div class="field">
      <label>Job description</label>
      <textarea rows="10" [ngModel]="description()" (ngModelChange)="description.set($event)"></textarea>
    </div>
    @if (error()) {
      <div class="alert alert-error">{{ error() }}</div>
    }
    <button class="btn-primary" (click)="submit()" [disabled]="saving()">
      @if (saving()) { Creating... } @else { Continue to CV optimization }
    </button>
  </div>
</div>
```

- [ ] **Step 2: Smoke test**

Visit `/dashboard/optimization`, paste a description → lands on detail view CV tab, ready to optimize.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pages/optimization/optimization.component.*
git commit -m "refactor(optimization-fe): replace standalone form with thin redirect into Applications"
```

---

### Task F3: Remove Tracking and Matching from nav; add Applications

**Files:**
- Modify: `frontend/src/app/pages/dashboard/dashboard.component.html` (nav)
- (Optionally remove the `/dashboard/matching` and `/dashboard/tracking` routes from `app.routes.ts` — but leave the component files for one more iteration to avoid breaking deep links during transition.)

- [ ] **Step 1: Update the dashboard nav**

Find and update the nav list to:

- Ingestion
- Profile
- Applications (new)
- Optimization (kept as the quick-paste entry)
- Interview

Remove "Matching" and "Tracking" links. (The routes still exist; only the nav entries are removed.)

- [ ] **Step 2: Smoke test**

Reload the app. Nav reflects the new layout. Direct URLs to `/dashboard/tracking` and `/dashboard/matching` still load (we'll delete those component files in a follow-up cleanup PR).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pages/dashboard/dashboard.component.html
git commit -m "feat(dashboard-fe): replace Tracking/Matching nav entries with Applications"
```

---

## Self-review (run after writing — done during plan authoring)

**Spec coverage:** Every spec section maps to tasks above.

- Spec §"Data model" → Task A1 (ORM) + A2 (migration).
- Spec §"New bounded context" → Tasks A1–C4 (entire backend phase).
- Spec §"API surface" → Task C1 (schemas) + C3 (CRUD routes) + C4 (artifact routes).
- Spec §"Skill auto-extraction" → Task B1 (extractor) + B2 (service uses it on create) + B2 (regenerate).
- Spec §"Frontend architecture" → Tasks D1–D4 (foundation) + E1–E7 (detail view + dialog) + F1–F3 (restructure).
- Spec §"Pipeline flow" → Task E8 (ingestion Track button) + F1 (Interview applications list) + F2 (Optimization redirect).
- Spec §"Migration" → Task A2 (Alembic + backfill).
- Spec §"Error handling and edge cases" — covered piecemeal: no profile (B3 raises, F frontends show alert), no match when optimizing (B3 raises, E5 shows alert), no stories (existing InterviewPrepService handles), LLM failures (B1 returns []).
- Spec §"Testing" — unit tests in A1, A4, B1, B2, B3; integration tests in C3, C4; manual smoke at CHECKPOINT 1 + each frontend task.

**Placeholder scan:** No "TBD", "TODO", "implement later", or "Similar to Task N" — code blocks are concrete. One area where the plan defers concrete code is Task B4 (`ProfileService.get_for_language`) because the implementation depends on the existing `ProfileService` shape which varies in the repo; the task tells the engineer to read the file first and adapt. That deferral is intentional and bounded.

**Type consistency:** `JobSnapshotSource` is used the same way everywhere (enum values `'ingested'`, `'manual'`, `'llm_extracted'`). `ApplicationAggregate` shape is consistent between domain (B2), API (C1 imports from domain), and frontend (D1 mirrors it field-for-field). `cv_language` is `str` (or `'en' | 'es'` on the frontend) everywhere.

**Scope check:** Plan is large (~25 tasks) but single-feature. The CHECKPOINT 1 marker between backend and frontend is the natural gate. If the user wants to split this into two PRs, Phase A–C is one shippable unit (backend API working end-to-end) and Phase D–F is the next.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-24-application-pipeline-redesign.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
