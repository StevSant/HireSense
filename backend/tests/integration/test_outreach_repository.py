import uuid as uuid_mod

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.outreach.domain import OutreachEvent, OutreachEventKind
from hiresense.outreach.infrastructure import OutreachRepository
from hiresense.outreach.infrastructure.orm import OutreachEventOrm  # noqa: F401


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _evt(app_id, kind, msg="hi"):
    return OutreachEvent(application_id=app_id, kind=kind, message=msg, contact_name="Sam")


def test_add_and_list_for():
    repo = OutreachRepository(session_factory=_factory())
    app_id = uuid_mod.uuid4()
    saved = repo.add(_evt(app_id, OutreachEventKind.SENT))
    assert saved.id is not None and saved.created_at is not None
    events = repo.list_for(app_id)
    assert len(events) == 1 and events[0].kind == OutreachEventKind.SENT


def test_latest_for_returns_most_recent():
    repo = OutreachRepository(session_factory=_factory())
    app_id = uuid_mod.uuid4()
    repo.add(_evt(app_id, OutreachEventKind.SENT))
    repo.add(_evt(app_id, OutreachEventKind.REPLIED, msg=None))
    latest = repo.latest_for(app_id)
    assert latest is not None and latest.kind == OutreachEventKind.REPLIED


def test_latest_per_application():
    repo = OutreachRepository(session_factory=_factory())
    a, b = uuid_mod.uuid4(), uuid_mod.uuid4()
    repo.add(_evt(a, OutreachEventKind.SENT))
    repo.add(_evt(a, OutreachEventKind.FOLLOWED_UP))
    repo.add(_evt(b, OutreachEventKind.SENT))
    latest = repo.latest_per_application()
    by_app = {e.application_id: e.kind for e in latest}
    assert by_app[a] == OutreachEventKind.FOLLOWED_UP and by_app[b] == OutreachEventKind.SENT
    assert len(latest) == 2
