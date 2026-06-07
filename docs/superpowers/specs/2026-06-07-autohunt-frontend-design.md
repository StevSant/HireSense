# Auto-Hunt Digests Frontend — Design

**Issue:** #33 · **Builds on:** the `autohunt` backend (`2026-05-31-proactive-auto-hunt-design.md`, which deferred "a frontend view" to a later phase — this is it).

## Context

The backend computes and persists periodic digests of the top *new* taste-ranked matches above a
quality floor (external cron drives `POST /autohunt/run`). The data is in-app via GET endpoints but
has no UI. This delivers the glanceable view: "5 strong new roles since yesterday."

## Backend contract (implemented, auth-gated, base `${environment.apiUrl}/autohunt`)

| Method | Path | Returns |
|---|---|---|
| GET | `/autohunt/digests/latest` | `Digest` **or HTTP 204** (no digests yet) |
| GET | `/autohunt/digests?limit=20` | `Digest[]` (newest first) |
| POST | `/autohunt/run` | `Digest` (manual trigger; normally cron) |

- `Digest { id, created_at: string|null, cutoff_at: string, entries: DigestEntry[], job_count: number }`
- `DigestEntry { job_id: string, title: string, company: string, url: string|null, score: number }`

## Frontend design

### Service + models (`#33`)
- `pages/autohunt/models/`: `digest-entry.model.ts` (`DigestEntry`), `digest.model.ts` (`Digest`).
- `core/services/autohunt.service.ts` (`providedIn:'root'`, `inject(HttpClient)`,
  `base = ${environment.apiUrl}/autohunt`): `latest(): Observable<Digest | null>` (map HTTP 204 /
  empty body → `null`), `listRecent(limit = 20): Observable<Digest[]>`, `run(): Observable<Digest>`.
  Mirror `OutreachService`/`InterviewService` style.

### Page `pages/autohunt/autohunt.component.ts` (+ html/scss), route `dashboard/autohunt`, sidebar nav
- **Latest digest** panel (hero): `latest()` on init. Header shows "N new matches since {cutoff_at}"
  (relative) and the run time; entries rendered as rows — `title @ company`, score as a percentage
  badge, an external link to `entry.url` (when present) and an **Optimize CV** deep-link to
  `/dashboard/optimization?job_id={job_id}` (reuse the existing prefill flow). 204 → empty state
  ("No digests yet — runs are scheduled via cron, or trigger one now").
- **Run now** button → `run()`; on success prepend/refresh latest + history; disable while running;
  surface errors inline. (Manual convenience; cron is the normal trigger.)
- **History** list: `listRecent()` — each digest a collapsible row (date + `job_count`), expandable
  to its entries. Empty + error states.

### Wiring
- Lazy route under `dashboard` children in `app.routes.ts`; sidebar nav link in
  `dashboard.component.html` (radar/🛰️-style icon, same markup as siblings).
- All subscriptions use `inject(DestroyRef)` + `takeUntilDestroyed` per the teardown standard.

## Testing
- `autohunt.service.spec.ts`: each method's URL/verb; `latest()` maps 204 → `null`.
- `autohunt.component.spec.ts`: latest renders entries; 204 → empty state; `run()` refreshes;
  history expand. Services mocked.

## Out of scope
Pre-drafting applications from digest entries (separate follow-up per the backend doc); email/push.
