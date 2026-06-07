# GitHub Issue Backlog — Design & Drafts

**Date:** 2026-06-07
**Status:** Draft — pending review before creation on GitHub
**Repo:** `StevSant/HireSense`

## Goal

Seed the repo's (currently empty) issue tracker with a curated backlog (~20 top-level issues + sub-issues) combining: designed-but-unbuilt features from `docs/superpowers/specs`, known bugs, and audit findings from backend + frontend sweeps. Every finding below was verified against actual code; speculative or already-built items were dropped during curation.

## Dropped findings (verified as false positives)

- *Preference feedback frontend missing* — `app-feedback-controls` is wired in both the list rows (`ingestion.component.html:196`) and detail panel, and `app-preference-tuning` is mounted in the toolbar. Built.
- *Job lifecycle frontend missing* — `status` field exists on `normalized-job.model.ts:26`, closed badge + `include_closed` toggle are implemented. Built.
- *Analytics/observability/portal-scanning "verify completeness"* — too vague to be actionable issues; no concrete gap found.

## Taxonomy

### Labels (to create)

| Label | Color | Purpose |
|---|---|---|
| `tech-debt` | `#c2410c` | Refactors, robustness, convention violations |
| `testing` | `#0e8a16` | Test coverage and test infrastructure |
| `epic` | `#3e4b9e` | Parent issue with sub-issues |
| `priority: P1` | `#b60205` | High value / risky if unfixed |
| `priority: P2` | `#fbca04` | Should do |
| `priority: P3` | `#c5def5` | Nice to have |
| `area: backend` | `#1d76db` | Backend work |
| `area: frontend` | `#e99695` | Frontend work |
| `module: ingestion` | `#bfd4f2` | Bounded context |
| `module: outreach` | `#bfd4f2` | Bounded context |
| `module: autohunt` | `#bfd4f2` | Bounded context |
| `module: preference` | `#bfd4f2` | Bounded context |
| `module: admin` | `#bfd4f2` | Bounded context |
| `module: identity` | `#bfd4f2` | Bounded context |
| `module: analytics` | `#bfd4f2` | Bounded context |

Existing defaults reused: `bug`, `enhancement`, `documentation`, `good first issue`.

### Milestones (to create)

1. **Feature completion** — designed features needing UI or next phases
2. **Stability & robustness** — bugs and risky tech debt
3. **Quality & conventions** — testing, conventions, docs

### Conventions

- Titles in conventional-commit style: `type(scope): description`
- Bodies: Context / Proposal / Acceptance criteria / References
- Big features = parent issue (`epic`) + native GitHub sub-issues
- `.github/ISSUE_TEMPLATE/` forms committed so future issues keep this shape

---

## Issue drafts

### Milestone: Feature completion

#### 1. [EPIC] feat(outreach): frontend for the outreach module
`epic` `enhancement` `area: frontend` `module: outreach` `priority: P1`

**Context:** The outreach backend is complete and wired (`POST /outreach/generate`, `POST /outreach/record`, `GET /outreach/events`, nudges via `due_followups`) but has zero frontend — no page, no service, no route.
**Proposal:** Build the outreach UI following the per-domain conventions (service wrapper in `core/services`, models in `.model.ts`, standalone signal components under `pages/outreach/`).
**Acceptance criteria:** Sub-issues below complete; outreach reachable from sidebar.
**References:** `docs/superpowers/specs/2026-05-31-outreach-networking-design.md`, `backend/src/hiresense/outreach/api/routes.py`

- **1a. feat(outreach): frontend service + models** — `OutreachService` wrapping the four endpoints; `outreach-event.model.ts` etc. mirroring backend schemas. `area: frontend` `module: outreach`
- **1b. feat(outreach): outreach page — generate + record flows** — form to generate a message for a job/contact (kind, style), edit, then record the send; list of past events. `area: frontend` `module: outreach`
- **1c. feat(outreach): follow-up nudges view** — surface due follow-ups (`due_followups`) with quick "record follow-up" action; badge count in sidebar nav. `area: frontend` `module: outreach`

#### 2. feat(autohunt): frontend for auto-hunt digests
`enhancement` `area: frontend` `module: autohunt` `priority: P2`

