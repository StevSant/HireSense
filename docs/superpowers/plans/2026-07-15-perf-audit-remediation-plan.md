# Performance / Token / LLM-Orchestration Audit Remediation — Implementation Plan

Source: 2026-07-15 full-repo performance audit (report `hiresense-perf-token-audit-2026-07-15.md`). Executes the audit's "quick wins" + medium-term items. Branch: `perf/audit-remediation`, worktree `C:\Users\Bryan\worktrees\hiresense-perf`.

## Global Constraints (binding for every task)

- Work ONLY inside the worktree `C:\Users\Bryan\worktrees\hiresense-perf`. Never touch the OneDrive checkout.
- Git: plain additive commits only (`git add <named files>` + `git commit -m "type(scope): ..."`, Conventional Commits, English). NEVER: push, stash, rebase, reset, checkout other branches, amend.
- Backend commands from `backend/`: `uv run python -m pytest <path>` (bare `uv run pytest` is broken on this machine), `uv run ruff check .`. NEVER run `ruff format` repo-wide.
- Known local quirk: full pytest may show 1 pre-existing failure in autopilot settings defaults (local `.env` sets `AUTOPILOT_PIPELINE_ENABLED=true`). Not a regression; ignore that one only.
- Architecture rules (backend/ARCHITECTURE.md): `domain/` imports no sqlalchemy/langchain/httpx; wiring only in `bootstrap/`; every package `__init__.py` re-exports public symbols; one class/function per file for NEW files.
- No hardcoded values: every new tunable goes in the matching `backend/src/hiresense/config/groups/*.py` group AND `backend/.env.example` (with a comment). Settings are flat on `settings.*`.
- Default test suite must stay DB-free (SQLite in-memory integration pattern already in `tests/`).
- Tests first (TDD) where practical; every behavior change gets a test.
- Frontend from `frontend/`: Angular 22 standalone + signals, zoneless. Tests: `npm test -- --include "**/<file>.spec.ts"`. Lint MUST pass: `npx ng lint` (CI runs it; `npm test` does not catch lint).
- Do not modify ranking semantics except where a task explicitly says so.

## Task 1: Unblock the event loop (sync DB/CPU on asyncio loop)

Fix the four confirmed sync-on-loop sites:

1. `backend/src/hiresense/adapters/vector_store/pgvector_adapter.py` — all four `async def` methods (`upsert`, `search`, `get_vector`, `delete`) run `with self._session_factory() as session: session.execute(...)` inline. Extract each method's sync body into a private sync helper (e.g. `_search_sync`) and call it via `await asyncio.to_thread(...)`. Update the class docstring (it currently *documents* the inline-sync behavior at lines 30-37 — that text must change).
2. `backend/src/hiresense/ingestion/domain/quick_scoring_service.py` — `score_page` calls `self._cache_repo.get_quick_bulk(...)` (line ~126) and `self._safe_upsert(...)` (line ~147) synchronously. Wrap the repo calls in `asyncio.to_thread` (`_safe_upsert` becomes async or the loop that calls it awaits `to_thread(self._cache_repo.upsert_quick, ...)` keeping the try/except semantics).
3. `backend/src/hiresense/admin/infrastructure/feature_configured_llm_adapter.py` — `generate()`/`stream()` call the sync `self._config_service.resolve(...)` on the loop (blocking DB + Fernet decrypt on TTL miss). Change both to `config = await asyncio.to_thread(self._config_service.resolve, self._feature_key)`.
4. `backend/src/hiresense/adapters/embedding/sentence_transformer_adapter.py` — lazy `_load_model` has no lock (lines ~18-23): two concurrent cold calls load the ~420MB model twice. Add an `asyncio.Lock` (double-checked: check, acquire, re-check, load).

Tests: unit tests proving (a) pgvector adapter methods still return mapped results (use a fake session factory recording the calling thread — assert not the event-loop thread), (b) quick scoring still merges cache hits + LLM results (existing tests in `tests/unit/ingestion` cover behavior — keep green), (c) concurrent first calls to the embedding adapter load the model exactly once (fake loader with a counter + asyncio.gather). Run: `uv run python -m pytest tests/unit/ingestion tests/unit/adapters tests/unit/admin -q` (adjust to actual test dirs) + `uv run ruff check .`.

## Task 2: Quick-scorer concurrency cap + bulk cache writes + rescore-gated global pass

