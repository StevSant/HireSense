# AGENTS.md

## Cursor Cloud specific instructions

HireSense is a monorepo: `backend/` (FastAPI + SQLAlchemy/Alembic, Python 3.12, managed by `uv`)
and `frontend/` (Angular 22, managed by `npm`). Standard commands live in `README.md` and
`CLAUDE.md` — consult those for the full list. Notes below are the non-obvious caveats for this
cloud environment.

### Services (dev)
- **Postgres 16 + pgvector** — installed natively (not Docker in this VM). Start it with
  `sudo pg_ctlcluster 16 main start` (check with `sudo pg_lsclusters`). DB/role/password are all
  `hiresense` on `localhost:5432`; the `vector` extension is enabled. This is a hard dependency —
  the backend has no SQLite fallback at runtime.
- **Backend API** — `uv run app` from `backend/` → uvicorn on `:8000` (reads `backend/.env`).
  First boot may download the `all-mpnet-base-v2` embedding model (needs network; `.env` sets
  `HF_HUB_OFFLINE=0` so this is allowed).
- **Frontend** — `npm start` from `frontend/` → `:4200`, proxies `/api` → `http://localhost:8000`
  (`proxy.conf.json`). The backend must be up for API calls to work.

### Node version gotcha (important)
The default `node` on PATH (`/exec-daemon/node`) is **v22.14.0**, but the Angular 22 CLI refuses to
run below **v22.22.3** (`ng lint` / `ng test` / `ng build` / `ng serve` all error out). Use the
nvm-managed Node 22 instead: `nvm use 22` (v22.23.1). This is already wired into `~/.bashrc`, so a
fresh login shell picks it up; if a non-interactive shell doesn't, run `nvm use 22` first.

### Backend test gotcha (important)
Run the backend suite (`uv run python -m pytest` from `backend/`) **without a populated
`backend/.env` in place**. A few narrow config-group unit tests (e.g.
`tests/unit/test_settings_retention.py`, `tests/unit/config/test_package_layout.py`) instantiate
`pydantic-settings` groups directly, and a present `.env` (or ambient config env vars) bleeds in and
fails them. CI runs green because it has no `.env`. To reproduce a clean run locally, move `.env`
aside for the test run (`mv .env .env.bak && uv run python -m pytest ; mv .env.bak .env`). The full
suite is DB-free (uses in-memory SQLite); pgvector-marked tests are opt-in (`-m pgvector`).

### backend/.env for local dev
`backend/.env` (copied from `.env.example`) uses `APP_MODE=local` with explicit known dev creds so
login is reproducible: **username `admin`, password `DevPass_local_2026`**. `LLM_API_KEY` is blank
(matching runs heuristic-only; LLM features return a "not configured" state), and
`OTEL_EXPORTER_OTLP_ENDPOINT` is blank (no collector running — otherwise you'll see benign OTEL
"Shutdown called, ignoring Log" noise at process exit; it is not a failure).

### Other notes
- The **"Fetch Jobs"** ingestion action hits external job-board APIs (Remotive, RemoteOK, etc.),
  which may be slow or blocked from this sandbox — expect it to be flaky here. Full-stack CRUD
  (e.g. profile / cover-letter templates → Postgres) works without any external service or LLM key.
- Observability (Grafana/OTel `otel-lgtm`) is optional and not run here.
