# HireSense - AI-Powered Job Matching & CV Optimization System

## Context

Job searching as a developer is noisy. You scroll through hundreds of irrelevant listings, manually compare requirements against your skills, and rewrite your CV for each application. HireSense flips this: it aggregates jobs from multiple sources, uses AI to analyze how well each job fits your profile, and helps you tailor your CV — all while keeping you in control of every change.

This is an open-source, self-hostable tool. Anyone can clone it, configure their LLM provider and job sources, and run their own instance.

## System Architecture

**Client-Server** with a **Modular Monolith Backend** (extractable boundaries) and an **Angular SPA Frontend**.

- **Server:** Single FastAPI process with strict internal module boundaries. Modules communicate via an in-memory event bus and typed contracts (DTOs). Any module can be extracted into a standalone service by swapping the bus implementation (in-memory to Redis Streams).
- **Client:** Angular standalone SPA communicating with the backend over REST API.
- **Database:** PostgreSQL + pgvector (single instance, per-module table prefixes).
- **Principles:** Clean Architecture, DDD bounded contexts, Hexagonal Architecture (ports/adapters), provider-agnostic design.

## Bounded Contexts (Modules)

### 1. Ingestion

Fetches, normalizes, and stores job listings from heterogeneous sources.

**Domain models:**
- `RawJobListing` — raw data as received from a source
- `NormalizedJob` — standardized representation (title, company, description, skills, location, salary range, source, language, URL, posted date)
- `SourceType` — enum: API, RSS, SCRAPER, MANUAL

**Port:** `JobSourcePort`
- `fetch_jobs(filters) -> list[RawJobListing]`
- `source_name() -> str`
- `source_type() -> SourceType`

**Adapters (MVP):**
- Remotive (API, no auth)
- RemoteOK (API, no auth)
- Jobicy (API, no auth)
- Himalayas (API, no auth)
- HN Who's Hiring (HN Firebase API)
- We Work Remotely (RSS)
- GetOnBoard (scraper)
- CSV import (manual)
- JSON import (manual)

**Scheduling:**
- Configurable cron via APScheduler (default: every 6 hours)
- On-demand fetch via API endpoint
- Schedule configurable in `.env`

**Events published:** `JobsIngestedEvent` (list of job IDs, source, timestamp)

### 2. Profile

Manages candidate CVs, extracts skills, generates embeddings.

**Domain models:**
- `CandidateProfile` — user's profile with skills and preferences
- `CVDocument` — a LaTeX source file with metadata (language, version, path)
- `ExtractedSkill` — skill with confidence score and category

**CV input:**
- **Primary:** LaTeX `.tex` file upload. The system parses sections (HEADER, SUMMARY, SKILLS, PROJECTS, EDUCATION) and extracts structured data.
- **Fallback:** PDF upload. System uses LLM to extract content, then generates a LaTeX template from it.

**Embedding generation:** Uses `LLMPort.embed()` to generate vector embeddings of the CV content. Stored via `VectorStorePort`.

### 3. Matching & Analysis

Semantic comparison and AI-powered analysis of job-CV fit.

**Domain models:**
- `MatchResult` — full analysis output for a job-CV pair
- `MatchScore` — composite score (0-100%) with breakdown
- `AnalysisBreakdown` — pros, cons, missing skills, recommendations

**LangGraph Agent (multi-step):**

```
Entry -> extract_job_skills -> extract_cv_skills -> semantic_compare -> score -> generate_analysis -> End
```

- **Node 1: `extract_job_skills`** — LLM extracts required/preferred skills, experience level, and key requirements from job description
- **Node 2: `extract_cv_skills`** — LLM extracts skills, experience, and strengths from CV (cached per CV version)
- **Node 3: `semantic_compare`** — Vector similarity between job and CV embeddings + structured skill overlap comparison
- **Node 4: `score`** — Weighted composite: semantic similarity + skill match + experience alignment + language match. Weights configurable via `.env` (defaults: 30/40/20/10)
- **Node 5: `generate_analysis`** — LLM generates human-readable pros, cons, missing skills, and actionable recommendations

**Events consumed:** `JobsIngestedEvent` (triggers batch analysis of new jobs)
**Events published:** `MatchCompletedEvent` (job ID, match ID, score)

### 4. CV Optimization

AI-driven LaTeX editing with user approval.

**Domain models:**
- `OptimizationJob` — tracks an optimization request lifecycle
- `TexDiff` — unified diff of original vs modified `.tex` content
- `ApprovalStatus` — enum: PENDING, APPROVED, REJECTED

**LangGraph Agent (multi-step):**

```
Entry -> analyze_gaps -> propose_edits -> validate_tex -> generate_diff -> End
```

- **Node 1: `analyze_gaps`** — Uses MatchResult recommendations to identify what to emphasize/reword
- **Node 2: `propose_edits`** — LLM modifies the `.tex` source. Strict prompt: "adjust wording to highlight relevant experience; do not fabricate skills or experience"
- **Node 3: `validate_tex`** — Attempts compilation via `LaTeXCompilerPort.validate()` to ensure valid LaTeX
- **Node 4: `generate_diff`** — Produces unified diff between original and modified `.tex`

