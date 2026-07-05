# Runtime Modes & Configuration Flexibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `APP_MODE=local|production` switch that lets the app boot with minimal config in local mode (degrading LLM + auth gracefully) while staying strict in production, and split the 570-line `config.py` into a clean per-concern `config/` package — with zero call-site changes.

**Architecture:** Task 1 adds the mode behavior in-place in `config.py` (make the 3 required deps optional except DATABASE_URL, add a `model_validator` that degrades in local / aggregates-and-raises in production). Task 2 mechanically splits `config.py` into a `config/` package of `BaseSettings` mixin groups composed into one flat `Settings` (flat attribute access preserved). Task 3 wires docker-compose, `.env.example`, and `CLAUDE.md`.

**Tech Stack:** Python 3.13, pydantic v2 / pydantic-settings, pytest, ruff.

## Global Constraints

- Run everything via `uv` (`uv run python -m pytest`, `uv run ruff check .`). Bare `uv run pytest`/`alembic` are broken on this machine — always use the `-m` form.
- `DATABASE_URL` (Postgres) is **required in both modes** — there is NO runtime SQLite fallback (pgvector ANN needs Postgres). SQLite stays test-only.
- Flat attribute access (`settings.otel_enabled`) MUST be preserved — every one of the 69 existing `settings.X` read-sites keeps working unchanged.
- Every env var keeps its exact current name; only the Python module layout changes.
- Field declarations, defaults, types, and their explanatory comments are moved **verbatim** during the split — do not rename, retype, re-default, or reword comments.
- `APP_MODE` defaults to `local`.
- Auth dev-secret in local mode is **ephemeral per-boot** (regenerated each `Settings()`), with a loud warning.
- ruff: line-length 100, target py312. One class/constant per file where practical (each group file owns its concern).
- Commit messages follow Conventional Commits, English, scope `config`. No AI attribution.

---

### Task 1: `APP_MODE` behavior + graceful degradation (in-place in `config.py`)

Add the mode switch and degradation logic to the existing single-file `config.py`. No package split yet — that de-risks the behavior change behind the existing test suite.

**Files:**
- Modify: `backend/src/hiresense/config.py`
- Create: `backend/tests/unit/config/__init__.py`
- Create: `backend/tests/unit/config/test_mode.py`

**Interfaces:**
- Produces: `AppMode` enum (`AppMode.LOCAL = "local"`, `AppMode.PRODUCTION = "production"`); `Settings.app_mode: AppMode` field (default `AppMode.LOCAL`); a `model_validator(mode="after")` named `_resolve_mode` that mutates/validates the instance and returns it.
- Consumes: nothing new.

- [ ] **Step 1: Create the test package marker**

Create `backend/tests/unit/config/__init__.py` (empty file).

- [ ] **Step 2: Write the failing mode tests**

Create `backend/tests/unit/config/test_mode.py`:

```python
import pytest


def _set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set every field that is required in production to a real value."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")


def test_local_generates_ephemeral_jwt_when_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")

    from hiresense.config import Settings

    settings = Settings()
    assert settings.jwt_secret_key  # non-empty, generated
    assert settings.auth_username == "admin"
    assert settings.auth_password  # generated dev password
    assert settings.llm_api_key == ""  # heuristic-only, not filled


def test_local_ephemeral_jwt_differs_across_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")

    from hiresense.config import Settings

    assert Settings().jwt_secret_key != Settings().jwt_secret_key


def test_local_missing_database_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")

    from hiresense.config import Settings

    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings()


def test_production_missing_required_lists_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("AUTH_USERNAME", "")
    monkeypatch.setenv("AUTH_PASSWORD", "")
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")

    from hiresense.config import Settings

    with pytest.raises(ValueError) as exc:
        Settings()
    message = str(exc.value)
    for env in ("DATABASE_URL", "LLM_API_KEY", "AUTH_PASSWORD", "JWT_SECRET_KEY", "AUTH_USERNAME"):
        assert env in message


def test_env_override_wins_in_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "local")
    _set_required(monkeypatch)
    monkeypatch.setenv("JWT_SECRET_KEY", "my-explicit-secret")

    from hiresense.config import Settings

    assert Settings().jwt_secret_key == "my-explicit-secret"


def test_production_with_all_required_boots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "production")
    _set_required(monkeypatch)

    from hiresense.config import Settings

    settings = Settings()
    assert settings.app_mode.value == "production"


def test_app_mode_defaults_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.delenv("APP_MODE", raising=False)

    from hiresense.config import Settings

    assert Settings().app_mode.value == "local"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run python -m pytest tests/unit/config/test_mode.py -v`
