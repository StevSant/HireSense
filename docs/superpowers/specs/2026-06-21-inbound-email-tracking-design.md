# Inbound Email → Tracking Signals — Design (Autopilot Phase 3)

**Date:** 2026-06-21
**Initiative:** [HireSense Autopilot](./2026-06-21-autopilot-initiative.md) — Phase 3
**Status:** Approved for planning
**Composes:** Phase 1 (scheduler) + Phase 2 (notifications). Independent of them for the core; uses them for automation + alerting.

## Goal

Detect status-changing recruiter emails (rejection, interview invite, offer) and
surface a one-click **proposed** tracking update — fed automatically by a periodic
inbox scan. The candidate confirms each signal; nothing changes an application's
status without an explicit click.

## Guiding decisions

1. **Detect-and-propose, NOT auto-apply.** An LLM misclassification that silently
   flips a live application to "rejected" is the worst failure mode. The pipeline
   produces *signals* in a review queue; confirming a signal calls the existing
   `TrackingService.update_status`. (Auto-apply for high-confidence signals is a
   deliberate future toggle, out of scope here.)
2. **Source = IMAP polling (config-gated) + a manual ingest endpoint.** Gmail
   OAuth in the backend is heavy and untestable without real Google credentials.
   IMAP (app-specific password) is lighter and, behind an `InboxReaderPort`, fully
   testable via a fake. The manual `POST /tracking/ingest-email` endpoint needs no
   email credentials, so the feature is usable and testable before IMAP is wired.
3. **Only active applications are matched** (status `applied` / `interviewing`).
   Unmatched or ambiguous signals are still recorded (unmatched) for manual linking.

## Non-goals

- Gmail/Google OAuth, webhook/inbound-parse providers (IMAP + manual only).
- Auto-applying status changes without confirmation (future toggle).
- Parsing emails for jobs NOT already tracked / creating new applications from
  email (v1 matches existing tracked applications only).
- Threading/conversation reconstruction — each email is classified independently.
- Calendar/interview-scheduling extraction (a later phase could add it).

## Architecture — new `inbox/` module (hexagonal)

### `domain/`
- `inbound_email.py` — `InboundEmail` (pure): `message_id: str`, `from_address: str`,
  `subject: str`, `body: str`, `received_at: datetime`.
- `email_signal.py` — `EmailSignalKind` enum: `rejection` | `interview` | `offer` |
  `other`. The classifier returns one.
- `classification.py` — `EmailClassification` (pure): `job_related: bool`,
  `kind: EmailSignalKind`, `company: str | None`, `role: str | None`,
  `confidence: float`.
- `detected_signal.py` — `DetectedSignal` (pure): `id`, `message_id`,
  `from_address`, `subject`, `received_at`, `kind`, `company`, `role`,
  `confidence`, `matched_application_id: UUID | None`, `proposed_status: str | None`,
  `state: SignalState` (`pending` | `applied` | `dismissed`), `created_at`.
- `signal_state.py` — `SignalState` enum.
- `email_classifier.py` — `EmailClassifier`: wraps a tracked LLM; `async classify(email: InboundEmail) -> EmailClassification`. Uses a structured-output prompt; on LLM error returns `job_related=False` (so a bad classify never crashes a scan).
- `application_matcher.py` — `ApplicationMatcher`: `match(classification, active_apps) -> (application_id | None, proposed_status | None)`. Fuzzy company match (normalized, case-insensitive substring/token overlap) restricted to active applications; maps `kind → ApplicationStatus` (`rejection→rejected`, `interview→interviewing`, `offer→offered`; `other→None`). Returns `(None, None)` on no/ambiguous match.
- `inbox_processing_service.py` — `InboxProcessingService`: orchestrates one scan.
  `async run() -> int` (count of NEW signals): reads emails (via `InboxReaderPort`),
  skips already-seen `message_id`s (dedup), classifies each, matches against the
  active tracked applications, persists a `DetectedSignal` (state `pending`) for
  each job-related email, returns the new-signal count. Also exposes
  `async ingest_one(email: InboundEmail) -> DetectedSignal | None` for the manual
  endpoint (returns None when not job-related).
- `ports/inbox_reader.py` — `InboxReaderPort` Protocol: `fetch_unseen() -> list[InboundEmail]`.
- `ports/detected_signal_repository.py` — `DetectedSignalRepository` Protocol:
  `add`, `list(state=None)`, `get`, `set_state(id, state)`, `exists_message_id(message_id) -> bool`.

### `infrastructure/`
- `imap_inbox_reader.py` — `ImapInboxReader` (implements `InboxReaderPort`) using
  `imaplib`; config-gated (blank host → returns `[]`, i.e. disabled). Reads a
  configurable folder, returns parsed `InboundEmail`s. Synchronous `imaplib`
  calls are wrapped via `asyncio.to_thread` at the call site in the service.
- `detected_signal_orm.py` + `detected_signal_repository.py` — `DetectedSignalOrm`
  (table `inbox_detected_signals`, unique index on `message_id`) + repo impl
  (extends `SqlRepository`). Registered in `infrastructure/registry.py`.

