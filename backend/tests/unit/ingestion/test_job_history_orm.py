from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from hiresense.ingestion.infrastructure import IngestionRunOrm, JobHistoryEventOrm
from hiresense.shared.infrastructure.database import Base


def _session_factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_run_and_event_round_trip_with_json_changed_fields():
    factory = _session_factory()
    now = datetime.now(timezone.utc)
    run_id = uuid.uuid4()

    with factory() as session:
        session.add(IngestionRunOrm(id=run_id, started_at=now, trigger="fetch", status="running"))
        session.add(
            JobHistoryEventOrm(
                id=uuid.uuid4(),
                job_id="job-1",
                run_id=run_id,
                event="updated",
                changed_fields={"title": {"old": "Engineer", "new": "Senior Engineer"}},
                reason=None,
                occurred_at=now,
            )
        )
        session.commit()

    with factory() as session:
        event = session.scalars(select(JobHistoryEventOrm)).one()
        assert event.changed_fields["title"]["new"] == "Senior Engineer"
        assert event.run_id == run_id
        run = session.scalars(select(IngestionRunOrm)).one()
        assert run.finished_at is None
        assert run.status == "running"


def test_event_run_id_is_nullable_for_sweep_closures():
    factory = _session_factory()
    with factory() as session:
        session.add(
            JobHistoryEventOrm(
                id=uuid.uuid4(),
                job_id="job-2",
                run_id=None,
                event="closed",
                changed_fields={},
                reason="dead_end_redirect",
                occurred_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

    with factory() as session:
        event = session.scalars(select(JobHistoryEventOrm)).one()
        assert event.run_id is None
        assert event.reason == "dead_end_redirect"