**User flow:**
1. User clicks "Optimize CV" for a specific job match
2. System returns a side-by-side diff
3. User approves or rejects
4. On approval: system writes the modified `.tex`, compiles to PDF via `xelatex`, returns the PDF

**Honesty constraint:** The optimization agent's system prompt explicitly forbids fabricating experience, inflating titles, or adding skills the user doesn't have. It can only reword, reorder, and emphasize existing content.

### 5. Identity

Basic authentication for the self-hosted instance.

- Username and password configured via `.env`
- Basic HTTP auth or simple JWT session
- Single user (no registration flow needed for MVP)
- Auth middleware applied to all API routes

## Shared Kernel

Lives in `src/hiresense/kernel/`. Contains ONLY:

- **Value objects:** `JobId`, `SkillTag`, `Score`, `Language`, `MatchScore`
- **Ports (protocols):**
  - `LLMPort` — `complete()`, `embed()`, `stream()`
  - `VectorStorePort` — `upsert()`, `search()`, `delete()`
  - `LaTeXCompilerPort` — `compile()`, `validate()`
  - `EventBus` — `publish()`, `subscribe()`
- **Contracts (inter-module DTOs):** `NormalizedJobDTO`, `CandidateSkillsDTO`, `MatchResultDTO`, `OptimizationRequestDTO`, etc.
- **Module protocol:** `register_module(app, bus, ports, config)` — each module implements this

## Adapter Implementations

### LLM Adapters
| Adapter | Provider | Notes |
|---------|----------|-------|
| `anthropic_adapter` | Claude (Anthropic) | Tool use support, strong reasoning |
| `openai_adapter` | GPT-4o (OpenAI) | Function calling, widely used |
| `groq_adapter` | Groq | Fast inference, cost-effective |
| `ollama_adapter` | Ollama (local) | Free, privacy-first, no API key needed |

Configured via `LLM_PROVIDER` in `.env`. Factory pattern instantiates the correct adapter.

### Vector Store Adapters
| Adapter | Default | Notes |
|---------|---------|-------|
| `pgvector_adapter` | Yes | Same PostgreSQL instance, simplest for self-host |
| `chroma_adapter` | No | Lightweight standalone option |

Configured via `VECTOR_STORE_PROVIDER` in `.env`.

### LaTeX Compiler Adapters
| Adapter | Notes |
|---------|-------|
| `xelatex_adapter` | Calls `xelatex` directly (requires TeX Live installed) |
| `docker_xelatex_adapter` | Runs compilation inside a TeX Live Docker container (no host install needed) |

## Event Bus

The event bus enables loose coupling between modules.

- **Default:** `InMemoryBus` — asyncio queues, zero infrastructure. Sufficient for single-process deployment.
- **Extractable:** `RedisStreamsBus` — drop-in replacement for when/if a module is extracted to a separate service.

Events are Pydantic models serialized to JSON. This ensures the same event schema works regardless of transport.

## Configuration

All configuration via `.env` file (Pydantic Settings). No hardcoded values.

```env
# Core
APP_NAME=HireSense
APP_PORT=8000
DEBUG=false

# Auth
AUTH_USERNAME=admin
AUTH_PASSWORD=changeme

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/hiresense

# LLM
LLM_PROVIDER=anthropic  # anthropic | openai | groq | ollama
LLM_API_KEY=sk-...
LLM_MODEL=claude-sonnet-4-6
EMBEDDING_MODEL=text-embedding-3-small

# Vector Store
VECTOR_STORE_PROVIDER=pgvector  # pgvector | chroma

# Job Ingestion
INGESTION_SCHEDULE=0 */6 * * *  # Every 6 hours
ENABLED_JOB_SOURCES=remotive,remoteok,jobicy,himalayas,hn_hiring,weworkremotely,getonboard

# LaTeX
LATEX_COMPILER=xelatex  # xelatex | docker_xelatex
CV_DIRECTORY=./cvs

# Language
SUPPORTED_LANGUAGES=en,es
DEFAULT_LANGUAGE=en
```

A `.env.example` is provided with placeholders and comments.

## Frontend (Angular SPA)

### Pages
1. **Dashboard** — Overview: recent jobs, top matches, quick stats
2. **Jobs** — Filterable list of all ingested jobs (source, date, location, skills)
3. **Match Detail** — For a selected job: score breakdown, pros/cons, missing skills, recommendations
4. **CV Optimization** — Side-by-side diff viewer (original vs optimized `.tex`), approve/reject buttons, PDF download
5. **Settings** — Configure job sources, schedule, LLM provider, upload CV
6. **Login** — Simple username/password form

