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

### Backend (from `backend/`, always via [`uv`](https://docs.astral.sh/uv/))

```bash
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
cp backend/.env.example backend/.env     # fill in auth / LLM / database secrets
docker compose up --build                # db, app, frontend, Grafana
```

With `APP_MODE=local` (the default) and a blank `LLM_API_KEY`, the app runs on
heuristic-only matching with default dev credentials, so you can develop without any
external services.

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

All checks must pass before a PR is merged. Run them locally:

```bash
# backend (from backend/)
uv run ruff check .
uv run python -m pytest

# frontend (from frontend/)
npm test
npx ng lint
```

The backend test suite runs **without Postgres** (integration tests use in-memory SQLite).
Tests that genuinely need pgvector are marked `@pytest.mark.pgvector` and skipped by default.
Please add tests for any new behavior.

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
- [ ] Tests added/updated and passing (`pytest`, `npm test`).
- [ ] Linters pass (`ruff check`, `ng lint`).
- [ ] Commits follow Conventional Commits.
- [ ] Docs/README updated if behavior or setup changed.

Open the PR against `main` with a clear description of **what** changed and **why**. Thanks
for contributing! 🎉
