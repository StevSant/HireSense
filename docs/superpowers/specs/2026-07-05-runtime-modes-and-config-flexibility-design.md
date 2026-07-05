# Runtime Modes & Configuration Flexibility — Design

**Date:** 2026-07-05
**Status:** Approved (pending spec review)

## Problem

Configuration is a single 570-line `Settings` class in `backend/src/hiresense/config.py`.
Three dependencies are hard-required (no default, boot refuses without them):
`database_url`, `llm_api_key`, and the auth trio (`auth_username`, `auth_password`,
`jwt_secret_key`). A fresh clone cannot boot without provisioning Postgres, an LLM key,
and secrets — even for a quick local look.

Meanwhile many subsystems *already* degrade gracefully via blank env vars (telemetry,
SMTP, IMAP, notifications, portfolio, scheduler, rate limiting, Adzuna, preference
learning), but that flexibility is inconsistent, undocumented, and not surfaced through
a single obvious knob.

The goal: **more flexibility, decided by `.env`.** Make the required dependencies degrade
gracefully in a local mode; introduce one top-level mode switch that bundles sensible
defaults; keep an escape hatch so any individual value can still be overridden; and clean
up the config file while we're in there.

## Goals

1. `APP_MODE=local|production` — one switch that sets a bundle of defaults. Default `local`.
2. `database_url` (Postgres) stays **required in both modes** — the pgvector ANN store
   depends on it, so there is no runtime SQLite fallback. It is one of the aggregated
   required values.
3. The other currently-required deps degrade in `local`:
   - `llm_api_key` blank → heuristic-only matching (LLM features return a clear
     "not configured" state; already supported at the factory level).
   - auth secrets blank → ephemeral per-boot dev secret + default creds, loud warning.
4. `production` is strict: blank required values fail loudly with **one aggregated**
   startup error listing everything missing.
5. Individual env vars always override mode defaults (escape hatch).
6. Split `config.py` into a `config/` package, one concern per file, **preserving flat
   attribute access** (`settings.otel_enabled`) so no consumer changes.
7. Document the contract in `.env.example` and `CLAUDE.md`.

## Non-goals

- No nested settings access (`settings.observability.enabled`) — would churn every
  read-site for no benefit. Flat access stays.
- No runtime SQLite fallback for the app. SQLite remains **test-only** (the suite builds
  the app against in-memory SQLite via fixtures that inject `DATABASE_URL`); the running
  app always needs a real Postgres URL. This keeps pgvector ANN intact and avoids a
  silent "am I on SQLite?" failure mode.
- Not touching the already-degrading subsystems' behavior — only documenting them and,
  where natural, letting the mode inform their defaults.

## Current-state findings (verified)

- `Settings()` is instantiated in exactly **one** place: `main.py:62`.
- **69** `settings.X` read-sites, **62** distinct fields, **all flat**. Only 4 files
  import `hiresense.config`.
- LLM already degrades: `make_tracked` (`bootstrap/tracked_factory.py:31`) returns `None`
  when `llm_api_key` is blank.
- SQLite path half-exists: `build_shared_infra` (`bootstrap/shared_infra.py:43-56`)
  special-cases `sqlite://` URLs (skips pool kwargs). `vector_store` is already `None`
  unless `vector_store_provider == "pgvector"`.
- Telemetry already: no-op when `otel_enabled` false; console exporter fallback when
  `otel_exporter_otlp_endpoint` blank (`observability/setup.py`, `exporters.py`).
- Placeholder-secret rejection already exists for `auth_password`/`jwt_secret_key`
  (`config.py:101`).

## Architecture

### Config package layout

```
backend/src/hiresense/config/
  __init__.py          # re-exports Settings (public symbol)
  settings.py          # class Settings(*group mixins); model_config; customise_sources
  mode.py              # AppMode enum + degradation/validation (model_validator logic)
  sources.py           # _CommaSeparatedMixin + Env/DotEnv source subclasses (moved out)
  groups/
    __init__.py        # re-exports every *Settings group
    core.py            # CoreSettings: app_name, app_port, debug, cors_*, auth_*, app_mode
    observability.py   # ObservabilitySettings: otel_*, log_*, deployment_environment
    database.py        # DatabaseSettings: database_url, db_pool_*, vector_store_provider
    llm.py             # LLMSettings: llm_*, embedding_*, match_* models
    http.py            # HttpSettings: http_timeout, http_max_retries, ...
    ingestion.py       # IngestionSettings: sources, URLs, revalidation, closure, csv, latex
    matching.py        # MatchingSettings: weight_*, prerank_*, semantic caches
    preference.py      # PreferenceSettings: preference_*
    analytics.py       # AnalyticsSettings: analytics_*, admin_usage_*
    scheduling.py      # SchedulingSettings: autohunt_*, autopilot_*, scheduler_*
    outreach.py        # OutreachSettings: outreach_*, smtp_*, notification_*, imap_*
    portfolio.py       # PortfolioSettings: portfolio_*
```

Each group is a `BaseSettings` subclass declaring only its fields (plus any field
validators local to it). `Settings` inherits from all groups via multiple inheritance;
`model_config`, `settings_customise_sources`, and the mode `model_validator` live on
`Settings`. Flat access (`settings.otel_enabled`) is preserved because all fields collapse
onto the one composed class.

The one-class-per-file rule is honored per group file; the composed `Settings` in
`settings.py` is the single composition point (its only job).

