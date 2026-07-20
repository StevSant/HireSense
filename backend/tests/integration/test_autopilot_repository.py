import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.autopilot.domain import AutopilotDraft, DraftStatus
from hiresense.autopilot.infrastructure import AutopilotDraftOrm, DraftRepositoryImpl  # noqa: F401
from hiresense.infrastructure.database import Base


def _factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_add_list_exists():
    repo = DraftRepositoryImpl(session_factory=_factory())
    repo.add(
        AutopilotDraft(
            job_id="j1",
            application_id=uuid.uuid4(),
            job_title="Dev",
            company="Acme",
            status=DraftStatus.DRAFTED,
            detail=None,
        )
    )
    assert repo.exists_for_job("j1") is True
    assert repo.exists_for_job("nope") is False
    items = repo.list(limit=10)
    assert len(items) == 1
    assert items[0].status is DraftStatus.DRAFTED


def _pending(job_id: str) -> AutopilotDraft:
    return AutopilotDraft(
        job_id=job_id, job_title="Dev", company="Acme", status=DraftStatus.PENDING
    )


def test_claim_reserves_then_rejects_duplicate():
    repo = DraftRepositoryImpl(session_factory=_factory())

    first = repo.claim(_pending("j1"))
    assert first is not None
    assert first.id is not None
    assert first.status is DraftStatus.PENDING

    # A second claim for the same job hits the unique constraint -> None.
    assert repo.claim(_pending("j1")) is None
    # A different job is still claimable.
    assert repo.claim(_pending("j2")) is not None

    # Only one row exists for j1: the reservation is the idempotency guard.
    assert len(repo.list(limit=10)) == 2


def test_finalize_updates_reserved_row_in_place():
    repo = DraftRepositoryImpl(session_factory=_factory())
    reserved = repo.claim(_pending("j1"))
    assert reserved is not None

    app_id = uuid.uuid4()
    finalized = repo.finalize(
        reserved.model_copy(
            update={"application_id": app_id, "status": DraftStatus.DRAFTED, "detail": "ok"}
        )
    )
    assert finalized.id == reserved.id
    assert finalized.status is DraftStatus.DRAFTED
    assert finalized.application_id == app_id

    items = repo.list(limit=10)
    assert len(items) == 1  # updated in place, not a new row
    assert items[0].status is DraftStatus.DRAFTED
