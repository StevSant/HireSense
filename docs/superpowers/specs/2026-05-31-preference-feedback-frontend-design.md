# Preference Feedback — Frontend Controls

**Date:** 2026-05-31
**Status:** Design proposed — light review recommended before planning (UX choices not yet brainstormed in depth)
**Depends on:** Phase 1 backend (merged) — the `/preference/feedback`, `/preference/explain`, `/preference/reset` endpoints

## Problem

The Phase 1 backend can learn taste and re-rank, but there is **no way for the user to give explicit feedback** — the only capture surface is the API. Without UI controls, the taste vector only ever moves from Phase 2 implicit signals; the immediate, intentional "more like this / not interested" loop the design promised is unreachable from the app.

## Goals

1. **Capture explicit feedback** on jobs: thumbs up / thumbs down / not-interested / more-like-this → `POST /preference/feedback`.
2. **Make the loop visible** — a small "why is this ranked here?" surface reading `GET /preference/explain`, and a reset.
3. **Fit existing Angular conventions** — standalone components, signals, OnPush, a root-injectable service using `environment.apiUrl`, matching the existing `core/services/*.service.ts` pattern.

## Current structure (observed)

- Job list page: `frontend/src/app/pages/ingestion/` (the `/jobs` endpoint is served by the ingestion router). Components include `job-detail-panel`, `job-filters`, `pagination`.
- `job-detail-panel.component.ts` is standalone, OnPush, uses `input`/`output`/`computed`/`signal`, injects `IngestionService`, and already exposes a `track = output<string>()` — i.e. it already emits job-level user actions. This is the natural home for feedback controls.
- Services live in `frontend/src/app/core/services/`, `@Injectable({ providedIn: 'root' })`, inject `HttpClient`, hit `` `${environment.apiUrl}/...` ``, return `Observable`s (see `tracking.service.ts`).
- Models live under `pages/<area>/models/` and `core/models/`.

## Decisions (proposed — confirm in review)

| Decision | Choice |
|---|---|
| Where controls live | On the **job detail panel** (primary) and optionally as compact icons on each list card. Start with the detail panel to limit surface area |
| Controls | `thumbs_up`, `thumbs_down`, `not_interested`, `more_like_this` — four actions; `not_interested` may visually hide/dim the job |
| Feedback affordance | Fire-and-forget POST with optimistic UI; toast/snackbar on failure; the control reflects the last action sent |
| Transparency surface | A small "Tuning" panel (e.g. in the ingestion page header or a settings drawer) showing `/explain` counts + drift, with a **Reset** button calling `POST /preference/reset` behind a confirm |
| Re-ranking refresh | After feedback, optionally re-fetch the job list so the new taste vector is reflected; debounce to avoid a fetch per click |

## Architecture

- **`PreferenceService`** (`core/services/preference.service.ts`, root-injectable):
  - `submitFeedback(jobId: string, kind: FeedbackKind): Observable<FeedbackSignal>` → `POST ${apiUrl}/preference/feedback` with `{ job_id, kind }`
  - `explain(): Observable<PreferenceExplanation>` → `GET ${apiUrl}/preference/explain`
  - `signals(): Observable<FeedbackSignal[]>` → `GET ${apiUrl}/preference/signals`
  - `reset(): Observable<void>` → `POST ${apiUrl}/preference/reset`
- **Models** (`pages/ingestion/models/` or a shared `core/models/`): `FeedbackKind` (string-union type), `FeedbackSignal`, `PreferenceExplanation` mirroring the backend response shapes.
- **Feedback controls component** (`pages/ingestion/components/feedback-controls/`): standalone, OnPush; `input` the `jobId`; emits/owns the four actions; calls `PreferenceService.submitFeedback`; reflects pending/last-sent state via signals. Embedded in `job-detail-panel`.
- **Tuning panel component** (`pages/ingestion/components/preference-tuning/`): reads `explain()`, renders counts + drift magnitude + active flag, and a guarded reset.
- Auth: requests go through the existing HTTP auth interceptor (the endpoints require auth), same as every other service — no special handling.

## Error handling & edge cases

- POST failure → non-blocking toast; do not lose the user's place; allow retry.
- Feedback on a job with no indexed embedding still 201s (backend stores it, no contribution) — UI need not special-case.
- Reset → confirm dialog; on success, refresh the tuning panel and (optionally) the list.
- Empty/`active:false` explain → render a neutral "No tuning yet — give feedback to personalize ranking" state.

## Testing

- Component tests (the project's existing Angular test setup): clicking each control calls `submitFeedback` with the right kind; failure shows the error affordance; the tuning panel renders counts from a mocked `explain()`; reset calls the endpoint behind confirmation.
- A lightweight service test asserting the correct URLs/bodies (HttpTestingController).

## Open questions for review

- List-card icons now, or detail-panel only first? (Proposal: detail-panel first.)
- Should `not_interested` immediately hide the job locally, and is that hide persistent across refetches (would need a backend "hidden" concept) or session-only? (Proposal: session-only dim for now; persistent hide is a separate feature.)
- Auto-refetch the list after feedback, or only on next manual refresh? (Proposal: debounced opt-in.)

## Out of scope

Backend "hidden jobs" persistence; per-card inline analytics; the LLM-phrased explanation (Phase 2 backend).
