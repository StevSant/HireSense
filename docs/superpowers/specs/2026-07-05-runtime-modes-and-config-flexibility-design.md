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
2. Currently-required deps degrade in `local`:
   - `database_url` blank → SQLite file fallback.
   - `llm_api_key` blank → heuristic-only matching (LLM features return a clear
     "not configured" state; already supported at the factory level).
   - auth secrets blank → ephemeral per-boot dev secret + default creds, loud warning.
3. `production` is strict: blank required values fail loudly with **one aggregated**
   startup error listing everything missing.
4. Individual env vars always override mode defaults (escape hatch).
5. Split `config.py` into a `config/` package, one concern per file, **preserving flat
   attribute access** (`settings.otel_enabled`) so no consumer changes.
6. Document the contract in `.env.example` and `CLAUDE.md`.

## Non-goals

- No nested settings access (`settings.observability.enabled`) — would churn every
  read-site for no benefit. Flat access stays.
- No async SQLite / aiosqlite work: the app builds only a **sync** engine
  (`shared_infra.py`), so a sync `sqlite:///` URL is sufficient.
- No pgvector-on-SQLite: SQLite fallback disables the pgvector ANN store (semantic
  pre-ranking degrades to the non-vector path). Real Postgres is still required for ANN.
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
> `vector_store_provider` lives with `database` since SQLite fallback toggles it).

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

**local mode — fill blanks, warn:**

| Field | Blank → | Signal |
|---|---|---|
| `database_url` | `sqlite:///./hiresense_dev.db` | `warnings.warn` + log |
| `vector_store_provider` | forced to `"none"` **iff** resolved DB is SQLite | log (info) |
| `llm_api_key` | left blank (heuristic-only) | log (info) |
| `jwt_secret_key` | `secrets.token_urlsafe(48)` (ephemeral) | **loud warn**: tokens reset on restart |
| `auth_username` | `"admin"` | warn |
| `auth_password` | ephemeral `secrets.token_urlsafe(16)` | **loud warn** (printed once so dev can log in) |
| `otel_exporter_otlp_endpoint` | left blank → console | (already) |

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
build_shared_infra(settings, ...)  # sees a fully-resolved config; SQLite branch already handled
setup_telemetry(app, settings)     # unchanged
```

`shared_infra.py` needs one small change: when `vector_store_provider == "none"` (or not
`"pgvector"`), leave `vector_store=None` (already the case). Confirm every `vector_store`
consumer tolerates `None` (they do today for the non-pgvector path).

## Error handling

- **Config errors** surface at `Settings()` construction (startup), never mid-request.
  Production missing-config → aggregated `ValueError` → process exits with a readable
  message. Local degradations → `warnings` + structured log lines, never silent.
- Ephemeral auth password is logged **once** at startup (local only) so the developer can
  authenticate; never logged in production (secret is required there).
- SQLite fallback + a `vector_store_provider=pgvector` explicitly set by the user in local
  mode: warn that pgvector needs Postgres and either (a) honor it and let it fail at query
  time, or (b) downgrade to `none` with a warning. **Decision: downgrade to `none` + warn**
  (fail-soft is the whole point of local mode).

## Testing

New `tests/unit/config/`:
- `local` mode with everything blank → `database_url` is the SQLite default, a
  `jwt_secret_key` is generated (non-empty, differs across two `Settings()` builds),
  `vector_store_provider == "none"`.
- `production` mode with blanks → raises, and the message names **every** missing field
  (not just the first).
- Env override beats mode default: `APP_MODE=local` + explicit `DATABASE_URL=postgres...`
  keeps the Postgres URL.
- Placeholder secret still rejected in both modes.
- Comma-separated parsing still works after the source move (regression).

Existing suite: builds the app on SQLite. With `APP_MODE=local` as the default, fixtures
that currently inject `DATABASE_URL` can be simplified (follow-up cleanup, not required for
green). Verify the full suite stays green and DB-free.

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
- **Silent SQLite in local**: someone could run "local" believing they're on Postgres. The
  startup warning names the SQLite path explicitly to avoid this.
```
