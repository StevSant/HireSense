# Job Sources Expansion — Implementation Plan

**Date:** 2026-07-24  
**Spec:** `docs/superpowers/specs/2026-07-24-job-sources-expansion-design.md`

## Phase 1 — Domain & shared infrastructure

1. Add `SourceCapabilities` + `SOURCE_CAPABILITY_REGISTRY` in
   `ingestion/domain/source_capabilities.py`; re-export from `domain/__init__.py`.
2. Add `SourceHealth` / `SourceHealthTracker` in
   `ingestion/domain/source_health.py`.
3. Extend `NormalizedJob` with `employment_type`, `equity_range`, `source_metadata`.
4. Extend ORM `IngestedJob` + repository map/upsert/content_hash.
5. Alembic migration for new columns.
6. Improve `cross_source_deduplicator` with source tiers + provenance merge helper.
7. Wire health updates into `IngestionOrchestrator.run`.

## Phase 2 — Adapters & normalizers

| Source | Files |
|---|---|
| Shared JSONL/CSV import helper | `adapters/_jsonl_import.py`, `normalizers/_import_fields.py` |
| Dice MCP | `adapters/dice.py`, `normalizers/dice_normalizer.py`, optional `_mcp_client.py` |
| CrunchBoard RSS | `adapters/crunchboard.py`, `normalizers/crunchboard_normalizer.py` |
| YC Jobs | `adapters/yc_jobs.py`, `normalizers/yc_jobs_normalizer.py` |
| Indeed import | `adapters/indeed.py`, `normalizers/indeed_normalizer.py` |
| Wellfound import | `adapters/wellfound.py`, `normalizers/wellfound_normalizer.py` |
| Glassdoor import | `adapters/glassdoor.py`, `normalizers/glassdoor_normalizer.py` |
| Monster import | `adapters/monster.py`, `normalizers/monster_normalizer.py` |

Update `adapters/__init__.py` and `normalizers/__init__.py`.

## Phase 3 — Config & bootstrap

1. `config/groups/job_sources.py` — URLs, limits, queries, import filenames, YC roles.
2. `config/groups/ingestion.py` — extend default `enabled_job_sources` with
   `dice`, `crunchboard`, `yc_jobs` (import sources opt-in via env).
3. `bootstrap/ingestion.py` — register adapters/normalizers; exclude import sources
   without files from hard failures; revalidation exclusions for pure-manual empty
   sources as needed.
4. `.env.example` comments for every knob.

## Phase 4 — API

1. `GET /ingestion/sources` → capabilities + enabled.
2. `GET /ingestion/sources/health` → health snapshot.
3. Ensure job list serialization includes new fields (Pydantic model already returned).

## Phase 5 — Frontend

1. Models: extend `NormalizedJob`; add `SourceCapability` / health models.
2. Service methods for sources + health.
3. Discover: dynamic board sources; badges; optional health notice; equity /
   employment_type / metadata display on cards/detail.
4. SCSS badge colors for new sources.
5. Unit tests for filters/badges/metadata.

## Phase 6 — Tests & docs

1. Unit tests per adapter/normalizer + registry + health + dedup + routes.
2. Update README supported-sources list.
3. Short `docs/` troubleshooting note or README subsection.
4. Run ruff, pytest, frontend lint/test/build.

## Migration

- One Alembic revision: add `employment_type`, `equity_range`, `source_metadata`
  (JSON, server default `{}`).

## Rollout checklist

- [ ] Spec + plan committed
- [ ] Automated sources green in unit tests without network
- [ ] Import sources documented with sample JSONL schemas
- [ ] Quality gates pass
- [ ] PR opened
