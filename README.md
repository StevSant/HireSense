<div align="center">

<img src="docs/assets/logo.svg" alt="HireSense" width="320" />

### AI-assisted job hunting — ingest, rank, and apply, end to end.

HireSense pulls postings from job boards and company ATS portals, ranks them against your
profile with **pgvector semantic search + tiered LLM scoring**, and manages the whole
pipeline: tracking, CV & cover-letter generation, interview prep, outreach, and analytics.

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Angular 21](https://img.shields.io/badge/Angular-21-DD0031?style=flat-square&logo=angular&logoColor=white)](https://angular.dev/)
[![PostgreSQL + pgvector](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![License: MIT](https://img.shields.io/badge/License-MIT-0f766e?style=flat-square)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-2dd4bf?style=flat-square)](#-contributing)

**[Quick Start](#-quick-start) · [How it works](#-how-it-works) · [Architecture](#-architecture) · [Screenshots](#-screenshots)**

</div>

<div align="center">
  <img src="docs/assets/discover.png" alt="HireSense — Discover view: ranked jobs with live match scores" width="100%" />
</div>

---

## What is HireSense?

Job hunting is a search problem drowning in noise: the same roles reposted across a dozen
boards, listings that don't match your stack, and no signal on where you actually stand in
the market. HireSense turns that firehose into a ranked, deduplicated shortlist.

It ingests postings from many sources, **pre-ranks the entire corpus** with pgvector ANN so
the best matches reach page one, refines with skill overlap and tiered LLM scoring, then
helps you act — track applications, generate tailored CVs and cover letters, prep for
interviews, and see where your profile sits on pay and fit.

## ✨ Features

- **Multi-source ingestion** — job boards (Remotive, RemoteOK, Jobicy, Himalayas,
  WeWorkRemotely, GetOnBoard, LinkedIn, HN "Who is hiring?") and company ATS portals
  (Greenhouse, Lever, Ashby), deduplicated by stable identity.
- **Semantic matching** — global pgvector ANN pre-ranking over the whole corpus, blended
  with skill overlap and **tiered LLM scoring** (cheap models filter, strong models rank).
- **Application pipeline** — track every role Saved → Applied → Interviewing → Offer, with
  per-application artifacts and research.
- **Document generation** — CVs and cover letters from templates, tailored to each posting.
- **Market analytics** — your pay band, best-fit companies and roles, and pipeline
  conversion, all derived from your matched jobs.
- **Autopilot** — scheduled hunts, notifications, and inbound-email → tracking, so the
  pipeline keeps moving without you babysitting it.
- **Change & closure detection** — jobs are updated in place on refetch and closed
  automatically when they disappear or 404 (see [How it works](#-how-it-works)).

## 📸 Screenshots

<table>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/assets/insights.png" alt="Analytics" /><br/>
      <sub><b>Insights</b> — market pay band, best-fit companies & roles, and pipeline conversion.</sub>
    </td>
    <td width="50%" valign="top">
      <img src="docs/assets/pipeline.png" alt="Application pipeline" /><br/>
      <sub><b>Pipeline</b> — track applications by stage with match scores and generated artifacts.</sub>
    </td>
  </tr>
</table>

## 🚀 Quick Start

Choose the path that fits you:

| Best for | Command |
|---|---|
| **Trying it out** (everything in Docker) | `docker compose up --build` |
| **Backend development** | `cd backend && uv sync && uv run app` |
| **Frontend development** | `cd frontend && npm install && npm start` |

**Docker** brings up the full stack — `db` (Postgres + pgvector), `app` (FastAPI :8000),
`frontend` (Angular :4200), and Grafana (:3000). First, set up backend config:

```bash
cp backend/.env.example backend/.env    # fill in auth / LLM / database secrets
docker compose up --build
```

> **No LLM key?** HireSense runs in `APP_MODE=local` by default — with a blank `LLM_API_KEY`
> it falls back to heuristic-only matching and default dev credentials, so you can explore
> the app before wiring up any external services. See [Configuration](#configuration).

## 🧠 How it works

### Matching pipeline

```
posting corpus  ──►  pgvector ANN pre-rank  ──►  skill overlap  ──►  tiered LLM scoring  ──►  ranked shortlist
 (all sources)       (global, whole corpus)      (fast filter)       (cheap → strong)          (page 1 = best fit)
```

Semantic pre-ranking runs over the **entire** corpus (not just the current page), so the
strongest matches surface first. LLM scoring is tiered — inexpensive models filter the long
tail, stronger models rank the finalists — keeping cost proportional to signal.

### Job lifecycle

Jobs are upserted by a stable identity (`source` + `source_id`, else `sha256(url)`); a
content hash drives in-place updates on refetch. Closures are detected two ways:

- **Snapshot sources** (company ATS portals) — a job missing from N consecutive complete
  fetches is marked `closed`.
- **Feed / search sources** — a throttled URL-probe sweep closes listings that 404 or show
  a "no longer available" marker. The in-app scheduler runs the sweep when
  `SCHEDULER_ENABLED=true`; when disabled, operators can trigger
  `POST /ingestion/revalidate` manually or from an external cron.

Closed jobs are hidden by default and dropped from semantic search.

## 🧩 Tech stack

| Layer | Tech |
|---|---|
| **Backend** | Python 3.12+, FastAPI, SQLAlchemy 2.0 + Alembic, Pydantic |
| **Database** | PostgreSQL 16 + `pgvector` (ANN semantic search) |
| **Frontend** | Angular 21 (standalone components, signals), Vitest |
| **LLM / embeddings** | LangChain provider abstraction (Anthropic default), `all-mpnet-base-v2` embeddings |
| **Observability** | OpenTelemetry → Grafana / Loki / Tempo (otel-lgtm) |
| **Tooling** | `uv` (Python), `npm` (frontend), `ruff`, `pytest` |

## 🏗️ Architecture

Hexagonal / clean architecture with **bounded-context modules** (`ingestion`, `matching`,
`applications`, `tracking`, `profile`, `analytics`, `outreach`, `autohunt`, …), each layered
`api → domain ← infrastructure`:

- **`domain/`** is pure Pydantic + business logic — imports no framework and no
  infrastructure; it depends only on ports (`Protocol`s).
- **`infrastructure/`** holds SQLAlchemy ORM classes and repositories that map ORM ↔ domain.
- **Wiring** happens only in `bootstrap/`; the domain never reaches for infrastructure.

Full detail — dependency rules, ports/adapters, the LLM decorator chain, and an "adding a
new module" recipe — lives in **[`backend/ARCHITECTURE.md`](backend/ARCHITECTURE.md)**.

## 💻 Local development

**Backend** (from `backend/`, always via [`uv`](https://docs.astral.sh/uv/)):

```bash
uv sync                                  # install deps (incl. dev group)
uv run python -m alembic upgrade head    # apply migrations
uv run app                               # dev server (uvicorn, reload, :8000)
uv run python -m pytest                  # tests (run DB-free against in-memory SQLite)
uv run ruff check .                      # lint
```

> **Note:** on some setups bare `uv run pytest` / `uv run alembic` fail — use the
> `uv run python -m …` form shown above.

**Frontend** (from `frontend/`):

```bash
npm install
npm start        # dev server (proxies /api → backend via proxy.conf.json)
npm run build    # production build
npm test         # Vitest
```

### Configuration

Every configurable value flows through `backend/src/hiresense/config/` + `.env` — no
hardcoded URLs, keys, or thresholds. `APP_MODE` sets a bundle of defaults:

| Mode | Behavior |
|---|---|
| **`local`** (default) | Blank `LLM_API_KEY` → heuristic-only matching; blank auth → ephemeral dev secret + default creds with a loud warning. `DATABASE_URL` (Postgres) is still required. |
| **`production`** | Strict: missing `DATABASE_URL` / `LLM_API_KEY` / auth trio fail fast at startup. Used by `docker-compose.yml`. |

## 🤝 Contributing

Contributions are welcome! HireSense follows a spec → plan → implement flow:

1. Check [`docs/superpowers/specs/`](docs/superpowers/specs/) and
   [`docs/superpowers/plans/`](docs/superpowers/plans/) for existing designs before changing
   a feature.
2. New features get a spec + implementation plan before code.
3. Commits follow [Conventional Commits](https://www.conventionalcommits.org/), scoped by
   module (e.g. `feat(outreach): …`).
4. Run `uv run ruff check .` and `uv run python -m pytest` (backend) and `npm test` +
   `npx ng lint` (frontend) before opening a PR.

New here? Browse the [open issues](https://github.com/StevSant/HireSense/issues) for a good
place to start.

## 📄 License

Released under the [MIT License](LICENSE).
