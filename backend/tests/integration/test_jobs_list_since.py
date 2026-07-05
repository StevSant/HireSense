from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.ingestion.infrastructure.models import IngestedJob
from hiresense.ingestion.infrastructure.jobs_repository import JobsRepository


def _factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_list_since_filters_by_fetched_at_status_and_bucket():
    factory = _factory()
    now = datetime.now(timezone.utc)
    with factory() as s:
        s.add_all(
            [
                IngestedJob(
                    id="new",
                    bucket="boards",
                    source="x",
                    source_type="board",
                    title="New",
                    identity_key="k1",
                    status="open",
                    fetched_at=now,
                ),
                IngestedJob(
                    id="old",
                    bucket="boards",
                    source="x",
                    source_type="board",
                    title="Old",
                    identity_key="k2",
                    status="open",
                    fetched_at=now - timedelta(days=10),
                ),
                IngestedJob(
                    id="closed",
                    bucket="boards",
                    source="x",
                    source_type="board",
                    title="Closed",
                    identity_key="k3",
                    status="closed",
                    fetched_at=now,
                ),
                IngestedJob(
                    id="portal",
                    bucket="portals",
                    source="y",
                    source_type="portal",
                    title="Portal",
                    identity_key="k4",
                    status="open",
                    fetched_at=now,
                ),
            ]
        )
        s.commit()
    repo = JobsRepository(session_factory=factory, bucket="boards")
    cutoff = now - timedelta(days=1)
    ids = [j.id for j in repo.list_since(cutoff)]
    assert ids == ["new"]  # old (before cutoff), closed (status), portal (bucket) all excluded
