import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.autopilot.domain import AutopilotDraft, DraftStatus
from hiresense.autopilot.infrastructure import AutopilotDraftOrm, DraftRepositoryImpl  # noqa: F401
from hiresense.infrastructure.database import Base


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_add_list_exists():
    repo = DraftRepositoryImpl(session_factory=_factory())
    repo.add(AutopilotDraft(job_id="j1", application_id=uuid.uuid4(), job_title="Dev",
                            company="Acme", status=DraftStatus.DRAFTED, detail=None))
    assert repo.exists_for_job("j1") is True
    assert repo.exists_for_job("nope") is False
    items = repo.list(limit=10)
    assert len(items) == 1
    assert items[0].status is DraftStatus.DRAFTED
