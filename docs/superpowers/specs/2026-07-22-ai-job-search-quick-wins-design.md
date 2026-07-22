# AI Job Search Comparison Quick Wins — Design

**Date:** 2026-07-22  
**Status:** Approved  
**Reference:** `MadsLorentzen/ai-job-search` at commit `d88c0236830387c87a07786a591c567300e76911`

## Goal

Implement the small, low-risk improvements found while comparing HireSense with the reference repository, and preserve the complete comparison as an actionable Markdown roadmap.

## Scope

### 1. Make rich matching candidate-aware

`POST /matching/evaluate` already accepts `profile_id`, but the route discards it and always calls the matching orchestrator with `profile=None`. The matching page also loads the selected candidate profile but does not send its ID when requesting the rich evaluation.

The fix will:

- resolve an explicitly supplied `profile_id` through `ProfileService` at the API boundary;
- return HTTP 404 with `Profile not found` when an explicit ID does not exist;
- pass the resolved `CandidateProfile` to the matching orchestrator;
- preserve the current candidate-independent behavior when the field is omitted; and
- make the matching page include the currently selected profile ID in its evaluate request.

Resolving the profile in the route keeps persistence concerns outside the matching domain. It also avoids adding a repository dependency to the orchestrator.

### 2. Add optional candidate context to batch evaluation

`POST /matching/batch-evaluate` will accept an optional `profile_id`. The route will resolve it once and pass the resolved profile to `BatchEvaluationService.evaluate_batch`. The service will reuse the same immutable profile for each concurrent job evaluation.

The existing request shape remains valid. An omitted profile ID continues to pass `None`, so existing clients and workflows do not break. This change exposes the capability without forcing a profile-selection redesign into the quick-win scope.

### 3. Make test telemetry deterministic

The application enables OpenTelemetry by default. Tests that construct the full app without driving its lifespan can leave exporter worker threads alive, causing connection errors and writes to closed pytest streams after an otherwise successful suite.

An autouse test fixture will set `OTEL_ENABLED=false` for ordinary tests. Tests that verify default configuration will explicitly remove that test override, while observability unit/integration tests continue to exercise telemetry with their own explicit settings and providers. Runtime defaults and production behavior remain unchanged.

### 4. Correct stale framework documentation

README and contributor guidance currently say Angular 21 while the locked frontend uses Angular 22. Documentation and badges will be updated to Angular 22. No dependency upgrade is part of this work.

### 5. Preserve the full recommendation backlog

A detailed report will be added under `docs/analysis/`. It will include:

- the comparison baseline and verification evidence;
- strengths HireSense should preserve;
- all correctness, security, workflow, product, testing, CI, performance, and maintainability suggestions;
- priority, effort, expected impact, and dependencies;
- a recommended delivery sequence; and
- an implementation-status table identifying the quick wins completed in this change.

## Error handling

- Explicit unknown profile IDs produce HTTP 404 before any paid matching work begins.
- Batch job failures retain the current per-job failure isolation and zero-score fallback.
- No profile ID remains a supported state and is not treated as an error.

## Testing strategy

Tests will be written before implementation changes:

- route test proving `/matching/evaluate` passes the resolved profile;
- route test proving an unknown explicit profile returns 404 and never evaluates;
- batch route test proving a resolved profile reaches the batch service;
- batch service test proving the same profile reaches each orchestrator call;
- frontend component test proving `evaluate()` sends the selected profile ID;
- configuration test proving the application default remains telemetry-enabled despite the test override; and
- focused suites followed by the full backend lint/test suite and frontend format/typecheck/lint/test/build checks.

## Non-goals

The following findings remain in the roadmap because they require product policy, broader threat modeling, or larger workflow changes:

- deterministic work-authorization eligibility gates;
- system-wide prompt-injection trust boundaries;
- claims ledger and requirement-to-evidence matrix;
- generated-PDF ATS and rendering QA;
- interview-round tracking;
- application-centric follow-up reminders;
- guided onboarding and readiness scoring;
- personalized upskilling plans;
- a formal job-source adapter SDK;
- GitHub Actions policy and dependency-review changes; and
- major frontend component decomposition or new end-to-end coverage.

## Acceptance criteria

1. Rich evaluation scores a supplied candidate profile rather than silently ignoring it.
2. Unknown supplied profile IDs fail clearly with HTTP 404.
3. Batch evaluation can use one optional profile across all jobs.
4. Existing requests without profile IDs behave as before.
5. The matching UI sends its selected profile ID.
6. Test runs do not attempt to export application telemetry unless a telemetry test explicitly opts in.
7. Angular documentation matches the installed major version.
8. The complete comparison and recommendation backlog exists in one discoverable Markdown document.
