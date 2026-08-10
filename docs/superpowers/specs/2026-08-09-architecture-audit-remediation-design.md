# Architecture Audit Remediation — Design

**Date:** 2026-08-09
**Status:** Specced
**Scope:** Full-repo audit (backend + frontend + repo surface) and a four-phase
remediation plan, prioritised for the project goal of surviving as an open-source
portfolio showpiece.

## Problem

HireSense is architecturally strong: hexagonal bounded contexts with genuinely clean
import discipline, 1,606 backend tests with zero skips, a 243-field typed config
package, and a CI pipeline stricter than most commercial repos.

Three things undermine it:

1. **A stranger cannot run it.** The documented quickstart fails on a fresh clone.
2. **The architecture is unenforced.** 125 constructor dependencies are typed `Any`
   (86 in `domain/`) while 15 modules define `ports/` packages — and no Python type
   checker exists. Ports are documentation, not contracts.
3. **The best work is invisible.** No CI badge, no coverage badge, no architecture
   diagram, and `ARCHITECTURE.md` omits a third of the modules.

Structural issues (fat modules, cross-context coupling, unmanaged prompts, a bypassed
frontend design system) are real but rank below the above for the stated goal: a
visitor who cannot boot the app never reaches them.

## Goals

1. Make `git clone` → running app work by following the README verbatim.
2. Convert the ports-and-adapters contract from documentation into a CI-enforced
   invariant.
3. Eliminate the error-handling sites that fabricate plausible-looking data.
4. Make existing rigor visible to a reviewer in the first five minutes.
5. Reduce structural coupling, starting with the highest leverage-to-risk ratio.
6. Keep every phase independently shippable.

## Non-goals

- Multi-tenancy / multi-user. HireSense stays single-tenant; 29 tables carry no
  `user_id` and retrofitting one is out of scope.
- Horizontal scaling. The in-process event bus, caches, and APScheduler pin the app to
  one process. That is an accepted constraint, not a defect to fix here.
- Migrating the sync SQLAlchemy engine (+54 `asyncio.to_thread` sites) to async.
- Grouping the 23 bounded contexts into sub-packages. Deferred until `ingestion` splits;
  revisit only if the root still reads as crowded.
- Rewriting prompts' content. This plan relocates and de-duplicates prompts; it does not
  tune them.

## Evidence provenance

Findings marked **[V]** were verified directly against the working tree during the audit.
Findings marked **[R]** come from subagent reports and carry file:line but were not
independently re-checked — confirm before acting.

---

## Phase 1 — Make it runnable and honest

**Outcome:** a fresh clone boots by following the README; config stops lying about
behaviour. No architectural change.

### 1.1 Boot blockers

- **[V] `enabled_opportunity_sources` is missing from the `_COMMA_FIELDS` allowlist**
  (`backend/src/hiresense/config/sources.py:9-24`), while `backend/.env.example:283`
  ships it **uncommented**. Pydantic attempts a JSON parse of `confs_tech,curated` and
  the app dies at startup. `confs_tech_topics` and `confs_tech_years` share the defect,
  masked only because they remain commented.
  **Fix:** derive the comma-split set from `list[...]`-annotated fields rather than
  extending the hand-maintained allowlist, so the next list field cannot reintroduce it.
  Also remove the duplicated line at `.env.example:282`.
- **[R] Root `.env` is required** for `POSTGRES_PASSWORD`
  (`docker-compose.yml:10,59`, `${POSTGRES_PASSWORD:?}` with no default); the README
  mentions only `backend/.env`.
- **[R] Placeholder secrets are correctly rejected**
  (`config/groups/core.py:11-16,54-62`) but the README never says to change them, so a
  correct security control reads as breakage.
- **[R] `README.md:122-124` claims `APP_MODE=local` by default**, contradicted by
  `docker-compose.yml:55` which forces `production`.
- **[R] No prerequisites section**; no `engines` field in `frontend/package.json`
  despite a hard Node ≥ 22.22.3 floor.

**Acceptance:** delete the local clone, re-clone, follow the README verbatim, reach a
working app. This must be performed, not reasoned about.

### 1.2 Repo hygiene

- **[V] 16 files under `.playwright-mcp/` are tracked** despite `.gitignore:31` — they
  predate the rule, and gitignore does not apply to tracked files. They contain the
  absolute local path `C:/Users/Bryan/OneDrive/Desktop/Bryan/Dev/Personal/HireSense/`
  in a public repo. Fix: `git rm -r --cached .playwright-mcp/`.
