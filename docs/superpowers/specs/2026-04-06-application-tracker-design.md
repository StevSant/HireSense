# Application Pipeline Tracker — Design Spec

**Date:** 2026-04-06
**Status:** Approved
**Phase:** 2 of 6 (career-ops feature adoption roadmap)

## Overview

Add a new `tracking` module that lets users track job applications through a pipeline: saved, applied, interviewing, offered, accepted, or rejected. This is the first module to use database persistence via SQLAlchemy ORM and Alembic migrations. Applications can be linked to ingested jobs or entered manually.

## Goals

- Track job applications with status, notes, and timestamps
- Persist to PostgreSQL via async SQLAlchemy (first ORM model in the project)
- Link to ingested jobs when available, support manual entries otherwise
- Dedicated "Pipeline" frontend page with filtering and inline status changes
- "Track" button on the ingestion page for quick tracking of scanned jobs

## Non-Goals

- Enforced status state machine (any status can move to any other)
- Automated status updates (e.g., from email parsing)
- Persisting NormalizedJob to the database (future phase)
- Foreign key constraint on job_id (NormalizedJob isn't persisted yet)

---

## Architecture

### File Structure

```
backend/src/hiresense/tracking/
├── __init__.py
├── domain/
│   ├── __init__.py
│   ├── models.py              — TrackedApplication ORM model + ApplicationStatus enum
│   └── services.py            — TrackingService (CRUD + status transitions)
├── infrastructure/
│   ├── __init__.py
│   └── repository.py          — SQLAlchemy async repository
├── api/
│   ├── __init__.py
│   ├── routes.py              — REST endpoints
│   ├── dependencies.py        — DI stubs
│   └── schemas.py             — Pydantic request/response models

backend/alembic/versions/
└── 001_create_tracked_applications.py  — First migration

frontend/src/app/pages/tracking/
├── tracking.component.ts
├── tracking.component.html
└── tracking.component.scss

frontend/src/app/core/models/
├── tracked-application.model.ts
├── create-application-request.model.ts
└── update-application-request.model.ts
```

### Dependency Flow

```
routes.py (REST endpoints)
  → TrackingService (business logic)
    → TrackingRepository (database access via SQLAlchemy async session)
      → PostgreSQL (tracked_applications table)
```

---

## Domain Model

### ApplicationStatus Enum

```python
class ApplicationStatus(str, Enum):
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
```

### TrackedApplication ORM Model

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | Primary key, server default `gen_random_uuid()` |
| `job_id` | `UUID` | Nullable, indexed — reference to ingested job (no FK constraint) |
| `title` | `String(255)` | Not null |
| `company` | `String(255)` | Not null |
| `url` | `String(2048)` | Nullable |
| `status` | `String(20)` | Not null, default `"saved"` |
| `notes` | `Text` | Nullable |
| `applied_at` | `DateTime(timezone=True)` | Nullable — auto-set when status moves to `applied` |
| `created_at` | `DateTime(timezone=True)` | Not null, server default `now()` |
| `updated_at` | `DateTime(timezone=True)` | Not null, server default `now()`, onupdate `now()` |

### Table: `tracked_applications`

Indexes:
- Primary key on `id`
- Index on `status` (for filtering)
- Index on `job_id` (for dedup lookups)

---

## Database Setup

### ORM Base

Create a shared SQLAlchemy `DeclarativeBase` in `backend/src/hiresense/infrastructure/database.py` (or extend the existing engine setup). All future ORM models will inherit from this base.

### Alembic Migration

First migration `001_create_tracked_applications.py`:
- Creates `tracked_applications` table with all columns and indexes
- Uses `op.create_table()` with proper column types for PostgreSQL
- Alembic `env.py` must be configured to use the async engine and import the ORM base metadata

### Async Session Factory

A session factory function that creates `AsyncSession` instances from the existing async engine in `infrastructure/`. The repository receives a session factory, not a raw engine.

---

## Repository

### TrackingRepository

```python
class TrackingRepository:
    def __init__(self, session_factory: Callable[..., AsyncSession]) -> None
    async def create(self, application: TrackedApplication) -> TrackedApplication
    async def get_by_id(self, id: UUID) -> TrackedApplication | None
    async def get_by_job_id(self, job_id: UUID) -> TrackedApplication | None
    async def list_all(self, status: ApplicationStatus | None = None) -> list[TrackedApplication]
    async def update(self, application: TrackedApplication) -> TrackedApplication
    async def delete(self, id: UUID) -> bool
```

Each method opens its own session via the factory, commits, and returns. No long-lived sessions.

---

## Service

### TrackingService

```python
class TrackingService:
    def __init__(self, repository: TrackingRepository, ingestion_orchestrator: Any) -> None
    async def track_job(self, request: CreateApplicationRequest) -> TrackedApplication
    async def track_from_ingestion(self, job_id: UUID) -> TrackedApplication
    async def get(self, id: UUID) -> TrackedApplication
    async def list(self, status: ApplicationStatus | None = None) -> list[TrackedApplication]
    async def update_status(self, id: UUID, status: ApplicationStatus, notes: str | None = None) -> TrackedApplication
    async def update_notes(self, id: UUID, notes: str) -> TrackedApplication
    async def remove(self, id: UUID) -> None
```

**Key behaviors:**
- `track_job()`: Creates from manual input (title, company, url, optional notes)
- `track_from_ingestion()`: Looks up NormalizedJob by job_id from the ingestion orchestrator's in-memory store, copies title/company/url. Returns 404 if job not found. Returns 409 if already tracked (checks `get_by_job_id`).
- `update_status()`: When transitioning to `applied`, auto-sets `applied_at` if null.
- No enforced state machine — any status transition is allowed.

---

## API Endpoints

### `POST /api/tracking`

**Request body (two modes):**

From ingestion:
```json
{ "job_id": "uuid-here" }
```

Manual entry:
```json
{
  "title": "Backend Engineer",
  "company": "Anthropic",
  "url": "https://example.com/job",
  "notes": "Found on LinkedIn"
}
```

**Response:** `201 Created` with `TrackedApplicationResponse`

**Errors:**
- `404` — job_id not found in ingestion store
- `409` — job_id already tracked

### `GET /api/tracking`

**Query params:** `?status=applied` (optional filter)

**Response:** `200` with `list[TrackedApplicationResponse]`

### `GET /api/tracking/{id}`

**Response:** `200` with `TrackedApplicationResponse` or `404`

### `PATCH /api/tracking/{id}`

**Request body (all optional):**
```json
{
  "status": "interviewing",
  "notes": "Phone screen scheduled for Monday"
}
```

**Response:** `200` with updated `TrackedApplicationResponse` or `404`

### `DELETE /api/tracking/{id}`

**Response:** `204 No Content` or `404`

### Pydantic Schemas

```python
class CreateApplicationRequest(BaseModel):
    job_id: UUID | None = None
    title: str | None = None
    company: str | None = None
    url: str | None = None
    notes: str | None = None

class UpdateApplicationRequest(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = None

class TrackedApplicationResponse(BaseModel):
    id: UUID
    job_id: UUID | None
    title: str
    company: str
    url: str | None
    status: ApplicationStatus
    notes: str | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

---

## Frontend

### New Page: Pipeline (`/tracking`)

Add to sidebar navigation alongside existing pages (Ingestion, Profile, Matching, Optimization).

**Layout:**
- Status filter dropdown at top (All, Saved, Applied, Interviewing, Offered, Accepted, Rejected)
- "Add Application" button opens a form dialog for manual entries (title, company, url, notes)
- Table with columns: Company, Title, Status (dropdown), Applied Date, Notes (truncated), Actions (delete)
- Status column is an inline `<select>` — changing it immediately PATCHes the backend
- Notes are editable inline (click to expand/edit)

### Ingestion Page Addition

Add a "Track" button to each job row in the ingestion table. Clicking it calls `POST /api/tracking` with `{ job_id }`. Button changes to "Tracked" (disabled) on success. Show toast on 409 (already tracked).

### TypeScript Models

```typescript
interface TrackedApplication {
  id: string;
  job_id: string | null;
  title: string;
  company: string;
  url: string | null;
  status: 'saved' | 'applied' | 'interviewing' | 'offered' | 'accepted' | 'rejected';
  notes: string | null;
  applied_at: string | null;
  created_at: string;
  updated_at: string;
}

interface CreateApplicationRequest {
  job_id?: string;
  title?: string;
  company?: string;
  url?: string;
  notes?: string;
}

interface UpdateApplicationRequest {
  status?: string;
  notes?: string;
}
```

---

## App Factory Wiring

In `main.py`:
1. Create `async_session_factory` from the existing async engine
2. Instantiate `TrackingRepository(session_factory)`
3. Instantiate `TrackingService(repository, ingestion_orchestrator)`
4. Override DI stubs and include router

---

## Future Considerations

- **Foreign key to jobs table** — when NormalizedJob is persisted, add a real FK constraint
- **Activity timeline** — track status change history with timestamps
- **Reminders** — notify when an application has been in a status too long
- **Bulk operations** — mark multiple applications as rejected at once
- **Export** — CSV/JSON export of pipeline data