### Key Components
- **Score badge** — Color-coded match percentage (green >75%, yellow 50-75%, red <50%)
- **Skill tags** — Visual chips showing matched/missing/extra skills
- **Diff viewer** — Side-by-side LaTeX diff with syntax highlighting
- **i18n** — English and Spanish via JSON translation files

### Tech
- Angular (standalone components, signals for reactivity)
- Angular Material or Tailwind CSS for styling
- Lazy-loaded feature routes

## File Structure

```
hiresense/
├── pyproject.toml
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── alembic/
│   ├── alembic.ini
│   └── versions/
├── cvs/
│   ├── originals/
│   ├── optimized/
│   └── compiled/
├── src/
│   └── hiresense/
│       ├── main.py                    # App factory, module registration
│       ├── config.py                  # Pydantic Settings
│       ├── kernel/
│       │   ├── value_objects.py
│       │   ├── events.py
│       │   ├── module.py              # Module protocol
│       │   ├── ports/
│       │   │   ├── llm.py
│       │   │   ├── vector_store.py
│       │   │   ├── latex_compiler.py
│       │   │   └── event_bus.py
│       │   └── contracts/
│       │       ├── ingestion.py
│       │       ├── profile.py
│       │       ├── matching.py
│       │       └── optimization.py
│       ├── adapters/
│       │   ├── llm/
│       │   ├── vector_store/
│       │   ├── latex/
│       │   └── event_bus/
│       ├── ingestion/
│       │   ├── domain/
│       │   ├── ports/
│       │   ├── adapters/              # One file per job source
│       │   ├── infrastructure/
│       │   └── api/
│       ├── profile/
│       │   ├── domain/
│       │   ├── infrastructure/
│       │   └── api/
│       ├── matching/
│       │   ├── domain/
│       │   ├── agent/                 # LangGraph graph + nodes
│       │   ├── infrastructure/
│       │   └── api/
│       ├── optimization/
│       │   ├── domain/
│       │   ├── agent/                 # LangGraph graph + nodes
│       │   ├── infrastructure/
│       │   └── api/
│       └── identity/
│           ├── services.py
│           └── api/
├── frontend/
│   ├── angular.json
│   └── src/
│       └── app/
│           ├── core/
│           ├── features/
│           │   ├── dashboard/
│           │   ├── jobs/
│           │   ├── matching/
│           │   └── optimization/
│           └── shared/
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

## Data Flow (End-to-End)

### 1. Job Ingestion
```
Scheduler/API trigger
  -> IngestionOrchestrator iterates enabled JobSourcePort adapters
  -> Each adapter returns RawJobListing[]
  -> Normalize to NormalizedJob (standardize fields, detect language)
  -> Generate embedding via LLMPort.embed()
  -> Store job + embedding in PostgreSQL/pgvector
  -> Publish JobsIngestedEvent to event bus
```

### 2. Matching & Analysis
```
JobsIngestedEvent received (or manual API trigger for single job)
  -> Retrieve job data + CV embedding from vector store
  -> Cosine similarity for initial semantic score
  -> Invoke LangGraph matching agent:
      extract_job_skills -> extract_cv_skills -> semantic_compare -> score -> generate_analysis
  -> Persist MatchResult to database
  -> Publish MatchCompletedEvent
```

### 3. CV Optimization
```
User clicks "Optimize CV" for a job match
  -> Load MatchResult + original .tex file
  -> Invoke LangGraph optimization agent:
      analyze_gaps -> propose_edits -> validate_tex -> generate_diff
  -> Return diff to frontend

User approves diff
  -> Write modified .tex to cvs/optimized/
  -> Compile via LaTeXCompilerPort -> PDF
  -> Store PDF in cvs/compiled/
  -> Return PDF download URL
```

## Implementation Phases

1. **Skeleton** — Project scaffolding, config, database, auth middleware, kernel ports, Docker Compose
2. **Ingestion** — 2-3 job source adapters (Remotive + RemoteOK + CSV import), scheduling, API endpoints
3. **Profile** — LaTeX parser, skill extraction, embedding generation, CV upload endpoint
4. **Matching** — LangGraph agent, semantic search, scoring, match results API
5. **Optimization** — LangGraph CV editing agent, diff generation, approval flow, LaTeX compilation
6. **Frontend** — Angular dashboard: job list, match scores, diff viewer, settings
7. **Polish** — Remaining job sources, Spanish support, error handling, comprehensive tests

## Verification Plan

### Backend
- Unit tests per module (mock ports with in-memory implementations)
- Integration tests with test PostgreSQL + pgvector (testcontainers)
- LangGraph agent tests with mock LLMPort (deterministic responses)
- API endpoint tests via httpx AsyncClient

### Frontend
- Component tests via Angular testing utilities
- E2E tests via Playwright

### End-to-End
- Full pipeline test: ingest sample jobs -> analyze -> optimize CV -> verify PDF output
- Test with both English and Spanish CVs

### Manual verification
- `docker-compose up` from clean clone should work
- `.env.example` should contain all required variables with comments
- README should cover setup in under 5 minutes
