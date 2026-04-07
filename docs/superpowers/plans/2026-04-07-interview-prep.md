# Interview Prep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a story bank (STAR+Reflection format) with CRUD persistence and LLM-powered interview preparation that matches stories to jobs, suggests competencies, technical topics, and negotiation points.

**Architecture:** New `interview/` bounded context following the tracking module's pattern — ORM model, sync SQLAlchemy repository, service layer, FastAPI routes with auth. The `InterviewPrepService` uses the existing LLM infrastructure. Second Alembic migration creates the `stories` table.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, Angular 21, pytest-asyncio

---

## File Map

### New Files

| File | Responsibility |
|---|---|
| `backend/src/hiresense/interview/__init__.py` | Package marker |
| `backend/src/hiresense/interview/domain/__init__.py` | Package marker |
| `backend/src/hiresense/interview/domain/models.py` | Story ORM + Competency enum |
| `backend/src/hiresense/interview/domain/services.py` | StoryService + InterviewPrepService |
| `backend/src/hiresense/interview/infrastructure/__init__.py` | Package marker |
| `backend/src/hiresense/interview/infrastructure/repository.py` | StoryRepository |
| `backend/src/hiresense/interview/api/__init__.py` | Package marker |
| `backend/src/hiresense/interview/api/schemas.py` | Pydantic schemas |
| `backend/src/hiresense/interview/api/routes.py` | REST endpoints |
| `backend/src/hiresense/interview/api/dependencies.py` | DI stubs |
| `backend/alembic/versions/002_create_stories.py` | Migration |
| `backend/tests/unit/interview/__init__.py` | Package marker |
| `backend/tests/unit/interview/test_models.py` | ORM model tests |
| `backend/tests/unit/interview/test_repository.py` | Repository tests |
| `backend/tests/unit/interview/test_services.py` | Service tests |
| `backend/tests/unit/interview/test_prep_service.py` | Prep service tests |
| `backend/tests/unit/interview/test_routes.py` | Route tests |
| `frontend/src/app/core/models/story.model.ts` | Story TS model |
| `frontend/src/app/core/models/competency.model.ts` | Competency type |
| `frontend/src/app/core/models/interview-prep.model.ts` | Prep result model |
| `frontend/src/app/pages/interview/interview.component.ts` | Page component |
| `frontend/src/app/pages/interview/interview.component.html` | Template |
| `frontend/src/app/pages/interview/interview.component.scss` | Styles |

### Modified Files

| File | Change |
|---|---|
| `backend/src/hiresense/infrastructure/registry.py` | Register Story model |
| `backend/src/hiresense/main.py` | Wire interview module |
| `frontend/src/app/app.routes.ts` | Add interview route |
| `frontend/src/app/pages/dashboard/dashboard.component.html` | Add sidebar link |

---

## Task 1: Story ORM model, Competency enum, and migration

**Files:**
- Create: `backend/src/hiresense/interview/__init__.py`, `domain/__init__.py`
- Create: `backend/src/hiresense/interview/domain/models.py`
- Create: `backend/alembic/versions/002_create_stories.py`
- Modify: `backend/src/hiresense/infrastructure/registry.py`
- Create: `backend/tests/unit/interview/__init__.py`
- Create: `backend/tests/unit/interview/test_models.py`

### Tests:

```python
from hiresense.interview.domain.models import Competency, Story


def test_competency_values() -> None:
    assert Competency.LEADERSHIP == "leadership"
    assert Competency.PROBLEM_SOLVING == "problem_solving"
    assert Competency.COLLABORATION == "collaboration"
    assert Competency.COMMUNICATION == "communication"
    assert Competency.ADAPTABILITY == "adaptability"
    assert Competency.TECHNICAL == "technical"
    assert Competency.INITIATIVE == "initiative"
    assert Competency.CONFLICT_RESOLUTION == "conflict_resolution"


def test_story_creation() -> None:
    story = Story(
        title="Led API migration",
        competency=Competency.TECHNICAL.value,
        situation="Legacy monolith needed modernization",
        task="Design and execute migration to microservices",
        action="Broke into 12 bounded contexts, migrated incrementally",
        result="95% reduction in deployment time",
    )
    assert story.title == "Led API migration"
    assert story.competency == Competency.TECHNICAL.value
    assert story.reflection is None
    assert story.tags is None
```

### Implementation:

```python
# models.py
from __future__ import annotations
import enum
import uuid as uuid_mod
from datetime import datetime
from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from hiresense.infrastructure.database import Base


class Competency(str, enum.Enum):
    LEADERSHIP = "leadership"
    PROBLEM_SOLVING = "problem_solving"
    COLLABORATION = "collaboration"
    COMMUNICATION = "communication"
    ADAPTABILITY = "adaptability"
    TECHNICAL = "technical"
    INITIATIVE = "initiative"
    CONFLICT_RESOLUTION = "conflict_resolution"


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    title: Mapped[str] = mapped_column(String(255))
    competency: Mapped[str] = mapped_column(String(30))
    situation: Mapped[str] = mapped_column(Text)
    task: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(Text)
    reflection: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

### Migration (002_create_stories.py):

```python
"""create stories table
Revision ID: 002
Revises: 001
"""
revision = "002"
down_revision = "001"