**Context:** AutoHunt backend exposes `POST /autohunt/run`, `GET /autohunt/digests`, `GET /autohunt/digests/latest` but there is no frontend page or service.
**Proposal:** Digest list + latest-digest view (matched jobs with scores), manual "run now" trigger, per conventions.
**Acceptance criteria:** Page routed and in sidebar; digests render with links to job detail; run trigger shows progress/result; specs for the service.
**References:** `docs/superpowers/specs/2026-05-31-proactive-auto-hunt-design.md`, `backend/src/hiresense/autohunt/api/routes.py`

#### 3. [EPIC] feat(preference): learning loop phase 2 — implicit signals, weight nudging, explanation v2
`epic` `enhancement` `area: backend` `module: preference` `priority: P2`

**Context:** Phase 1 (taste vector + explicit feedback) shipped. Phase 2 design exists but is unimplemented.
**References:** `docs/superpowers/specs/2026-05-31-preference-learning-loop-phase2-design.md`, `docs/superpowers/specs/2026-05-31-preference-weight-nudging-concept.md`, `docs/superpowers/plans/2026-05-31-preference-phase2-implicit-and-explanation.md`

- **3a. feat(preference): implicit signals from tracking status changes** — publish/subscribe `TrackingStatusChangedEvent`; record implicit feedback (applied/interview/offer = positive). `area: backend` `module: preference`
- **3b. feat(preference): dimension weight nudging** — needs a brainstorm first per the concept doc (where dimension scores are cached, nudge math, override application in composite scoring). `area: backend` `module: preference`
- **3c. feat(preference): LLM-phrased explanation v2** — richer "why this score" explanations. `area: backend` `module: preference`

#### 4. feat(identity): real admin role + account settings UI
`enhancement` `area: backend` `area: frontend` `module: identity` `priority: P2`

**Context:** `frontend/src/app/core/guards/admin.guard.ts:5` has `TODO(#19): gate on real admin role once the backend exposes one` (the referenced issue never existed). Identity backend only exposes `POST /auth/login`; no user/account UI.
**Proposal:** Backend exposes role on the auth token/user endpoint; admin guard checks it; minimal account settings page.
**Acceptance criteria:** Admin routes blocked for non-admin users end-to-end; TODO removed and pointed at this issue.
**References:** `frontend/src/app/core/guards/admin.guard.ts:5`, `backend/src/hiresense/identity/api/routes.py`

### Milestone: Stability & robustness

#### 5. bug(ingestion): min_score gate culls jobs before page-level semantic scoring
`bug` `area: backend` `module: ingestion` `priority: P1`

**Context:** In `ingestion/api/routes.py`, `filter_and_paginate` applies `min_score` (line 223) before the page-level semantic scoring pass (lines 229–244). When the pre-ranker is passthrough (no vector store / empty profile) or scores aren't yet persisted, jobs are culled on their skill-only score. Verbose-tag sources (e.g., getonboard, 15–30 tags) suffer tag dilution and get unfairly filtered before semantic scoring can rescue them.
**Proposal:** Apply the min_score gate after semantic scores exist for the candidate set, or exempt jobs with `semantic_score is None` from the gate.
**Acceptance criteria:** A getonboard-style job with low skill-overlap but high semantic fit survives the first request after restart; regression test.
**References:** `backend/src/hiresense/ingestion/api/routes.py:196-244`

#### 6. tech-debt(infrastructure): add missing ORM imports to registry.py
`tech-debt` `area: backend` `priority: P1` `good first issue`

**Context:** `infrastructure/registry.py` must import every ORM class or Alembic `--autogenerate` silently misses tables. Missing: `DigestOrm` (autohunt), `OutreachEventOrm` (outreach), `FeedbackSignalOrm` + `PreferenceModelOrm` (preference).
**Acceptance criteria:** All four imported; an autogenerate run produces an empty diff; consider a test asserting every `*Orm` subclass of `Base` is reachable via the registry module.
**References:** `backend/src/hiresense/infrastructure/registry.py`

#### 7. tech-debt(ingestion): retry/backoff for external HTTP adapters
`tech-debt` `area: backend` `module: ingestion` `priority: P2`

**Context:** All job-source adapters do single un-retried `await self._http.get(...)`; the shared `httpx.AsyncClient` (`main.py:48`) sets only `timeout` — no transport retries, no backoff. Transient 5xx/429/timeouts silently lose jobs for that cycle.
**Proposal:** Configure `httpx.AsyncHTTPTransport(retries=...)` plus a small backoff helper for 429/5xx in the adapter base; retry counts/backoff via `config.py` + `.env.example`.
**Acceptance criteria:** Transient failure of one fetch retries before giving up; tests with a flaky mock transport.
**References:** `backend/src/hiresense/main.py:48`, `backend/src/hiresense/ingestion/adapters/`

