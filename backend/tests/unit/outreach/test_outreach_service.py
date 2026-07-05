import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

import pytest

from hiresense.outreach.domain import OutreachEvent, OutreachEventKind
from hiresense.outreach.domain.outreach_service import OutreachService


class _App:
    def __init__(self, id, company="Acme", status="applied"):
        self.id = id
        self.company = company
        self.title = "Backend Engineer"
        self.status = status
        self.url = None


class _Tracking:
    def __init__(self, apps):
        self._apps = {a.id: a for a in apps}

    def get(self, app_id):
        if app_id not in self._apps:
            raise ValueError("not found")
        return self._apps[app_id]


class _Profile:
    async def get_current_profile(self, language=None):
        return type("P", (), {"name": "Bryan"})()

    def get_for_language(self, language):
        return type("V", (), {"skills": ["python"], "summary": "dev"})()


class _Research:
    def get(self, company):
        return None


class _Gen:
    def __init__(self):
        self.called = False

    async def generate(self, **kwargs):
        self.called = True
        return "drafted message"


class _Repo:
    def __init__(self, latest=None):
        self.added = []
        self._latest_per = latest or []

    def add(self, event):
        saved = event.model_copy(
            update={"id": uuid_mod.uuid4(), "created_at": datetime.now(timezone.utc)}
        )
        self.added.append(saved)
        return saved

    def list_for(self, app_id):
        return [e for e in self.added if e.application_id == app_id]

    def latest_per_application(self):
        return self._latest_per


def _svc(tracking, repo, gen=None, profile=None, research=None):
    return OutreachService(
        tracking_service=tracking,
        profile_service=profile or _Profile(),
        research_service=research or _Research(),
        generator=gen or _Gen(),
        repo=repo,
        style_guide_path="does/not/exist.md",
        followup_cadence_days=7,
        max_chars=500,
        language="en",
    )


@pytest.mark.asyncio
async def test_generate_resolves_and_records_nothing():
    app_id = uuid_mod.uuid4()
    gen = _Gen()
    repo = _Repo()
    svc = _svc(_Tracking([_App(app_id)]), repo, gen=gen)
    out = await svc.generate(app_id, contact_name="Sam")
    assert out == "drafted message" and gen.called
    assert repo.added == []  # generate persists nothing


@pytest.mark.asyncio
async def test_generate_unknown_app_raises():
    repo = _Repo()
    svc = _svc(_Tracking([]), repo)
    with pytest.raises(ValueError):
        await svc.generate(uuid_mod.uuid4())


def test_record_persists_event():
    app_id = uuid_mod.uuid4()
    repo = _Repo()
    svc = _svc(_Tracking([_App(app_id)]), repo)
    evt = svc.record(app_id, kind=OutreachEventKind.SENT, message="hi", contact_name="Sam")
    assert evt.kind == OutreachEventKind.SENT
    assert len(repo.added) == 1


def _latest(app_id, kind, days_ago):
    return OutreachEvent(
        id=uuid_mod.uuid4(),
        application_id=app_id,
        kind=kind,
        message="hi",
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )


def test_due_followups_logic():
    due = uuid_mod.uuid4()  # sent 10d ago, status applied -> due
    fresh = uuid_mod.uuid4()  # sent 2d ago -> not due
    replied = uuid_mod.uuid4()  # latest is replied -> not due
    advanced = uuid_mod.uuid4()  # sent 10d ago but status interviewing -> not due
    repo = _Repo(
        latest=[
            _latest(due, OutreachEventKind.SENT, 10),
            _latest(fresh, OutreachEventKind.SENT, 2),
            _latest(replied, OutreachEventKind.REPLIED, 10),
            _latest(advanced, OutreachEventKind.SENT, 10),
        ]
    )
    tracking = _Tracking(
        [
            _App(due, status="applied"),
            _App(fresh, status="applied"),
            _App(replied, status="applied"),
            _App(advanced, status="interviewing"),
        ]
    )
    svc = _svc(tracking, repo)
    nudges = svc.due_followups()
    ids = {n.application_id for n in nudges}
    assert ids == {due}
    assert nudges[0].days_since >= 10 and nudges[0].company == "Acme"