Expected: FAIL — `app_mode` attribute / `AppMode` import errors, and blanks currently raise pydantic "field required" instead of the mode logic.

- [ ] **Step 4: Add the `AppMode` enum and mode logic to `config.py`**

At the top of `backend/src/hiresense/config.py`, after the existing imports, add:

```python
import logging
import secrets
import warnings
from enum import Enum

from pydantic import model_validator

_logger = logging.getLogger(__name__)


class AppMode(str, Enum):
    """Runtime mode. LOCAL degrades missing LLM/auth config; PRODUCTION is strict."""

    LOCAL = "local"
    PRODUCTION = "production"


# DATABASE_URL is required in BOTH modes (pgvector ANN needs Postgres; no SQLite fallback).
_ALWAYS_REQUIRED: tuple[tuple[str, str], ...] = (("DATABASE_URL", "database_url"),)
# These degrade in local, but are required in production.
_PRODUCTION_REQUIRED: tuple[tuple[str, str], ...] = (
    ("LLM_API_KEY", "llm_api_key"),
    ("AUTH_USERNAME", "auth_username"),
    ("AUTH_PASSWORD", "auth_password"),
    ("JWT_SECRET_KEY", "jwt_secret_key"),
)


def _missing(settings: "Settings", required: tuple[tuple[str, str], ...]) -> list[str]:
    return [env for env, attr in required if not getattr(settings, attr)]


def _apply_mode(settings: "Settings") -> "Settings":
    """Resolve APP_MODE: raise an aggregated error for missing required config, or
    degrade blanks in local mode. Mutates and returns the settings instance."""
    if settings.app_mode is AppMode.PRODUCTION:
        missing = _missing(settings, _ALWAYS_REQUIRED + _PRODUCTION_REQUIRED)
        if missing:
            raise ValueError(
                "Production mode (APP_MODE=production) requires these settings, "
                "currently missing/blank:\n"
                + "\n".join(f"  - {name}" for name in missing)
                + "\nSet them in backend/.env or switch to APP_MODE=local for a "
                "degraded local run."
            )
        _logger.info("HireSense config resolved: APP_MODE=production")
        return settings

    # local mode
    missing_db = _missing(settings, _ALWAYS_REQUIRED)
    if missing_db:
        raise ValueError(
            "APP_MODE=local still requires these settings, currently missing/blank:\n"
            + "\n".join(f"  - {name}" for name in missing_db)
            + "\nStart Postgres (docker compose up db) and set DATABASE_URL — "
            "pgvector ANN has no SQLite fallback."
        )
    if not settings.llm_api_key:
        _logger.info(
            "APP_MODE=local: LLM_API_KEY not set — matching runs heuristic-only "
            "(no LLM scoring; LLM-backed features return a not-configured state)."
        )
    if not settings.jwt_secret_key:
        settings.jwt_secret_key = secrets.token_urlsafe(48)
        warnings.warn(
            "APP_MODE=local: JWT_SECRET_KEY not set — generated an EPHEMERAL secret; "
            "issued tokens reset on every restart. Set JWT_SECRET_KEY for stable sessions.",
            stacklevel=2,
        )
    if not settings.auth_username:
        settings.auth_username = "admin"
        _logger.warning("APP_MODE=local: AUTH_USERNAME not set — defaulting to 'admin'.")
    if not settings.auth_password:
        generated = secrets.token_urlsafe(16)
        settings.auth_password = generated
        warnings.warn(
            f"APP_MODE=local: AUTH_PASSWORD not set — generated a dev password: "
            f"{generated}  (set AUTH_PASSWORD to silence this).",
            stacklevel=2,
        )
    _logger.info("HireSense config resolved: APP_MODE=local")
    return settings
```

- [ ] **Step 5: Add the `app_mode` field, make the 3 deps optional, and register the validator**

In the `Settings` class body:

1. Add `app_mode` as the first field under `# Core`:

