# Interview Prep — Design Spec

**Date:** 2026-04-07
**Status:** Approved
**Phase:** 4 of 6 (career-ops feature adoption roadmap)

## Overview

Add a new `interview` module with two features: a persistent story bank for behavioral interview stories (STAR+Reflection format), and LLM-powered interview preparation that matches stories to jobs, suggests topics, and generates negotiation talking points.

## Goals

- CRUD story bank with STAR+Reflection format, tagged by competency
- Persist stories to PostgreSQL (second ORM model after TrackedApplication)
- LLM-powered interview prep: match stories to job, suggest competencies to probe, technical topics, negotiation points
- Dedicated "Interview" frontend page with story management and prep generation

## Non-Goals

- Audio/video mock interview practice
- Calendar integration for scheduling interviews
- Automated story extraction from CV (future enhancement)

---

## Architecture

### File Structure

```
backend/src/hiresense/interview/
├── __init__.py
├── domain/
│   ├── __init__.py
│   ├── models.py              — Story ORM model + Competency enum
│   └── services.py            — StoryService (CRUD) + InterviewPrepService (LLM)
├── infrastructure/
│   ├── __init__.py
│   └── repository.py          — StoryRepository (sync SQLAlchemy)
├── api/
│   ├── __init__.py
│   ├── routes.py              — REST endpoints
│   └── schemas.py             — Pydantic request/response models

backend/alembic/versions/
└── 002_create_stories.py      — Second migration

frontend/src/app/pages/interview/
├── interview.component.ts
├── interview.component.html
└── interview.component.scss
```

---

## Domain Model

### Competency Enum

```python
class Competency(str, Enum):
    LEADERSHIP = "leadership"
    PROBLEM_SOLVING = "problem_solving"
    COLLABORATION = "collaboration"
    COMMUNICATION = "communication"
    ADAPTABILITY = "adaptability"
    TECHNICAL = "technical"
    INITIATIVE = "initiative"
    CONFLICT_RESOLUTION = "conflict_resolution"
```

### Story ORM Model

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | Primary key |
| `title` | `String(255)` | Not null — short label (e.g., "Led API migration") |
| `competency` | `String(30)` | Not null — one of Competency enum values |
| `situation` | `Text` | Not null — STAR: context |
| `task` | `Text` | Not null — STAR: what was needed |
| `action` | `Text` | Not null — STAR: what you did |
| `result` | `Text` | Not null — STAR: outcome |
| `reflection` | `Text` | Nullable — what you learned |
| `tags` | `String(500)` | Nullable — comma-separated additional tags |
| `created_at` | `DateTime(timezone=True)` | Server default now() |
| `updated_at` | `DateTime(timezone=True)` | Server default now(), onupdate |

---

## Repository

### StoryRepository

```python
class StoryRepository:
    def create(self, story: Story) -> Story
    def get_by_id(self, id: UUID) -> Story | None
    def list_all(self, competency: Competency | None = None) -> list[Story]
    def save(self, story: Story) -> Story
    def delete(self, id: UUID) -> bool
```

---

## Services

### StoryService

Simple CRUD over the repository:
- `add_story(title, competency, situation, task, action, result, reflection?, tags?) -> Story`
- `get(id) -> Story`
- `list(competency?) -> list[Story]`
- `update(id, fields...) -> Story`
- `remove(id) -> None`

### InterviewPrepService

LLM-powered preparation for a specific job:

```python
class InterviewPrepService:
    def __init__(self, llm, story_repo) -> None

    async def prepare(self, job: dict, stories: list[Story]) -> InterviewPrep
```

**InterviewPrep** (Pydantic model):
```python
class StoryMatch(BaseModel):
    story_id: UUID
    story_title: str
    relevance: str          # why this story fits

class InterviewPrep(BaseModel):
    job_title: str
    company: str
    matched_stories: list[StoryMatch]
    competencies_to_probe: list[str]
    technical_topics: list[str]
    negotiation_points: list[str]
```

The LLM receives the job description + all stories, and returns structured JSON with:
- Which stories are most relevant and why
- Which competencies the interviewer will likely test
- Technical topics to review
- Negotiation talking points (salary, remote work, equity, growth)

---

## API Endpoints

### Stories CRUD

| Method | Path | Description |
|---|---|---|
| `POST /api/interview/stories` | Create story | 201 |
| `GET /api/interview/stories` | List (optional ?competency= filter) | 200 |
| `GET /api/interview/stories/{id}` | Get one | 200/404 |
| `PATCH /api/interview/stories/{id}` | Update fields | 200/404 |
| `DELETE /api/interview/stories/{id}` | Remove | 204/404 |

### Interview Prep

| Method | Path | Description |
|---|---|---|
| `POST /api/interview/prepare` | Generate prep for a job | 200 |

**Prepare request:**
```json
{
  "job_title": "Backend Engineer",
  "company": "Anthropic",
  "description": "Build APIs...",
  "location": "Remote"
}
```

**Prepare response:**
```json
{
  "job_title": "Backend Engineer",
  "company": "Anthropic",
  "matched_stories": [
    { "story_id": "uuid", "story_title": "Led API migration", "relevance": "Direct experience with API design" }
  ],
  "competencies_to_probe": ["technical", "problem_solving", "collaboration"],
  "technical_topics": ["System design", "API versioning", "Database optimization"],
  "negotiation_points": ["Remote work flexibility", "Equity package common at this stage"]
}
```

---

## Frontend

### New Page: Interview (`/interview`)

**Two tabs/sections:**

1. **Story Bank** — Table of stories with competency badge, title, actions (edit/delete). "Add Story" button opens a form with STAR+R fields.

2. **Prepare** — Form to enter/select a job, "Generate Prep" button, results display showing matched stories, competencies, topics, and negotiation points.

### Sidebar Navigation

Add "Interview" link after "Pipeline" in the dashboard sidebar.

---

## App Factory Wiring

1. Reuse existing `sync_session_factory` from tracking module
2. Create `StoryRepository(session_factory)`
3. Create `StoryService(repository)`
4. Create `InterviewPrepService(llm, story_repo)`
5. Override DI stubs and include router
6. Auth required on all endpoints (same as tracking)

---

## Future Considerations

- Auto-extract stories from CV sections
- Story versioning (improve stories over time)
- Mock interview mode (LLM asks questions, you answer)
- Link prep results to tracked applications
