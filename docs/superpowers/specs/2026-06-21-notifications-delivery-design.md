# Notifications / Delivery — Design (Autopilot Phase 2)

**Date:** 2026-06-21
**Initiative:** [HireSense Autopilot](./2026-06-21-autopilot-initiative.md) — Phase 2
**Status:** Approved for planning
**Depends on:** Phase 1 (scheduler) — shipped.

## Goal

When the scheduler produces a new-match digest, email it to the user; when a
scheduled job fails, email a short alert. Single-user, config-driven, and a
silent no-op when unconfigured — so enabling it is purely additive and Phase 1
behavior is unchanged when notifications are off.

## Non-goals

- Web push / browser notifications and an in-app notification center (later phases).
- Migrating the outreach module onto the shared sender beyond back-compat re-exports.
- Failure-alert throttling / digesting (every failure emails — acceptable safety net for now).
- HTML email templating frameworks — a simple text body (optionally a minimal
  HTML part) is sufficient.
- Multi-recipient / per-user routing — this is a single-user app (one admin from
  config; no users table, no per-user email).

## Configuration

Added to `config.py` + `.env.example`:

- `notification_email: str = ""` — recipient address. **Blank disables**
  notifications (sends become no-ops; the test endpoint returns 503). Mirrors
  the existing outreach `smtp_host`/`outreach_from_email` gating pattern.
- `notification_from_email: str = ""` — From address for notification email.
  When blank, bootstrap falls back to `smtp_username`.

Reuses the existing SMTP credentials: `smtp_host`, `smtp_port`, `smtp_username`,
`smtp_password`, `smtp_use_tls`.

## Shared email sender (consolidation)

A second email consumer now exists (outreach was the first), so the email
primitives move to the cross-cutting locations prescribed by `ARCHITECTURE.md`
(`ports/`, `adapters/`, kernel/shared types):

- `kernel/` ← `EmailMessage` (currently `outreach/domain/email_message.py`).
- `ports/email_sender.py` ← `EmailSenderPort`; `ports/` (or kernel) ← `EmailUnavailableError`.
- `adapters/smtp_email_sender.py` ← `SmtpEmailSender`.

**Back-compat:** the existing `outreach/domain/email_message.py`,
`outreach/ports/email_sender.py`, `outreach/infrastructure/smtp_email_sender.py`,
and `outreach/domain/email_unavailable_error.py` become **thin re-exports** of
the moved symbols, so all current outreach code and tests keep importing from
the same paths with no behavior change. Package `__init__.py` re-exports are
updated accordingly.

Notifications and outreach each construct their **own** `SmtpEmailSender`
instance (different From addresses) from the one shared class. The sender is
synchronous (`smtplib`); all notification sends run via `asyncio.to_thread` so
they never block the event loop.

## New module: `notifications/` (hexagonal)

### `domain/`
- `notification_service.py` — `NotificationService`:
  - `async notify_new_matches(digest) -> bool` — renders + sends the digest
    email. Returns `False` (no send) when disabled (blank recipient). A send
    error (e.g. `EmailUnavailableError`, SMTP failure) is **caught and logged**
    and returns `False` — it must never break a scheduled job.
  - `async notify_job_failure(job_name: str, detail: str | None) -> bool` — same
    contract; sends a short failure alert.
  - `async send_test() -> None` — sends a fixed test email. When disabled
    (blank recipient) or SMTP is unconfigured it raises `EmailUnavailableError`;
    the admin endpoint maps that to 503. Other send errors propagate the same way.
  - `enabled` property = `bool(notification_email)`.
  - Sends via an injected `EmailSenderPort` wrapped in `asyncio.to_thread`,
    constructing an `EmailMessage(to=notification_email, subject, body)`.
- `digest_email.py` — `render_digest_email(digest) -> tuple[str, str]` (subject,
  body). Pure. Body lists the top matches: title · company · score · URL, plus
  the run timestamp and match count.
- `job_failure_email.py` — `render_job_failure_email(job_name, detail) -> tuple[str, str]`.
  Pure.