```python
    # Runtime mode. local = degrade missing LLM/auth config (dev-friendly);
    # production = strict, refuses to boot without every required value.
    app_mode: AppMode = AppMode.LOCAL
```

2. Change the three currently-required fields to optional with empty defaults (the mode validator enforces/fills them). Replace:

```python
    auth_username: str
    auth_password: str
    jwt_secret_key: str
```

with:

```python
    auth_username: str = ""
    auth_password: str = ""
    jwt_secret_key: str = ""
```

and replace `database_url: str` with `database_url: str = ""`, and `llm_api_key: str` with `llm_api_key: str = ""`. Leave their surrounding comments intact.

3. Add an `app_mode` normalizer so `APP_MODE=Production`/`PRODUCTION` still parse, placed near the existing `_reject_placeholder_secrets` validator:

```python
    @field_validator("app_mode", mode="before")
    @classmethod
    def _normalize_app_mode(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value
```

4. Add the mode resolution as the final validator on the class (after all fields, before/after `settings_customise_sources` is fine — put it right before `settings_customise_sources`):

```python
    @model_validator(mode="after")
    def _resolve_mode(self) -> "Settings":
        return _apply_mode(self)
```

- [ ] **Step 6: Run the mode tests to verify they pass**

Run: `uv run python -m pytest tests/unit/config/test_mode.py -v`
Expected: PASS (all 7 tests).

- [ ] **Step 7: Run the existing config + app tests (regression)**

Run: `uv run python -m pytest tests/unit/test_config.py tests/unit/test_app.py -v`
Expected: PASS — existing tests set all required values, so no degradation triggers and behavior is unchanged. The placeholder-rejection test still raises (field validators still run on provided values).

- [ ] **Step 8: Run the full suite + lint**

Run: `uv run python -m pytest -q && uv run ruff check src/hiresense/config.py tests/unit/config/`
Expected: full suite green (one known spurious autopilot-default FAIL may appear from the local `.env` per the repo memory — confirm it is that one and pre-existing, not new). ruff clean on the touched files.

- [ ] **Step 9: Commit**

```bash
git add backend/src/hiresense/config.py backend/tests/unit/config/
git commit -m "feat(config): add APP_MODE with local degradation and production strict validation"
```

---

### Task 2: Split `config.py` into a `config/` package (mechanical, no behavior change)

Turn the single file into a per-concern package of `BaseSettings` mixin groups composed into one flat `Settings`. Pure move — the full suite from Task 1 is the safety net.

**Files:**
- Create: `backend/src/hiresense/config/__init__.py`
- Create: `backend/src/hiresense/config/settings.py`
- Create: `backend/src/hiresense/config/mode.py`
- Create: `backend/src/hiresense/config/sources.py`
- Create: `backend/src/hiresense/config/groups/__init__.py`
- Create: `backend/src/hiresense/config/groups/core.py`
- Create: `backend/src/hiresense/config/groups/observability.py`
- Create: `backend/src/hiresense/config/groups/database.py`
- Create: `backend/src/hiresense/config/groups/llm.py`
- Create: `backend/src/hiresense/config/groups/http.py`
- Create: `backend/src/hiresense/config/groups/ingestion.py`
- Create: `backend/src/hiresense/config/groups/job_sources.py`
- Create: `backend/src/hiresense/config/groups/portals.py`
- Create: `backend/src/hiresense/config/groups/matching.py`
- Create: `backend/src/hiresense/config/groups/preference.py`
- Create: `backend/src/hiresense/config/groups/analytics.py`
- Create: `backend/src/hiresense/config/groups/scheduling.py`
- Create: `backend/src/hiresense/config/groups/outreach.py`
- Create: `backend/src/hiresense/config/groups/applications.py`
- Create: `backend/src/hiresense/config/groups/portfolio.py`
- Delete: `backend/src/hiresense/config.py`
- Create: `backend/tests/unit/config/test_package_layout.py`

**Interfaces:**
- Consumes: `AppMode`, `_apply_mode`, and the field set from Task 1's `config.py`.
- Produces: `hiresense.config.Settings` (unchanged public symbol, flat access), `hiresense.config.AppMode`; `hiresense.config.groups.*Settings` group classes; `hiresense.config.mode.AppMode` / `apply_mode`.

