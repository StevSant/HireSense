from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.ingestion.infrastructure.models import IngestedJob  # noqa: F401
from hiresense.analytics.infrastructure import CorpusAnalyticsRepository


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _seed(factory):
    with factory() as s:
        s.add_all([
            IngestedJob(id="1", bucket="boards", source="x", source_type="board",
                        title="A", skills=["Python", "React"], remote_modality="remote",
                        salary_range="$100k-$120k", status="open", identity_key="k1",
                        posted_date=datetime(2026, 5, 1, tzinfo=timezone.utc)),
            IngestedJob(id="2", bucket="boards", source="x", source_type="board",
                        title="B", skills=["python", "go"], remote_modality="on_site",
                        salary_range="competitive", status="open", identity_key="k2",
                        posted_date=datetime(2026, 5, 8, tzinfo=timezone.utc)),
            IngestedJob(id="3", bucket="boards", source="x", source_type="board",
                        title="C", skills=["rust"], remote_modality="remote",
                        salary_range=None, status="closed", identity_key="k3",
                        posted_date=datetime(2026, 5, 8, tzinfo=timezone.utc)),
        ])
        s.commit()


def test_open_skill_lists_excludes_closed():
    factory = _factory(); _seed(factory)
    repo = CorpusAnalyticsRepository(session_factory=factory)
    lists = repo.open_skill_lists()
    # 2 open jobs → 2 skill lists; the closed "rust" job is excluded.
    assert len(lists) == 2
    flat = sorted(s for sub in lists for s in sub)
    assert "Python" in flat and "rust" not in flat


def test_remote_modality_counts_open_only():
    factory = _factory(); _seed(factory)
    repo = CorpusAnalyticsRepository(session_factory=factory)
    counts = repo.remote_modality_counts()
    assert counts.get("remote") == 1 and counts.get("on_site") == 1


def test_open_salary_strings_and_total():
    factory = _factory(); _seed(factory)
    repo = CorpusAnalyticsRepository(session_factory=factory)
    salaries, total_open = repo.open_salary_strings()
    assert total_open == 2
    assert "$100k-$120k" in salaries and "competitive" in salaries


def test_salary_strings_for_ids():
    factory = _factory(); _seed(factory)
    repo = CorpusAnalyticsRepository(session_factory=factory)
    assert repo.salary_strings_for_ids(["1", "3"]) == {"1": "$100k-$120k", "3": None}