#### 8. tech-debt(frontend): standardize subscription teardown with DestroyRef
`tech-debt` `area: frontend` `priority: P2`

**Context:** 9 page components subscribe to HTTP observables with no teardown (admin-llm-settings, admin-usage, applications, interview, matching, profile, tracking, …). HTTP observables complete on response so these aren't classic leaks, but in-flight responses after navigation write to destroyed-component signals and any future long-lived streams would leak.
**Proposal:** Adopt `inject(DestroyRef)` + `.pipe(takeUntilDestroyed(this.destroyRef))` as the standard pattern; document it in `agent-os/standards/frontend/`.
**Acceptance criteria:** All listed components migrated; standard documented.
**References:** e.g. `frontend/src/app/pages/admin/admin-usage.component.ts:58`, `frontend/src/app/pages/matching/matching.component.ts:57-79`

#### 9. tech-debt(adapters): event bus should log handler exceptions
`tech-debt` `area: backend` `priority: P3` `good first issue`

**Context:** `adapters/event_bus/in_memory_bus.py:58` catches all handler exceptions, records span status + metric, but never logs which handler failed with what error — silent crashes are hard to debug.
**Proposal:** `logger.exception(...)` with handler + event names before recording the metric.
**References:** `backend/src/hiresense/adapters/event_bus/in_memory_bus.py:58`

#### 10. tech-debt(ingestion): clean up orphaned vector embeddings after pruning
`tech-debt` `area: backend` `module: ingestion` `priority: P3`

**Context:** `prune_older_than()` deletes jobs; vector eviction is best-effort with no FK cascade (acknowledged in migration `014_create_vector_embeddings.py:36`). Orphans accumulate and waste disk; harmless otherwise.
**Proposal:** Periodic cleanup that deletes `vector_embeddings` rows with no matching job (piggyback on the prune call), or add the FK cascade.
**References:** `backend/src/hiresense/ingestion/infrastructure/jobs_repository.py:135-151`, `backend/alembic/versions/014_create_vector_embeddings.py:36`

#### 11. bug(identity): login loading state never cleared on success
`bug` `area: frontend` `module: identity` `priority: P3` `good first issue`

**Context:** `login.component.ts:21-34` navigates away in `next` without `this.loading.set(false)`; spinner persists until navigation completes.
**References:** `frontend/src/app/pages/login/login.component.ts:21-34`

### Milestone: Quality & conventions

#### 12. [EPIC] testing(frontend): spec coverage for untested page components
`epic` `testing` `area: frontend` `priority: P2`

**Context:** Only 7 of 35 page components have specs (analytics charts + preference controls). 28 components are untested.

- **12a. testing(frontend): admin specs** — admin-llm-settings, admin-usage. `testing` `module: admin`
- **12b. testing(frontend): applications + tracking specs** — applications, application-detail, 4 tab components, tracking. `testing`
- **12c. testing(frontend): ingestion component specs** — job-filters, pagination, deep-analysis, job-detail-panel. `testing` `module: ingestion`
- **12d. testing(frontend): remaining page specs** — dashboard, login, matching, optimization, profile, interview, applications-prep-list. `testing`

#### 13. testing(ingestion): pgvector ANN validation strategy
`testing` `area: backend` `module: ingestion` `priority: P2`

**Context:** The suite runs against SQLite; pgvector ANN search has no automated validation at all — only manual checks against `docker compose up db`.
**Proposal:** Opt-in integration test marker (`pytest -m pgvector`) that runs against the compose DB, exercising upsert → ANN query → eviction; document the workflow in CLAUDE.md/ARCHITECTURE.md.
**References:** `backend/ARCHITECTURE.md` (ANN validation note), `backend/tests/unit/test_pgvector_adapter.py`

#### 14. tech-debt(admin): align admin module with hexagonal rules
`tech-debt` `area: backend` `module: admin` `priority: P3`

**Context:** Two known deviations: (1) `llm_factory.py` / `llm_test_runner.py` import langchain from `domain/` (documented follow-up in ARCHITECTURE.md); (2) `usage_aggregator.py:12` imports infrastructure types under `TYPE_CHECKING` — types should live in the port or domain.
**Acceptance criteria:** LangChain-touching code moved to `infrastructure/`; aggregator typed against port/domain types; ARCHITECTURE.md follow-up note removed.
**References:** `backend/src/hiresense/admin/domain/llm_factory.py`, `backend/src/hiresense/admin/domain/usage_aggregator.py:12`