**Field → group mapping (move each field's declaration + comment verbatim):**

- `core.py` → `CoreSettings`: `app_mode`, `app_name`, `app_port`, `debug`, `cors_origins`, `cors_allow_methods`, `cors_allow_headers`, `auth_username`, `auth_password`, `jwt_secret_key`, `auth_role`, `supported_languages`, `default_language`, `max_upload_bytes`, `batch_concurrency`, `event_bus_drain_timeout_seconds`, `rate_limit_enabled`, `rate_limit_max_requests`, `rate_limit_window_seconds`. Also move `_PLACEHOLDER_SECRETS`, the `_reject_placeholder_secrets` validator, and the `_normalize_app_mode` validator here.
- `observability.py` → `ObservabilitySettings`: `otel_enabled`, `otel_service_name`, `otel_exporter_otlp_endpoint`, `deployment_environment`, `log_level`, `log_format`, `otel_traces_sampler_ratio`, `otel_exporter_insecure`.
- `database.py` → `DatabaseSettings`: `database_url`, `db_pool_size`, `db_max_overflow`, `db_pool_pre_ping`, `db_pool_recycle_seconds`, `vector_store_provider`.
- `llm.py` → `LLMSettings`: `llm_provider`, `llm_api_key`, `llm_model`, `llm_settings_encryption_key`, `embedding_model`, `embedding_device`, `embedding_dim`, `match_quick_model`, `match_deep_model`, `match_quick_batch_size`, `match_quick_job_char_limit`, `match_deep_job_char_limit`.
- `http.py` → `HttpSettings`: `http_timeout`, `http_max_retries`, `http_retry_base_delay`, `http_retry_status_codes`.
- `ingestion.py` → `IngestionSettings`: `ingestion_schedule`, `enabled_job_sources`, `csv_import_dir`, `ingestion_min_match_score`, `ingestion_max_page_size`, `ingestion_source_champions_per_source`, `ingestion_max_job_age_days`, `ingestion_cooldown_seconds`, `ingestion_job_retention_days`, `job_closure_miss_threshold`, `job_revalidation_interval_hours`, `job_revalidation_batch`, `job_revalidation_concurrency`, `job_revalidation_delay`, `job_revalidation_user_agent`, `job_closed_markers`.
- `job_sources.py` → `JobSourcesSettings`: `remotive_api_url`, `remoteok_api_url`, `jobicy_api_url`, `himalayas_api_url`, `hn_algolia_api_url`, `weworkremotely_rss_url`, `getonboard_api_url`, `getonboard_categories`, `linkedin_jobs_url`, `linkedin_detail_concurrency`, `linkedin_detail_delay`, `arbeitnow_api_url`, `themuse_api_url`, `themuse_categories`, `themuse_api_key`, `adzuna_api_url`, `adzuna_app_id`, `adzuna_app_key`, `adzuna_countries`, `adzuna_query`.
- `portals.py` → `PortalsSettings`: `portals_config_path`, `portal_scan_timeout`, `greenhouse_api_url`, `lever_api_url`, `ashby_api_url`, `workable_api_url`, `smartrecruiters_api_url`, `recruitee_api_url`.
- `matching.py` → `MatchingSettings`: `prerank_weight_skill`, `prerank_weight_semantic`, `prerank_top_k_cap`, `semantic_job_cache_size`, `semantic_profile_cache_size`, `weight_semantic`, `weight_skill_match`, `weight_experience`, `weight_language`, `weight_seniority`, `weight_compensation`, `weight_growth`, `weight_culture`, `weight_application`, `weight_interview`.
- `preference.py` → `PreferenceSettings`: all `preference_*` fields.
- `analytics.py` → `AnalyticsSettings`: `analytics_cache_ttl_seconds`, `analytics_target_salary_top_k`, `analytics_target_salary_min_sample`, `analytics_focus_fresh_days`, `analytics_corpus_sample_cap`, `admin_usage_recent_limit`.
- `scheduling.py` → `SchedulingSettings`: `autohunt_top_n`, `autohunt_min_score`, `autohunt_initial_lookback_days`, `autohunt_digest_retention_days`, `autohunt_schedule`, `autopilot_pipeline_enabled`, `autopilot_pipeline_top_n`, `autopilot_pipeline_schedule`, `scheduler_enabled`, `scheduler_run_retention_days`.
- `outreach.py` → `OutreachSettings`: `outreach_style_guide_path`, `outreach_followup_cadence_days`, `outreach_max_chars`, `outreach_followup_schedule`, `smtp_host`, `smtp_port`, `smtp_username`, `smtp_password`, `smtp_use_tls`, `outreach_from_email`, `notification_email`, `notification_from_email`, `imap_host`, `imap_port`, `imap_username`, `imap_password`, `imap_folder`, `imap_use_ssl`, `inbox_scan_schedule`, `inbox_signal_match_min_confidence`.
- `applications.py` → `ApplicationsSettings`: `latex_compiler`, `latex_timeout_seconds`, `cv_directory`.
- `portfolio.py` → `PortfolioSettings`: all `portfolio_*` fields.

> Every group class is a `BaseSettings` subclass that declares ONLY its fields (and, for core, its validators). Groups define NO `model_config` and NO `settings_customise_sources` — those live only on the composed `Settings`. `_COMMA_FIELDS` (the comma-split set) stays with the sources in `sources.py`.

- [ ] **Step 1: Write the package-layout test (failing)**

Create `backend/tests/unit/config/test_package_layout.py`:

```python
import pytest


def _set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")


def test_public_symbols_importable(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    from hiresense.config import AppMode, Settings

    settings = Settings()
    # Flat access across several groups still works.
    assert settings.otel_enabled is True
    assert settings.database_url.startswith("postgresql")
    assert settings.weight_semantic == 15
    assert settings.portfolio_ref_prefix == "hiresense"
    assert settings.app_mode is AppMode.LOCAL


def test_groups_are_importable_from_package() -> None:
    from hiresense.config.groups import (
        CoreSettings,
        DatabaseSettings,
        LLMSettings,
        ObservabilitySettings,
        PortfolioSettings,
    )

    assert CoreSettings is not None
    assert DatabaseSettings is not None
    assert LLMSettings is not None
    assert ObservabilitySettings is not None
    assert PortfolioSettings is not None


def test_no_duplicate_field_across_groups() -> None:
    # Guards the mixin composition: two groups declaring the same field would
    # silently shadow. Assert the union has no collisions.
    from hiresense.config import groups as g

    seen: dict[str, str] = {}
    group_classes = [
        g.CoreSettings, g.ObservabilitySettings, g.DatabaseSettings, g.LLMSettings,
        g.HttpSettings, g.IngestionSettings, g.JobSourcesSettings, g.PortalsSettings,
        g.MatchingSettings, g.PreferenceSettings, g.AnalyticsSettings,
        g.SchedulingSettings, g.OutreachSettings, g.ApplicationsSettings,
        g.PortfolioSettings,
    ]
    for cls in group_classes:
        for field in cls.model_fields:
            assert field not in seen, f"{field} declared in both {seen[field]} and {cls.__name__}"
            seen[field] = cls.__name__
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run python -m pytest tests/unit/config/test_package_layout.py -v`
Expected: FAIL — `hiresense.config.groups` does not exist yet.

- [ ] **Step 3: Create `config/sources.py`**

Move `_CommaSeparatedMixin`, `_COMMA_FIELDS`, `_CommaSeparatedEnvSource`, `_CommaSeparatedDotEnvSource` from the old `config.py` verbatim:

```python
from typing import Any, ClassVar

from pydantic_settings import DotEnvSettingsSource, EnvSettingsSource


class _CommaSeparatedMixin:
    """Mixin that splits comma-separated strings into lists for known fields."""

    _COMMA_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "enabled_job_sources",
            "supported_languages",
            "getonboard_categories",
            "job_closed_markers",
            "http_retry_status_codes",
            "cors_allow_methods",
            "cors_allow_headers",
            "portfolio_sources",
            "themuse_categories",
            "adzuna_countries",
        }
    )

    def prepare_field_value(
        self, field_name: str, field: Any, value: Any, value_is_complex: bool
    ) -> Any:
        if field_name in self._COMMA_FIELDS and isinstance(value, str):
            return [s.strip() for s in value.split(",") if s.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class _CommaSeparatedEnvSource(_CommaSeparatedMixin, EnvSettingsSource):
    pass


class _CommaSeparatedDotEnvSource(_CommaSeparatedMixin, DotEnvSettingsSource):
    pass
```

> Note: `themuse_categories` and `adzuna_countries` are list-typed and were previously NOT in `_COMMA_FIELDS` (they parsed via JSON). Adding them here makes `THEMUSE_CATEGORIES=a,b` work as comma-separated too — a benign superset. If you prefer strict parity with the old file, omit those two lines. Keep the decision consistent with Step: leave them IN (matches the "more flexibility" goal).

- [ ] **Step 4: Create `config/mode.py`**

Move `AppMode`, `_ALWAYS_REQUIRED`, `_PRODUCTION_REQUIRED`, `_missing`, and `_apply_mode` from Task 1's `config.py`. Rename `_apply_mode` to a public `apply_mode` (it's now cross-module):

