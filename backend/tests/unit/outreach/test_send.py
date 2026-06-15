import uuid as uuid_mod
from datetime import datetime, timezone

import pytest

from hiresense.outreach.domain import (
    EmailMessage,
    EmailUnavailableError,
    OutreachEventKind,
)
from hiresense.outreach.domain.outreach_service import OutreachService


class _App:
    def __init__(self, id):
        self.id = id
        self.company = "Acme"
        self.title = "Backend Engineer"
        self.status = "applied"


class _Tracking:
    def __init__(self, apps):
        self._apps = {a.id: a for a in apps}

    def get(self, app_id):
        if app_id not in self._apps:
            raise ValueError("not found")
        return self._apps[app_id]


class _Repo:
    def __init__(self):
        self.added = []

    def add(self, event):
        saved = event.model_copy(
            update={"id": uuid_mod.uuid4(), "created_at": datetime.now(timezone.utc)}
        )
        self.added.append(saved)
        return saved


class _Sender:
    def __init__(self, error=None):
        self.sent = []
        self._error = error

    def send(self, message: EmailMessage) -> None:
        if self._error is not None:
            raise self._error
        self.sent.append(message)


def _svc(tracking, repo, sender):
    return OutreachService(
        tracking_service=tracking,
        profile_service=None,
        research_service=None,
        generator=None,
        repo=repo,
        style_guide_path="does/not/exist.md",
        followup_cadence_days=7,
        max_chars=500,
        language="en",
        sender=sender,
    )


@pytest.mark.asyncio
async def test_send_dispatches_email_and_records_sent_event():
    app_id = uuid_mod.uuid4()
    repo = _Repo()
    sender = _Sender()
    svc = _svc(_Tracking([_App(app_id)]), repo, sender)

    event = await svc.send(
        app_id, to="recruiter@acme.com", subject="Hello", message="Body", contact_name="Sam"
    )

    assert len(sender.sent) == 1
    assert sender.sent[0].to == "recruiter@acme.com"
    assert sender.sent[0].subject == "Hello"
    assert sender.sent[0].body == "Body"
    assert event.kind == OutreachEventKind.SENT
    assert event.contact_name == "Sam"
    assert len(repo.added) == 1


@pytest.mark.asyncio
async def test_send_missing_application_raises_and_records_nothing():
    repo = _Repo()
    sender = _Sender()
    svc = _svc(_Tracking([]), repo, sender)

    with pytest.raises(ValueError):
        await svc.send(uuid_mod.uuid4(), to="x@y.com", subject="s", message="m")

    assert sender.sent == []
    assert repo.added == []


@pytest.mark.asyncio
async def test_send_propagates_unavailable_and_records_nothing():
    app_id = uuid_mod.uuid4()
    repo = _Repo()
    sender = _Sender(error=EmailUnavailableError("SMTP is not configured"))
    svc = _svc(_Tracking([_App(app_id)]), repo, sender)

    with pytest.raises(EmailUnavailableError):
        await svc.send(app_id, to="x@y.com", subject="s", message="m")

    assert repo.added == []  # failed send must not be recorded as SENT