### `api/`
- `provider.py` — `NotificationProvider` exposing the service.
- `dependencies.py` — `get_notification_service`.
- `routes.py` — router `/notifications` gated by `require_auth`:
  - `POST /notifications/test` *(admin)* → calls `send_test()`; 200 on success,
    503 when unconfigured/SMTP error.
  - `GET /notifications/status` → `{enabled: bool, recipient_masked: str | null}`
    (recipient masked like the LLM key masking already used in admin).

No `infrastructure/` in this module — it reuses the shared `SmtpEmailSender`
adapter, injected by bootstrap.

## Triggers

No event-bus indirection: there is a single consumer (email), so the
`NotificationService` is injected directly where it's needed (YAGNI; revisit if
multiple consumers appear).

### New matches
In `build_scheduler`, when a `notification_service` is provided, the
`autohunt_digest` job's callable is wrapped: it calls `autohunt_service.run()`,
and if the returned `Digest` has `job_count > 0`, awaits
`notification_service.notify_new_matches(digest)`, then returns the digest
(unchanged, so the existing `count_items=_digest_count` still records the count).
Empty digests send nothing. When no `notification_service` is provided, the job
is wired exactly as in Phase 1.

### Failures
`JobRunner` gains an optional `failure_notifier` parameter typed to a new
`scheduler.domain.ports` Protocol (`JobFailureNotifier` with
`async notify_job_failure(job_name, detail)`), so the scheduler module stays
independent of `notifications`. In the FAILURE branch, after recording the
`JobRun`, it awaits `failure_notifier.notify_job_failure(name, detail)` inside a
try/except that swallows + logs notifier errors (a notification failure must
never change the job outcome or raise). When `failure_notifier` is `None`
(default), behavior is byte-identical to Phase 1. `NotificationService`
satisfies this Protocol structurally.

## Wiring

- `bootstrap/notifications.py` — `build_notifications(settings, ...) ->
  NotificationBuild(provider, service)`. Builds the shared `SmtpEmailSender`
  (From = `notification_from_email or smtp_username`) and the
  `NotificationService`. Always builds (the service self-disables on blank
  recipient) so the router and triggers wire uniformly.
- `main.py` — builds notifications **before** `build_scheduler`; passes
  `notification_service` into `build_scheduler`; sets `app.state.notifications`;
  mounts the notifications router.
- `build_scheduler` gains an optional `notification_service` keyword param
  (default `None`) used to wrap the autohunt job and to pass `failure_notifier`
  into the `JobRunner`.

## Error handling

- Notification sends are best-effort: disabled or failing sends are logged and
  swallowed on the digest/failure paths; only `send_test()` surfaces errors (→ 503).
- A notifier exception inside `JobRunner` is caught so the job's recorded outcome
  is never altered.
- Sends run off the event loop via `asyncio.to_thread`.

## Frontend

A minimal admin **Notifications** page under `pages/admin/`, mirroring the
Phase 1 scheduler page: shows status (enabled / masked recipient from
`GET /notifications/status`) and a "Send test email" button (`POST
/notifications/test`) with success/failure feedback. Adds one nav entry. A
per-domain `NotificationService` (frontend) wraps the two calls; models in a
`.model.ts`.

## Testing

- **Unit:** `render_digest_email` includes each entry's title/company/score/URL
  + count; `render_job_failure_email` includes the job name + detail.
  `NotificationService`: disabled → no-op returns `False` and never calls the
  sender; enabled → constructs the right `EmailMessage` and calls the sender;
  sender raising `EmailUnavailableError` on the digest path → returns `False`
  (no raise); `send_test()` propagates the error.
- **Integration:** `POST /notifications/test` returns 200 with a fake sender and
  503 when unconfigured; `GET /notifications/status` reflects enabled/masked
  recipient. Scheduler: a `JobRunner` FAILURE invokes the injected
  `failure_notifier`; the wrapped autohunt job calls `notify_new_matches` only
  when `job_count > 0`. Uses the in-memory SQLite + `StaticPool` + `require_auth`
  / `require_admin` override conventions.
- Back-compat: existing outreach email tests still pass against the re-exported
  symbols (no changes to those tests).

## What this unblocks

- Phase 4 (autopilot pipeline) reuses `NotificationService` for the review-queue
  "drafts ready" notification.
- Future channels (web push, in-app center) can subscribe to the same triggers.
