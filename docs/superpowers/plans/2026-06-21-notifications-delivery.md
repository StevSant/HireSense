# Notifications / Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Email the user a digest when the scheduler finds new matches, and a short alert when a scheduled job fails — config-driven and a silent no-op when unconfigured.

**Architecture:** Promote the existing email primitives to the cross-cutting `kernel`/`ports`/`adapters` packages (outreach keeps working via re-exports). Add a `notifications/` hexagonal module with a `NotificationService` (pure render functions + an injected `EmailSenderPort` run via `asyncio.to_thread`). Trigger it directly (no event bus): wrap the scheduler's `autohunt_digest` job to notify on new matches, and give `JobRunner` an optional failure-notifier port.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, `smtplib` (existing `SmtpEmailSender`), Angular 21 (standalone + signals), Vitest.

**Spec:** [`docs/superpowers/specs/2026-06-21-notifications-delivery-design.md`](../specs/2026-06-21-notifications-delivery-design.md)

## Global Constraints

- Single-user app (one admin from config; no users table). Recipient is a config value.
- `notification_email` blank → notifications are a silent no-op (sends return `False`); the test endpoint returns 503. Mirrors outreach's SMTP gating.
- The email-primitive move MUST keep all existing outreach import paths working via thin re-exports (no outreach behavior change, no outreach test changes).
- All notification sends run via `asyncio.to_thread` (the sender is synchronous `smtplib`) — never block the event loop.
- No event-bus indirection — single consumer; inject `NotificationService` directly.
- When `build_scheduler` gets no `notification_service` and `JobRunner` gets no `failure_notifier`, Phase 1 behavior is byte-identical.
- One class/enum/constant per file; every package `__init__.py` re-exports public symbols; import from the contextual package.
- `domain/` imports no framework packages and nothing from `infrastructure/`.
- Tests: `cd backend && uv run python -m pytest <path> -v` (never bare `uv run pytest`). Integration tests build the app over in-memory SQLite with `StaticPool` and override `require_auth`/`require_admin`.
- Lint: `cd backend && uv run ruff check .`. Do NOT run `ruff format .`. Frontend: `npx ng lint` before pushing (CI runs it; `npm test`/`build` skip it).
- No hardcoded values — tunables go through `config.py` + `.env.example`.
- Working tree has PRE-EXISTING unrelated modified/untracked files. Stage ONLY each task's files with explicit paths. Never `git add -A`/`git add .`.

---

## File Structure

**Shared email primitives (moved; outreach files become re-exports):**
- `backend/src/hiresense/kernel/email_message.py` — `EmailMessage` (moved here).
- `backend/src/hiresense/ports/email_unavailable_error.py` — `EmailUnavailableError` (moved).
- `backend/src/hiresense/ports/email_sender.py` — `EmailSenderPort` (moved).
- `backend/src/hiresense/adapters/smtp_email_sender.py` — `SmtpEmailSender` (moved).
- Re-export shims: `outreach/domain/email_message.py`, `outreach/domain/email_unavailable_error.py`, `outreach/ports/email_sender.py`, `outreach/infrastructure/smtp_email_sender.py`.

**New `notifications/` module:**
- `domain/notification_service.py` — `NotificationService`.
- `domain/digest_email.py` — `render_digest_email`.
- `domain/job_failure_email.py` — `render_job_failure_email`.
- `domain/__init__.py`, `__init__.py` — re-exports.
- `api/provider.py`, `api/dependencies.py`, `api/routes.py`, `api/__init__.py`.

**Scheduler integration:**
- `scheduler/domain/ports/job_failure_notifier.py` — `JobFailureNotifier` Protocol.
- Modify `scheduler/domain/job_runner.py` (optional `failure_notifier`).
- Modify `bootstrap/scheduler.py` (optional `notification_service`).

**Wiring & config:**
- `bootstrap/notifications.py` — `build_notifications`.
- Modify `config.py`, `.env.example`, `main.py`, `bootstrap/__init__.py`.

**Frontend:**
- `core/models/notification.model.ts`, `core/services/notification.service.ts`.
- `pages/admin/notifications/notifications.component.{ts,html,scss,spec.ts}`.
- Modify `app.routes.ts`, `core/nav/hubs.const.ts`.

---

## Task 1: Promote email primitives to shared packages (with re-exports)

**Files:**
- Create: `backend/src/hiresense/kernel/email_message.py`, `backend/src/hiresense/ports/email_unavailable_error.py`, `backend/src/hiresense/ports/email_sender.py`, `backend/src/hiresense/adapters/smtp_email_sender.py`
- Modify: `backend/src/hiresense/kernel/__init__.py`, `backend/src/hiresense/ports/__init__.py`, `backend/src/hiresense/adapters/__init__.py`
- Modify (→ re-export shims): `backend/src/hiresense/outreach/domain/email_message.py`, `backend/src/hiresense/outreach/domain/email_unavailable_error.py`, `backend/src/hiresense/outreach/ports/email_sender.py`, `backend/src/hiresense/outreach/infrastructure/smtp_email_sender.py`
- Test: `backend/tests/unit/test_shared_email_primitives.py`