1. New setting `match_quick_concurrency: int = 4` in `backend/src/hiresense/config/groups/llm.py` + `.env.example` entry (`MATCH_QUICK_CONCURRENCY=4` with comment). Wire it in `backend/src/hiresense/bootstrap/ingestion.py` where `QuickScoringService` is built (batch_size already passed there ~line 312).
2. `quick_scoring_service.py`: bound the chunk fan-out (`asyncio.gather` at ~line 136-142) with an `asyncio.Semaphore(self._concurrency)` — mirror the existing pattern in `ingestion/domain/job_quality_classifier.py:122-128`.
3. Add `upsert_quick_bulk(results: list[QuickMatchResult], profile_hash: str) -> None` to `backend/src/hiresense/ingestion/infrastructure/job_match_cache_repository.py`: ONE session, SELECT existing rows for the (job_ids, profile_hash) set, update/insert, ONE commit. Update the port/Protocol if one exists and any fakes in tests. `QuickScoringService` then replaces the per-result `_safe_upsert` loop with one `await asyncio.to_thread(self._cache_repo.upsert_quick_bulk, all_results, profile_hash)` (keep a try/except that logs and continues on failure — cache write failure must never fail scoring). Keep `upsert_quick` (deep path uses the same shape; do not touch deep).
4. `backend/src/hiresense/ingestion/api/routes.py` ~lines 338-343: the whole-corpus cache-only `score_page(all_jobs, llm_on_miss=False)` runs on EVERY GET. Gate it: run the whole-corpus overlay only when `rescore` is true OR the sort is match-sort AND page == 1 is insufficient — minimal semantics-preserving version: keep the global overlay only when sorting by match (`sort` startswith "match"); for non-match sorts overlay only `result.jobs` after pagination. Read the surrounding code first; preserve cross-source ranking on match-sort (that is why the global pass exists). If in doubt, gate on match-sort only and document.

Tests: semaphore bounds concurrent `_score_chunk` executions (fake LLM that tracks max concurrency); bulk upsert writes N rows in one call (fake/SQLite session); routes test asserting non-match-sort request does not call `get_quick_bulk` with the full corpus (existing integration tests style in `tests/integration/`). Run targeted pytest + ruff.

## Task 3: Token guardrails — default max_tokens + input char caps

1. Per-feature default `max_tokens`: in `backend/src/hiresense/admin/domain/llm_config_service.py` `_resolve_fresh`, after computing effective extra_params, if `"max_tokens"` absent, inject a default from settings. Add to `config/groups/llm.py`: `llm_default_max_tokens: int = 2048`, `llm_classifier_max_tokens: int = 512`. Classifier features (use the small cap): `inbox-classification`, `job_quality_classifier`, `application_skill_extractor`, `preference_explanation`, `match_quick_scorer`... NO — match_quick_scorer returns per-job JSON for up to 20 jobs; give it `llm_default_max_tokens`. Keep a module-level frozenset of classifier feature keys next to the service (document why). Admin-set `max_tokens` in extra_params always wins. LLMConfigService lives in domain and already receives settings? Check its constructor — if it doesn't receive settings, pass the two ints from bootstrap wiring (bootstrap builds it) to keep domain framework-free. `.env.example`: `LLM_DEFAULT_MAX_TOKENS=2048`, `LLM_CLASSIFIER_MAX_TOKENS=512` with comments.
2. Dimension scorer input caps: `backend/src/hiresense/matching/domain/scorers/llm_scorer.py` — add a single truncation point in `BaseLLMScorer` (e.g. `_truncate(text, limit)` + a `job_char_limit` ctor param default 4000) and use it in every scorer's `_build_prompt` for the job description (5 of 6 scorers are currently uncapped; `seniority_scorer.py` already caps at 2000 — unify through the base). Wire the limit from `config/groups/matching.py` (`match_dimension_job_char_limit: int = 4000`) via `bootstrap/matching.py`. `.env.example` entry.
3. CV optimizer: `backend/src/hiresense/optimization/domain/services.py` (~lines 79-93) — cap `job_description` at the existing deep limit (reuse `match_deep_job_char_limit`, passed in from bootstrap; do NOT import settings in domain). Do NOT truncate `original_tex` (breaks the `original` anchor replacement).
4. PDF parser: `backend/src/hiresense/profile/domain/pdf_parser.py` (~line 56) — cap extracted text at a new `cv_parse_char_limit: int = 20000` (config group for profile/llm + `.env.example`).