#### 15. chore(config): move Remotive/RemoteOK base URLs into config
`tech-debt` `area: backend` `module: ingestion` `priority: P3` `good first issue`

**Context:** Other sources read base URLs from `config.py`; `RemotiveAdapter` and `RemoteOKAdapter` hardcode theirs, violating the no-hardcoded-values rule and blocking test redirection.
**Acceptance criteria:** `REMOTIVE_API_URL` / `REMOTEOK_API_URL` in `config.py`, `.env`, `.env.example` (with comments); adapters read from settings.
**References:** `backend/src/hiresense/ingestion/adapters/remotive.py:8`, `.../remoteok.py:8`

#### 16. tech-debt(cross-cutting): bound large result-set queries
`tech-debt` `area: backend` `priority: P3`

**Context:** `llm_usage_log_repository.list_recent()` and `analytics corpus_repository.open_skill_lists()` load unbounded result sets into memory; fine today, degrades as the corpus grows.
**Proposal:** Limits/pagination on `list_recent`; cap or stream `open_skill_lists` (config-driven threshold).
**References:** `backend/src/hiresense/admin/infrastructure/llm_usage_log_repository.py:87-91`, `backend/src/hiresense/analytics/infrastructure/corpus_repository.py:20`

#### 17. tech-debt(frontend): convention cleanup — inline interfaces, hardcoded suggestions, chart magic numbers
`tech-debt` `area: frontend` `priority: P3` `good first issue`

**Context:** Bundled small violations: `ExtraParam`/`OverrideDraft` defined inline in `admin-llm-settings.component.ts:10-22` (belong in `.model.ts`); LLM provider/model suggestions hardcoded (`admin-llm-settings.component.ts:27-32`) — fetch from backend or move to `core/constants/`; bar-chart layout magic numbers (`admin-usage.component.ts:128-143`) → named constants/inputs.
**Acceptance criteria:** All three cleaned up per `agent-os/standards/frontend/`.

#### 18. tech-debt(frontend): error logging strategy
`tech-debt` `area: frontend` `priority: P3`

**Context:** HTTP errors only land in component UI signals (e.g., `tracking.component.ts:71`); nothing reaches the console or any tracker, so field debugging is blind.
**Proposal:** Small `ErrorReportingService` (console in dev; hook for OTel/browser tracker later) called from catch paths / a shared interceptor.
**References:** `frontend/src/app/pages/tracking/tracking.component.ts:71`

#### 19. tech-debt(frontend): accessibility pass
`tech-debt` `area: frontend` `priority: P3`

**Context:** Quick scan shows missing ARIA labels, table alt text, and keyboard navigation in modals/panels.
**Proposal:** Run axe (or Angular ESLint a11y rules) on the main pages; fix the high-signal findings; add the lint rules to keep it enforced.

#### 20. docs(architecture): clarify the stateless-module rule vs analytics infrastructure
`documentation` `area: backend` `module: analytics` `priority: P3`

**Context:** ARCHITECTURE.md says stateless modules (incl. analytics) have no `infrastructure/`, but `analytics/infrastructure/corpus_repository.py` exists as a read-only aggregator over the corpus. Either the rule needs a "read-only query adapters allowed" carve-out, or the repository belongs elsewhere.
**Acceptance criteria:** ARCHITECTURE.md updated to match reality (or code relocated); the rule unambiguous for future modules.
**References:** `backend/ARCHITECTURE.md`, `backend/src/hiresense/analytics/infrastructure/corpus_repository.py`

---

## Issue templates (to commit)

`.github/ISSUE_TEMPLATE/` with three YAML forms matching the body convention above:

- `feature.yml` — Context / Proposal / Acceptance criteria / References; auto-label `enhancement`
- `bug.yml` — Context / Reproduction / Expected vs actual / References; auto-label `bug`
- `tech-debt.yml` — Context / Proposal / References; auto-label `tech-debt`
- `config.yml` — `blank_issues_enabled: true`

## Execution order (after approval)

1. Create labels (`gh label create`), milestones (`gh api`)
2. Create the 20 top-level issues (`gh issue create`), then link sub-issues via the GraphQL `addSubIssue` mutation
3. Commit issue templates + this design doc
