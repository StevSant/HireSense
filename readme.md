# HireSense

AI-assisted job hunting: ingest job postings from many sources, rank them against your
profile with semantic + LLM matching, and manage applications end to end.

- **Ingestion** — pulls listings from job boards (Remotive, RemoteOK, Jobicy, Himalayas,
  WeWorkRemotely, GetOnBoard, LinkedIn, HN "Who is hiring?") and company ATS portals
  (Greenhouse, Lever, Ashby). Detects changes and closures on refetch (see below).
- **Matching** — global semantic pre-ranking via pgvector ANN over the whole corpus
  (so the best matches reach page 1), blended with skill overlap and tiered LLM scoring.
- **Applications** — track applications, generate CVs / cover letters from templates.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy + Alembic, pydantic |
| Database | PostgreSQL 16 + `pgvector` (ANN semantic search) |
| Frontend | Angular (standalone components, signals) |
| LLM / embeddings | LangChain provider abstraction (Anthropic default), `all-mpnet-base-v2` embeddings |
| Tooling | `uv` (Python), `npm` (frontend), `ruff`, `pytest` |

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env   # fill in auth/LLM/database secrets
docker compose up --build
```

Services: `db` (pgvector), `app` (FastAPI), `frontend` (Angular). See `docker-compose.yml`
for ports.

## Local development

**Backend** (from `backend/`):

```bash
uv sync                                  # install deps (incl. dev group)
uv run python -m alembic upgrade head    # apply migrations
uv run app                               # run the API
uv run python -m pytest                  # tests
```

> Note: on some setups bare `uv run pytest` / `uv run alembic` fail — use the
> `uv run python -m …` form shown above.

**Frontend** (from `frontend/`):

```bash
npm install
npm start        # dev server (proxies /api to the backend via proxy.conf.json)
npm run build    # production build
```

## Job lifecycle (change & closure detection)

On refetch, jobs are upserted by a stable identity (`source` + `source_id`, else
`sha256(url)`); a content hash drives in-place updates. Closures are detected two ways:

- **Snapshot sources** (company ATS portals): a job missing from N consecutive complete
  fetches is marked `closed`.
- **Feed/search sources**: a throttled URL-probe sweep (`POST /ingestion/revalidate`,
  driven by an external cron) closes listings that 404 or show a "no longer available"
  marker.

Closed jobs are hidden by default (with a "Show closed" toggle) and dropped from semantic
search. Age-based pruning is a GC backstop.

## Architecture

Hexagonal / clean architecture with bounded-context modules
(`ingestion`, `matching`, `applications`, `profile`, `admin`) layered `api → domain ← infrastructure`;
the domain depends only on ports (Protocols), never on frameworks. Full detail:
[`backend/ARCHITECTURE.md`](backend/ARCHITECTURE.md).