Tests: resolve() injects default max_tokens only when admin hasn't set it; classifier keys get the small cap; scorers truncate long descriptions (build prompt with 50k-char desc, assert length bounded); optimizer prompt bounded. Run targeted pytest + ruff.

## Task 4: Rate-limit artifact routes + parallelize autopilot & inbox + 202 run-now

1. `backend/src/hiresense/applications/api/routes.py`: add the existing `enforce_expensive_rate_limit` dependency (see `optimization/api/routes.py:31` for usage) to the four LLM artifact routes: match, optimize, interview-prep, cover-letter (~lines 188-257).
2. Autopilot: `backend/src/hiresense/autopilot/domain/autopilot_pipeline_service.py` — replace the serial `for entry ... await self._draft_one(entry)` (~line 40) with bounded concurrency: `asyncio.Semaphore(concurrency)` + `asyncio.gather` where `concurrency` is a new ctor param wired from a new setting `autopilot_draft_concurrency: int = 3` (config group where the other autopilot settings live — find them; `.env.example` entry). Preserve the per-entry try/except isolation (~lines 56-62) and the `exists_for_job` dedup — note `repo.exists_for_job`/`repo.add` are sync: wrap in `to_thread` within the concurrent path to stay loop-safe, and guard against two concurrent drafts of the same job (dedup check before gather is enough since entries are distinct jobs).
3. `backend/src/hiresense/autopilot/api/routes.py` POST `/run` (~lines 23-28): return 202 immediately. Use the pattern: create an `asyncio.create_task` on the running pipeline, KEEP a module/app-level reference guarded against concurrent runs (if a run is already in flight return 409 or `{"status":"already_running"}`), respond `{"status": "started"}` with `status_code=202`. Response model changes accordingly; update frontend expectations ONLY if the frontend consumes the response body (check `frontend/src/app/core/services/autopilot.service.ts` and the drafts page; adjust typing minimally).
4. Inbox: `backend/src/hiresense/inbox/domain/inbox_processing_service.py` — replace the serial per-email loop (~line 44) with bounded gather (semaphore 3, constant module-level with comment or reuse a config knob if one fits naturally; keep per-email dedup + try/except semantics).

Tests: rate-limited routes return 429 when hammered (existing rate-limit test conventions); autopilot draft concurrency bounded + one failure doesn't kill the batch; run-now returns 202 and rejects concurrent second call; inbox batch processes all emails with a failing one isolated. Run targeted pytest + ruff.

## Task 5: Deploy/docker/docs

1. `docker-compose.yml`: (a) add named volume `hf-cache` mounted at the app's HF cache dir (`/root/.cache/huggingface`) and set `HF_HUB_OFFLINE: "0"` in the app `environment:` block (env_file currently forwards `=1` from `.env`, which breaks first-run model load in a fresh container — compose `environment` overrides `env_file`; add a YAML comment explaining). (b) healthcheck for `app` hitting `http://localhost:8000/health` (curl or python one-liner — check what the image has; uvicorn image is python: use `python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status==200 else 1)"`). (c) `frontend.depends_on: app: condition: service_healthy`.
2. `backend/.dockerignore` and `frontend/.dockerignore` (new): `.env*`, `.venv`, `__pycache__`, `.git`, `node_modules`, `dist`, `cvs`, `csv_imports`, coverage artifacts as applicable per context.
3. `backend/ARCHITECTURE.md` lines 159-165: rewrite the stale "pgvector search swap" follow-up — ANN pre-ranking IS wired (`SemanticPreRanker` at ingestion routes); remaining work is corpus-materialization pushdown (filters/pagination into SQL, champions/min_score-exemption over a candidate window), tracked by issue #132.
4. Document the single-worker constraint: short section in ARCHITECTURE.md ("Scaling constraints": in-memory event bus, in-process rate limiter + scheduler, per-process embedding model/LRU caches ⇒ exactly one uvicorn worker; externalize before adding workers).

Validation: `docker compose config -q` parses; no pytest impact. Commit.

## Task 6: Observability — spans, metrics, labels