> Grouping note: fields are partitioned by concern, but the composed class is flat. Where
> a field is read by multiple concerns it lives with its primary owner (e.g.
> `vector_store_provider` lives with `database`).

### Mode resolution & degradation

`mode.py` defines:

```python
class AppMode(str, Enum):
    LOCAL = "local"
    PRODUCTION = "production"
```

Degradation runs as a `model_validator(mode="after")` on `Settings` (so it applies in the
app *and* in tests, every time `Settings()` is built). Because degraded fields default to
`""`/empty, a non-empty value unambiguously means "user set it" → env override wins.

**local mode — fill blanks, warn (`database_url` is NOT degraded — see below):**

| Field | Blank → | Signal |
|---|---|---|
| `llm_api_key` | left blank (heuristic-only) | log (info) |
| `jwt_secret_key` | `secrets.token_urlsafe(48)` (ephemeral) | **loud warn**: tokens reset on restart |
| `auth_username` | `"admin"` | warn |
| `auth_password` | ephemeral `secrets.token_urlsafe(16)` | **loud warn** (printed once so dev can log in) |
| `otel_exporter_otlp_endpoint` | left blank → console | (already) |

`database_url` is **required in local too**: if blank it is reported through the same
aggregated missing-required error as production (in local the aggregated list is usually
just `DATABASE_URL`, since LLM/auth degrade instead).

**production mode — collect all, one error:**

`mode.py` gathers every missing/invalid required value
(`database_url`, `llm_api_key`, `auth_username`, `auth_password`, `jwt_secret_key`) and, if
any are missing, raises a single `ValueError` listing them all, e.g.:

```
Production mode (APP_MODE=production) requires these settings, currently missing/blank:
  - DATABASE_URL
  - LLM_API_KEY
  - AUTH_PASSWORD
Set them in backend/.env or switch to APP_MODE=local for a degraded local run.
```

Placeholder-secret rejection (existing) still applies to any provided value in both modes.
In production, a blank `otel_exporter_otlp_endpoint` is a **warning**, not fatal (console
telemetry is a valid, if noisy, prod choice).

### Data flow

```
.env / env vars
      │  (pydantic-settings sources: init, comma-sep env, comma-sep dotenv, secrets)
      ▼
group mixins declare fields ──► Settings composes them (flat)
      │
      ▼
model_validator(after) ──► mode.resolve(self)
      ├─ local:      fill blanks + warn, return self
      └─ production: collect missing → raise ValueError(all) OR return self
      ▼
main.py: settings = Settings()   # degradation already applied
      ▼
build_shared_infra(settings, ...)  # sees a fully-resolved config; unchanged
setup_telemetry(app, settings)     # unchanged
```

`shared_infra.py` needs **no change** — it already builds a Postgres engine from
`database_url` and only builds `PgVectorStore` when `vector_store_provider == "pgvector"`.
Since Postgres stays required, both paths keep working as today.

## Error handling

- **Config errors** surface at `Settings()` construction (startup), never mid-request.
  Missing required config (both modes for `database_url`; also `llm_api_key`/auth in
  production) → aggregated `ValueError` → process exits with a readable message. Local
  degradations (LLM/auth) → `warnings` + structured log lines, never silent.
- Ephemeral auth password is logged **once** at startup (local only) so the developer can
  authenticate; never logged in production (secret is required there).

## Testing

New `tests/unit/config/`:
- `local` mode with LLM/auth blank but `DATABASE_URL` set → no error; a `jwt_secret_key`
  is generated (non-empty, differs across two `Settings()` builds); `llm_api_key` stays
  blank.
- `local` mode with `DATABASE_URL` also blank → raises the aggregated error naming
  `DATABASE_URL`.
- `production` mode with blanks → raises, and the message names **every** missing field
  (not just the first).
- Env override beats mode default: explicit `LLM_API_KEY`/`JWT_SECRET_KEY` in local mode
  are kept, not overwritten by degradation.
- Placeholder secret still rejected in both modes.
- Comma-separated parsing still works after the source move (regression).

Existing suite: builds the app on SQLite via fixtures that inject `DATABASE_URL`. That
stays exactly as-is (SQLite is test-only; the running app still needs Postgres). Verify the
full suite stays green and DB-free.

## Migration / rollout

- Pure config refactor + additive behavior. No DB migration.
- `docker-compose.yml`: set `APP_MODE=production` (or explicit values) for the `app`
  service so compose keeps its current strictness; document it.
- `.env.example`: add `APP_MODE=local` at the top with the local/production contract
  documented; regroup entries to mirror the new package. Every existing var keeps its name
  (env keys unchanged — only the Python module layout changes).
- `CLAUDE.md`: add a "Configuration & runtime modes" subsection under the config note.

## Risks

- **Multiple-inheritance of `BaseSettings`**: pydantic-settings supports field inheritance
  across bases; MRO is linear and fields are declarative, so collisions are unlikely, but
  the plan must verify no two groups declare the same field name and that
  `settings_customise_sources` + comma-sep sources still fire (regression test covers it).
- **Ephemeral secret confusion**: a dev restarting the server gets logged out. Mitigated by
  the loud warning and documentation; devs who want stability set a real `JWT_SECRET_KEY`.
- **Local mode without Postgres**: because there is no SQLite fallback, a fresh `local`
  clone still needs a `DATABASE_URL` before the app boots. This is intentional (pgvector
  needs Postgres); the aggregated error names `DATABASE_URL` so the fix is obvious, and
  `docker compose up db` provides one with zero extra config.
```