```python
from __future__ import annotations

import logging
import secrets
import warnings
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hiresense.config.settings import Settings

_logger = logging.getLogger(__name__)


class AppMode(str, Enum):
    """Runtime mode. LOCAL degrades missing LLM/auth config; PRODUCTION is strict."""

    LOCAL = "local"
    PRODUCTION = "production"


_ALWAYS_REQUIRED: tuple[tuple[str, str], ...] = (("DATABASE_URL", "database_url"),)
_PRODUCTION_REQUIRED: tuple[tuple[str, str], ...] = (
    ("LLM_API_KEY", "llm_api_key"),
    ("AUTH_USERNAME", "auth_username"),
    ("AUTH_PASSWORD", "auth_password"),
    ("JWT_SECRET_KEY", "jwt_secret_key"),
)


def _missing(settings: "Settings", required: tuple[tuple[str, str], ...]) -> list[str]:
    return [env for env, attr in required if not getattr(settings, attr)]


def apply_mode(settings: "Settings") -> "Settings":
    """Resolve APP_MODE: raise an aggregated error for missing required config, or
    degrade blanks in local mode. Mutates and returns the settings instance."""
    # (body identical to Task 1's _apply_mode)
```

Copy the `apply_mode` body verbatim from Task 1's `_apply_mode`.

