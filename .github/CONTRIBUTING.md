# Contributing to HireSense

Thanks for your interest in improving HireSense! This guide covers how to get set up,
the conventions we follow, and how to get a change merged.

By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- 🐛 **Report a bug** — open an [issue](https://github.com/StevSant/HireSense/issues) with
  steps to reproduce, expected vs. actual behavior, and your environment.
- 💡 **Propose a feature** — open an issue describing the problem you're solving before
  writing code, so we can agree on the approach.
- 🔧 **Send a pull request** — fixes, features, docs, and tests are all welcome.

New here? Browse the [open issues](https://github.com/StevSant/HireSense/issues) — anything
small and self-contained is a good first change.

## Development setup

HireSense is a monorepo: a Python/FastAPI `backend/` and an Angular `frontend/`.

**Prerequisites:** [`uv`](https://docs.astral.sh/uv/), Node **≥ 22.22.3**, Docker, and a
PostgreSQL 16 + `pgvector` database. Postgres is **required in every mode** — ANN semantic
search runs in the database and there is no SQLite fallback for the running app.

### Config: two `.env` files

```bash
cp .env.example .env                     # repo root — Compose vars (POSTGRES_PASSWORD, ports)
cp backend/.env.example backend/.env     # application config (auth, LLM, DATABASE_URL, …)
```

Then replace the placeholders: `POSTGRES_PASSWORD` has no default in `docker-compose.yml`,
and startup **rejects** `AUTH_PASSWORD=changeme` / `JWT_SECRET_KEY=change-this-to-a-random-secret`.
Generate real values with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

### Backend (from `backend/`, always via [`uv`](https://docs.astral.sh/uv/))

```bash
docker compose up -d db                  # Postgres + pgvector — required
uv sync                                  # install deps (incl. dev group)
uv run python -m alembic upgrade head    # apply migrations
uv run app                               # dev server (uvicorn, reload, :8000)
```

> **Note:** on some setups bare `uv run pytest` / `uv run alembic` fail — use the
> `uv run python -m …` form.

### Frontend (from `frontend/`)

```bash
npm install
npm start        # dev server (proxies /api → backend via proxy.conf.json)
```

### Everything at once (Docker)

```bash
docker compose up --build                # db, app, frontend, Grafana
docker compose exec app uv run python -m alembic upgrade head   # create the schema
```

Compose deliberately sets `APP_MODE=production` — it is a real deployment, so it refuses to
boot with anything missing. The dev server (`uv run app`) defaults to `APP_MODE=local`, where
a blank `LLM_API_KEY` degrades to heuristic-only matching and blank auth generates ephemeral
dev credentials with a loud warning, so you can develop without any external service.
`DATABASE_URL` is required either way.

## How we work: spec → plan → implement

Non-trivial features follow a lightweight design-first flow:

1. Before changing an existing feature, check
   [`docs/superpowers/specs/`](../docs/superpowers/specs/) and
   [`docs/superpowers/plans/`](../docs/superpowers/plans/) — most features have a design doc.
2. New features get a spec and an implementation plan (following the existing
   `YYYY-MM-DD-<feature>-…` naming) before code.

## Coding standards

- **Backend architecture is hexagonal.** Each bounded-context module is layered
  `api → domain ← infrastructure`. The `domain/` layer is pure Pydantic + business logic and
  imports **no** framework or infrastructure — it depends only on ports (`Protocol`s). See
  [`backend/ARCHITECTURE.md`](../backend/ARCHITECTURE.md) before making structural changes.
- **No hardcoded config.** Every URL, key, or threshold flows through
  `backend/src/hiresense/config/` + `.env`; add new settings to `.env.example` too.
- **Frontend is standalone Angular + signals** — no NgModules; per-domain services wrap HTTP.
- **Every package `__init__.py` re-exports its public symbols** — import from the contextual
  package, not the implementation file.

## Tests and linting

All checks must pass before a PR is merged. This is the **complete** list CI enforces
(`.github/workflows/ci.yml`) — running only a subset locally can still go red:

```bash
# backend (from backend/)
uv run ruff format --check .   # CI fails on formatting, not just lint
uv run ruff check .
uv run python -m pytest --cov=hiresense --cov-fail-under=85
```

```bash
# frontend (from frontend/) — needs Node >= 22.22.3
npm run format:check                        # prettier
npx tsc --noEmit -p tsconfig.app.json       # typecheck: app
npx tsc --noEmit -p tsconfig.spec.json      # typecheck: specs
npx ng lint                                 # angular-eslint, incl. a11y rules
npm test
npm run test:e2e:smoke                      # needs: npx playwright install chromium
npm run build
```

> **Formatting gotcha:** `npm test` and `npm run build` do *not* run prettier or `ng lint` —
> CI does. Run `npm run format` and `npx ng lint` before pushing.

CI additionally runs, against a live Postgres service container, `alembic upgrade head`,
`alembic check` (schema-drift), and the pgvector suite (`pytest -m pgvector`). If your change
touches ORM classes or migrations, reproduce that locally with `docker compose up -d db`.

The default backend test suite runs **without Postgres** (integration tests use in-memory
SQLite). Tests that genuinely need pgvector are marked `@pytest.mark.pgvector` and skipped by
default. Please add tests for any new behavior — coverage is gated at 85%.

## Commit messages

We follow [Conventional Commits](https://www.conventionalcommits.org/), scoped by module:

```
feat(outreach): add follow-up sequence scheduling
fix(ingestion): dedupe jobs sharing a source_id
docs(readme): document APP_MODE
```

Types: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`.

## Pull request checklist

Before opening a PR:

- [ ] The change is focused — one logical concern per PR.
- [ ] Tests added/updated and passing (`pytest`, `npm test`), coverage still ≥ 85%.
- [ ] Formatters clean (`ruff format --check`, `npm run format:check`).
- [ ] Typecheck clean (`tsc --noEmit` for both `tsconfig.app.json` and `tsconfig.spec.json`).
- [ ] Linters pass (`ruff check`, `ng lint`).
- [ ] Commits follow Conventional Commits.
- [ ] Docs/README updated if behavior or setup changed.

Open the PR against `main` with a clear description of **what** changed and **why**. Thanks
for contributing! 🎉
