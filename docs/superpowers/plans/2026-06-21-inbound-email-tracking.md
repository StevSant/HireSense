# Inbound Email → Tracking Signals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect status-changing recruiter emails and surface one-click proposed tracking updates, fed by a periodic inbox scan — composing the Phase 1 scheduler and Phase 2 notifications.

**Architecture:** New hexagonal `inbox/` module: an `EmailClassifier` (tracked LLM → JSON) and `ApplicationMatcher` feed an `InboxProcessingService` that stores `DetectedSignal`s (a review queue). Emails arrive via an `InboxReaderPort` (IMAP adapter, config-gated) or a manual `POST /tracking/ingest-email` endpoint. Confirming a signal calls the existing `TrackingService.update_status`. A scheduler `inbox_scan` job runs the service; a new `NotificationService.notify_inbox_signals` announces new signals.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, `imaplib`, the tracked LLM factory, Angular 21 (standalone + signals), Vitest.

**Spec:** [`docs/superpowers/specs/2026-06-21-inbound-email-tracking-design.md`](../specs/2026-06-21-inbound-email-tracking-design.md)

## Global Constraints

- **Detect-and-propose, never auto-apply:** signals are stored `pending`; only an explicit confirm calls `TrackingService.update_status`. Nothing changes an application's status automatically.
- Matching is restricted to **active** applications (status `applied` or `interviewing`).
- IMAP is **config-gated**: blank `imap_host` → `ImapInboxReader.fetch_unseen()` returns `[]` (disabled). The manual ingest endpoint works regardless.
- Best-effort: a classifier LLM error → `job_related=False` (skip, log); an IMAP error → `[]` (logged); a notification failure never fails a scan. Nothing here raises into the scheduler.
- Dedup on `message_id` (unique index + `exists_message_id` check).
- `domain/` imports no framework packages and nothing from `infrastructure/`. The LLM is consumed via the `LLMPort` (`await llm.complete(prompt, system=...) -> str`).
- ONE class/enum/function per file; every package `__init__.py` re-exports; import from the contextual package.
- Every ORM class imported in `infrastructure/registry.py`.
- When `inbox_processing_service=None` is passed to `build_scheduler` (default), the `inbox_scan` job is absent and Phase 1/2 behavior is byte-identical.
- Tests: `cd backend && uv run python -m pytest <path> -v` (never bare `uv run pytest`). Integration tests use in-memory SQLite + `StaticPool` + `require_auth` override. No real IMAP or LLM in tests.
- Lint: `cd backend && uv run ruff check .` (NOT `ruff format .`). Frontend: `npx ng lint` before pushing.
- No hardcoded values — tunables go through `config.py` + `.env.example`.
- Working tree has PRE-EXISTING unrelated modified/untracked files. Stage ONLY each task's files with explicit paths. Never `git add -A`.

---

## File Structure

**New `inbox/` module:**
- `domain/inbound_email.py` (`InboundEmail`), `domain/email_signal_kind.py` (`EmailSignalKind`), `domain/classification.py` (`EmailClassification`), `domain/signal_state.py` (`SignalState`), `domain/detected_signal.py` (`DetectedSignal`).
- `domain/email_classifier.py` (`EmailClassifier`), `domain/application_matcher.py` (`ApplicationMatcher`), `domain/inbox_processing_service.py` (`InboxProcessingService`).
- `domain/ports/inbox_reader.py` (`InboxReaderPort`), `domain/ports/detected_signal_repository.py` (`DetectedSignalRepository`).
- `infrastructure/detected_signal_orm.py` (`DetectedSignalOrm`), `infrastructure/detected_signal_repository.py` (`DetectedSignalRepositoryImpl`), `infrastructure/imap_inbox_reader.py` (`ImapInboxReader`).
- `api/provider.py` (`InboxProvider`), `api/dependencies.py`, `api/routes.py` (`router`).
- `__init__.py` + each package `__init__.py`.

**Modified:**
- `config.py`, `.env.example` (IMAP + scan settings).
- `infrastructure/registry.py` (register `DetectedSignalOrm`).
- `notifications/domain/inbox_signals_email.py` (new render fn) + `notification_service.py` (`notify_inbox_signals`) + `notifications/domain/__init__.py`.
- `bootstrap/inbox.py` (new `build_inbox`), `bootstrap/scheduler.py` (`inbox_scan` job), `bootstrap/__init__.py`, `main.py`.
- New migration `backend/alembic/versions/034_add_inbox_detected_signals.py`.

**Frontend:** `core/models/inbox.model.ts`, `core/services/inbox.service.ts`, `pages/tracking/signals/signals.component.{ts,html,scss,spec.ts}` (or an admin route — mirror existing), `app.routes.ts`/nav.

---

## Task 1: Config — IMAP + inbox scan settings

**Files:**
- Modify: `backend/src/hiresense/config.py`, `backend/.env.example`
- Test: `backend/tests/unit/test_settings_inbox.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_settings_inbox.py
from hiresense.config import Settings


def test_inbox_settings_defaults():
    s = Settings()
    assert s.imap_host == ""
    assert s.imap_port == 993
    assert s.imap_folder == "INBOX"
    assert s.imap_use_ssl is True
    assert s.inbox_scan_schedule == "0 */2 * * *"
    assert s.inbox_signal_match_min_confidence == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/test_settings_inbox.py -v`
Expected: FAIL — `AttributeError: ... 'imap_host'`.

- [ ] **Step 3: Add the settings**

In `config.py`, after the notifications block, add:

```python
    # --- Inbox scanning (Autopilot Phase 3: inbound email -> tracking signals) ---
    # IMAP inbox to scan for recruiter emails. BLANK imap_host disables scanning
    # (the manual POST /tracking/ingest-email endpoint still works). Use an
    # app-specific password, not the account password.
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    imap_use_ssl: bool = True
    # Cron cadence for the scheduler 'inbox_scan' job (read by the scheduler).
    inbox_scan_schedule: str = "0 */2 * * *"
    # Classifications below this confidence get no proposed status (cannot be
    # one-click-applied; still listed for manual handling).
    inbox_signal_match_min_confidence: float = 0.5
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/test_settings_inbox.py -v`
Expected: PASS.

- [ ] **Step 5: Update `.env.example`**

Append to `backend/.env.example`:

```dotenv
# --- Inbox scanning (Autopilot Phase 3) ---
# IMAP inbox for recruiter-email detection. Blank IMAP_HOST disables scanning.
# Use an app-specific password.
IMAP_HOST=
IMAP_PORT=993
IMAP_USERNAME=
IMAP_PASSWORD=
IMAP_FOLDER=INBOX
IMAP_USE_SSL=true
# Cron cadence for the inbox_scan scheduler job.
INBOX_SCAN_SCHEDULE=0 */2 * * *
# Min classifier confidence for a signal to get a one-click-appliable status.
INBOX_SIGNAL_MATCH_MIN_CONFIDENCE=0.5
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/config.py backend/.env.example backend/tests/unit/test_settings_inbox.py
git commit -m "feat(inbox): add IMAP + inbox-scan config"
```

---

## Task 2: Domain models + enums

**Files:**
- Create: `backend/src/hiresense/inbox/__init__.py` (empty), `inbox/domain/inbound_email.py`, `inbox/domain/email_signal_kind.py`, `inbox/domain/classification.py`, `inbox/domain/signal_state.py`, `inbox/domain/detected_signal.py`, `inbox/domain/__init__.py`
- Test: `backend/tests/unit/inbox/test_domain_models.py` (+ `tests/unit/inbox/__init__.py`)

**Interfaces:**
- Produces: `InboundEmail(message_id, from_address, subject, body, received_at)`; `EmailSignalKind` (`REJECTION`/`INTERVIEW`/`OFFER`/`OTHER`, values `"rejection"`/`"interview"`/`"offer"`/`"other"`); `EmailClassification(job_related, kind, company, role, confidence)`; `SignalState` (`PENDING`/`APPLIED`/`DISMISSED`); `DetectedSignal(id, message_id, from_address, subject, received_at, kind, company, role, confidence, matched_application_id, proposed_status, state, created_at)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/inbox/test_domain_models.py
from datetime import datetime, timezone

from hiresense.inbox.domain import (
    DetectedSignal,
    EmailClassification,
    EmailSignalKind,
    InboundEmail,
    SignalState,
)


def test_models_construct():
    email = InboundEmail(
        message_id="m1", from_address="r@acme.com", subject="Update",
        body="...", received_at=datetime.now(timezone.utc),
    )
    assert email.message_id == "m1"
    c = EmailClassification(job_related=True, kind=EmailSignalKind.REJECTION,
                            company="Acme", role="Dev", confidence=0.8)
    assert c.kind is EmailSignalKind.REJECTION
    sig = DetectedSignal(
        message_id="m1", from_address="r@acme.com", subject="Update",
        received_at=email.received_at, kind=EmailSignalKind.REJECTION,
        company="Acme", role="Dev", confidence=0.8,
        matched_application_id=None, proposed_status=None, state=SignalState.PENDING,
    )
    assert sig.state is SignalState.PENDING
    assert EmailSignalKind.OFFER.value == "offer"
    assert SignalState.DISMISSED.value == "dismissed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/inbox/test_domain_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hiresense.inbox'`.