- [ ] **Step 5: Create the 15 group files under `config/groups/`**

For each file, define one `BaseSettings` subclass with the fields listed in the mapping above, moved verbatim (declaration + comment) from Task 1's `config.py`. Template (example for `observability.py`):

```python
from pydantic_settings import BaseSettings


class ObservabilitySettings(BaseSettings):
    """OpenTelemetry + logging configuration."""

    # (move the otel_* / log_* / deployment_environment fields here verbatim)
```

`core.py` additionally imports `AppMode` from `hiresense.config.mode`, declares `app_mode: AppMode = AppMode.LOCAL`, and carries `_PLACEHOLDER_SECRETS`, `_reject_placeholder_secrets`, and `_normalize_app_mode`.

- [ ] **Step 6: Create `config/groups/__init__.py`**

Re-export every group (package-level import per the repo's import-style rule):

```python
from hiresense.config.groups.analytics import AnalyticsSettings
from hiresense.config.groups.applications import ApplicationsSettings
from hiresense.config.groups.core import CoreSettings
from hiresense.config.groups.database import DatabaseSettings
from hiresense.config.groups.http import HttpSettings
from hiresense.config.groups.ingestion import IngestionSettings
from hiresense.config.groups.job_sources import JobSourcesSettings
from hiresense.config.groups.llm import LLMSettings
from hiresense.config.groups.matching import MatchingSettings
from hiresense.config.groups.observability import ObservabilitySettings
from hiresense.config.groups.outreach import OutreachSettings
from hiresense.config.groups.portals import PortalsSettings
from hiresense.config.groups.portfolio import PortfolioSettings
from hiresense.config.groups.preference import PreferenceSettings
from hiresense.config.groups.scheduling import SchedulingSettings

__all__ = [
    "AnalyticsSettings", "ApplicationsSettings", "CoreSettings", "DatabaseSettings",
    "HttpSettings", "IngestionSettings", "JobSourcesSettings", "LLMSettings",
    "MatchingSettings", "ObservabilitySettings", "OutreachSettings", "PortalsSettings",
    "PortfolioSettings", "PreferenceSettings", "SchedulingSettings",
]
```

- [ ] **Step 7: Create `config/settings.py` (the composition point)**

```python
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from hiresense.config.groups import (
    AnalyticsSettings,
    ApplicationsSettings,
    CoreSettings,
    DatabaseSettings,
    HttpSettings,
    IngestionSettings,
    JobSourcesSettings,
    LLMSettings,
    MatchingSettings,
    ObservabilitySettings,
    OutreachSettings,
    PortalsSettings,
    PortfolioSettings,
    PreferenceSettings,
    SchedulingSettings,
)
from hiresense.config.mode import apply_mode
from hiresense.config.sources import (
    _CommaSeparatedDotEnvSource,
    _CommaSeparatedEnvSource,
)


class Settings(
    CoreSettings,
    ObservabilitySettings,
    DatabaseSettings,
    LLMSettings,
    HttpSettings,
    IngestionSettings,
    JobSourcesSettings,
    PortalsSettings,
    MatchingSettings,
    PreferenceSettings,
    AnalyticsSettings,
    SchedulingSettings,
    OutreachSettings,
    ApplicationsSettings,
    PortfolioSettings,
):
    """Composed application settings — flat attribute access over all groups."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @model_validator(mode="after")
    def _resolve_mode(self) -> "Settings":
        return apply_mode(self)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        return (
            init_settings,
            _CommaSeparatedEnvSource(settings_cls),
            _CommaSeparatedDotEnvSource(settings_cls),
            file_secret_settings,
        )
```

- [ ] **Step 8: Create `config/__init__.py`**

```python
from hiresense.config.mode import AppMode
from hiresense.config.settings import Settings

__all__ = ["Settings", "AppMode"]
```

- [ ] **Step 9: Delete the old single-file config**

```bash
git rm backend/src/hiresense/config.py
```

- [ ] **Step 10: Run the layout + mode tests**

Run: `uv run python -m pytest tests/unit/config/ -v`
Expected: PASS — public symbols import, groups import, no duplicate fields, all Task 1 mode tests still green.

- [ ] **Step 11: Run the FULL suite + lint (regression across all 69 read-sites)**

Run: `uv run python -m pytest -q && uv run ruff check src/hiresense/config tests/unit/config`
Expected: full suite green (same known autopilot-default caveat as Task 1). ruff clean. If any `ImportError: cannot import name ... from hiresense.config` appears, a symbol other than `Settings`/`AppMode` was imported from the old module — check the 4 importers (`bootstrap/identity.py`, `bootstrap/shared_infra.py`, `bootstrap/tracked_factory.py`, `main.py`); they import only `Settings`, so no change is expected.

- [ ] **Step 12: Commit**

```bash
git add backend/src/hiresense/config backend/tests/unit/config
git rm --cached backend/src/hiresense/config.py 2>/dev/null || true
git commit -m "refactor(config): split config.py into a per-concern config/ package"
```

---

### Task 3: Wire docker-compose, `.env.example`, and docs

Make the running surfaces reflect the new switch.

**Files:**
- Modify: `docker-compose.yml` (app service `environment:` block)
- Modify: `backend/.env.example`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `APP_MODE` from Task 1/2.

- [ ] **Step 1: Set production mode in docker-compose**

In `docker-compose.yml`, under the `app` service `environment:` block (currently lines ~45-52), add `APP_MODE: production` as the first entry:

```yaml
    environment:
      # Compose is a real deployment: fail loudly on missing config.
      APP_MODE: production
      # In-network overrides: .env is host-oriented (localhost); inside the
      # compose network the app must address services by name.
      DATABASE_URL: postgresql+asyncpg://hiresense:hiresense@db:5432/hiresense
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-lgtm:4317
      LOG_FORMAT: json
      SCHEDULER_ENABLED: "true"
```

- [ ] **Step 2: Add `APP_MODE` + contract to `.env.example`**

At the very top of `backend/.env.example`, before `# === Core ===`, add:

```bash
# === Runtime mode ===
# local      → dev-friendly: blank LLM_API_KEY runs matching heuristic-only;
#              blank AUTH_*/JWT_SECRET_KEY auto-generate an EPHEMERAL dev secret
#              (tokens reset on restart) with a startup warning. DATABASE_URL is
#              STILL required (pgvector ANN needs Postgres — no SQLite fallback).
# production → strict: refuses to boot unless DATABASE_URL, LLM_API_KEY, and the
#              AUTH_USERNAME/AUTH_PASSWORD/JWT_SECRET_KEY trio are all set. Missing
#              values fail at startup with a single aggregated error.
# Any individual variable below always overrides its mode default.
APP_MODE=local

```

Then update the `# === Auth ===` block comment to note the local-mode behavior (blank → ephemeral dev secret), keeping the placeholder-rejection note for production users.

- [ ] **Step 3: Add a "Configuration & runtime modes" subsection to `CLAUDE.md`**

Under the existing config note (the paragraph ending "…new settings must also be added to `.env.example` with a comment."), append:

```markdown

#### Runtime modes (`APP_MODE`)

`APP_MODE` (in `config/mode.py`, default `local`) sets a bundle of defaults;
any individual env var overrides its mode default.

- **`local`** — blank `LLM_API_KEY` → heuristic-only matching (LLM features return
  a not-configured state); blank auth secrets → an ephemeral per-boot dev secret +
  default creds with a loud startup warning. `DATABASE_URL` (Postgres) is still
  required — there is no SQLite fallback (pgvector ANN needs Postgres).
- **`production`** — strict: missing `DATABASE_URL` / `LLM_API_KEY` / auth trio fail
  at startup with one aggregated error. `docker-compose.yml` sets `APP_MODE=production`.

Config is a `config/` package: per-concern `BaseSettings` groups under
`config/groups/` composed into one flat `Settings` in `config/settings.py`
(flat `settings.otel_enabled` access preserved). Add new fields to the matching
group and re-export nothing extra — `Settings` inherits every group's fields.
```

- [ ] **Step 4: Verify the surfaces**

Run: `grep -n "APP_MODE" docker-compose.yml backend/.env.example CLAUDE.md`
Expected: `APP_MODE: production` in compose, `APP_MODE=local` in `.env.example`, and the modes subsection in `CLAUDE.md`.

- [ ] **Step 5: Sanity-boot the app in production mode with a missing value (manual verify)**

Run (from `backend/`):
`APP_MODE=production AUTH_PASSWORD= uv run python -c "from hiresense.config import Settings; Settings()"`
(PowerShell: `$env:APP_MODE="production"; $env:AUTH_PASSWORD=""; uv run python -c "from hiresense.config import Settings; Settings()"`)
Expected: exits with the aggregated `ValueError` naming `AUTH_PASSWORD` (and any other blanks). Confirms strict mode fails loudly. Unset the vars afterward.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml backend/.env.example CLAUDE.md
git commit -m "docs(config): document APP_MODE and set production mode in docker-compose"
```

---

## Self-Review

**Spec coverage:**
- APP_MODE switch, default local → Task 1 (field + validator), Task 3 (compose/docs). ✓
- DATABASE_URL required both modes, no SQLite fallback → Task 1 `_ALWAYS_REQUIRED`, tests, `.env.example` note. ✓
- LLM blank → heuristic-only → Task 1 (leaves `llm_api_key` blank + info log; factory already returns None). ✓
- Auth blank → ephemeral per-boot secret + warn → Task 1 (`secrets.token_urlsafe`, `warnings.warn`), test `test_local_ephemeral_jwt_differs_across_builds`. ✓
- Production aggregated error naming all missing → Task 1, test `test_production_missing_required_lists_all`. ✓
- Env override wins → Task 1, test `test_env_override_wins_in_local`. ✓
- Config split into per-concern package, flat access preserved → Task 2, tests `test_public_symbols_importable` / `test_no_duplicate_field_across_groups`. ✓
- Docs + compose → Task 3. ✓

**Placeholder scan:** No TBD/TODO. Group-file bodies say "move verbatim from Task 1's config.py" with an exhaustive per-file field list — a mechanical move, not a vague instruction. `apply_mode` body is defined in full in Task 1 and referenced by name in Task 2 Step 4. No unresolved symbols.

**Type consistency:** `AppMode` (str Enum) defined once (Task 1), moved to `config/mode.py` (Task 2). `_apply_mode` (Task 1) → `apply_mode` (Task 2, rename is explicit and the only caller is the `_resolve_mode` validator, updated in Task 2 Step 7). `Settings` and group class names match between the mapping, `groups/__init__.py`, `settings.py`, and the tests. `_COMMA_FIELDS` gains `themuse_categories`/`adzuna_countries` (called out explicitly in Task 2 Step 3).
