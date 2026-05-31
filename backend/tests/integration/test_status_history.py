
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.tracking.domain.models import TrackedApplication
from hiresense.tracking.infrastructure.orm import TrackedApplicationOrm  # noqa: F401
from hiresense.tracking.infrastructure.status_history_orm import ApplicationStatusHistoryOrm  # noqa: F401
from hiresense.tracking.infrastructure.repository import TrackingRepository


def _factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_create_seeds_initial_history_row():
    repo = TrackingRepository(session_factory=_factory())
    app = repo.create(TrackedApplication(title="Eng", company="Acme", status="saved"))
    history = repo.history_for(app.id)
    assert len(history) == 1
    assert history[0].from_status is None
    assert history[0].to_status == "saved"


def test_save_with_history_appends_transition_row():
    repo = TrackingRepository(session_factory=_factory())
    app = repo.create(TrackedApplication(title="Eng", company="Acme", status="saved"))
    app.status = "applied"
    repo.save_with_history(app, from_status="saved", to_status="applied")
    history = repo.history_for(app.id)
    assert [(h.from_status, h.to_status) for h in history] == [
        (None, "saved"),
        ("saved", "applied"),
    ]


def test_list_history_returns_all_ordered():
    repo = TrackingRepository(session_factory=_factory())
    a = repo.create(TrackedApplication(title="A", company="X", status="saved"))
    b = repo.create(TrackedApplication(title="B", company="Y", status="saved"))
    a.status = "applied"
    repo.save_with_history(a, from_status="saved", to_status="applied")
    all_rows = repo.list_history()
    assert len(all_rows) == 3
    assert {r.application_id for r in all_rows} == {a.id, b.id}
