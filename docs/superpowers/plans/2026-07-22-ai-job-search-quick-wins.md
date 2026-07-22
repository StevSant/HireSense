# AI Job Search Comparison Quick Wins — Implementation Plan

> **For Codex:** Execute this plan with `superpowers:executing-plans`, using test-driven development and verification-before-completion.

**Goal:** Fix candidate-independent rich matching, make test telemetry deterministic, correct stale Angular documentation, and preserve the full repository comparison as an actionable Markdown roadmap.

**Architecture:** Resolve candidate profiles once in FastAPI routes through the existing `ProfileService`, then pass domain models into matching services. Keep profile context optional for backward compatibility. The Angular matching page supplies the profile it already has loaded. Test infrastructure disables application telemetry by default without changing runtime settings.

**Tech stack:** FastAPI, Pydantic, Python asyncio, pytest, Angular 22 signals, Vitest, Ruff, Prettier, TypeScript.

---

## Task 1: Resolve profiles in single-job rich evaluation

**Files:**

- Modify: `backend/tests/unit/matching/test_evaluate_route.py`
- Modify: `backend/src/hiresense/matching/api/routes.py`

1. Extend the route-test fake orchestrator to record the received profile and add a fake profile service.
2. Add a test posting `profile_id` and asserting the resolved `CandidateProfile` reaches `orchestrator.evaluate`.
3. Add a test posting an unknown `profile_id` and asserting HTTP 404 plus zero orchestrator calls.
4. Run `uv run pytest tests/unit/matching/test_evaluate_route.py -q` from `backend/` and confirm both new tests fail for the expected reason.
5. Inject the existing profile-service dependency into `evaluate_job`.
6. Resolve an explicitly supplied ID, raise `HTTPException(404, "Profile not found")` when absent, and pass the result to the orchestrator. Preserve `None` when omitted.
7. Rerun the focused test and confirm it passes.

## Task 2: Carry optional profile context through batch evaluation

**Files:**

- Modify: `backend/tests/unit/matching/test_batch_service.py`
- Modify: `backend/tests/unit/matching/test_batch_route.py`
- Modify: `backend/src/hiresense/matching/api/schemas.py`
- Modify: `backend/src/hiresense/matching/api/routes.py`
- Modify: `backend/src/hiresense/matching/domain/batch_service.py`

1. Add a batch-service test that passes a sentinel profile and asserts every orchestrator call receives the same object.
2. Add batch-route tests proving an explicit ID is resolved once and supplied to the batch service, and an unknown ID returns HTTP 404 without evaluating jobs.
3. Run the two focused test files and confirm the new tests fail for the expected missing arguments/behavior.
4. Add optional `profile_id` to `BatchEvaluateRequest`.
5. Change `BatchEvaluationService.evaluate_batch` to accept `profile=None` and forward it to every evaluation.
6. Resolve the optional profile once in the route and pass it into the service.
7. Rerun the two focused test files and confirm they pass.

## Task 3: Send the selected profile from the Angular matching page

**Files:**

- Modify: `frontend/src/app/pages/matching/matching.component.spec.ts`
- Modify: `frontend/src/app/pages/matching/matching.component.ts`

1. Add a component test with English and Spanish profiles, select Spanish, call `evaluate()`, and assert the request contains the Spanish profile ID.
2. Run `npx ng test --watch=false --include='src/app/pages/matching/matching.component.spec.ts'` from `frontend/` (or the project-supported focused equivalent) and confirm failure because `profile_id` is absent.
3. Add a small selected-profile computed signal/helper shared by profile hydration and evaluation.
4. Include `profile_id` only when a profile is loaded.
5. Rerun the focused test and confirm it passes.

## Task 4: Disable application telemetry by default in tests

**Files:**

- Create: `backend/tests/conftest.py`
- Modify: `backend/tests/unit/test_app.py`
- Modify: `backend/tests/unit/config/test_package_layout.py`

1. Add an app test asserting the ordinary test-created app has no installed OTel provider list.
2. Run the focused app test and confirm it fails with the developer `.env` telemetry configuration.
3. Add a function-scoped autouse fixture that sets `OTEL_ENABLED=false` through `monkeypatch` for every test.
4. In the configuration-default test, explicitly remove `OTEL_ENABLED` so it continues proving the runtime default is `true` rather than the test override.
5. Run configuration, application, and observability tests and confirm they pass without exporter connection/shutdown noise.

## Task 5: Correct Angular-version documentation

**Files:**

- Modify: `README.md`
- Modify: `CLAUDE.md`

1. Replace Angular 21 references with Angular 22, including the README badge.
2. Run `rg -n "Angular 21|Angular-21" README.md CLAUDE.md docs` and confirm no current-stack statement remains stale. Historical design documents may be left unchanged when they intentionally describe their creation-time stack.

## Task 6: Write the complete comparison and recommendation roadmap

**Files:**

- Create: `docs/analysis/2026-07-22-ai-job-search-improvements.md`

1. Record the reference commit and HireSense verification baseline.
2. Summarize what HireSense already does better and should preserve.
3. Document every finding under correctness, security, application readiness, workflow, ingestion, onboarding, interview/follow-up, learning, testing, CI, performance, and maintainability.
4. Give each recommendation priority, effort, impact, dependencies, and concrete implementation direction.
5. Include a staged delivery order and a status table marking this plan's quick wins as implemented.
6. Run a link/path/readability review and `git diff --check`.

## Task 7: Full verification

**Files:** All modified files.

1. From `backend/`, run `uv run ruff format --check .` and `uv run ruff check .`.
2. From `backend/`, run `uv run python -m pytest -q` and confirm the suite passes without post-suite OTel exporter errors.
3. From `frontend/`, run `npm run format:check`, app/spec TypeScript checks, `npx ng lint`, `npx ng test --watch=false`, and `npm run build`.
4. From the repository root, run `git diff --check` and inspect `git status --short`.
5. Review the final diff for accidental changes, backward compatibility, and consistency between the report and actual implementation.
