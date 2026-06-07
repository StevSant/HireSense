# Outreach Frontend — Design

**Epic:** #29 · **Children:** #30 (service + models), #31 (page — generate + record), #32 (follow-up nudges view)
**Depends on:** the existing `outreach` backend module (`/outreach/*` endpoints) and `applications` (to pick a target application).

## Context

The backend outreach loop (generate → record → nudge, copy-only) is built and tested; the
`2026-05-31-outreach-networking-design.md` doc lists "the frontend compose/timeline UI" as the
out-of-scope future work. This epic delivers that UI: a single Outreach page that lets the user
draft an on-brand message for a tracked application, record outreach actions, see the per-application
timeline, and act on due follow-up nudges.

## Backend contract (already implemented)

All routes are auth-gated under `/outreach`.

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/outreach/generate` | `{ application_id, contact_name?, channel? }` | `{ message }` — 503 if no LLM, 404 if app missing |
| POST | `/outreach/record` | `{ application_id, kind, message?, contact_name?, channel? }` | `OutreachEvent` (201) |
| GET | `/outreach/events?application_id=<uuid>` | — | `OutreachEvent[]` |
| POST | `/outreach/nudge` | — | `OutreachNudge[]` (due follow-ups) |

- `OutreachEvent { id, application_id, kind, contact_name?, channel?, message?, created_at }`
- `OutreachNudge { application_id, company, contact_name?, sent_at, days_since }`
- `OutreachEventKind = 'sent' | 'followed_up' | 'replied'`

## Frontend design

### #30 — service + models
- `pages/outreach/models/` (one interface per `.model.ts`, package convention): `outreach-event.model.ts`
  (`OutreachEvent`), `outreach-event-kind.model.ts` (`OutreachEventKind` union), `outreach-nudge.model.ts`
  (`OutreachNudge`), `generate-request.model.ts`, `generate-response.model.ts`, `record-request.model.ts`.
- `core/services/outreach.service.ts` (`@Injectable({providedIn:'root'})`, `inject(HttpClient)`,
  `base = ${environment.apiUrl}/outreach`): `generate(req)`, `record(req)`, `listEvents(applicationId)`,
  `dueFollowups()`. Mirrors `InterviewService`/`ApplicationsService` style exactly.

### #31 — Outreach page (generate + record), `pages/outreach/outreach.component.ts`
Standalone component, signal state, route `dashboard/outreach`, sidebar nav entry.
- **Target picker:** load applications via `ApplicationsService.list()`; a `<select>` of `title @ company`.
  Accept a `?application_id=` query param to preselect (so the applications page / detail can deep-link in).
- **Compose:** optional `contactName` + `channel` inputs → **Generate** calls `generate` and fills an
  editable `message` textarea (the user can tweak before recording). Surface the 503 ("generation
  unavailable") and 404 states as inline notices, not blank errors. Copy-to-clipboard button.
- **Record:** **Mark as sent** records `kind:'sent'` with the current message + contact + channel;
  buttons to record `followed_up` / `replied`. On success, refresh the timeline.
- **Timeline:** `listEvents(selectedId)` rendered newest-first with kind badge, contact/channel,
  relative time, and the message body. Empty + error states.

### #32 — follow-up nudges view (section on the same page)
- On load, `dueFollowups()` populates a "Needs a follow-up" list: company, contact, `days_since`
  ("sent N days ago"), each row links to that application and offers **Mark followed up** (records
  `followed_up` for that `application_id`, then removes it from the list and refreshes the timeline if
  it's the selected app). Empty state ("You're all caught up"). Error state.

### Wiring
- Add the lazy route to `app.routes.ts` under the `dashboard` children.
- Add a sidebar nav link in `dashboard.component.html` (same markup as siblings; an envelope/📨 icon).
- All HTTP subscriptions use `inject(DestroyRef)` + `takeUntilDestroyed` per the teardown standard.

## Testing
- `outreach.service.spec.ts`: each method hits the right URL/verb/body (HttpTestingController).
- `outreach.component.spec.ts`: generate happy path fills the message; 503 → notice; record sent →
  timeline refresh; nudges load + "mark followed up" removes the row. Services mocked.

## Out of scope (unchanged from backend doc)
Outbound send, inbound-reply inbox, first-class contacts entity. This is copy-only.
