# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

HireSense — AI-assisted job hunting. Ingests postings from job boards and company ATS portals, ranks them against the user's profile (pgvector ANN semantic pre-ranking + skill overlap + tiered LLM scoring), and manages applications end to end (tracking, CV/cover-letter generation, interview prep, outreach, analytics).

Monorepo: `backend/` (Python 3.12+, FastAPI, SQLAlchemy + Alembic, PostgreSQL 16 + pgvector), `frontend/` (Angular 21, standalone components + signals, Vitest), `docker-compose.yml` (db, app, frontend, otel-lgtm/Grafana).

## Commands

### Backend (run from `backend/`, always via `uv`)

```bash
uv sync                                  # install deps (incl. dev group)
uv run python -m alembic upgrade head    # apply migrations
uv run app                               # dev server (uvicorn, reload, port 8000)
uv run python -m pytest                  # all tests
uv run python -m pytest tests/unit/outreach                          # one module's tests
uv run python -m pytest tests/integration/test_outreach_endpoints.py::test_name  # single test
uv run ruff check .                      # lint
uv run ruff format .                     # format
uv run python -m alembic revision --autogenerate -m "msg"            # new migration
```

**Quirk:** bare `uv run pytest` / `uv run alembic` fail on some Windows setups (broken exe trampolines) — always use the `uv run python -m …` form. `uv run ruff` and `uv run app` work fine.

The full test suite runs **without Postgres** — integration tests build the app against in-memory SQLite. Anything that genuinely needs pgvector (ANN search) can only be validated against a live DB (`docker compose up db`).

**pgvector ANN validation (opt-in).** `tests/integration/test_pgvector_ann.py` exercises the real `PgVectorStore` (upsert → ANN `<=>` ranking → `delete` eviction → dimension handling) against the compose Postgres+pgvector DB. These tests are marked `@pytest.mark.pgvector` and are **skipped by default** — the default `uv run python -m pytest` run stays green and DB-free. To run them:

```bash
docker compose up db                      # start Postgres+pgvector on :5432
export DATABASE_URL=postgresql+asyncpg://hiresense:hiresense@localhost:5432/hiresense   # PowerShell: $env:DATABASE_URL="..."
uv run python -m pytest -m pgvector       # collects only the pgvector tests
```

The opt-in is enforced in `tests/integration/conftest.py`: a collection hook skips any `pgvector`-marked test unless `-m pgvector` is passed, and the fixture skips gracefully (no error) if the DB is unreachable. The fixture creates, truncates, and drops the `vector_embeddings` table itself, sized to `EMBEDDING_DIM`, so the run is self-contained.

### Frontend (run from `frontend/`)

```bash
npm install
npm start                                # dev server, proxies /api → backend (proxy.conf.json)
npm run build                            # production build
npm test                                 # Vitest via ng test
npm test -- --include "**/foo.spec.ts"   # single spec file
npm test -- --filter "test name"         # single test by name
```

### Docker

```bash
docker compose up --build    # db :5432, app :8000, frontend :4200, Grafana :3000
```

Backend config lives in `backend/.env` (copy from `backend/.env.example`). Every configurable value goes through the `src/hiresense/config/` package + `.env` — never hardcode URLs, keys, or thresholds; new settings must also be added to `.env.example` with a comment.

#### Runtime modes (`APP_MODE`)

`APP_MODE` (in `config/mode.py`, default `local`) sets a bundle of defaults; any individual env var overrides its mode default.

- **`local`** — blank `LLM_API_KEY` → heuristic-only matching (LLM features return a not-configured state); blank auth secrets → an ephemeral per-boot dev secret + default creds with a loud startup warning. `DATABASE_URL` (Postgres) is still required — there is no SQLite fallback (pgvector ANN needs Postgres).
- **`production`** — strict: missing `DATABASE_URL` / `LLM_API_KEY` / auth trio fail at startup with one aggregated error. `docker-compose.yml` sets `APP_MODE=production`.