- [ ] **Step 3: Implement the models**

`backend/src/hiresense/inbox/__init__.py`: empty file. Also create `backend/tests/unit/inbox/__init__.py`: empty file.

`inbox/domain/email_signal_kind.py`:

```python
from __future__ import annotations

from enum import Enum


class EmailSignalKind(str, Enum):
    """The status-changing signal an email carries (or OTHER)."""

    REJECTION = "rejection"
    INTERVIEW = "interview"
    OFFER = "offer"
    OTHER = "other"
```

`inbox/domain/signal_state.py`:

```python
from __future__ import annotations

from enum import Enum


class SignalState(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    DISMISSED = "dismissed"
```

`inbox/domain/inbound_email.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class InboundEmail(BaseModel):
    """A raw inbound email to classify (pure domain model)."""

    message_id: str
    from_address: str
    subject: str
    body: str
    received_at: datetime
```

`inbox/domain/classification.py`:

```python
from __future__ import annotations

from pydantic import BaseModel

from hiresense.inbox.domain.email_signal_kind import EmailSignalKind


class EmailClassification(BaseModel):
    """Result of classifying one email."""

    job_related: bool
    kind: EmailSignalKind = EmailSignalKind.OTHER
    company: str | None = None
    role: str | None = None
    confidence: float = 0.0
```

`inbox/domain/detected_signal.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel

from hiresense.inbox.domain.email_signal_kind import EmailSignalKind
from hiresense.inbox.domain.signal_state import SignalState


class DetectedSignal(BaseModel):
    """A detected, reviewable email signal (pure domain model)."""

    id: uuid_mod.UUID | None = None
    message_id: str
    from_address: str
    subject: str
    received_at: datetime
    kind: EmailSignalKind
    company: str | None = None
    role: str | None = None
    confidence: float = 0.0
    matched_application_id: uuid_mod.UUID | None = None
    proposed_status: str | None = None
    state: SignalState = SignalState.PENDING
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
```

`inbox/domain/__init__.py`:

```python
from hiresense.inbox.domain.classification import EmailClassification
from hiresense.inbox.domain.detected_signal import DetectedSignal
from hiresense.inbox.domain.email_signal_kind import EmailSignalKind
from hiresense.inbox.domain.inbound_email import InboundEmail
from hiresense.inbox.domain.signal_state import SignalState

__all__ = [
    "DetectedSignal",
    "EmailClassification",
    "EmailSignalKind",
    "InboundEmail",
    "SignalState",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/inbox/test_domain_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/inbox/__init__.py backend/src/hiresense/inbox/domain backend/tests/unit/inbox
git commit -m "feat(inbox): add domain models + enums"
```

---

## Task 3: Domain ports

**Files:**
- Create: `inbox/domain/ports/inbox_reader.py`, `inbox/domain/ports/detected_signal_repository.py`, `inbox/domain/ports/__init__.py`
- Test: `backend/tests/unit/inbox/test_ports_importable.py`

**Interfaces:**
- Produces: `InboxReaderPort` (`fetch_unseen() -> list[InboundEmail]`); `DetectedSignalRepository` (`add(signal) -> DetectedSignal`, `list(state=None) -> list[DetectedSignal]`, `get(id) -> DetectedSignal | None`, `set_state(id, state) -> DetectedSignal | None`, `exists_message_id(message_id) -> bool`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/inbox/test_ports_importable.py
from hiresense.inbox.domain.ports import DetectedSignalRepository, InboxReaderPort


def test_ports_are_runtime_checkable():
    class _Reader:
        def fetch_unseen(self): ...

    class _Repo:
        def add(self, signal): ...
        def list(self, state=None): ...
        def get(self, id): ...
        def set_state(self, id, state): ...
        def exists_message_id(self, message_id): ...

    assert isinstance(_Reader(), InboxReaderPort)
    assert isinstance(_Repo(), DetectedSignalRepository)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/inbox/test_ports_importable.py -v`
Expected: FAIL — `ModuleNotFoundError: ...inbox.domain.ports`.

- [ ] **Step 3: Implement the ports**

`inbox/domain/ports/inbox_reader.py`:

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from hiresense.inbox.domain.inbound_email import InboundEmail


@runtime_checkable
class InboxReaderPort(Protocol):
    """Reads unseen emails from a mailbox. Returns [] when disabled/unreachable."""

    def fetch_unseen(self) -> list[InboundEmail]: ...
```

`inbox/domain/ports/detected_signal_repository.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from typing import Protocol, runtime_checkable

from hiresense.inbox.domain.detected_signal import DetectedSignal
from hiresense.inbox.domain.signal_state import SignalState


@runtime_checkable
class DetectedSignalRepository(Protocol):
    def add(self, signal: DetectedSignal) -> DetectedSignal: ...

    def list(self, state: SignalState | None = None) -> list[DetectedSignal]: ...

    def get(self, id: uuid_mod.UUID) -> DetectedSignal | None: ...

    def set_state(self, id: uuid_mod.UUID, state: SignalState) -> DetectedSignal | None: ...

    def exists_message_id(self, message_id: str) -> bool: ...
```

`inbox/domain/ports/__init__.py`:

```python
from hiresense.inbox.domain.ports.detected_signal_repository import DetectedSignalRepository
from hiresense.inbox.domain.ports.inbox_reader import InboxReaderPort

__all__ = ["DetectedSignalRepository", "InboxReaderPort"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/inbox/test_ports_importable.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/inbox/domain/ports backend/tests/unit/inbox/test_ports_importable.py
git commit -m "feat(inbox): add inbox-reader + signal-repository ports"
```

---

## Task 4: EmailClassifier

**Files:**
- Create: `inbox/domain/email_classifier.py`
- Modify: `inbox/domain/__init__.py`
- Test: `backend/tests/unit/inbox/test_email_classifier.py`

**Interfaces:**
- Consumes: an `LLMPort`-shaped object (`await llm.complete(prompt, system="") -> str`); `InboundEmail`.
- Produces: `EmailClassifier(llm)`; `async classify(email: InboundEmail) -> EmailClassification`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/inbox/test_email_classifier.py
from datetime import datetime, timezone

import pytest

from hiresense.inbox.domain import EmailClassifier, EmailSignalKind, InboundEmail


class _LLM:
    def __init__(self, response=None, raise_exc=None):
        self._response = response
        self._raise = raise_exc

    async def complete(self, prompt, system=""):
        if self._raise is not None:
            raise self._raise
        return self._response


def _email():
    return InboundEmail(message_id="m1", from_address="r@acme.com",
                        subject="Your application", body="We regret to inform you...",
                        received_at=datetime.now(timezone.utc))


@pytest.mark.asyncio
async def test_parses_structured_json():
    llm = _LLM(response='{"job_related": true, "kind": "rejection", "company": "Acme", "role": "Dev", "confidence": 0.9}')
    result = await EmailClassifier(llm).classify(_email())
    assert result.job_related is True
    assert result.kind is EmailSignalKind.REJECTION
    assert result.company == "Acme"
    assert result.confidence == 0.9


@pytest.mark.asyncio
async def test_llm_error_returns_not_job_related():
    result = await EmailClassifier(_LLM(raise_exc=RuntimeError("boom"))).classify(_email())
    assert result.job_related is False


@pytest.mark.asyncio
async def test_unparseable_response_returns_not_job_related():
    result = await EmailClassifier(_LLM(response="not json at all")).classify(_email())
    assert result.job_related is False


@pytest.mark.asyncio
async def test_no_llm_returns_not_job_related():
    result = await EmailClassifier(None).classify(_email())
    assert result.job_related is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/inbox/test_email_classifier.py -v`
Expected: FAIL — `ImportError: cannot import name 'EmailClassifier'`.

- [ ] **Step 3: Implement**

`inbox/domain/email_classifier.py`:

```python
from __future__ import annotations

import json
import logging
from typing import Any

from hiresense.inbox.domain.classification import EmailClassification
from hiresense.inbox.domain.email_signal_kind import EmailSignalKind
from hiresense.inbox.domain.inbound_email import InboundEmail

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You classify recruiting emails. Decide if the email concerns a job "
    "application the recipient made, and which status signal it carries. "
    'Respond with ONLY a JSON object: {"job_related": bool, "kind": one of '
    '"rejection"|"interview"|"offer"|"other", "company": string or null, '
    '"role": string or null, "confidence": number 0..1}. No prose, no markdown.'
)