1. `backend/src/hiresense/adapters/embedding/sentence_transformer_adapter.py`: wrap encode in a span `embedding.encode` (attributes: batch_size) + histogram `embedding_encode_duration_ms` — follow the tracer/metric acquisition pattern in `matching/domain/services.py` (`get_domain_metrics()`, `_tracer`). Careful: adapter layer may import otel freely (it's not domain).
2. `backend/src/hiresense/adapters/vector_store/pgvector_adapter.py`: span `vector.search` with `top_k` + result-count attributes around search.
3. `backend/src/hiresense/ingestion/domain/services.py`: per-source child span `ingestion.source.fetch` + histogram `source_fetch_duration_ms{source}` around each source fetch in the run loop (~line 78). Domain already uses the observability helpers here (ingestion.run span exists) — follow that pattern.
4. `backend/src/hiresense/admin/domain/usage_recorder.py` (~lines 40-45, 69-71): add `"feature": feature_key` attribute to the tokens + duration instruments (cost/errors already carry it); keep task refs — store `loop.create_task(...)` results in a `set` with `task.add_done_callback(set.discard)` so tasks aren't GC'd and threadpool bursts remain observable. (Full batching is a follow-up, out of scope.)
5. `backend/src/hiresense/observability/metrics.py`: register the new instruments following the existing DomainMetrics shape.

Tests: metrics module unit test asserting new instruments exist; usage recorder keeps a ref until done (drain in test). Run targeted pytest + ruff.

## Task 7: Frontend reliability — timeout, error mapping, duplicate fetch, poll, dropdown

1. Timeout interceptor (new `frontend/src/app/core/interceptors/timeout.interceptor.ts` + spec): RxJS `timeout()` keyed by URL: LLM-slow prefixes (`/interview/prepare`, `/research`, `/optimization`, `/cover-letter`, `/matching/analyze`, `/matching/evaluate`, `/outreach/generate`, `/applications/.../match|optimize|interview-prep|cover-letter`, `/tracking/batch-evaluate`, `/profile/translate`, `/profile/upload-file`) → 120000 ms; everything else → 30000 ms. Constants in `frontend/src/environments/environment*.ts` (both files) — no magic numbers in the interceptor. On timeout emit an HttpErrorResponse-like error the existing error branches render. Register after auth interceptor in `app.config.ts`.
2. Central LLM-error mapping: small util `frontend/src/app/core/services/llm-error.util.ts` (+ spec) `mapLlmError(err, fallback: string): string` — 503 → "LLM isn't configured — add a key in Admin → LLM settings."; timeout → "The request timed out — the model may be busy. Try again."; else `err.error?.detail || fallback`. Use it in: `interview.component.ts` (~line 223), `matching.component.ts` (~207, ~232), `cv-optimization-runner.service.ts` (~43), `cover-letter-runner.service.ts` (~38). (outreach + company-intel already have good messages — leave them.)
3. Duplicate initial fetch: `ingestion.component.ts` `ngOnInit` (~line 188) fires `loadJobs()`, and `job-filters.component.ts` `ngOnInit` (~24-39) emits stored/geo location → second `loadJobs()` (switchMap cancels the first — comment at ingestion.component.ts:116-122 documents it). Fix: `job-filters` should emit its initial (possibly empty) filter state SYNCHRONOUSLY once and ingestion should do its FIRST load only from that emission (remove the direct `loadJobs()` in ngOnInit, or have job-filters always emit exactly once at init — pick the design that keeps "no stored location" working with exactly ONE initial request). Update the stale comment.
4. Visibility-gated poll: `ingestion.component.ts` ~line 265 revalidation `timer(15000,15000).take(8)` — skip ticks when `document.visibilityState !== 'visible'` (filter operator).
5. Matching page dropdown: `matching.component.ts` ~line 81 `queryJobs('boards', 1, 100)` eager on init — reduce to `page_size=25` AND defer until the select is first opened (signal-gated lazy load; keep the `?job_id=` deep-link prefill working via the existing single-job fallback).

Tests: interceptor spec (timeout fires, prefix table respected), llm-error util spec, ingestion spec asserting exactly one initial queryJobs call, matching spec for lazy dropdown. Run `npm test -- --include` for touched specs, then `npx ng lint`.

## Task 8: Frontend — generalize the LLM runner pattern (survive navigation)

Model on `core/services/cv-optimization-runner.service.ts` + `cover-letter-runner.service.ts`. Create a root-scoped generic `LlmRunnerService` (or per-feature runners if the generic fights the types): keyed runs (`isRunning(key)`, `result(key)`, `error(key)` signals), results cached in the service. Migrate: interview prep (`interview.component.ts:214`), matching analyze + evaluate (`matching.component.ts:198,224`), outreach generate (`outreach.component.ts:154`), applications batch-evaluate (`applications.component.ts:271`) — remove `takeUntilDestroyed` on these calls (subscription lives in the service), components read signals. Keys: interview → application/job id; matching → job id + op; outreach → target id; batch-evaluate → constant. Preserve existing UX (spinners/errors) and the llm-error mapping from Task 7.

Tests: runner service spec (run survives "component destroy" — result lands in cache and is readable after; error path). Component specs updated. `npm test` touched specs + `npx ng lint`.

## Task 9: Collapse 6 dimension scorers into one combined LLM call

Current: `matching/domain/services.py:83` gathers 6 `BaseLLMScorer`s (wired `bootstrap/matching.py:30-43`), 6 LLM calls/job. Model: `matching/domain/deep_analysis_service.py:106` already returns 5 dimensions in ONE call.

1. New `matching/domain/scorers/combined_scorer.py`: `CombinedDimensionScorer` — one prompt listing the 6 dimensions (seniority, compensation, growth, culture, application_strength, interview_readiness) with their scoring instructions (port each scorer's `_build_prompt` guidance into one section each; keep them concise), returns JSON `{"dimensions": [{"dimension": name, "score": 0-1, "rationale": str}, ...]}`. Truncate job description via the Task-3 shared cap. Feature key: `match_dimension_scorer` (new admin feature — check how feature keys are registered/seeded in admin so the settings UI lists it; follow whatever exists for other keys).
2. `MatchingOrchestrator.evaluate`: use the combined scorer as the default path; on parse failure or missing dimensions, FALL BACK to the existing per-scorer fan-out (keep the 6 scorers wired for fallback + the explicit `dimension_scorers` override param used by preference flow — read `bootstrap/dimension_scorer_adapter.py:46` and preserve its contract). Weight overrides (`services.py:85-92`) must apply identically to combined results (each dimension keeps its configured weight from the wiring).
3. Re-export via scorers package `__init__.py`. Register the feature key default model mapping wherever the other match features get theirs (config/groups/llm.py pattern).

Tests: combined scorer parses well-formed response into 6 DimensionResults with correct weights; malformed → fallback path invoked (fake LLM); orchestrator composite matches old formula given same scores; batch path still bounded by `batch_concurrency`. Score-parity is judgment — assert structure, not exact scores. Run matching unit tests + ruff.

## Task 10: Anthropic prompt caching (cache_control on stable prefixes)

1. `adapters/llm/langchain_adapter.py`: optional ctor flag `cache_system_prefix: bool = False`. When True and a system prompt is present, build the SystemMessage with content blocks: `[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]` (LangChain ChatAnthropic supports content-block cache_control; verify against installed langchain_anthropic version in the worktree venv — if unsupported, set it via `additional_kwargs` per the version's API; write a unit test with a fake model capturing messages).
2. `admin/infrastructure/llm_factory.py` / `feature_configured_llm_adapter.py`: enable the flag only when `config.provider == "anthropic"`. Non-anthropic providers keep plain SystemMessage (OpenAI caches automatically; groq/ollama ignore).
3. Move the stable candidate block into the cached prefix for the highest-volume prompt: `quick_scoring_service.py` — the CANDIDATE block (level, skills, summary) moves from the user prompt into the system prompt string (system = static instructions + "\n\nCANDIDATE\n..." built per score_page call; it is byte-stable across chunks within a run and across runs for the same profile_hash). JOBS stay in the user message. Update `_build_prompt` accordingly + tests.
4. Add setting `llm_prompt_cache_enabled: bool = True` (config/groups/llm.py + .env.example) gating the whole behavior.

Tests: fake chat model asserts cache_control present for anthropic-flagged adapter and absent otherwise; quick-scorer system prompt contains candidate block and user prompt contains only jobs. Run adapter + ingestion unit tests + ruff.

## Task 11 (stretch — do NOT start without controller confirmation): SSE streaming for cover letter + CV translate

Fix `usage_tracking_llm_adapter.stream()` recording zero usage first; then SSE endpoints + frontend consumption. Large; likely deferred to its own branch.

## Final

Full backend suite + `uv run ruff check .`; frontend `npm test` + `npx ng lint`; whole-branch review; report. No push.