### `api/`
- `provider.py`, `dependencies.py`, `routes.py` (`router` re-export), all auth-gated:
  - `POST /tracking/ingest-email` — body `{from_address, subject, body, message_id?, received_at?}`; classifies + matches + stores a pending signal; returns the `DetectedSignal` (or 204 when not job-related). The manual / fallback source.
  - `GET /inbox/signals?state=` — the review queue.
  - `POST /inbox/signals/{id}/confirm` — applies the proposed status via
    `TrackingService.update_status` (only when the signal is matched + has a
    proposed status), sets state `applied`; 409 if unmatched/no proposed status.
  - `POST /inbox/signals/{id}/dismiss` — sets state `dismissed`.

> Routing note: `ingest-email` is mounted under the existing `/tracking` prefix
> (it produces tracking signals), while the review queue lives under a new
> `/inbox` prefix. Both are in the `inbox` module's router(s).

## Configuration (config.py + .env.example)

- `imap_host: str = ""`, `imap_port: int = 993`, `imap_username: str = ""`,
  `imap_password: str = ""`, `imap_folder: str = "INBOX"`, `imap_use_ssl: bool = True`.
  Blank `imap_host` → IMAP scanning disabled (the manual endpoint still works).
- `inbox_scan_schedule: str = "0 */2 * * *"` — cron for the scheduler `inbox_scan`
  job (informational like the other cadence strings; the scheduler reads it).
- `inbox_signal_match_min_confidence: float = 0.5` — classifications below this are
  recorded as `kind=other`/low-confidence and never get a proposed status (so they
  can't be one-click-applied; still visible for manual handling).

## Scheduler integration (Phase 1)

`build_scheduler` gains a 5th job `inbox_scan` (cron `inbox_scan_schedule`) whose
callable runs `InboxProcessingService.run()` and returns the new-signal count
(`count_items=int` identity). Wired only when an `inbox_processing_service` is
provided to `build_scheduler` (default `None` → job absent, Phase 1/2 unchanged).
When IMAP is disabled (`imap_host` blank) the job runs but processes `[]` (a
no-op returning 0) — harmless.

## Notifications integration (Phase 2)

When a scan produces ≥1 new signal, `InboxProcessingService` calls an injected
`notification_service.notify_inbox_signals(count)` (a new best-effort method on
`NotificationService`, mirroring the existing ones). Injected optionally; absent
→ no notification. The notify call is wrapped best-effort so it never fails a scan.

## Error handling

- Classifier LLM failure → `job_related=False` (email skipped, logged); never
  crashes a scan.
- IMAP failure → `ImapInboxReader.fetch_unseen` logs and returns `[]`; the scan
  records 0 and the scheduler job is SUCCESS (empty), not FAILURE.
- Confirm on an unmatched signal → 409 (nothing to apply).
- Dedup on `message_id` (unique index + `exists_message_id` check) so re-scans and
  retries don't create duplicate signals.
- All sends/scans best-effort; a notification failure never affects the scan.

## Frontend

A **Signals** review surface (a card/section in the tracking page, plus a route):
lists pending `DetectedSignal`s (sender, subject, detected kind, matched
application + proposed status, confidence) with **Confirm** and **Dismiss**
buttons; confirm calls the confirm endpoint and refreshes the tracking board.
Unmatched signals show "no match" and offer Dismiss only (manual linking is a
later enhancement). A per-domain `InboxService` wraps the calls; models in a
`.model.ts`. Standalone + signals + OnPush, mirroring prior phases.

## Migration & registry

New Alembic migration `034_add_inbox_detected_signals` (hand-written, numeric,
`down_revision="033"`) creating `inbox_detected_signals` with the unique
`message_id` index. `DetectedSignalOrm` imported in `infrastructure/registry.py`.
Post-merge: `uv run python -m alembic upgrade head` on the dev DB.

## Testing

- **Unit:** `ApplicationMatcher` (company fuzzy match; restricts to active; kind→status
  map; no/ambiguous match → unmatched); `EmailClassifier` maps a faked LLM
  structured result and returns `job_related=False` on LLM error; `SignalState`
  transitions; `InboxProcessingService` dedups by message_id and counts new signals
  (faked reader + repo + classifier).
- **Integration:** `POST /tracking/ingest-email` → pending signal (and 204 when not
  job-related); `confirm` → `update_status` recorded a transition + signal `applied`;
  `confirm` on unmatched → 409; `dismiss` → `dismissed`; `GET /inbox/signals`
  filters by state. In-memory SQLite + StaticPool + `require_auth` override.
  Scheduler: `inbox_scan` job present when the service is injected; runs via a fake
  `InboxReaderPort` and produces signals. No real IMAP/LLM in tests.

## Decomposition fallback

The IMAP adapter + the `inbox_scan` scheduler job + IMAP config form a separable
"automation layer" on top of the testable core (classifier + matcher + signal store
+ review API/UI + manual ingest). If the plan runs long, land the core first and the
IMAP/scheduler layer second.

## What this unblocks

- Phase 4 (autopilot pipeline) can treat confirmed interview signals as a trigger
  for interview-prep generation.
- A future auto-apply toggle and manual signal→application linking build on the
  `DetectedSignal` store.