def upgrade():
    op.create_table("stories",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("competency", sa.String(30), nullable=False),
        sa.Column("situation", sa.Text(), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("reflection", sa.Text(), nullable=True),
        sa.Column("tags", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table("stories")
```

Register in `infrastructure/registry.py`:
```python
from hiresense.interview.domain.models import Story  # noqa: F401
```

Commits:
1. `feat(interview): add Story ORM model and Competency enum`
2. `feat(interview): add Alembic migration for stories table`

---

## Task 2: StoryRepository

**Files:**
- Create: `backend/src/hiresense/interview/infrastructure/__init__.py`
- Create: `backend/src/hiresense/interview/infrastructure/repository.py`
- Create: `backend/tests/unit/interview/test_repository.py`

Follow exact pattern from `tracking/infrastructure/repository.py`. Tests use in-memory SQLite.

### Tests (7 tests):
1. `test_create_and_get_by_id`
2. `test_get_by_id_not_found`
3. `test_list_all`
4. `test_list_filter_by_competency`
5. `test_save_update`
6. `test_delete`
7. `test_delete_not_found`

### Implementation:

```python
class StoryRepository:
    def __init__(self, session_factory) -> None
    def get_by_id(self, id: UUID) -> Story | None
    def list_all(self, competency: Competency | None = None) -> list[Story]
    def create(self, story: Story) -> Story
    def save(self, story: Story) -> Story
    def delete(self, id: UUID) -> bool
```

Commit: `feat(interview): add StoryRepository`

---

## Task 3: StoryService

**Files:**
- Create: `backend/src/hiresense/interview/domain/services.py`
- Create: `backend/tests/unit/interview/test_services.py`

### Tests (8 tests):
1. `test_add_story`
2. `test_get_story`
3. `test_get_story_not_found`
4. `test_list_stories`
5. `test_list_by_competency`
6. `test_update_story`
7. `test_remove_story`
8. `test_remove_not_found`

### Implementation:

```python
class StoryService:
    def __init__(self, repository) -> None

    def add_story(self, title, competency, situation, task, action, result, reflection=None, tags=None) -> Story
    def get(self, id: UUID) -> Story
    def list(self, competency=None) -> list[Story]
    def update(self, id, **fields) -> Story
    def remove(self, id) -> None
```

Commit: `feat(interview): add StoryService with CRUD`

---

## Task 4: InterviewPrepService

**Files:**
- Add to: `backend/src/hiresense/interview/domain/services.py`
- Create: `backend/tests/unit/interview/test_prep_service.py`

### Tests (4 tests):
1. `test_prepare_returns_matched_stories` — with stories, LLM returns structured prep
2. `test_prepare_no_stories` — empty story bank, LLM still returns topics/negotiation
3. `test_prepare_no_llm` — returns default prep with "LLM not configured"
4. `test_prepare_llm_failure` — graceful degradation

### Implementation:

```python
class InterviewPrep(BaseModel):
    job_title: str
    company: str
    matched_stories: list[StoryMatch]
    competencies_to_probe: list[str]
    technical_topics: list[str]
    negotiation_points: list[str]

class StoryMatch(BaseModel):
    story_id: UUID
    story_title: str
    relevance: str

class InterviewPrepService:
    def __init__(self, llm, story_repo) -> None

    async def prepare(self, job: dict) -> InterviewPrep
        # 1. Load all stories from repo
        # 2. Build prompt with job + story summaries
        # 3. LLM returns JSON with matches, competencies, topics, negotiation
        # 4. Parse and return InterviewPrep
```

LLM prompt includes job description + numbered list of stories (title + competency + situation summary). Asks LLM to return structured JSON.

Commit: `feat(interview): add InterviewPrepService with LLM-powered preparation`

---

## Task 5: API schemas and routes

**Files:**
- Create: `backend/src/hiresense/interview/api/__init__.py`
- Create: `backend/src/hiresense/interview/api/schemas.py`
- Create: `backend/src/hiresense/interview/api/dependencies.py`
- Create: `backend/src/hiresense/interview/api/routes.py`
- Create: `backend/tests/unit/interview/test_routes.py`

### Endpoints:
- `POST /interview/stories` (201)
- `GET /interview/stories` (200, optional ?competency= filter)
- `GET /interview/stories/{id}` (200/404)
- `PATCH /interview/stories/{id}` (200/404)
- `DELETE /interview/stories/{id}` (204/404)
- `POST /interview/prepare` (200)

All routes require auth via `dependencies=[Depends(require_auth)]` on router.

### Tests (8 tests):
1. `test_create_story`
2. `test_list_stories`
3. `test_get_story`
4. `test_get_story_not_found`
5. `test_update_story`
6. `test_delete_story`
7. `test_delete_story_not_found`
8. `test_prepare_interview`

Commit: `feat(interview): add REST API routes for stories and interview prep`

---

## Task 6: Wire into app factory

**Files:**
- Modify: `backend/src/hiresense/main.py`

Reuse existing `sync_session_factory` from tracking. Create StoryRepository, StoryService, InterviewPrepService. Override DI stubs, include router.

Commit: `feat(app): wire interview module`

---

## Task 7: Frontend — models, page, sidebar

**Files:**
- Create: TS models (story, competency, interview-prep)
- Create: interview component (ts, html, scss)
- Modify: app.routes.ts, dashboard.component.html

### Interview Page Layout:
- **Story Bank tab**: table of stories (title, competency badge, actions), "Add Story" form with STAR+R fields
- **Prepare tab**: job input (title, company, description), "Generate Prep" button, results showing matched stories, competencies, topics, negotiation points

Commits:
1. `feat(frontend): add interview TypeScript models`
2. `feat(frontend): add Interview page with story bank and prep UI`

---

## Task 8: Full verification

Run all backend tests, frontend build, lint.