**Interfaces:**
- Produces: `from hiresense.kernel import EmailMessage` (fields `to: str`, `subject: str`, `body: str`); `from hiresense.ports import EmailSenderPort, EmailUnavailableError`; `from hiresense.adapters import SmtpEmailSender` (ctor kwargs `host, port, username, password, from_email, use_tls`; method `send(message: EmailMessage) -> None`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_shared_email_primitives.py
from hiresense.adapters import SmtpEmailSender
from hiresense.kernel import EmailMessage
from hiresense.ports import EmailSenderPort, EmailUnavailableError

# Back-compat: outreach paths must resolve to the SAME objects.
from hiresense.outreach.domain import EmailMessage as OutreachEmailMessage
from hiresense.outreach.domain import EmailUnavailableError as OutreachErr
from hiresense.outreach.infrastructure import SmtpEmailSender as OutreachSender
from hiresense.outreach.ports import EmailSenderPort as OutreachPort


def test_shared_symbols_importable_and_constructible():
    msg = EmailMessage(to="a@b.com", subject="s", body="b")
    assert (msg.to, msg.subject, msg.body) == ("a@b.com", "s", "b")
    assert issubclass(EmailUnavailableError, RuntimeError)


def test_outreach_reexports_are_identical_objects():
    assert OutreachEmailMessage is EmailMessage
    assert OutreachErr is EmailUnavailableError
    assert OutreachSender is SmtpEmailSender
    assert OutreachPort is EmailSenderPort


def test_smtp_sender_raises_when_unconfigured():
    sender = SmtpEmailSender(host="", port=587, username="", password="", from_email="", use_tls=True)
    try:
        sender.send(EmailMessage(to="a@b.com", subject="s", body="b"))
        assert False, "expected EmailUnavailableError"
    except EmailUnavailableError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/test_shared_email_primitives.py -v`
Expected: FAIL — `ImportError: cannot import name 'EmailMessage' from 'hiresense.kernel'`.

- [ ] **Step 3: Create the shared modules**

`backend/src/hiresense/kernel/email_message.py`:

```python
from __future__ import annotations

from pydantic import BaseModel


class EmailMessage(BaseModel):
    """A plain-text email to send via an EmailSenderPort."""

    to: str
    subject: str
    body: str
```

`backend/src/hiresense/ports/email_unavailable_error.py`:

```python
from __future__ import annotations


class EmailUnavailableError(RuntimeError):
    """Raised when email can't be sent because SMTP isn't configured.

    The API layer maps this to HTTP 503.
    """
```

`backend/src/hiresense/ports/email_sender.py`:

```python
from __future__ import annotations

from typing import Protocol

from hiresense.kernel import EmailMessage


class EmailSenderPort(Protocol):
    """Sends an email. Implementations raise EmailUnavailableError when sending
    isn't possible (e.g. SMTP not configured)."""

    def send(self, message: EmailMessage) -> None: ...
```

`backend/src/hiresense/adapters/smtp_email_sender.py`:

```python
from __future__ import annotations

import smtplib
from email.message import EmailMessage as MimeEmailMessage

from hiresense.kernel import EmailMessage
from hiresense.ports import EmailUnavailableError


class SmtpEmailSender:
    """Sends email over SMTP. Config-gated: when host/from are unset it raises
    EmailUnavailableError instead of pretending to send."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        use_tls: bool,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_email = from_email
        self._use_tls = use_tls

    def send(self, message: EmailMessage) -> None:
        if not self._host or not self._from_email:
            raise EmailUnavailableError("SMTP is not configured")
        mime = MimeEmailMessage()
        mime["From"] = self._from_email
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.body)
        with smtplib.SMTP(self._host, self._port) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(mime)
```

- [ ] **Step 4: Update the shared package `__init__.py` files**

In `backend/src/hiresense/kernel/__init__.py`, add the import (keep entries sorted) and add `"EmailMessage"` to `__all__`:

```python
from hiresense.kernel.email_message import EmailMessage
```

In `backend/src/hiresense/ports/__init__.py`, add (near the other imports) and add both names to `__all__` if the file has one:

```python
from hiresense.ports.email_sender import EmailSenderPort
from hiresense.ports.email_unavailable_error import EmailUnavailableError
```

Replace `backend/src/hiresense/adapters/__init__.py` (currently just a docstring) with:

```python
"""HireSense - cross-cutting adapters."""

from hiresense.adapters.smtp_email_sender import SmtpEmailSender

__all__ = ["SmtpEmailSender"]
```

- [ ] **Step 5: Convert the outreach files to re-export shims**

`backend/src/hiresense/outreach/domain/email_message.py`:

```python
from hiresense.kernel import EmailMessage

__all__ = ["EmailMessage"]
```

`backend/src/hiresense/outreach/domain/email_unavailable_error.py`:

```python
from hiresense.ports import EmailUnavailableError

__all__ = ["EmailUnavailableError"]
```

`backend/src/hiresense/outreach/ports/email_sender.py`:

```python
from hiresense.ports import EmailSenderPort

__all__ = ["EmailSenderPort"]
```

`backend/src/hiresense/outreach/infrastructure/smtp_email_sender.py`:

```python
from hiresense.adapters import SmtpEmailSender

__all__ = ["SmtpEmailSender"]
```

- [ ] **Step 6: Run tests to verify they pass (incl. outreach regression)**

Run: `cd backend && uv run python -m pytest tests/unit/test_shared_email_primitives.py tests/unit/outreach tests/integration/test_outreach_endpoints.py -v`
Expected: PASS — new test green AND all existing outreach tests still green (re-exports preserved).

- [ ] **Step 7: Commit**

```bash
git add backend/src/hiresense/kernel/email_message.py backend/src/hiresense/kernel/__init__.py backend/src/hiresense/ports/email_unavailable_error.py backend/src/hiresense/ports/email_sender.py backend/src/hiresense/ports/__init__.py backend/src/hiresense/adapters/smtp_email_sender.py backend/src/hiresense/adapters/__init__.py backend/src/hiresense/outreach/domain/email_message.py backend/src/hiresense/outreach/domain/email_unavailable_error.py backend/src/hiresense/outreach/ports/email_sender.py backend/src/hiresense/outreach/infrastructure/smtp_email_sender.py backend/tests/unit/test_shared_email_primitives.py
git commit -m "refactor(email): promote email sender to shared kernel/ports/adapters with re-exports"
```

---

## Task 2: Config — notification settings

**Files:**
- Modify: `backend/src/hiresense/config.py`, `backend/.env.example`
- Test: `backend/tests/unit/test_settings_notifications.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_settings_notifications.py
from hiresense.config import Settings


def test_notification_settings_default_blank():
    s = Settings()
    assert s.notification_email == ""
    assert s.notification_from_email == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/test_settings_notifications.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'notification_email'`.

- [ ] **Step 3: Add the settings**

In `config.py`, after the SMTP block (`outreach_from_email`), add:

```python
    # --- Notifications (Autopilot Phase 2: digest + failure-alert email) ---
    # Recipient for scheduler digest/failure emails. BLANK disables notifications
    # (sends become no-ops; POST /notifications/test returns 503). Reuses the
    # smtp_* credentials above.
    notification_email: str = ""
    # From address for notification email. Falls back to smtp_username when blank.
    notification_from_email: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/test_settings_notifications.py -v`
Expected: PASS.

- [ ] **Step 5: Update `.env.example`**

Append to `backend/.env.example`:

```dotenv
# --- Notifications (Autopilot Phase 2) ---
# Recipient for scheduler digest + job-failure emails. Blank disables. Reuses SMTP_* above.
NOTIFICATION_EMAIL=
# From address for notification email (falls back to SMTP_USERNAME when blank).
NOTIFICATION_FROM_EMAIL=
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/config.py backend/.env.example backend/tests/unit/test_settings_notifications.py
git commit -m "feat(notifications): add notification_email + notification_from_email config"
```

---

## Task 3: Notifications domain — email render functions

**Files:**
- Create: `backend/src/hiresense/notifications/__init__.py` (empty), `backend/src/hiresense/notifications/domain/digest_email.py`, `backend/src/hiresense/notifications/domain/job_failure_email.py`, `backend/src/hiresense/notifications/domain/__init__.py`
- Test: `backend/tests/unit/notifications/test_email_render.py` (+ `backend/tests/unit/notifications/__init__.py`)

**Interfaces:**
- Produces: `render_digest_email(digest) -> tuple[str, str]` (subject, body); `render_job_failure_email(job_name: str, detail: str | None) -> tuple[str, str]`. `digest` is `hiresense.autohunt.domain.Digest` with `.entries: list[DigestEntry]` (fields `title`, `company`, `url: str | None`, `score: float`) and `.job_count: int`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/notifications/test_email_render.py
from hiresense.autohunt.domain import Digest, DigestEntry
from hiresense.notifications.domain import render_digest_email, render_job_failure_email


def _digest():
    return Digest(
        cutoff_at=None,
        job_count=2,
        entries=[
            DigestEntry(job_id="1", title="Senior Python Dev", company="Acme", url="http://x/1", score=0.91),
            DigestEntry(job_id="2", title="Backend Engineer", company="Globex", url=None, score=0.84),
        ],
    )


def test_digest_email_lists_each_match():
    subject, body = render_digest_email(_digest())
    assert "2" in subject  # match count in the subject
    assert "Senior Python Dev" in body
    assert "Acme" in body
    assert "Backend Engineer" in body
    assert "Globex" in body
    assert "http://x/1" in body  # link present when url is set


def test_job_failure_email_includes_name_and_detail():
    subject, body = render_job_failure_email("ingestion_fetch", "connection refused")
    assert "ingestion_fetch" in subject or "ingestion_fetch" in body
    assert "connection refused" in body
```

Note: `Digest.cutoff_at` is required; the test passes `None` — confirm `Digest` accepts `cutoff_at=None`. If `Digest` rejects `None`, pass a real datetime: `from datetime import datetime, timezone` then `cutoff_at=datetime.now(timezone.utc)`. (The model in `autohunt/domain/digest.py` declares `cutoff_at: datetime`, so use a real datetime in the test.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/notifications/test_email_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hiresense.notifications'`.

- [ ] **Step 3: Implement the render functions**

`backend/src/hiresense/notifications/__init__.py`: empty file.

`backend/src/hiresense/notifications/domain/digest_email.py`:

```python
from __future__ import annotations

from typing import Any


def render_digest_email(digest: Any) -> tuple[str, str]:
    """Render a new-matches digest into (subject, plain-text body)."""
    count = digest.job_count
    subject = f"HireSense: {count} new job match{'es' if count != 1 else ''}"
    lines = [f"{count} new match{'es' if count != 1 else ''} found:", ""]
    for entry in digest.entries:
        score_pct = round(entry.score * 100)
        line = f"- {entry.title} · {entry.company} ({score_pct}%)"
        if entry.url:
            line += f"\n  {entry.url}"
        lines.append(line)
    lines.append("")
    lines.append("Open HireSense to review and apply.")
    return subject, "\n".join(lines)
```

`backend/src/hiresense/notifications/domain/job_failure_email.py`:

```python
from __future__ import annotations


def render_job_failure_email(job_name: str, detail: str | None) -> tuple[str, str]:
    """Render a scheduled-job failure alert into (subject, plain-text body)."""
    subject = f"HireSense: scheduled job '{job_name}' failed"
    body = (
        f"The scheduled job '{job_name}' failed during its last run.\n\n"
        f"Error: {detail or '(no detail)'}\n\n"
        "Check the scheduler admin page for run history."
    )
    return subject, body
```

`backend/src/hiresense/notifications/domain/__init__.py`:

```python
from hiresense.notifications.domain.digest_email import render_digest_email
from hiresense.notifications.domain.job_failure_email import render_job_failure_email

__all__ = ["render_digest_email", "render_job_failure_email"]
```

- [ ] **Step 4: Fix the test's `cutoff_at` and run to verify it passes**

Edit the test's `_digest()` to use a real datetime (`cutoff_at=datetime.now(timezone.utc)`, importing `datetime, timezone`).

Run: `cd backend && uv run python -m pytest tests/unit/notifications/test_email_render.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/notifications/__init__.py backend/src/hiresense/notifications/domain backend/tests/unit/notifications
git commit -m "feat(notifications): add digest + job-failure email render functions"
```

---

## Task 4: Notifications domain — NotificationService

**Files:**
- Create: `backend/src/hiresense/notifications/domain/notification_service.py`
- Modify: `backend/src/hiresense/notifications/domain/__init__.py`
- Test: `backend/tests/unit/notifications/test_notification_service.py`

**Interfaces:**
- Consumes: `render_digest_email`, `render_job_failure_email`; `from hiresense.kernel import EmailMessage`; `from hiresense.ports import EmailUnavailableError`; an `EmailSenderPort`-shaped sender (`send(EmailMessage)`).
- Produces: `NotificationService(*, sender, to_email: str)`; `async notify_new_matches(digest) -> bool`; `async notify_job_failure(job_name, detail) -> bool`; `async send_test() -> None`; property `enabled: bool`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/notifications/test_notification_service.py
from datetime import datetime, timezone

import pytest

from hiresense.autohunt.domain import Digest, DigestEntry
from hiresense.notifications.domain import NotificationService
from hiresense.ports import EmailUnavailableError


class _Sender:
    def __init__(self, raise_exc=None):
        self.sent = []
        self._raise = raise_exc

    def send(self, message):
        if self._raise is not None:
            raise self._raise
        self.sent.append(message)


def _digest():
    return Digest(
        cutoff_at=datetime.now(timezone.utc),
        job_count=1,
        entries=[DigestEntry(job_id="1", title="Dev", company="Acme", url=None, score=0.9)],
    )


@pytest.mark.asyncio
async def test_disabled_when_recipient_blank_is_noop():
    sender = _Sender()
    svc = NotificationService(sender=sender, to_email="")
    assert svc.enabled is False
    assert await svc.notify_new_matches(_digest()) is False
    assert await svc.notify_job_failure("ingestion_fetch", "boom") is False
    assert sender.sent == []


@pytest.mark.asyncio
async def test_enabled_sends_to_recipient():
    sender = _Sender()
    svc = NotificationService(sender=sender, to_email="me@x.com")
    assert await svc.notify_new_matches(_digest()) is True
    assert len(sender.sent) == 1
    assert sender.sent[0].to == "me@x.com"
    assert "new job match" in sender.sent[0].subject


@pytest.mark.asyncio
async def test_send_error_on_digest_path_is_swallowed():
    sender = _Sender(raise_exc=EmailUnavailableError("smtp down"))
    svc = NotificationService(sender=sender, to_email="me@x.com")
    assert await svc.notify_new_matches(_digest()) is False  # no raise


@pytest.mark.asyncio
async def test_send_test_raises_when_disabled():
    svc = NotificationService(sender=_Sender(), to_email="")
    with pytest.raises(EmailUnavailableError):
        await svc.send_test()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/notifications/test_notification_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'NotificationService'`.

- [ ] **Step 3: Implement NotificationService**

`backend/src/hiresense/notifications/domain/notification_service.py`:

```python
from __future__ import annotations

import asyncio
import logging
from typing import Any

from hiresense.kernel import EmailMessage
from hiresense.notifications.domain.digest_email import render_digest_email
from hiresense.notifications.domain.job_failure_email import render_job_failure_email
from hiresense.ports import EmailUnavailableError

logger = logging.getLogger(__name__)


class NotificationService:
    """Sends digest + failure-alert email. Disabled (blank recipient) → no-op.
    Best-effort: send errors on the notify_* paths are logged and swallowed so a
    notification failure never breaks a scheduled job. send_test() lets errors
    propagate so the admin endpoint can surface them as 503."""

    def __init__(self, *, sender: Any, to_email: str) -> None:
        self._sender = sender
        self._to = to_email

    @property
    def enabled(self) -> bool:
        return bool(self._to)

    def masked_recipient(self) -> str | None:
        """Masked recipient for the status API (never exposes the raw address)."""
        if not self._to:
            return None
        name, _, domain = self._to.partition("@")
        head = name[0] if name else ""
        return f"{head}***@{domain}" if domain else f"{head}***"

    async def notify_new_matches(self, digest: Any) -> bool:
        subject, body = render_digest_email(digest)
        return await self._safe_send(subject, body)

    async def notify_job_failure(self, job_name: str, detail: str | None) -> bool:
        subject, body = render_job_failure_email(job_name, detail)
        return await self._safe_send(subject, body)

    async def send_test(self) -> None:
        if not self.enabled:
            raise EmailUnavailableError("Notifications are not configured (blank recipient)")
        await self._send("HireSense: test notification", "This is a HireSense test notification.")

    async def _safe_send(self, subject: str, body: str) -> bool:
        if not self.enabled:
            return False
        try:
            await self._send(subject, body)
            return True
        except Exception:  # noqa: BLE001 - notifications are best-effort
            logger.exception("Notification send failed")
            return False

    async def _send(self, subject: str, body: str) -> None:
        await asyncio.to_thread(
            self._sender.send, EmailMessage(to=self._to, subject=subject, body=body)
        )
```

Update `backend/src/hiresense/notifications/domain/__init__.py`:

```python
from hiresense.notifications.domain.digest_email import render_digest_email
from hiresense.notifications.domain.job_failure_email import render_job_failure_email
from hiresense.notifications.domain.notification_service import NotificationService

__all__ = ["NotificationService", "render_digest_email", "render_job_failure_email"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/notifications/test_notification_service.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/notifications/domain backend/tests/unit/notifications/test_notification_service.py
git commit -m "feat(notifications): add NotificationService (best-effort send, disabled no-op)"
```

---

## Task 5: Notifications API — provider, dependencies, routes

**Files:**
- Create: `backend/src/hiresense/notifications/api/provider.py`, `backend/src/hiresense/notifications/api/dependencies.py`, `backend/src/hiresense/notifications/api/routes.py`, `backend/src/hiresense/notifications/api/__init__.py`
- Test: `backend/tests/integration/test_notifications_endpoints.py`

**Interfaces:**
- Consumes: `NotificationService`; `from hiresense.ports import EmailUnavailableError`; `require_auth`, `require_admin`.
- Produces: `NotificationProvider(service)` with `get_service()`; `get_notification_service(request)`; router with `POST /notifications/test` (admin), `GET /notifications/status`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_notifications_endpoints.py
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import require_admin, require_auth
from hiresense.notifications.api import router as notifications_router
from hiresense.notifications.api.dependencies import get_notification_service
from hiresense.notifications.domain import NotificationService


class _Sender:
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)


def _build_app(to_email: str):
    service = NotificationService(sender=_Sender(), to_email=to_email)
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "u"
    app.dependency_overrides[require_admin] = lambda: {"role": "admin"}
    app.dependency_overrides[get_notification_service] = lambda: service
    app.include_router(notifications_router)
    return app


@pytest.mark.asyncio
async def test_status_reports_enabled_and_masked_recipient():
    app = _build_app("alice@example.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/notifications/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["recipient_masked"] is not None
    assert "alice@example.com" not in body["recipient_masked"]  # masked, not raw


@pytest.mark.asyncio
async def test_test_endpoint_sends_when_enabled():
    app = _build_app("alice@example.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post("/notifications/test")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_test_endpoint_503_when_disabled():
    app = _build_app("")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post("/notifications/test")
    assert resp.status_code == 503
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/integration/test_notifications_endpoints.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hiresense.notifications.api'`.

- [ ] **Step 3: Implement provider + dependencies**

`backend/src/hiresense/notifications/api/provider.py`:

```python
from __future__ import annotations

from hiresense.notifications.domain import NotificationService


class NotificationProvider:
    def __init__(self, service: NotificationService) -> None:
        self._service = service

    def get_service(self) -> NotificationService:
        return self._service
```

`backend/src/hiresense/notifications/api/dependencies.py`:

```python
from __future__ import annotations

from fastapi import Request

from hiresense.notifications.domain import NotificationService


def get_notification_service(request: Request) -> NotificationService:
    return request.app.state.notifications.get_service()
```

- [ ] **Step 4: Implement routes + `__init__`**

`backend/src/hiresense/notifications/api/routes.py`:

```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from hiresense.identity.api.dependencies import require_admin, require_auth
from hiresense.notifications.api.dependencies import get_notification_service
from hiresense.notifications.domain import NotificationService
from hiresense.ports import EmailUnavailableError

router = APIRouter(
    prefix="/notifications", tags=["notifications"], dependencies=[Depends(require_auth)]
)


class NotificationStatus(BaseModel):
    enabled: bool
    recipient_masked: str | None


@router.get("/status", response_model=NotificationStatus)
def status(
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationStatus:
    return NotificationStatus(
        enabled=service.enabled, recipient_masked=service.masked_recipient()
    )


@router.post("/test", status_code=200)
async def send_test(
    service: Annotated[NotificationService, Depends(get_notification_service)],
    _admin: Annotated[dict, Depends(require_admin)],
) -> dict[str, bool]:
    try:
        await service.send_test()
    except EmailUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"sent": True}
```

> Accessing `service._to` from the route is awkward. Cleaner: add a public
> `masked_recipient` property to `NotificationService` returning the masked
> string (move `_mask` into the service). If you prefer that, add to
> `NotificationService`: a `masked_recipient(self) -> str | None` method using the
> same masking, and call it from the route instead of touching `_to`. Either is
> acceptable; prefer the public method to avoid the `# noqa: SLF001`.

`backend/src/hiresense/notifications/api/__init__.py`:

```python
from hiresense.notifications.api.routes import router

__all__ = ["router"]
```

(`status` uses the `NotificationService.masked_recipient()` method added in Task 4 — no private-attribute access.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/integration/test_notifications_endpoints.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/notifications/api backend/tests/integration/test_notifications_endpoints.py
git commit -m "feat(notifications): add status + test-send API"
```

---

## Task 6: Scheduler integration — failure notifier + autohunt wrap

**Files:**
- Create: `backend/src/hiresense/scheduler/domain/ports/job_failure_notifier.py`
- Modify: `backend/src/hiresense/scheduler/domain/ports/__init__.py`, `backend/src/hiresense/scheduler/domain/job_runner.py`, `backend/src/hiresense/bootstrap/scheduler.py`
- Test: `backend/tests/unit/scheduler/test_job_runner_failure_notify.py`, `backend/tests/unit/scheduler/test_build_scheduler_notifications.py`

**Interfaces:**
- Consumes (Task 4): a `NotificationService` with `async notify_new_matches(digest) -> bool` and `async notify_job_failure(job_name, detail) -> bool`.
- Produces: `JobFailureNotifier` Protocol (`async notify_job_failure(job_name: str, detail: str | None) -> bool`); `JobRunner(..., failure_notifier: JobFailureNotifier | None = None)`; `build_scheduler(..., notification_service=None)`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/scheduler/test_job_runner_failure_notify.py
from datetime import datetime, timezone

import pytest

from hiresense.scheduler.domain import JobDefinition, JobRunner, JobStatus


class _RunRepo:
    def __init__(self): self.recorded = []
    def record(self, run): self.recorded.append(run); return run
    def recent(self, n, limit): return []
    def latest(self, n): return None


class _ToggleRepo:
    def is_enabled(self, name, default): return True
    def set_enabled(self, name, enabled): ...
    def all_states(self): return {}


class _Notifier:
    def __init__(self, raise_exc=None): self.calls = []; self._raise = raise_exc
    async def notify_job_failure(self, job_name, detail):
        self.calls.append((job_name, detail))
        if self._raise: raise self._raise
        return True


def _defn(run):
    return JobDefinition(name="job", run=run, cron="0 9 * * *", interval_hours=None, count_items=len)


def _runner(defn, notifier):
    return JobRunner(definitions=[defn], run_repo=_RunRepo(), toggle_repo=_ToggleRepo(),
                     failure_notifier=notifier)


@pytest.mark.asyncio
async def test_failure_invokes_notifier():
    async def run(): raise RuntimeError("boom")
    notifier = _Notifier()
    result = await _runner(_defn(run), notifier).run("job")
    assert result.status is JobStatus.FAILURE
    assert notifier.calls == [("job", "boom")]


@pytest.mark.asyncio
async def test_notifier_error_is_swallowed():
    async def run(): raise RuntimeError("boom")
    notifier = _Notifier(raise_exc=RuntimeError("notify failed"))
    # Must not raise; failure still recorded.
    result = await _runner(_defn(run), notifier).run("job")
    assert result.status is JobStatus.FAILURE


@pytest.mark.asyncio
async def test_success_does_not_notify():
    async def run(): return [1]
    notifier = _Notifier()
    result = await _runner(_defn(run), notifier).run("job")
    assert result.status is JobStatus.SUCCESS
    assert notifier.calls == []
```

```python
# backend/tests/unit/scheduler/test_build_scheduler_notifications.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.bootstrap.scheduler import build_scheduler
from hiresense.infrastructure.database import Base
from hiresense.scheduler.infrastructure import JobRunOrm, JobToggleOrm  # noqa: F401


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


class _Settings:
    ingestion_schedule = "0 */6 * * *"
    job_revalidation_interval_hours = 24
    autohunt_schedule = "0 9 * * *"
    outreach_followup_schedule = "0 10 * * *"
    scheduler_run_retention_days = 30


class _Orchestrator:
    async def run(self): return [1, 2]
class _Revalidation:
    async def sweep(self): return []
class _Outreach:
    def due_followups(self): return []


class _Autohunt:
    def __init__(self, job_count): self._jc = job_count
    async def run(self): return type("D", (), {"job_count": self._jc})()


class _Notifier:
    def __init__(self): self.matches = []
    async def notify_new_matches(self, digest): self.matches.append(digest)
    async def notify_job_failure(self, job_name, detail): ...


def _build(autohunt, notifier):
    return build_scheduler(
        settings=_Settings(), sync_session_factory=_factory(),
        ingestion_orchestrator=_Orchestrator(), revalidation_service=_Revalidation(),
        autohunt_service=autohunt, outreach_service=_Outreach(), notification_service=notifier,
    )


@pytest.mark.asyncio
async def test_autohunt_notifies_when_matches():
    notifier = _Notifier()
    build = _build(_Autohunt(job_count=3), notifier)
    run = await build.provider.run_now("autohunt_digest")
    assert run.status.value == "success"
    assert run.items_affected == 3
    assert len(notifier.matches) == 1


@pytest.mark.asyncio
async def test_autohunt_silent_when_no_matches():
    notifier = _Notifier()
    build = _build(_Autohunt(job_count=0), notifier)
    await build.provider.run_now("autohunt_digest")
    assert notifier.matches == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_job_runner_failure_notify.py tests/unit/scheduler/test_build_scheduler_notifications.py -v`
Expected: FAIL — `TypeError: JobRunner.__init__() got an unexpected keyword argument 'failure_notifier'` / `build_scheduler() got an unexpected keyword argument 'notification_service'`.

- [ ] **Step 3: Add the JobFailureNotifier port**

`backend/src/hiresense/scheduler/domain/ports/job_failure_notifier.py`:

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class JobFailureNotifier(Protocol):
    """Notified when a scheduled job records a FAILURE. Implementations must be
    best-effort (never raise into the caller)."""

    async def notify_job_failure(self, job_name: str, detail: str | None) -> bool: ...
```

Update `backend/src/hiresense/scheduler/domain/ports/__init__.py` to add:

```python
from hiresense.scheduler.domain.ports.job_failure_notifier import JobFailureNotifier
```

and add `"JobFailureNotifier"` to `__all__`.

- [ ] **Step 4: Add `failure_notifier` to JobRunner**

In `backend/src/hiresense/scheduler/domain/job_runner.py`, add the import and param, and notify in the exception branch.

Add to imports:

```python
from hiresense.scheduler.domain.ports import JobFailureNotifier
```

Change `__init__` to accept and store the notifier (add the keyword param after `clock`):

```python
        clock: Callable[[], datetime] | None = None,
        failure_notifier: JobFailureNotifier | None = None,
    ) -> None:
        self._defs = {d.name: d for d in definitions}
        self._run_repo = run_repo
        self._toggle_repo = toggle_repo
        self._clock = clock or _utcnow
        self._failure_notifier = failure_notifier
```

In the `except Exception` branch of `run()`, record the failure to a variable, notify, then return it. Replace:

```python
        except Exception as exc:  # noqa: BLE001 - scheduler must never crash
            logger.exception("Scheduled job %r failed", name)
            return self._record(name, started, self._clock(), JobStatus.FAILURE, str(exc), None)
```

with:

```python
        except Exception as exc:  # noqa: BLE001 - scheduler must never crash
            logger.exception("Scheduled job %r failed", name)
            run = self._record(name, started, self._clock(), JobStatus.FAILURE, str(exc), None)
            await self._notify_failure(name, str(exc))
            return run
```

Add this method to the class (after `_count`):

```python
    async def _notify_failure(self, name: str, detail: str) -> None:
        if self._failure_notifier is None:
            return
        try:
            await self._failure_notifier.notify_job_failure(name, detail)
        except Exception:  # noqa: BLE001 - notification is best-effort
            logger.exception("Failure notification for job %r failed", name)
```

- [ ] **Step 5: Wire notifications into build_scheduler**

In `backend/src/hiresense/bootstrap/scheduler.py`, add an `_autohunt_with_notify` helper and the `notification_service` param.

Add near `_digest_count` / `_as_async`:

```python
def _autohunt_job(autohunt_service: Any, notification_service: Any):
    """The autohunt job: run, and on new matches (job_count > 0) fire a digest
    notification. Returns the Digest unchanged so count_items still works."""

    async def _run():
        digest = await autohunt_service.run()
        if notification_service is not None and getattr(digest, "job_count", 0) > 0:
            await notification_service.notify_new_matches(digest)
        return digest

    return _run
```

Change the `build_scheduler` signature to add `notification_service: Any = None` (keyword), set the autohunt job's `run` to `_autohunt_job(autohunt_service, notification_service)`, and pass `failure_notifier=notification_service` to the `JobRunner`:

```python
def build_scheduler(
    *,
    settings: Any,
    sync_session_factory: Any,
    ingestion_orchestrator: Any,
    revalidation_service: Any,
    autohunt_service: Any,
    outreach_service: Any,
    notification_service: Any = None,
) -> SchedulerBuild:
```

In the `definitions` list, replace the `autohunt_digest` entry's `run=autohunt_service.run` with `run=_autohunt_job(autohunt_service, notification_service)`.

And change the runner construction:

```python
    job_runner = JobRunner(
        definitions=definitions,
        run_repo=run_repo,
        toggle_repo=toggle_repo,
        failure_notifier=notification_service,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler -v`
Expected: PASS — the two new test files green AND the existing scheduler unit tests still green (default `failure_notifier=None` / `notification_service=None` unchanged).

- [ ] **Step 7: Commit**

```bash
git add backend/src/hiresense/scheduler/domain/ports/job_failure_notifier.py backend/src/hiresense/scheduler/domain/ports/__init__.py backend/src/hiresense/scheduler/domain/job_runner.py backend/src/hiresense/bootstrap/scheduler.py backend/tests/unit/scheduler/test_job_runner_failure_notify.py backend/tests/unit/scheduler/test_build_scheduler_notifications.py
git commit -m "feat(notifications): trigger digest + failure email from the scheduler"
```

---

## Task 7: Wiring — build_notifications + main.py

**Files:**
- Create: `backend/src/hiresense/bootstrap/notifications.py`
- Modify: `backend/src/hiresense/bootstrap/__init__.py`, `backend/src/hiresense/main.py`
- Test: `backend/tests/integration/test_notifications_app_wiring.py`

**Interfaces:**
- Consumes: `NotificationProvider`, `NotificationService`, `SmtpEmailSender`, `build_scheduler(notification_service=...)`.
- Produces: `build_notifications(settings) -> NotificationBuild(provider, service)`; `app.state.notifications`; mounted `/notifications` router.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_notifications_app_wiring.py
import pytest
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.main import create_app


@pytest.mark.asyncio
async def test_notifications_status_mounted():
    app = create_app()
    app.dependency_overrides[require_auth] = lambda: "u"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/notifications/status")
    assert resp.status_code == 200
    assert "enabled" in resp.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/integration/test_notifications_app_wiring.py -v`
Expected: FAIL — 404 on `/notifications/status`.

- [ ] **Step 3: Implement build_notifications**

`backend/src/hiresense/bootstrap/notifications.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hiresense.adapters import SmtpEmailSender
from hiresense.notifications.api.provider import NotificationProvider
from hiresense.notifications.domain import NotificationService


@dataclass(frozen=True)
class NotificationBuild:
    provider: NotificationProvider
    service: NotificationService


def build_notifications(settings: Any) -> NotificationBuild:
    sender = SmtpEmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        from_email=settings.notification_from_email or settings.smtp_username,
        use_tls=settings.smtp_use_tls,
    )
    service = NotificationService(sender=sender, to_email=settings.notification_email)
    return NotificationBuild(provider=NotificationProvider(service), service=service)
```

Update `backend/src/hiresense/bootstrap/__init__.py` — add (in alphabetical position) and to `__all__`:

```python
from hiresense.bootstrap.notifications import NotificationBuild, build_notifications
```

- [ ] **Step 4: Wire into main.py**

Add the router import near the others:

```python
from hiresense.notifications.api import router as notifications_router
```

Add `build_notifications` to the `from hiresense.bootstrap import (...)` block.

Build notifications BEFORE the scheduler block, and pass it in. Insert before the `# --- Scheduler ---` block:

```python
    # --- Notifications (Autopilot Phase 2: digest + failure-alert email) ---
    notifications = build_notifications(settings)
    app.state.notifications = notifications.provider
    app.include_router(notifications_router)
```

Then change the existing `build_scheduler(...)` call to pass the service:

```python
    scheduler_build = build_scheduler(
        settings=settings,
        sync_session_factory=infra.sync_session_factory,
        ingestion_orchestrator=ingestion.orchestrator,
        revalidation_service=ingestion.revalidation_service,
        autohunt_service=autohunt.service,
        outreach_service=outreach.provider.get_outreach_service(),
        notification_service=notifications.service,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/integration/test_notifications_app_wiring.py tests/integration/test_scheduler_app_wiring.py -v`
Expected: PASS — notifications status mounted AND the scheduler wiring test still green.

- [ ] **Step 6: Run the full backend suite + lint**

Run: `cd backend && uv run python -m pytest -q && uv run ruff check .`
Expected: all green; no new ruff issues.

- [ ] **Step 7: Commit**

```bash
git add backend/src/hiresense/bootstrap/notifications.py backend/src/hiresense/bootstrap/__init__.py backend/src/hiresense/main.py backend/tests/integration/test_notifications_app_wiring.py
git commit -m "feat(notifications): build + mount notifications, wire into scheduler"
```

---

## Task 8: Frontend — admin Notifications page

**Files:**
- Create: `frontend/src/app/core/models/notification.model.ts`, `frontend/src/app/core/services/notification.service.ts`, `frontend/src/app/core/services/notification.service.spec.ts`
- Create: `frontend/src/app/pages/admin/notifications/notifications.component.{ts,html,scss,spec.ts}`
- Modify: `frontend/src/app/app.routes.ts`, `frontend/src/app/core/nav/hubs.const.ts`

**Interfaces:**
- Consumes: `GET /api/notifications/status` → `{enabled: boolean, recipient_masked: string | null}`; `POST /api/notifications/test` → `{sent: boolean}` (or 503).

- [ ] **Step 1: Write the failing service spec**

```typescript
// frontend/src/app/core/services/notification.service.spec.ts
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { NotificationService } from './notification.service';

describe('NotificationService', () => {
  let service: NotificationService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [NotificationService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(NotificationService);
    httpMock = TestBed.inject(HttpTestingController);
  });
  afterEach(() => httpMock.verify());

  it('gets status', () => {
    let result: unknown;
    service.status().subscribe((r) => (result = r));
    const req = httpMock.expectOne('/api/notifications/status');
    expect(req.request.method).toBe('GET');
    req.flush({ enabled: true, recipient_masked: 'a***@x.com' });
    expect((result as { enabled: boolean }).enabled).toBe(true);
  });

  it('sends a test', () => {
    service.sendTest().subscribe();
    const req = httpMock.expectOne('/api/notifications/test');
    expect(req.request.method).toBe('POST');
    req.flush({ sent: true });
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npm test -- --include "**/notification.service.spec.ts"`
Expected: FAIL — cannot find `./notification.service`.

- [ ] **Step 3: Implement model + service**

`frontend/src/app/core/models/notification.model.ts`:

```typescript
export interface NotificationStatus {
  enabled: boolean;
  recipient_masked: string | null;
}
```

(Snake_case to match the backend wire format — this project has no camelCasing HTTP interceptor; confirm against `core/interceptors/` if unsure, as in the Phase 1 scheduler model.)

`frontend/src/app/core/services/notification.service.ts`:

```typescript
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { NotificationStatus } from '../models/notification.model';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/notifications';

  status(): Observable<NotificationStatus> {
    return this.http.get<NotificationStatus>(`${this.base}/status`);
  }

  sendTest(): Observable<{ sent: boolean }> {
    return this.http.post<{ sent: boolean }>(`${this.base}/test`, {});
  }
}
```

- [ ] **Step 4: Run to verify the service spec passes**

Run: `cd frontend && npm test -- --include "**/notification.service.spec.ts"`
Expected: PASS.

- [ ] **Step 5: Write the failing component spec**

```typescript
// frontend/src/app/pages/admin/notifications/notifications.component.spec.ts
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { NotificationsComponent } from './notifications.component';

describe('NotificationsComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [NotificationsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });

  it('loads status on init', () => {
    const fixture = TestBed.createComponent(NotificationsComponent);
    fixture.detectChanges();
    const req = httpMock.expectOne('/api/notifications/status');
    req.flush({ enabled: true, recipient_masked: 'a***@x.com' });
    expect(fixture.componentInstance.status()?.enabled).toBe(true);
    httpMock.verify();
  });
});
```

- [ ] **Step 6: Run to verify it fails**

Run: `cd frontend && npm test -- --include "**/notifications.component.spec.ts"`
Expected: FAIL — cannot find `./notifications.component`.

- [ ] **Step 7: Implement the component**

`frontend/src/app/pages/admin/notifications/notifications.component.ts`:

```typescript
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NotificationService } from '../../../core/services/notification.service';
import { NotificationStatus } from '../../../core/models/notification.model';

@Component({
  selector: 'app-notifications',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './notifications.component.html',
  styleUrl: './notifications.component.scss',
})
export class NotificationsComponent implements OnInit {
  private readonly service = inject(NotificationService);
  readonly status = signal<NotificationStatus | null>(null);
  readonly busy = signal(false);
  readonly testResult = signal<string | null>(null);

  ngOnInit(): void {
    this.service.status().subscribe((s) => this.status.set(s));
  }

  sendTest(): void {
    this.busy.set(true);
    this.testResult.set(null);
    this.service.sendTest().subscribe({
      next: () => {
        this.busy.set(false);
        this.testResult.set('Test email sent.');
      },
      error: () => {
        this.busy.set(false);
        this.testResult.set('Send failed — check SMTP / recipient config.');
      },
    });
  }
}
```

`frontend/src/app/pages/admin/notifications/notifications.component.html`:

```html
<section class="notifications">
  <h1>Notifications</h1>
  @if (status(); as s) {
    <p>
      Status:
      <strong>{{ s.enabled ? 'Enabled' : 'Disabled (set NOTIFICATION_EMAIL)' }}</strong>
    </p>
    @if (s.recipient_masked) {
      <p>Recipient: <code>{{ s.recipient_masked }}</code></p>
    }
  }
  <button type="button" (click)="sendTest()" [disabled]="busy() || !(status()?.enabled)">
    Send test email
  </button>
  @if (testResult()) {
    <p class="result">{{ testResult() }}</p>
  }
</section>
```

`frontend/src/app/pages/admin/notifications/notifications.component.scss`:

```scss
.notifications {
  padding: 1rem;

  button {
    margin-top: 0.5rem;
  }

  .result {
    margin-top: 0.75rem;
    font-weight: 600;
  }
}
```

- [ ] **Step 8: Register route + nav (mirror the scheduler page)**

In `frontend/src/app/app.routes.ts`, add an entry mirroring the existing `admin/scheduler` route added in Phase 1:

```typescript
  {
    path: 'admin/notifications',
    canActivate: [adminGuard],
    loadComponent: () =>
      import('./pages/admin/notifications/notifications.component').then(
        (m) => m.NotificationsComponent,
      ),
  },
```

(Match the exact shape of the existing `admin/scheduler` route — same guard import and `loadComponent` style. Read that route first.)

In `frontend/src/app/core/nav/hubs.const.ts`, add to the admin hub tabs (mirroring the Phase 1 `Scheduler` entry):

```typescript
      { label: 'Notifications', path: '/dashboard/admin/notifications' },
```

(Match the exact path prefix the existing `Scheduler` entry uses — read it first; it was `/dashboard/admin/scheduler`.)

- [ ] **Step 9: Run component spec + lint + build**

Run: `cd frontend && npm test -- --include "**/notifications.component.spec.ts"`
Expected: PASS.

Run: `cd frontend && npx ng lint && npm run build`
Expected: lint clean; build succeeds.

- [ ] **Step 10: Verify clean staging and commit**

Confirm via `git status` that only the new notification files + `app.routes.ts` + `hubs.const.ts` are staged (NOT the pre-existing modified frontend files).

```bash
git add frontend/src/app/core/models/notification.model.ts frontend/src/app/core/services/notification.service.ts frontend/src/app/core/services/notification.service.spec.ts frontend/src/app/pages/admin/notifications frontend/src/app/app.routes.ts frontend/src/app/core/nav/hubs.const.ts
git commit -m "feat(notifications): admin notifications page (status + test email)"
```

---

## Final verification

- [ ] Backend: `cd backend && uv run python -m pytest -q && uv run ruff check .` — all green.
- [ ] Frontend: `cd frontend && npx ng lint && npm test` — all green.
- [ ] Manual smoke (optional, needs SMTP): set `NOTIFICATION_EMAIL` + SMTP_* in `.env`, run `uv run app`, `POST /notifications/test` → receive an email; toggle off → `GET /notifications/status` shows disabled and the test endpoint 503s.

## Spec coverage check (self-review)

- Recipient config + blank-disables → Task 2. Shared sender consolidation w/ re-exports → Task 1. Render functions → Task 3. NotificationService (disabled/enabled/error/test) → Task 4. status + test API w/ masking → Task 5. Failure trigger (JobRunner port) + new-match trigger (autohunt wrap) → Task 6. build_notifications + main wiring before scheduler → Task 7. Admin frontend → Task 8. asyncio.to_thread sends → Task 4. No event bus → Tasks 6–7. Phase-1-identical when disabled → Tasks 6 defaults. Back-compat outreach → Task 1.
