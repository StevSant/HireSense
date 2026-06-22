import uuid
from datetime import datetime, timezone

import pytest

from hiresense.inbox.domain import (
    ApplicationMatcher,
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


class _FailingReader:
    def fetch_unseen(self): raise OSError("connection refused")


class _Classifier:
    def __init__(self, result): self._result = result
    async def classify(self, email): return self._result


class _Notifier:
    def __init__(self): self.calls = []
    async def notify_inbox_signals(self, count):
        self.calls.append(count)
        return True


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
async def test_run_returns_zero_when_reader_raises():
    classification = EmailClassification(job_related=True, kind=EmailSignalKind.REJECTION,
                                         company="Acme", role="Dev", confidence=0.9)
    svc = _service(_FailingReader(), _Repo(), classification)
    count = await svc.run()
    assert count == 0


@pytest.mark.asyncio
async def test_ingest_one_returns_none_when_not_job_related():
    result = await _service(_Reader([]), _Repo(),
                            EmailClassification(job_related=False)).ingest_one(_email())
    assert result is None