Config is a package: per-concern `BaseSettings` groups under `config/groups/` composed into one flat `Settings` in `config/settings.py` (flat `settings.otel_enabled` access preserved). Add a new field to the matching group file — `Settings` inherits every group's fields, so nothing extra needs re-exporting.

### Concurrent sessions / worktrees

The main checkout may be shared with another active session (and lives under OneDrive, which fights with heavy git churn). For multi-commit feature work, prefer an isolated `git worktree` **outside** the OneDrive tree, then `uv sync` and copy `backend/.env` into it. Clean up worktrees when done.

## Architecture

**Required reading before structural backend changes: [`backend/ARCHITECTURE.md`](backend/ARCHITECTURE.md).** It contains the full dependency rules, the per-module layout, the global ports/adapters table, the LLM adapter decorator chain, and a step-by-step "adding a new module" recipe. The summary below is the minimum to orient yourself.

### Backend — hexagonal, bounded contexts

`src/hiresense/<module>/` per bounded context (`ingestion`, `matching`, `applications`, `tracking`, `profile`, `admin`, `analytics`, `outreach`, `autohunt`, `preference`, `interview`, `research`, `optimization`, `identity`, …), each layered `api → domain ← infrastructure`:

- `domain/` is pure Pydantic + business logic. It imports **nothing** from `infrastructure/` and **no** framework packages (`sqlalchemy`, `langchain*`, `httpx`). It depends only on ports (`Protocol`s).
- `infrastructure/` holds SQLAlchemy `*Orm` classes and repositories that map ORM ↔ domain models. Stateless modules have no `ports/`/`infrastructure/` at all — don't add empty placeholders.
- Wiring happens only in `bootstrap/` (`build_<module>(infra, …)` → `Provider` stored on `app.state`; `api/dependencies.py` reads it back per request). Never wire via fallback imports in the domain.
- Cross-cutting ports/adapters (`LLMPort`, `EmbeddingPort`, `VectorStorePort`, `EventBus`, …) live in `src/hiresense/ports/` and `src/hiresense/adapters/`.
- Every ORM class must be imported in `infrastructure/registry.py` or Alembic `--autogenerate` won't see its table.
- Every package `__init__.py` re-exports its public symbols; import from the contextual package (`from hiresense.ingestion.adapters import RemotiveAdapter`), never from the implementation file.

Coding standards (DI pattern, domain events, kernel/shared types, LLM scorers, module structure) are documented in `agent-os/standards/backend/`; consult the matching standard before writing code in those areas.

### Frontend — Angular standalone + signals

No NgModules: standalone components with lazy-loaded routes (`app.routes.ts`). All component reactive state uses signals. Structure: `src/app/core/` (guards, interceptors, models, services) and `src/app/pages/<domain>/` mirroring the backend modules. Conventions: per-domain services wrapping HTTP, interfaces in `.model.ts` files by domain — see `agent-os/standards/frontend/`.

### Job lifecycle (cross-cutting behavior)

Jobs are upserted by stable identity (`source` + `source_id`, else `sha256(url)`); a content hash drives in-place updates. Closure detection: snapshot sources (ATS portals) close jobs missing from N consecutive complete fetches; feed sources close via a throttled URL-probe sweep (`POST /ingestion/revalidate`) driven by an **external** cron — the app never self-schedules revalidation. Closed jobs are hidden by default and excluded from semantic search.

## Feature workflow

Feature work follows a spec → plan → implement flow documented under `docs/superpowers/`:

1. Before changing an existing feature, check `docs/superpowers/specs/` and `docs/superpowers/plans/` for its design doc — most features have one (`YYYY-MM-DD-<feature>-design.md`).
2. New features get a spec in `docs/superpowers/specs/` and an implementation plan in `docs/superpowers/plans/` before code, following the existing naming convention.

Commits follow Conventional Commits (`type(scope): description`), scoped by module (e.g. `feat(outreach): …`).
