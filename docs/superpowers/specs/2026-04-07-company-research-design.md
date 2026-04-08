# Company Deep Research — Design Spec

**Date:** 2026-04-07
**Status:** Approved
**Phase:** 6 of 6 (career-ops feature adoption roadmap)

## Overview

Add LLM-powered company research that synthesizes funding stage, tech stack, culture signals, growth trajectory, pros/cons, and red flags for any company. Results are persisted to PostgreSQL for caching. Research is triggered inline from the Pipeline page via a "Research" button per tracked application.

## Goals

- LLM-powered company analysis using model knowledge + job description context
- Persist results to DB (one record per company, refreshable)
- Inline "Research" button on Pipeline page with collapsible detail panel
- Graceful degradation when LLM unavailable

## Non-Goals

- Web scraping or external search APIs (future enhancement)
- Glassdoor/LinkedIn API integration
- Automated research on all ingested jobs
- Separate "Company Directory" page

---

## Architecture

New `research` bounded context following the same pattern as tracking and interview modules — ORM model, sync SQLAlchemy repository, service layer, FastAPI routes with auth.

### New Files

| File | Responsibility |
|---|---|
| `backend/src/hiresense/research/__init__.py` | Package marker |
| `backend/src/hiresense/research/domain/__init__.py` | Package marker |
| `backend/src/hiresense/research/domain/models.py` | CompanyResearch ORM model |
| `backend/src/hiresense/research/domain/services.py` | CompanyResearchService |
| `backend/src/hiresense/research/infrastructure/__init__.py` | Package marker |
| `backend/src/hiresense/research/infrastructure/repository.py` | CompanyResearchRepository |
| `backend/src/hiresense/research/api/__init__.py` | Package marker |
| `backend/src/hiresense/research/api/schemas.py` | Request/response models |
| `backend/src/hiresense/research/api/routes.py` | REST endpoints |
| `backend/src/hiresense/research/api/dependencies.py` | DI stubs |
| `backend/alembic/versions/003_create_company_research.py` | Third migration |
| `frontend/src/app/core/models/company-research.model.ts` | CompanyResearch TS interface |

### Modified Files

| File | Change |
|---|---|
| `backend/src/hiresense/infrastructure/registry.py` | Register CompanyResearch model |
| `backend/src/hiresense/main.py` | Wire research module |
| `frontend/src/app/pages/tracking/tracking.component.ts` | Add research button + panel state |
| `frontend/src/app/pages/tracking/tracking.component.html` | Add button + collapsible panel |

---

## Domain Model

### CompanyResearch ORM Model

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary key |
| `company_name` | String(255) | Not null, unique, indexed |
| `funding_stage` | String(100) | Not null |
| `tech_stack` | Text | Not null |
| `culture_summary` | Text | Not null |
| `growth_trajectory` | Text | Not null |
| `red_flags` | Text | Nullable |
| `pros` | Text | Not null |
| `cons` | Text | Not null |
| `raw_llm_response` | Text | Not null (for debugging) |
| `created_at` | DateTime(timezone=True) | Server default now() |
| `updated_at` | DateTime(timezone=True) | Server default now(), onupdate |

Unique index on `company_name` (case-insensitive lookup via `.lower().strip()` in service layer).

---

## Repository

### CompanyResearchRepository

```python
class CompanyResearchRepository:
    def __init__(self, session_factory) -> None
    def get_by_company_name(self, company_name: str) -> CompanyResearch | None
    def create(self, research: CompanyResearch) -> CompanyResearch
    def save(self, research: CompanyResearch) -> CompanyResearch
```

Lookup by `company_name` uses case-insensitive comparison.

---

## Service

### CompanyResearchService

```python
class CompanyResearchService:
    def __init__(self, llm, repository) -> None

    async def research(self, company_name: str, job_description: str = "") -> CompanyResearch:
        # 1. Normalize company_name (lower().strip())
        # 2. Check DB cache
        # 3. If cached, return it
        # 4. If not cached, call LLM with company name + job description
        # 5. Parse structured JSON response
        # 6. Persist to DB
        # 7. Return

    async def refresh(self, company_name: str, job_description: str = "") -> CompanyResearch:
        # Same as research() but skips cache, overwrites existing record

    def get(self, company_name: str) -> CompanyResearch | None:
        # Cache lookup only, no LLM call
```

### LLM Prompt

The prompt includes:
- Company name
- Job description (if provided) for additional context
- Structured output request:

```
Analyze this company for a job seeker. Return JSON with:
- funding_stage: string (e.g. "Series B", "Public", "Bootstrapped", "Unknown")
- tech_stack: string (known technologies, languages, frameworks)
- culture_summary: string (2-3 sentences about work culture)
- growth_trajectory: string (2-3 sentences about company growth)
- red_flags: string or null (any concerns a candidate should know)
- pros: string (positive aspects for a candidate)
- cons: string (negative aspects or challenges)
```

JSON parsing follows the same strategy as BaseLLMScorer: direct parse → markdown block extraction → fallback defaults.

### Graceful Degradation

- No LLM: return a CompanyResearch with all fields set to "LLM not configured"
- LLM failure: return a CompanyResearch with all fields set to "Research unavailable"
- Both cases: do NOT persist the fallback to DB (so next request retries)

---

## API Endpoints

### POST /api/research

Research a company (returns cached if available).

**Request:**
```json
{
  "company_name": "Anthropic",
  "job_description": "Build AI safety systems..."
}
```

**Response:**
```json
{
  "id": "uuid",
  "company_name": "Anthropic",
  "funding_stage": "Series D",
  "tech_stack": "Python, Rust, distributed systems, ML infrastructure",
  "culture_summary": "Research-driven culture focused on AI safety...",
  "growth_trajectory": "Rapid growth, major enterprise partnerships...",
  "red_flags": null,
  "pros": "Cutting-edge AI work, strong mission, competitive compensation",
  "cons": "High intensity, rapidly evolving priorities",
  "created_at": "2026-04-07T12:00:00Z",
  "updated_at": "2026-04-07T12:00:00Z"
}
```

### POST /api/research/refresh

Force re-research (overwrites cached result).

Same request/response as above.

### GET /api/research/{company_name}

Get cached research only (no LLM call).

Returns 200 with research or 404 if not cached.

All endpoints require auth.

---

## Frontend

### Pipeline Page Integration

- **"Research" button** in the Actions column of each tracked application row
- On click: calls `POST /api/research` with `company_name` from the app + `job_description` from `app.notes`
- Loading state: button shows spinner
- Results: collapsible panel below the row showing:
  - Funding Stage badge
  - Tech Stack (comma-separated tags)
  - Culture Summary paragraph
  - Growth Trajectory paragraph
  - Pros / Cons in two columns
  - Red Flags (highlighted if present)
  - "Refresh" button to force re-research
  - "Last updated" timestamp

---

## App Factory Wiring

1. Reuse existing `sync_session_factory`
2. Create `CompanyResearchRepository(session_factory)`
3. Create `CompanyResearchService(llm, repository)`
4. Override DI stubs and include router
5. Auth required on all endpoints

---

## Future Considerations

- Web search integration (Tavily, SerpAPI) for real-time data
- Auto-research when tracking a new job
- Company comparison view (side-by-side)
- Research quality scoring based on LLM confidence