class EmailClassifier:
    """Pure LLM unit: classify an inbound email into a status signal. Never
    raises — an LLM or parse failure yields job_related=False."""

    def __init__(self, llm: Any | None) -> None:
        self._llm = llm

    async def classify(self, email: InboundEmail) -> EmailClassification:
        if self._llm is None:
            return EmailClassification(job_related=False)
        prompt = (
            f"From: {email.from_address}\n"
            f"Subject: {email.subject}\n\n"
            f"{email.body[:4000]}"
        )
        try:
            raw = await self._llm.complete(prompt, system=SYSTEM_PROMPT)
        except Exception:  # noqa: BLE001 - classification is best-effort
            logger.exception("inbox: classifier LLM call failed")
            return EmailClassification(job_related=False)
        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> EmailClassification:
        try:
            data = json.loads(raw.strip())
            kind = EmailSignalKind(data.get("kind", "other"))
            return EmailClassification(
                job_related=bool(data.get("job_related", False)),
                kind=kind,
                company=data.get("company"),
                role=data.get("role"),
                confidence=float(data.get("confidence", 0.0)),
            )
        except Exception:  # noqa: BLE001 - tolerate any malformed LLM output
            logger.warning("inbox: could not parse classifier output")
            return EmailClassification(job_related=False)
```

Update `inbox/domain/__init__.py` to add:

```python
from hiresense.inbox.domain.email_classifier import EmailClassifier
```

and add `"EmailClassifier"` to `__all__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/inbox/test_email_classifier.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/inbox/domain/email_classifier.py backend/src/hiresense/inbox/domain/__init__.py backend/tests/unit/inbox/test_email_classifier.py
git commit -m "feat(inbox): add EmailClassifier (LLM JSON, never raises)"
```

---

## Task 5: ApplicationMatcher

**Files:**
- Create: `inbox/domain/application_matcher.py`
- Modify: `inbox/domain/__init__.py`
- Test: `backend/tests/unit/inbox/test_application_matcher.py`

**Interfaces:**
- Consumes: `EmailClassification`; `TrackedApplication` (from `hiresense.tracking.domain`, has `id`, `company`, `status`); `ApplicationStatus` (from `hiresense.tracking.domain.models`).
- Produces: `ApplicationMatcher(min_confidence: float)`; `match(classification, active_apps: list) -> tuple[UUID | None, str | None]` (matched application id, proposed status value). Maps `rejection→rejected`, `interview→interviewing`, `offer→offered`; `other`/low-confidence/no-match → `(None, None)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/inbox/test_application_matcher.py
import uuid

from hiresense.inbox.domain import ApplicationMatcher, EmailClassification, EmailSignalKind
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


def _app(company, status=ApplicationStatus.APPLIED):
    return TrackedApplication(id=uuid.uuid4(), title="Dev", company=company, status=status.value)


def _classification(kind, company, confidence=0.9):
    return EmailClassification(job_related=True, kind=kind, company=company,
                               role="Dev", confidence=confidence)


def test_matches_active_app_by_company_and_maps_status():
    app = _app("Acme Corp")
    matcher = ApplicationMatcher(min_confidence=0.5)
    matched_id, proposed = matcher.match(_classification(EmailSignalKind.REJECTION, "Acme"), [app])
    assert matched_id == app.id
    assert proposed == ApplicationStatus.REJECTED.value


def test_interview_maps_to_interviewing():
    app = _app("Globex")
    matched_id, proposed = ApplicationMatcher(0.5).match(
        _classification(EmailSignalKind.INTERVIEW, "Globex"), [app])
    assert proposed == ApplicationStatus.INTERVIEWING.value


def test_no_company_match_returns_none():
    app = _app("Acme")
    matched_id, proposed = ApplicationMatcher(0.5).match(
        _classification(EmailSignalKind.REJECTION, "Initech"), [app])
    assert (matched_id, proposed) == (None, None)


def test_low_confidence_returns_none():
    app = _app("Acme")
    matched_id, proposed = ApplicationMatcher(0.5).match(
        _classification(EmailSignalKind.REJECTION, "Acme", confidence=0.2), [app])
    assert (matched_id, proposed) == (None, None)


def test_other_kind_returns_none():
    app = _app("Acme")
    matched_id, proposed = ApplicationMatcher(0.5).match(
        _classification(EmailSignalKind.OTHER, "Acme"), [app])
    assert (matched_id, proposed) == (None, None)