- **[R]** Delete `docs/reference/tips_for_getting_jobs copy.md`,
  `docs/reference/Cover_letter.docx`, and the empty `backend/tests/e2e/` and
  `backend/tests/opportunities/` directories.
- **[R]** `CLAUDE.md:9` says Angular 21; `frontend/package.json:22` says `^22.1.0`.
- **[R]** `AGENTS.md:43-45` documents a login that only works on the author's machine.

### 1.3 Correctness bugs

- **[V] The four heuristic matching weights are dead.**
  `config/groups/matching.py:27-37` declares ten weights under
  `# Matching weights (must sum to 100)`. `weight_semantic` (15),
  `weight_skill_match` (20), `weight_experience` (10), and `weight_language` (5) — half
  the declared budget — are read by nothing in `src/`. The one call site,
  `matching/domain/services.py:267`, invokes `breakdown.weighted_average()` with no
  argument, falling through to the hardcoded `{semantic: 0.35, skill: 0.30,
  experience: 0.20, language: 0.15}` at `matching/domain/models.py:16-21`.

  The root cause is that **two disjoint scoring systems share one config block**: the
  heuristic breakdown (config-invisible, hardcoded ratios) and the six LLM dimensions
  (correctly wired via `bootstrap/matching.py:39-64`). An operator cannot tell which
  knobs are live.

  **Fix:** pass the four weights through to `weighted_average()`, or delete them and
  document the two systems separately. Either way the "must sum to 100" comment must go.
- **[V] `workday_api_url` is dead** — one hit in the entire backend, its own definition
  at `config/groups/portals.py:24`, shipping the literal placeholder
  `https://example.myworkdayjobs.com/wday/cxs`. `WorkdayAdapter` never receives it.
- **[R] `globant_adapter.py:22` and `thoughtworks_adapter.py:21`** hardcode base URLs
  with no config field, unlike the six other portal adapters.
- **[R] `FALLBACK_BOARD_SOURCES`** (`frontend/.../ingestion.component.ts:29-43`) lists
  13 sources; the backend registry declares 20. The component already calls
  `/ingestion/sources`, which serves that registry.
- **[V] `--text-default`** is used at `frontend/src/styles.scss:541` and defined
  nowhere; the hover silently does nothing.

---

## Phase 2 — Enforce the architecture, then expose it

**Outcome:** the ports-and-adapters claim becomes machine-checked, and error handling
stops inventing data.

### 2.1 Add a type checker (highest-leverage single change)

**[R] 125 constructor dependencies are annotated `Any`** — 86 in `domain/`, across 73
classes — while `ports/` defines 7 lean Protocols and 15 modules define their own.
`backend/pyproject.toml` configures no mypy/pyright/ty; `ci.yml` type-checks only the
frontend.

Verified consequence: **[V]** `autohunt/domain/autohunt_service.py:55` calls
`self._jobs_repo.list_since(...)`. That method is on the concrete
`JobsRepository:340`, **not** on `JobsRepositoryPort` (16 members, `list_since` absent),
and **not** on `InMemoryJobsRepository`. Because the dependency is typed `Any`
(`autohunt_service.py:22`), a second bounded context is bound to a concrete
infrastructure class and would `AttributeError` under substitution. The `Any` did not
merely hide the violation — it enabled it.

**Plan:** add pyright at `basic` to backend CI, module-at-a-time behind a per-file
ignore list. Start with `analytics/` (three fully-untyped services) and
`matching/domain/services.py`. Replace `Any` with port types as each module is enabled.

Related, unlocked by this:
- **[R] `LLMPort.stream`** (`ports/llm.py:7-10`) has zero domain callers and is
  implemented only by the three adapter-chain classes forwarding to each other. None of
  the 28 LLM test doubles implement it. Split the Protocol or delete the member.
- **[R] `profile/domain/services.py:138`** probes `hasattr(self._latex_compiler,
  "render_cv_tex")` for a method that *is* declared on `LatexCompilerPort` — because the
  dependency is `Any`.

### 2.2 Stop fabricating data

**[R] 102 `except Exception` sites; 71 in `domain/`. 65 are legitimate** (per-source
fan-out that records failure into a result object — the codebase already knows the right
pattern). **31 are hidden failures.** Fix these first:

- **[V] `research/domain/services.py:95`** — the worst site. A bare `except Exception`
  with **no logging** spans the LLM call, parsing, and the DB write, returning
  `_make_fallback`, which sets `funding_stage`, `tech_stack`, `culture_summary`,
  `growth_trajectory`, `red_flags`, `pros`, and `cons` all to the literal string
  `"Research unavailable"` (`:12`) — served as HTTP 200, shape-identical to a real result.
- **[R] `matching/domain/services.py:202` and `:328`** — LLM failure yields hardcoded
  `0.5` dimension scores fed into the weighted composite at full weight, `:202` with no
  logging. A plausible-looking mediocre match, half fabricated.
- **[R] `admin/domain/llm_settings_service.py:302`** — silently falls back to
  `self._env_api_key` on any non-`EncryptionUnavailableError`, with no log. Corrupted
  ciphertext, a rotated key, or a tampered row all silently swap credentials.

**The correct policy is already written in this repo** at
`interview/domain/services.py:169-171` and `optimization/domain/services.py:76-78`
(issues #147/#142: *"Do NOT return a benign placeholder — it gets persisted as real prep
and hides genuine bugs"*). Apply it to the modules that predate it.

Also **[R]**: `main.py:133`'s `LLMTimeoutError → 504` handler is unreachable, because 13
of 15 LLM call sites catch `Exception` first.

### 2.3 Unify error → HTTP mapping

**[R]** `kernel/exception_handlers.py:16-20` states routers never restate the mapping,
but `DomainError` subclasses `ValueError` (`kernel/exceptions/base.py:4`), so a
route-level `except ValueError` shadows the central handler. 21 routes across 8 files
hand-roll it, and one file maps `ValueError` to both 422 and 404
(`interview/api/routes.py:31,72`).

Worst case: `applications/api/routes.py:301` and `profile/api/routes.py:157` catch
`RuntimeError → 503 "LLM not configured"`. `RuntimeError` is the base of
`LatexCompileError`, so **a LaTeX compile failure reports "LLM not configured".**

Add `LLMNotConfiguredError` and an upstream-timeout type to the kernel set; migrate the
21 sites; delete the two `except RuntimeError` blocks.

### 2.4 Make rigor visible

- CI status + coverage badges. `pytest-cov` is already a declared dev dependency
  (`backend/pyproject.toml:81`) but `--cov` is never passed; wire it with
  `--cov-fail-under`. **[R]** All six current README badges are static images encoding
  no live state.
- **[R] Zero mermaid diagrams repo-wide.** `mkdocs.yml:48` already enables
  `pymdownx.superfences`. One architecture diagram is the highest signal-per-line change
  available.
- **[R]** `ARCHITECTURE.md` omits 10 of 30 modules (`autohunt`, `claims`, `inbox`,
  `network`, `notifications`, `observability`, `opportunities`, `outreach`, `portfolio`,
  `preference`) and says "12 sources" where there are ~27.
- **[R]** `mkdocs.yml:52-53` publishes a one-page nav while `exclude_docs` fails to
  exclude `docs/open-source-launch/`, making internal launch copy publicly reachable but
  unlinked.

---

## Phase 3 — Backend structure

Ordered by leverage-to-risk, not by size.

### 3.1 Highest ratio first

- **[R] Extract `JobQueryService` from `IngestionOrchestrator`**
  (`ingestion/domain/services.py:274-306`). Six one-line pass-throughs to the repository
  made the orchestrator the ambient job-query god object, which is why four other
  modules import it. ~33 lines moved drops ingestion's fan-in from 10 to ~4.
- **[V] Move `json_extract` to `kernel/`.** `ingestion/domain/quick_scoring_service.py`
  and `job_quality_classifier.py` import it from `matching.domain.scorers` — a JSON
  parser with nothing to do with matching. This breaks two of the three
  `ingestion → matching` domain edges at near-zero risk. Delete the 7 duplicate
  markdown-fence strippers **[R]** while there.
- **[R] Split `MatchingOrchestrator`.** `evaluate` (`:76-130`) and `analyze`
  (`:213-284`) share zero instance attributes and never call each other. Splitting also
  removes the private-attribute reach at `bootstrap/dimension_scorer_adapter.py:37`
  (**[V]** the only cross-object private access in 32.9k LOC — and it silently disables
  preference nudging if the field is renamed).
- **[R] Null objects instead of `| None`.** 40 optional collaborator params across 31
  classes produce 74 `is None` guards. `InMemoryProfileRepository` deletes 16 guards
  from `profile/domain/services.py` alone; a `NullLLM` raising `LLMNotConfiguredError`
  collapses 14 divergent not-configured policies.

### 3.2 Folder structure

**[V]** The root mixes two axes of decomposition: 23 business contexts (~29,600 LOC)
alongside 7 technical folders (~5,300 LOC). `ports/` sits alphabetically between
`portfolio/` and `preference/`, and collides conceptually with each module's own
`ports/`.

```
src/hiresense/
├── main.py
├── shared/          # was: kernel, ports, adapters, infrastructure, observability, config
├── composition/     # was: bootstrap/ — named for what it is
└── <23 business contexts, flat>
```

`admin/` (2,668 LOC — LLM settings, usage tracking, audit logging) moves to the platform
side; it is operations, not job-hunting domain. Context grouping stays deferred.

### 3.3 Normalise the composition layer

**[V]** `bootstrap/` has six competing conventions: four return shapes (`XBuild`,
bare provider, `XBuild | None`, `XBuild` wrapping only `.provider`), five input
signatures (`build_scheduler` bypasses `SharedInfra` entirely), no naming rule for the
"extra" field, `Any` at load-bearing seams (`SharedInfra` has 5 of 8 fields as `Any`),
a hand-maintained unsorted `__all__`, and three files that are not builders at all.

- **A:** one contract — `build_<module>(ctx: BuildContext) -> ModuleBuild`, always
  returning `.provider`, never `None`; move the three non-builders into
  `composition/adapters/` and `composition/infra/`; assert the contract in a test that
  walks the package.
- **B:** a declarative `ModuleSpec` manifest (name, builder, router, state key,
  requires, provides). `create_app` becomes a topological sort — ~20 lines instead of
  314 — and the two-phase back-patching (`attach_job_lookup`,
  `attach_dimension_scorer`) becomes declared, resolvable dependency data.

Ship A first; it stands alone.

### 3.4 Dissolve the second composition root

**[V]** `ingestion/api/routes.py` imports from `matching`, `profile`, `network`,
`portfolio`, and `identity` — mostly into their `domain/` internals, not through ports.
Its `list_jobs` handler spans lines 281-608. That is not a fat endpoint; it is a
cross-context use case wired outside `bootstrap/`. Extract it into a use-case service.

### 3.5 Prompts

**[R] 37 prompt sites, ~16,000 characters, all inline literals in domain services**,
in three coexisting shapes with no rule. No versioning, no A/B, no independent
diffability. `ARCHITECTURE.md` does not contain the word "prompt".

The critical finding is not storage but **duplicated policy across prompts required to
agree**: the 6-dimension rubric exists twice (`combined_scorer.py:25-49` vs the six
individual scorers), and the gating rules exist twice with different numeric caps
(`quick_scoring_service.py:33-51` vs `deep_analysis_service.py:32-42`). Both paths are
wired simultaneously and feed the same composite.

**Plan:**
1. Deduplicate first — `dimension_rubric.py` and `gating_rules.py` as single sources.
   Worth doing even if nothing else here happens.
2. A per-context `<module>/prompts/` package (never a global one — that breaks bounded
   contexts). Pure text plus f-string assembly, so `domain/` purity holds.
3. A `Prompt` frozen dataclass in `kernel/` with `key` (matching `FEATURE_REGISTRY`) and
   `version`, rendering as a pure function — snapshot-testable without a fake port.
4. **Add `prompt_version` to the `job_match_cache` key.** Today a prompt edit poisons
   the cache: `(job_id, profile_hash)` carries no prompt identity, so old and new results
   mix in one list with no invalidation.
5. File-backed overrides only for voice-heavy prompts (cover letter, outreach),
   generalising the working `outreach/domain/style_guide.py` pattern. Scoring prompts
   stay code-owned — their output shape is a parsing contract.
6. Move the ~13 hardcoded truncation limits to config as each prompt is touched; they
   are the largest LLM-cost lever.

### 3.6 Test infrastructure

**[R]** No `tests/conftest.py` exists. 307 of 510 test class definitions carry a
duplicated name (`FakeResponse` ×18, `FakeHttpClient` ×16, 28 LLM doubles).
`test_analytics_endpoints.py` needs 128 lines of setup before its first assertion. Add
`tests/conftest.py` and `tests/fakes/`.

**[R]** `tests/unit/profile/__pycache__/test_cover_letter_template_routes.cpython-313.pyc`
exists with no corresponding `.py`. A test was deleted, leaving `cover_letter_templates/`
(327 LOC, fully wired) as the only backend module with zero coverage. Restore it.

---

## Phase 4 — Frontend

**[V] `core/` imports from `pages/` 75 times across 22 files** — the exact layering
inversion the backend forbids. A reviewer comparing halves reads the frontend as the
unowned one.

**[V] The design system is bypassed:** `styles.scss:27` defines `--accent: #0f766e`
(teal) while 7 files redefine `$primary: #4f46e5` (indigo) and `outreach.component.scss`
uses `#2563eb` (blue). `.btn-primary` is defined 9 times. Angular's emulated
encapsulation means the component rule always wins — the design system loses every
conflict. **[R]** 715 raw hex literals across 117 distinct colours; ~1,302 lines of
measured top-level duplication; no `@use`/`@import` anywhere, which is *why* the `$var`
preamble is retyped.

**Sequencing — mechanical and low-risk first:**

1. `tsconfig` path aliases (`@core/*`, `@shared/*`, `@features/*`). Unblocks everything.
2. `styles/_tokens.scss` + `_mixins.scss`; delete the 7 duplicated preambles; convert
   hex to tokens. Fix `--text-default` here.
3. **Move the 109 models to `core/contracts/`** — a pure import rewrite that erases all
   75 inversion imports in one commit.
4. `core/api/` — `ApiClient`, `api-routes.ts` (kills 126 `apiUrl` concatenations **and**
   the drifting regex copy in `timeout.interceptor.ts`), `http-error.ts` (**[R]** the
   correct helper `mapLlmError` already exists and has exactly one call site while the
   idiom is re-implemented 68 times).
5. `shared/ui/` component library; delete each of the 92 overrides as its primitive lands.
6. Signal stores per feature, worst first: `ingestion` (525 lines, 19 signals, 11
   `.subscribe()`, five responsibilities) → `outreach` → `applications` → `admin`.
7. Flip `OnPush` to the schematics default; fix the 23 stragglers.
8. `openapi-typescript` in CI so backend contract drift fails the build. Today
   `strictTemplates` checks the frontend against its own hand-written interfaces, not
   reality.

**Already good — do not touch:** zero `any` repo-wide, maximally strict `tsconfig`, 523
`@if`/`@for` with zero legacy directives, 136 `takeUntilDestroyed`, the reasoned
interceptor ordering, `LlmRunnerService`, and `profile.component.ts` (259 lines, 9
extracted children) as the counter-example the other pages should follow.

---

## Risks

- **Phase 2's type checker will surface a large initial finding count.** Mitigate with a
  per-file ignore list; enable module-at-a-time. Do not attempt a repo-wide flip.
- **Phase 3.5 prompt deduplication changes LLM inputs.** The combined and individual
  scorer paths currently disagree; unifying them *will* shift some scores. That is the
  point, but snapshot the before/after on a fixed job set.
- **Prompt caching depends on prefix stability.**
  `quick_scoring_service._build_system_prompt` (`:182-208`) deliberately places the
  byte-stable candidate block in the system prefix. Any prompt refactor must preserve it.
- **Phase 4 step 3 touches ~109 files.** Mechanical, but land it alone.
- The audit was read-only; `[R]` findings should be confirmed before acting.

## What is already exemplary — do not spend effort here

Domain-layer framework purity (**[V]** zero `sqlalchemy`/`httpx`/`fastapi`/`langchain`
imports in any `domain/` file; one `bs4` exception at
`ingestion/domain/html_stripper.py:3`). The global `ports/` package (200 lines, 7 lean
Protocols). `SqlRepository` adoption (24/24). The fan-out error handling in
ingestion/scheduler/portal-scanner. The 580-line commented `.env.example`. The security
posture — placeholder-secret rejection, wildcard-CORS refusal citing CWE-942, a dedicated
login limiter citing ASVS V2.2.1. `test_ssrf_guard.py`'s DNS-rebinding coverage. And
1,606 tests with zero skips, zero xfail, and zero `.only`.