def test_ambiguous_multiple_matches_returns_none():
    apps = [_app("Acme"), _app("Acme Inc")]
    matched_id, proposed = ApplicationMatcher(0.5).match(
        _classification(EmailSignalKind.REJECTION, "Acme"), apps)
    assert (matched_id, proposed) == (None, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/inbox/test_application_matcher.py -v`
Expected: FAIL — `ImportError: cannot import name 'ApplicationMatcher'`.

- [ ] **Step 3: Implement**

`inbox/domain/application_matcher.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from typing import Any

from hiresense.inbox.domain.classification import EmailClassification
from hiresense.inbox.domain.email_signal_kind import EmailSignalKind
from hiresense.tracking.domain.models import ApplicationStatus

_KIND_TO_STATUS = {
    EmailSignalKind.REJECTION: ApplicationStatus.REJECTED,
    EmailSignalKind.INTERVIEW: ApplicationStatus.INTERVIEWING,
    EmailSignalKind.OFFER: ApplicationStatus.OFFERED,
}

_ACTIVE_STATUSES = {ApplicationStatus.APPLIED.value, ApplicationStatus.INTERVIEWING.value}


def _normalize(company: str | None) -> str:
    return "".join(ch for ch in (company or "").lower() if ch.isalnum() or ch.isspace()).strip()


class ApplicationMatcher:
    """Matches a classified email to one active tracked application by company.
    Returns (application_id, proposed_status_value) or (None, None) when there's
    no signal-bearing kind, confidence is too low, or the company match is absent
    or ambiguous."""

    def __init__(self, min_confidence: float) -> None:
        self._min_confidence = min_confidence

    def match(
        self, classification: EmailClassification, active_apps: list[Any]
    ) -> tuple[uuid_mod.UUID | None, str | None]:
        status = _KIND_TO_STATUS.get(classification.kind)
        if status is None or classification.confidence < self._min_confidence:
            return None, None
        target = _normalize(classification.company)
        if not target:
            return None, None
        matches = [
            app
            for app in active_apps
            if app.status in _ACTIVE_STATUSES and _company_matches(target, _normalize(app.company))
        ]
        if len(matches) != 1:
            return None, None  # no match or ambiguous
        return matches[0].id, status.value


def _company_matches(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return a in b or b in a
```

Update `inbox/domain/__init__.py` to add `from hiresense.inbox.domain.application_matcher import ApplicationMatcher` and `"ApplicationMatcher"` in `__all__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/inbox/test_application_matcher.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/inbox/domain/application_matcher.py backend/src/hiresense/inbox/domain/__init__.py backend/tests/unit/inbox/test_application_matcher.py
git commit -m "feat(inbox): add ApplicationMatcher (active-only, company fuzzy)"
```

---

## Task 6: InboxProcessingService

**Files:**
- Create: `inbox/domain/inbox_processing_service.py`
- Modify: `inbox/domain/__init__.py`
- Test: `backend/tests/unit/inbox/test_inbox_processing_service.py`

**Interfaces:**
- Consumes: `InboxReaderPort`, `DetectedSignalRepository`, `EmailClassifier`, `ApplicationMatcher`; a tracking-list callable `list_active() -> list[TrackedApplication]`; an optional notifier with `async notify_inbox_signals(count) -> bool`.
- Produces: `InboxProcessingService(*, reader, repo, classifier, matcher, list_active, notifier=None)`; `async run() -> int` (new-signal count); `async ingest_one(email: InboundEmail) -> DetectedSignal | None`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/inbox/test_inbox_processing_service.py
import uuid
from datetime import datetime, timezone

import pytest

from hiresense.inbox.domain import (
    ApplicationMatcher,
    DetectedSignal,
    EmailClassification,
    EmailSignalKind,
    InboundEmail,
    InboxProcessingService,
    SignalState,
)
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


class _Reader:
    def __init__(self, emails): self._emails = emails
    def fetch_unseen(self): return self._emails


class _Repo:
    def __init__(self): self.signals = []
    def add(self, signal):
        signal.id = uuid.uuid4()
        self.signals.append(signal)
        return signal
    def list(self, state=None): return self.signals
    def get(self, id): return next((s for s in self.signals if s.id == id), None)
    def set_state(self, id, state): ...
    def exists_message_id(self, message_id):
        return any(s.message_id == message_id for s in self.signals)


class _Classifier:
    def __init__(self, result): self._result = result
    async def classify(self, email): return self._result


class _Notifier:
    def __init__(self): self.calls = []
    async def notify_inbox_signals(self, count): self.calls.append(count); return True


def _email(mid="m1"):
    return InboundEmail(message_id=mid, from_address="r@acme.com", subject="App",
                        body="We regret...", received_at=datetime.now(timezone.utc))


def _service(reader, repo, classification, notifier=None):
    app = TrackedApplication(id=uuid.uuid4(), title="Dev", company="Acme",
                             status=ApplicationStatus.APPLIED.value)
    return InboxProcessingService(
        reader=reader, repo=repo, classifier=_Classifier(classification),
        matcher=ApplicationMatcher(min_confidence=0.5), list_active=lambda: [app],
        notifier=notifier,
    )


@pytest.mark.asyncio
async def test_run_creates_matched_pending_signal():
    repo = _Repo()
    classification = EmailClassification(job_related=True, kind=EmailSignalKind.REJECTION,
                                         company="Acme", role="Dev", confidence=0.9)
    count = await _service(_Reader([_email()]), repo, classification).run()
    assert count == 1
    sig = repo.signals[0]
    assert sig.state is SignalState.PENDING
    assert sig.matched_application_id is not None
    assert sig.proposed_status == ApplicationStatus.REJECTED.value


@pytest.mark.asyncio
async def test_run_skips_non_job_related():
    repo = _Repo()
    count = await _service(_Reader([_email()]), repo,
                           EmailClassification(job_related=False)).run()
    assert count == 0
    assert repo.signals == []


@pytest.mark.asyncio
async def test_run_dedups_by_message_id():
    repo = _Repo()
    classification = EmailClassification(job_related=True, kind=EmailSignalKind.REJECTION,
                                         company="Acme", role="Dev", confidence=0.9)
    svc = _service(_Reader([_email("dup"), _email("dup")]), repo, classification)
    count = await svc.run()
    assert count == 1


@pytest.mark.asyncio
async def test_run_notifies_when_new_signals():
    notifier = _Notifier()
    classification = EmailClassification(job_related=True, kind=EmailSignalKind.REJECTION,
                                         company="Acme", role="Dev", confidence=0.9)
    await _service(_Reader([_email()]), _Repo(), classification, notifier=notifier).run()
    assert notifier.calls == [1]


@pytest.mark.asyncio
async def test_ingest_one_returns_none_when_not_job_related():
    result = await _service(_Reader([]), _Repo(),
                            EmailClassification(job_related=False)).ingest_one(_email())
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/inbox/test_inbox_processing_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'InboxProcessingService'`.

- [ ] **Step 3: Implement**

`inbox/domain/inbox_processing_service.py`:

```python
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from hiresense.inbox.domain.application_matcher import ApplicationMatcher
from hiresense.inbox.domain.detected_signal import DetectedSignal
from hiresense.inbox.domain.email_classifier import EmailClassifier
from hiresense.inbox.domain.inbound_email import InboundEmail
from hiresense.inbox.domain.ports import DetectedSignalRepository, InboxReaderPort

logger = logging.getLogger(__name__)


class InboxProcessingService:
    """Orchestrates one inbox scan: read → classify → match → store pending
    signals (dedup by message_id). Best-effort: never raises into the caller."""

    def __init__(
        self,
        *,
        reader: InboxReaderPort,
        repo: DetectedSignalRepository,
        classifier: EmailClassifier,
        matcher: ApplicationMatcher,
        list_active: Callable[[], list[Any]],
        notifier: Any | None = None,
    ) -> None:
        self._reader = reader
        self._repo = repo
        self._classifier = classifier
        self._matcher = matcher
        self._list_active = list_active
        self._notifier = notifier

    async def run(self) -> int:
        emails = await asyncio.to_thread(self._reader.fetch_unseen)
        new_count = 0
        for email in emails:
            signal = await self._process(email)
            if signal is not None:
                new_count += 1
        if new_count and self._notifier is not None:
            try:
                await self._notifier.notify_inbox_signals(new_count)
            except Exception:  # noqa: BLE001 - notification is best-effort
                logger.exception("inbox: signal notification failed")
        return new_count

    async def ingest_one(self, email: InboundEmail) -> DetectedSignal | None:
        return await self._process(email)

    async def _process(self, email: InboundEmail) -> DetectedSignal | None:
        if self._repo.exists_message_id(email.message_id):
            return None
        classification = await self._classifier.classify(email)
        if not classification.job_related:
            return None
        matched_id, proposed = self._matcher.match(classification, self._list_active())
        signal = DetectedSignal(
            message_id=email.message_id,
            from_address=email.from_address,
            subject=email.subject,
            received_at=email.received_at,
            kind=classification.kind,
            company=classification.company,
            role=classification.role,
            confidence=classification.confidence,
            matched_application_id=matched_id,
            proposed_status=proposed,
        )
        return self._repo.add(signal)
```

Update `inbox/domain/__init__.py` to add `from hiresense.inbox.domain.inbox_processing_service import InboxProcessingService` and `"InboxProcessingService"` in `__all__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/inbox/test_inbox_processing_service.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/inbox/domain/inbox_processing_service.py backend/src/hiresense/inbox/domain/__init__.py backend/tests/unit/inbox/test_inbox_processing_service.py
git commit -m "feat(inbox): add InboxProcessingService (scan/ingest, dedup, notify)"
```

---

## Task 7: Infrastructure — ORM, repository, IMAP reader

**Files:**
- Create: `inbox/infrastructure/detected_signal_orm.py`, `inbox/infrastructure/detected_signal_repository.py`, `inbox/infrastructure/imap_inbox_reader.py`, `inbox/infrastructure/__init__.py`
- Modify: `backend/src/hiresense/infrastructure/registry.py`
- Test: `backend/tests/integration/test_inbox_repository.py`, `backend/tests/unit/inbox/test_imap_reader_disabled.py`

**Interfaces:**
- Produces: `DetectedSignalOrm` (table `inbox_detected_signals`); `DetectedSignalRepositoryImpl(session_factory)` implementing `DetectedSignalRepository`; `ImapInboxReader(*, host, port, username, password, folder, use_ssl)` implementing `InboxReaderPort`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/integration/test_inbox_repository.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.inbox.domain import DetectedSignal, EmailSignalKind, SignalState
from hiresense.inbox.infrastructure import DetectedSignalOrm, DetectedSignalRepositoryImpl  # noqa: F401


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _signal(mid="m1"):
    return DetectedSignal(
        message_id=mid, from_address="r@acme.com", subject="App",
        received_at=datetime.now(timezone.utc), kind=EmailSignalKind.REJECTION,
        company="Acme", role="Dev", confidence=0.9,
        matched_application_id=uuid.uuid4(), proposed_status="rejected",
    )


def test_add_list_get_setstate_dedup():
    repo = DetectedSignalRepositoryImpl(session_factory=_factory())
    added = repo.add(_signal())
    assert added.id is not None
    assert repo.exists_message_id("m1") is True
    assert repo.exists_message_id("nope") is False
    assert len(repo.list()) == 1
    assert len(repo.list(state=SignalState.PENDING)) == 1
    assert len(repo.list(state=SignalState.APPLIED)) == 0
    updated = repo.set_state(added.id, SignalState.APPLIED)
    assert updated.state is SignalState.APPLIED
    assert repo.get(added.id).state is SignalState.APPLIED
```

```python
# backend/tests/unit/inbox/test_imap_reader_disabled.py
from hiresense.inbox.infrastructure import ImapInboxReader


def test_blank_host_returns_empty():
    reader = ImapInboxReader(host="", port=993, username="", password="",
                             folder="INBOX", use_ssl=True)
    assert reader.fetch_unseen() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/integration/test_inbox_repository.py tests/unit/inbox/test_imap_reader_disabled.py -v`
Expected: FAIL — `ImportError: cannot import name 'DetectedSignalOrm'`.

- [ ] **Step 3: Implement the ORM**

`inbox/infrastructure/detected_signal_orm.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from hiresense.infrastructure.database import Base


class DetectedSignalOrm(Base):
    """A detected, reviewable inbound-email signal."""

    __tablename__ = "inbox_detected_signals"

    id: Mapped[uuid_mod.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_mod.uuid4)
    message_id: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    from_address: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    company: Mapped[str | None] = mapped_column(String(256), nullable=True)
    role: Mapped[str | None] = mapped_column(String(256), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    matched_application_id: Mapped[uuid_mod.UUID | None] = mapped_column(Uuid, nullable=True)
    proposed_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
```

- [ ] **Step 4: Implement the repository**

`inbox/infrastructure/detected_signal_repository.py`:

```python
from __future__ import annotations

import uuid as uuid_mod

from sqlalchemy import select

from hiresense.infrastructure import SqlRepository
from hiresense.inbox.domain import DetectedSignal, EmailSignalKind, SignalState
from hiresense.inbox.infrastructure.detected_signal_orm import DetectedSignalOrm


def _to_domain(row: DetectedSignalOrm) -> DetectedSignal:
    return DetectedSignal(
        id=row.id,
        message_id=row.message_id,
        from_address=row.from_address,
        subject=row.subject,
        received_at=row.received_at,
        kind=EmailSignalKind(row.kind),
        company=row.company,
        role=row.role,
        confidence=row.confidence,
        matched_application_id=row.matched_application_id,
        proposed_status=row.proposed_status,
        state=SignalState(row.state),
        created_at=row.created_at,
    )


class DetectedSignalRepositoryImpl(SqlRepository):
    def add(self, signal: DetectedSignal) -> DetectedSignal:
        row = DetectedSignalOrm(
            message_id=signal.message_id,
            from_address=signal.from_address,
            subject=signal.subject,
            received_at=signal.received_at,
            kind=signal.kind.value,
            company=signal.company,
            role=signal.role,
            confidence=signal.confidence,
            matched_application_id=signal.matched_application_id,
            proposed_status=signal.proposed_status,
            state=signal.state.value,
        )
        return self._insert(row, _to_domain)

    def list(self, state: SignalState | None = None) -> list[DetectedSignal]:
        stmt = select(DetectedSignalOrm).order_by(DetectedSignalOrm.received_at.desc())
        if state is not None:
            stmt = stmt.where(DetectedSignalOrm.state == state.value)
        return self._select_all(stmt, _to_domain)

    def get(self, id: uuid_mod.UUID) -> DetectedSignal | None:
        return self._get_by_pk(DetectedSignalOrm, id, _to_domain)

    def set_state(self, id: uuid_mod.UUID, state: SignalState) -> DetectedSignal | None:
        return self._update_by_pk(DetectedSignalOrm, id, {"state": state.value}, _to_domain)

    def exists_message_id(self, message_id: str) -> bool:
        with self._session_factory() as session:
            stmt = select(DetectedSignalOrm.id).where(
                DetectedSignalOrm.message_id == message_id
            ).limit(1)
            return session.scalars(stmt).first() is not None
```

- [ ] **Step 5: Implement the IMAP reader**

`inbox/infrastructure/imap_inbox_reader.py`:

```python
from __future__ import annotations

import email as email_lib
import imaplib
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from hiresense.inbox.domain import InboundEmail

logger = logging.getLogger(__name__)


class ImapInboxReader:
    """Reads UNSEEN emails over IMAP. Config-gated: a blank host disables it
    (returns []). Never raises — connection/parse errors log and return what was
    gathered so a scan degrades to a no-op."""

    def __init__(
        self, *, host: str, port: int, username: str, password: str, folder: str, use_ssl: bool
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._folder = folder
        self._use_ssl = use_ssl

    def fetch_unseen(self) -> list[InboundEmail]:
        if not self._host:
            return []
        try:
            return self._fetch()
        except Exception:  # noqa: BLE001 - inbox read is best-effort
            logger.exception("inbox: IMAP fetch failed")
            return []

    def _fetch(self) -> list[InboundEmail]:
        client = (
            imaplib.IMAP4_SSL(self._host, self._port)
            if self._use_ssl
            else imaplib.IMAP4(self._host, self._port)
        )
        out: list[InboundEmail] = []
        try:
            client.login(self._username, self._password)
            client.select(self._folder)
            _, data = client.search(None, "UNSEEN")
            ids = data[0].split() if data and data[0] else []
            for num in ids:
                _, msg_data = client.fetch(num, "(RFC822)")
                if not msg_data or not isinstance(msg_data[0], tuple):
                    continue
                parsed = self._parse(msg_data[0][1])
                if parsed is not None:
                    out.append(parsed)
        finally:
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass
        return out

    @staticmethod
    def _parse(raw: bytes) -> InboundEmail | None:
        try:
            msg = email_lib.message_from_bytes(raw)
            body = ImapInboxReader._extract_body(msg)
            received = parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else None
            return InboundEmail(
                message_id=msg.get("Message-ID") or "",
                from_address=msg.get("From") or "",
                subject=msg.get("Subject") or "",
                body=body,
                received_at=received or datetime.now(timezone.utc),
            )
        except Exception:  # noqa: BLE001
            logger.warning("inbox: could not parse an email")
            return None

    @staticmethod
    def _extract_body(msg) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(part.get_content_charset() or "utf-8", "replace")
            return ""
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(msg.get_content_charset() or "utf-8", "replace")
        return ""
```

`inbox/infrastructure/__init__.py`:

```python
from hiresense.inbox.infrastructure.detected_signal_orm import DetectedSignalOrm
from hiresense.inbox.infrastructure.detected_signal_repository import DetectedSignalRepositoryImpl
from hiresense.inbox.infrastructure.imap_inbox_reader import ImapInboxReader

__all__ = ["DetectedSignalOrm", "DetectedSignalRepositoryImpl", "ImapInboxReader"]
```

Add to `backend/src/hiresense/infrastructure/registry.py` (alphabetical):

```python
from hiresense.inbox.infrastructure import DetectedSignalOrm  # noqa: F401
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/integration/test_inbox_repository.py tests/unit/inbox/test_imap_reader_disabled.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/hiresense/inbox/infrastructure backend/src/hiresense/infrastructure/registry.py backend/tests/integration/test_inbox_repository.py backend/tests/unit/inbox/test_imap_reader_disabled.py
git commit -m "feat(inbox): add signal ORM/repo + config-gated IMAP reader"
```

---

## Task 8: API — provider, dependencies, routes

**Files:**
- Create: `inbox/api/provider.py`, `inbox/api/dependencies.py`, `inbox/api/routes.py`, `inbox/api/__init__.py`
- Test: `backend/tests/integration/test_inbox_endpoints.py`

**Interfaces:**
- Consumes: `InboxProcessingService`, `DetectedSignalRepository`, `SignalState`; `TrackingService` (`async update_status(id, ApplicationStatus, notes=None)`) via `get_tracking_service`; `ApplicationStatus`; `require_auth`.
- Produces: `InboxProvider(service, repo)` with `get_service()` + `get_repo()`; `get_inbox_provider`; router with `POST /tracking/ingest-email`, `GET /inbox/signals`, `POST /inbox/signals/{id}/confirm`, `POST /inbox/signals/{id}/dismiss`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_inbox_endpoints.py
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.inbox.api import router as inbox_router
from hiresense.inbox.api.dependencies import get_inbox_provider
from hiresense.inbox.api.provider import InboxProvider
from hiresense.inbox.domain import (
    ApplicationMatcher, EmailClassification, EmailSignalKind, InboxProcessingService,
)
from hiresense.tracking.api.dependencies import get_tracking_service
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


class _Reader:
    def fetch_unseen(self): return []


class _Repo:
    def __init__(self): self.signals = []
    def add(self, s): s.id = uuid.uuid4(); self.signals.append(s); return s
    def list(self, state=None):
        return [s for s in self.signals if state is None or s.state == state]
    def get(self, id): return next((s for s in self.signals if s.id == id), None)
    def set_state(self, id, state):
        s = self.get(id); s.state = state; return s
    def exists_message_id(self, mid): return any(s.message_id == mid for s in self.signals)


class _Classifier:
    async def classify(self, email):
        return EmailClassification(job_related=True, kind=EmailSignalKind.REJECTION,
                                   company="Acme", role="Dev", confidence=0.9)


class _Tracking:
    def __init__(self, app): self._app = app; self.updated = []
    async def update_status(self, id, status, notes=None):
        self.updated.append((id, status)); return self._app


def _build_app():
    app_model = TrackedApplication(id=uuid.uuid4(), title="Dev", company="Acme",
                                   status=ApplicationStatus.APPLIED.value)
    repo = _Repo()
    service = InboxProcessingService(
        reader=_Reader(), repo=repo, classifier=_Classifier(),
        matcher=ApplicationMatcher(min_confidence=0.5), list_active=lambda: [app_model],
    )
    tracking = _Tracking(app_model)
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "u"
    app.dependency_overrides[get_inbox_provider] = lambda: InboxProvider(service=service, repo=repo)
    app.dependency_overrides[get_tracking_service] = lambda: tracking
    app.include_router(inbox_router)
    return app, repo, tracking, app_model


@pytest.mark.asyncio
async def test_ingest_then_confirm_updates_status():
    app, repo, tracking, app_model = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.post("/tracking/ingest-email", json={
            "from_address": "r@acme.com", "subject": "Update", "body": "We regret..."})
        assert r.status_code == 201
        sig = r.json()
        assert sig["proposed_status"] == "rejected"

        lst = await client.get("/inbox/signals?state=pending")
        assert len(lst.json()) == 1

        conf = await client.post(f"/inbox/signals/{sig['id']}/confirm")
        assert conf.status_code == 200
    assert tracking.updated[0][1] == ApplicationStatus.REJECTED
    assert repo.get(uuid.UUID(sig["id"])).state.value == "applied"


@pytest.mark.asyncio
async def test_confirm_unmatched_returns_409():
    app, repo, tracking, _ = _build_app()
    # Insert an unmatched signal directly.
    from hiresense.inbox.domain import DetectedSignal
    sig = repo.add(DetectedSignal(
        message_id="x", from_address="a@b.com", subject="s",
        received_at=datetime.now(timezone.utc), kind=EmailSignalKind.OTHER,
        matched_application_id=None, proposed_status=None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        conf = await client.post(f"/inbox/signals/{sig.id}/confirm")
    assert conf.status_code == 409


@pytest.mark.asyncio
async def test_dismiss_sets_state():
    app, repo, tracking, _ = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        r = await client.post("/tracking/ingest-email", json={
            "from_address": "r@acme.com", "subject": "Update", "body": "We regret..."})
        sid = r.json()["id"]
        d = await client.post(f"/inbox/signals/{sid}/dismiss")
        assert d.status_code == 200
    assert repo.get(uuid.UUID(sid)).state.value == "dismissed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/integration/test_inbox_endpoints.py -v`
Expected: FAIL — `ModuleNotFoundError: ...inbox.api`.

- [ ] **Step 3: Implement provider + dependencies**

`inbox/api/provider.py`:

```python
from __future__ import annotations

from hiresense.inbox.domain import InboxProcessingService
from hiresense.inbox.domain.ports import DetectedSignalRepository


class InboxProvider:
    def __init__(self, *, service: InboxProcessingService, repo: DetectedSignalRepository) -> None:
        self._service = service
        self._repo = repo

    def get_service(self) -> InboxProcessingService:
        return self._service

    def get_repo(self) -> DetectedSignalRepository:
        return self._repo
```

`inbox/api/dependencies.py`:

```python
from __future__ import annotations

from fastapi import Request

from hiresense.inbox.api.provider import InboxProvider


def get_inbox_provider(request: Request) -> InboxProvider:
    return request.app.state.inbox
```

- [ ] **Step 4: Implement routes + `__init__`**

`inbox/api/routes.py`:

```python
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from hiresense.identity.api.dependencies import require_auth
from hiresense.inbox.api.dependencies import get_inbox_provider
from hiresense.inbox.api.provider import InboxProvider
from hiresense.inbox.domain import DetectedSignal, InboundEmail, SignalState
from hiresense.tracking.api.dependencies import get_tracking_service
from hiresense.tracking.domain import TrackingService
from hiresense.tracking.domain.models import ApplicationStatus

router = APIRouter(tags=["inbox"], dependencies=[Depends(require_auth)])


class IngestEmailRequest(BaseModel):
    from_address: str
    subject: str
    body: str
    message_id: str | None = None
    received_at: datetime | None = None


@router.post("/tracking/ingest-email", response_model=None, status_code=201)
async def ingest_email(
    body: IngestEmailRequest,
    provider: Annotated[InboxProvider, Depends(get_inbox_provider)],
) -> DetectedSignal | Response:
    email = InboundEmail(
        message_id=body.message_id or f"manual-{uuid_mod.uuid4()}",
        from_address=body.from_address,
        subject=body.subject,
        body=body.body,
        received_at=body.received_at or datetime.now(timezone.utc),
    )
    signal = await provider.get_service().ingest_one(email)
    if signal is None:
        return Response(status_code=204)
    return signal


@router.get("/inbox/signals", response_model=list[DetectedSignal])
def list_signals(
    provider: Annotated[InboxProvider, Depends(get_inbox_provider)],
    state: SignalState | None = None,
) -> list[DetectedSignal]:
    return provider.get_repo().list(state=state)


@router.post("/inbox/signals/{signal_id}/confirm", response_model=DetectedSignal)
async def confirm_signal(
    signal_id: uuid_mod.UUID,
    provider: Annotated[InboxProvider, Depends(get_inbox_provider)],
    tracking: Annotated[TrackingService, Depends(get_tracking_service)],
) -> DetectedSignal:
    repo = provider.get_repo()
    signal = repo.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    if signal.matched_application_id is None or signal.proposed_status is None:
        raise HTTPException(status_code=409, detail="Signal has no matched application to update")
    await tracking.update_status(
        signal.matched_application_id, ApplicationStatus(signal.proposed_status)
    )
    updated = repo.set_state(signal_id, SignalState.APPLIED)
    return updated


@router.post("/inbox/signals/{signal_id}/dismiss", response_model=DetectedSignal)
def dismiss_signal(
    signal_id: uuid_mod.UUID,
    provider: Annotated[InboxProvider, Depends(get_inbox_provider)],
) -> DetectedSignal:
    repo = provider.get_repo()
    if repo.get(signal_id) is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    return repo.set_state(signal_id, SignalState.DISMISSED)
```

`inbox/api/__init__.py`:

```python
from hiresense.inbox.api.routes import router

__all__ = ["router"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/integration/test_inbox_endpoints.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/inbox/api backend/tests/integration/test_inbox_endpoints.py
git commit -m "feat(inbox): add ingest-email + signal review API"
```

---

## Task 9: NotificationService.notify_inbox_signals

**Files:**
- Create: `backend/src/hiresense/notifications/domain/inbox_signals_email.py`
- Modify: `backend/src/hiresense/notifications/domain/notification_service.py`, `backend/src/hiresense/notifications/domain/__init__.py`
- Test: `backend/tests/unit/notifications/test_inbox_signals_notify.py`

**Interfaces:**
- Produces: `render_inbox_signals_email(count: int) -> tuple[str, str]`; `NotificationService.notify_inbox_signals(count: int) -> bool` (best-effort, like the others).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/notifications/test_inbox_signals_notify.py
import pytest

from hiresense.notifications.domain import NotificationService, render_inbox_signals_email


class _Sender:
    def __init__(self): self.sent = []
    def send(self, message): self.sent.append(message)


def test_render_includes_count():
    subject, body = render_inbox_signals_email(3)
    assert "3" in subject
    assert "3" in body


@pytest.mark.asyncio
async def test_notify_inbox_signals_sends_when_enabled():
    sender = _Sender()
    svc = NotificationService(sender=sender, to_email="me@x.com")
    assert await svc.notify_inbox_signals(2) is True
    assert len(sender.sent) == 1


@pytest.mark.asyncio
async def test_notify_inbox_signals_noop_when_disabled():
    sender = _Sender()
    svc = NotificationService(sender=sender, to_email="")
    assert await svc.notify_inbox_signals(2) is False
    assert sender.sent == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/notifications/test_inbox_signals_notify.py -v`
Expected: FAIL — `ImportError: cannot import name 'render_inbox_signals_email'`.

- [ ] **Step 3: Implement the render fn + service method**

`backend/src/hiresense/notifications/domain/inbox_signals_email.py`:

```python
from __future__ import annotations


def render_inbox_signals_email(count: int) -> tuple[str, str]:
    """Render an inbox-signals alert into (subject, plain-text body)."""
    noun = "signal" if count == 1 else "signals"
    subject = f"HireSense: {count} new application {noun} detected"
    body = (
        f"{count} new email {noun} were detected from your inbox.\n\n"
        "Open HireSense to review and confirm the proposed tracking updates."
    )
    return subject, body
```

In `notification_service.py`, add the import at the top:

```python
from hiresense.notifications.domain.inbox_signals_email import render_inbox_signals_email
```

and add the method (after `notify_job_failure`):

```python
    async def notify_inbox_signals(self, count: int) -> bool:
        subject, body = render_inbox_signals_email(count)
        return await self._safe_send(subject, body)
```

Update `notifications/domain/__init__.py` to export `render_inbox_signals_email` (add the import and `__all__` entry).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/notifications/test_inbox_signals_notify.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/notifications/domain/inbox_signals_email.py backend/src/hiresense/notifications/domain/notification_service.py backend/src/hiresense/notifications/domain/__init__.py backend/tests/unit/notifications/test_inbox_signals_notify.py
git commit -m "feat(inbox): add notify_inbox_signals to NotificationService"
```

---

## Task 10: Bootstrap + scheduler inbox_scan job + main wiring

**Files:**
- Create: `backend/src/hiresense/bootstrap/inbox.py`
- Modify: `backend/src/hiresense/bootstrap/scheduler.py`, `backend/src/hiresense/bootstrap/__init__.py`, `backend/src/hiresense/main.py`
- Test: `backend/tests/unit/scheduler/test_build_scheduler_inbox.py`, `backend/tests/integration/test_inbox_app_wiring.py`

**Interfaces:**
- Consumes: `InboxProcessingService`, `EmailClassifier`, `ApplicationMatcher`, `ImapInboxReader`, `DetectedSignalRepositoryImpl`; the tracked LLM factory; `TrackingService` (for `list_active`); `NotificationService`.
- Produces: `build_inbox(infra, tracked, *, tracking_service, notification_service=None) -> InboxBuild(provider, service)`; `build_scheduler(..., inbox_processing_service=None)` adds an `inbox_scan` job when provided.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/scheduler/test_build_scheduler_inbox.py
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
    inbox_scan_schedule = "0 */2 * * *"
    scheduler_run_retention_days = 30


class _Svc:
    async def run(self): return 4


def _noop():
    class _N:
        async def run(self): return []
        async def sweep(self): return []
    return _N()


@pytest.mark.asyncio
async def test_inbox_scan_job_present_when_service_injected():
    class _Auto:
        async def run(self): return type("D", (), {"job_count": 0})()
    class _Out:
        def due_followups(self): return []
    build = build_scheduler(
        settings=_Settings(), sync_session_factory=_factory(),
        ingestion_orchestrator=_noop(), revalidation_service=_noop(),
        autohunt_service=_Auto(), outreach_service=_Out(),
        inbox_processing_service=_Svc(),
    )
    names = {v.name for v in build.provider.list_jobs()}
    assert "inbox_scan" in names
    run = await build.provider.run_now("inbox_scan")
    assert run.items_affected == 4


def test_inbox_scan_absent_by_default():
    class _Auto:
        async def run(self): return type("D", (), {"job_count": 0})()
    class _Out:
        def due_followups(self): return []
    build = build_scheduler(
        settings=_Settings(), sync_session_factory=_factory(),
        ingestion_orchestrator=_noop(), revalidation_service=_noop(),
        autohunt_service=_Auto(), outreach_service=_Out(),
    )
    names = {v.name for v in build.provider.list_jobs()}
    assert "inbox_scan" not in names
```

```python
# backend/tests/integration/test_inbox_app_wiring.py
import pytest
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.main import create_app


@pytest.mark.asyncio
async def test_inbox_signals_route_mounted():
    app = create_app()
    app.dependency_overrides[require_auth] = lambda: "u"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/inbox/signals")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler/test_build_scheduler_inbox.py tests/integration/test_inbox_app_wiring.py -v`
Expected: FAIL — `build_scheduler() got an unexpected keyword argument 'inbox_processing_service'` / 404 on `/inbox/signals`.

- [ ] **Step 3: Implement build_inbox**

`backend/src/hiresense/bootstrap/inbox.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.inbox.api.provider import InboxProvider
from hiresense.inbox.domain import (
    ApplicationMatcher,
    EmailClassifier,
    InboxProcessingService,
)
from hiresense.inbox.infrastructure import DetectedSignalRepositoryImpl, ImapInboxReader
from hiresense.tracking.domain.models import ApplicationStatus


@dataclass(frozen=True)
class InboxBuild:
    provider: InboxProvider
    service: InboxProcessingService


def build_inbox(
    infra: SharedInfra,
    tracked: Callable[[str], Any],
    *,
    tracking_service: Any,
    notification_service: Any = None,
) -> InboxBuild:
    s = infra.settings
    repo = DetectedSignalRepositoryImpl(session_factory=infra.sync_session_factory)
    reader = ImapInboxReader(
        host=s.imap_host,
        port=s.imap_port,
        username=s.imap_username,
        password=s.imap_password,
        folder=s.imap_folder,
        use_ssl=s.imap_use_ssl,
    )
    active = {ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEWING}

    def _list_active() -> list[Any]:
        apps: list[Any] = []
        for status in active:
            apps.extend(tracking_service.list(status=status))
        return apps

    service = InboxProcessingService(
        reader=reader,
        repo=repo,
        classifier=EmailClassifier(tracked("inbox-classification")),
        matcher=ApplicationMatcher(min_confidence=s.inbox_signal_match_min_confidence),
        list_active=_list_active,
        notifier=notification_service,
    )
    return InboxBuild(provider=InboxProvider(service=service, repo=repo), service=service)
```

Add to `bootstrap/__init__.py` (alphabetical) and `__all__`:

```python
from hiresense.bootstrap.inbox import InboxBuild, build_inbox
```

- [ ] **Step 4: Add the inbox_scan job to build_scheduler**

In `bootstrap/scheduler.py`, add `inbox_processing_service: Any = None` to the `build_scheduler` signature (keyword). After building the base `definitions` list, append the inbox job conditionally — insert this right before the `run_repo = ...` line:

```python
    if inbox_processing_service is not None:
        definitions.append(
            JobDefinition(
                name="inbox_scan",
                run=inbox_processing_service.run,
                cron=settings.inbox_scan_schedule,
                interval_hours=None,
                count_items=lambda n: n if isinstance(n, int) else None,
            )
        )
```

(`InboxProcessingService.run()` returns an `int`, so `count_items` records it directly.)

- [ ] **Step 5: Wire main.py**

Add the router import near the others:

```python
from hiresense.inbox.api import router as inbox_router
```

Add `build_inbox` to the `from hiresense.bootstrap import (...)` block.

After the notifications block and BEFORE the scheduler block, add:

```python
    # --- Inbox (Autopilot Phase 3: inbound email -> tracking signals) ---
    inbox = build_inbox(
        infra,
        tracked,
        tracking_service=tracking.service,
        notification_service=notifications.service,
    )
    app.state.inbox = inbox.provider
    app.include_router(inbox_router)
```

Then add `inbox_processing_service=inbox.service` to the existing `build_scheduler(...)` call.

> `tracking.service` exists on the `TrackingBuild` (the tracking provider wraps it).
> Confirm by reading `bootstrap/tracking.py`; if the build exposes the service under
> a different attribute, use that. `tracked` is the factory already in scope in
> `create_app` (used by other `build_*` calls).

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/scheduler tests/integration/test_inbox_app_wiring.py -v`
Expected: PASS — inbox tests green AND existing scheduler tests still green.

- [ ] **Step 7: Run the full backend suite + lint**

Run: `cd backend && uv run python -m pytest -q && uv run ruff check .`
Expected: all green; no new ruff issues.

- [ ] **Step 8: Commit**

```bash
git add backend/src/hiresense/bootstrap/inbox.py backend/src/hiresense/bootstrap/scheduler.py backend/src/hiresense/bootstrap/__init__.py backend/src/hiresense/main.py backend/tests/unit/scheduler/test_build_scheduler_inbox.py backend/tests/integration/test_inbox_app_wiring.py
git commit -m "feat(inbox): build_inbox + inbox_scan scheduler job + main wiring"
```

---

## Task 11: Alembic migration

**Files:**
- Create: `backend/alembic/versions/034_add_inbox_detected_signals.py`

- [ ] **Step 1: Hand-write the migration**

This project uses sequential numeric revisions; current head is `033`. Mirror the
style of `033_add_scheduler_tables.py`. Create `034_add_inbox_detected_signals.py`:

```python
"""add inbox_detected_signals

Revision ID: 034
Revises: 033
Create Date: 2026-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inbox_detected_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.String(length=512), nullable=False),
        sa.Column("from_address", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("company", sa.String(length=256), nullable=True),
        sa.Column("role", sa.String(length=256), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("matched_application_id", sa.Uuid(), nullable=True),
        sa.Column("proposed_status", sa.String(length=16), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inbox_detected_signals_message_id",
        "inbox_detected_signals",
        ["message_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_inbox_detected_signals_message_id", table_name="inbox_detected_signals")
    op.drop_table("inbox_detected_signals")
```

- [ ] **Step 2: Verify history is linear (no DB needed)**

Run: `cd backend && uv run python -m alembic history`
Expected: `034` appears after `033`; no "multiple heads" error.

- [ ] **Step 3: Confirm metadata still builds**

Run: `cd backend && uv run python -m pytest tests/integration/test_inbox_repository.py -v`
Expected: PASS (table builds from metadata, matching the migration).

> Post-merge reminder: run `uv run python -m alembic upgrade head` on the dev DB.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/034_add_inbox_detected_signals.py
git commit -m "feat(inbox): migration for inbox_detected_signals"
```

---

## Task 12: Frontend — Signals review surface

**Files:**
- Create: `frontend/src/app/core/models/inbox.model.ts`, `frontend/src/app/core/services/inbox.service.ts`, `frontend/src/app/core/services/inbox.service.spec.ts`
- Create: `frontend/src/app/pages/tracking/signals/signals.component.{ts,html,scss,spec.ts}`
- Modify: `frontend/src/app/app.routes.ts`, `frontend/src/app/core/nav/hubs.const.ts`

**Interfaces:**
- Consumes: `GET /api/inbox/signals?state=pending` → `DetectedSignal[]`; `POST /api/inbox/signals/{id}/confirm`; `POST /api/inbox/signals/{id}/dismiss`. Backend serializes snake_case (no camelCasing interceptor — verify against `core/interceptors/` and an existing model).

- [ ] **Step 1: Write the failing service spec**

```typescript
// frontend/src/app/core/services/inbox.service.spec.ts
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { InboxService } from './inbox.service';

describe('InboxService', () => {
  let service: InboxService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [InboxService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(InboxService);
    httpMock = TestBed.inject(HttpTestingController);
  });
  afterEach(() => httpMock.verify());

  it('lists pending signals', () => {
    let result: unknown;
    service.listPending().subscribe((r) => (result = r));
    const req = httpMock.expectOne('/api/inbox/signals?state=pending');
    expect(req.request.method).toBe('GET');
    req.flush([{ id: '1', subject: 'X', kind: 'rejection', state: 'pending',
      proposed_status: 'rejected', matched_application_id: 'a', company: 'Acme',
      from_address: 'r@a.com', confidence: 0.9 }]);
    expect((result as unknown[]).length).toBe(1);
  });

  it('confirms a signal', () => {
    service.confirm('1').subscribe();
    const req = httpMock.expectOne('/api/inbox/signals/1/confirm');
    expect(req.request.method).toBe('POST');
    req.flush({ id: '1', state: 'applied' });
  });

  it('dismisses a signal', () => {
    service.dismiss('1').subscribe();
    const req = httpMock.expectOne('/api/inbox/signals/1/dismiss');
    expect(req.request.method).toBe('POST');
    req.flush({ id: '1', state: 'dismissed' });
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npm test -- --include "**/inbox.service.spec.ts"`
Expected: FAIL — cannot find `./inbox.service`.

- [ ] **Step 3: Implement model + service**

`frontend/src/app/core/models/inbox.model.ts`:

```typescript
export interface DetectedSignal {
  id: string;
  message_id: string;
  from_address: string;
  subject: string;
  received_at: string;
  kind: 'rejection' | 'interview' | 'offer' | 'other';
  company: string | null;
  role: string | null;
  confidence: number;
  matched_application_id: string | null;
  proposed_status: string | null;
  state: 'pending' | 'applied' | 'dismissed';
}
```

(Snake_case to match the wire format — this project has no camelCasing HTTP interceptor; confirm against `core/interceptors/` as in prior phases.)

`frontend/src/app/core/services/inbox.service.ts`:

```typescript
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { DetectedSignal } from '../models/inbox.model';

@Injectable({ providedIn: 'root' })
export class InboxService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/inbox';

  listPending(): Observable<DetectedSignal[]> {
    return this.http.get<DetectedSignal[]>(`${this.base}/signals?state=pending`);
  }

  confirm(id: string): Observable<DetectedSignal> {
    return this.http.post<DetectedSignal>(`${this.base}/signals/${id}/confirm`, {});
  }

  dismiss(id: string): Observable<DetectedSignal> {
    return this.http.post<DetectedSignal>(`${this.base}/signals/${id}/dismiss`, {});
  }
}
```

- [ ] **Step 4: Run to verify the service spec passes**

Run: `cd frontend && npm test -- --include "**/inbox.service.spec.ts"`
Expected: PASS.

- [ ] **Step 5: Write the failing component spec**

```typescript
// frontend/src/app/pages/tracking/signals/signals.component.spec.ts
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { SignalsComponent } from './signals.component';

describe('SignalsComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [SignalsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    httpMock = TestBed.inject(HttpTestingController);
  });
  afterEach(() => httpMock.verify());

  it('loads pending signals on init', () => {
    const fixture = TestBed.createComponent(SignalsComponent);
    fixture.detectChanges();
    const req = httpMock.expectOne('/api/inbox/signals?state=pending');
    req.flush([{ id: '1', subject: 'X', kind: 'rejection', state: 'pending',
      proposed_status: 'rejected', matched_application_id: 'a', company: 'Acme',
      from_address: 'r@a.com', confidence: 0.9 }]);
    expect(fixture.componentInstance.signals().length).toBe(1);
  });
});
```

- [ ] **Step 6: Run to verify it fails**

Run: `cd frontend && npm test -- --include "**/signals.component.spec.ts"`
Expected: FAIL — cannot find `./signals.component`.

- [ ] **Step 7: Implement the component**

`frontend/src/app/pages/tracking/signals/signals.component.ts`:

```typescript
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { InboxService } from '../../../core/services/inbox.service';
import { DetectedSignal } from '../../../core/models/inbox.model';

@Component({
  selector: 'app-signals',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './signals.component.html',
  styleUrl: './signals.component.scss',
})
export class SignalsComponent implements OnInit {
  private readonly service = inject(InboxService);
  readonly signals = signal<DetectedSignal[]>([]);
  readonly busy = signal<string | null>(null);

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.service.listPending().subscribe((s) => this.signals.set(s));
  }

  confirm(s: DetectedSignal): void {
    this.busy.set(s.id);
    this.service.confirm(s.id).subscribe(() => {
      this.busy.set(null);
      this.reload();
    });
  }

  dismiss(s: DetectedSignal): void {
    this.busy.set(s.id);
    this.service.dismiss(s.id).subscribe(() => {
      this.busy.set(null);
      this.reload();
    });
  }
}
```

`frontend/src/app/pages/tracking/signals/signals.component.html`:

```html
<section class="signals">
  <h1>Inbox signals</h1>
  @if (signals().length === 0) {
    <p>No pending signals.</p>
  }
  @for (s of signals(); track s.id) {
    <div class="signal">
      <div class="meta">
        <strong>{{ s.kind }}</strong> · {{ s.company || s.from_address }}
        <small>{{ s.subject }}</small>
      </div>
      <div class="proposed">
        @if (s.proposed_status) {
          → propose <strong>{{ s.proposed_status }}</strong>
        } @else {
          <span class="muted">no match</span>
        }
      </div>
      <div class="actions">
        <button type="button" (click)="confirm(s)"
                [disabled]="busy() === s.id || !s.proposed_status">Confirm</button>
        <button type="button" (click)="dismiss(s)" [disabled]="busy() === s.id">Dismiss</button>
      </div>
    </div>
  }
</section>
```

`frontend/src/app/pages/tracking/signals/signals.component.scss`:

```scss
.signals {
  padding: 1rem;

  .signal {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border, #e2e2e2);
  }

  .muted { color: var(--muted, #888); }
  .actions button { margin-left: 0.5rem; }
}
```

- [ ] **Step 8: Register route + nav**

In `app.routes.ts`, add a route mirroring the existing admin sub-routes (use the same guard the tracking page uses — read an existing tracking/authed route first; if tracking is behind `authGuard`, use that):

```typescript
  {
    path: 'tracking/signals',
    loadComponent: () =>
      import('./pages/tracking/signals/signals.component').then((m) => m.SignalsComponent),
  },
```

In `core/nav/hubs.const.ts`, add a nav entry under the tracking hub (mirror an existing tracking entry; use the matching path prefix that the existing tracking nav entries use):

```typescript
      { label: 'Inbox signals', path: '/dashboard/tracking/signals' },
```

(Read the existing tracking route + nav entries first and match their exact guard and path prefix.)

- [ ] **Step 9: Run component spec + lint + build**

Run: `cd frontend && npm test -- --include "**/signals.component.spec.ts"`
Expected: PASS.

Run: `cd frontend && npx ng lint && npm run build`
Expected: lint clean; build succeeds.

- [ ] **Step 10: Verify clean staging and commit**

Confirm via `git status` that ONLY the new inbox files + `app.routes.ts` + `hubs.const.ts` are staged (NOT the pre-existing modified frontend files).

```bash
git add frontend/src/app/core/models/inbox.model.ts frontend/src/app/core/services/inbox.service.ts frontend/src/app/core/services/inbox.service.spec.ts frontend/src/app/pages/tracking/signals frontend/src/app/app.routes.ts frontend/src/app/core/nav/hubs.const.ts
git commit -m "feat(inbox): signals review page (confirm/dismiss)"
```

---

## Final verification

- [ ] Backend: `cd backend && uv run python -m pytest -q && uv run ruff check .` — all green.
- [ ] Frontend: `cd frontend && npx ng lint && npm test` — all green.
- [ ] Manual smoke (optional): `POST /tracking/ingest-email` with a rejection-style body for a company you have an active application at → a pending signal appears in `GET /inbox/signals`; confirm it → the application's status becomes `rejected` and a `StatusTransition` is recorded.

## Spec coverage check (self-review)

- Config (IMAP + scan cadence + min confidence) → Task 1. Domain models/enums → Task 2. Ports → Task 3. Classifier (LLM JSON, never raises) → Task 4. Matcher (active-only, kind→status, fuzzy, ambiguity→none) → Task 5. Processing service (scan/ingest, dedup, notify) → Task 6. ORM/repo + config-gated IMAP reader + registry → Task 7. ingest-email + review API (confirm→update_status, 409 unmatched, dismiss) → Task 8. notify_inbox_signals → Task 9. build_inbox + inbox_scan scheduler job (absent by default) + main wiring before scheduler → Task 10. Migration 034 → Task 11. Frontend review surface → Task 12. Detect-and-propose (no auto-apply) → Tasks 6/8. Best-effort everywhere → Tasks 4/6/7. Phase-1/2 unchanged when service absent → Task 10 defaults.
