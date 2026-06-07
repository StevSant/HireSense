from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.admin.infrastructure import LLMUsageLogRepository
from hiresense.admin.infrastructure.llm_usage_log_model import LLMUsageLog
from hiresense.infrastructure.database import Base


def _factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _seed(factory, n: int):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with factory() as s:
        s.add_all([
            LLMUsageLog(
                feature_key="match_quick_scorer",
                provider="anthropic",
                model="claude-haiku-4-5",
                input_tokens=i,
                output_tokens=i,
                total_tokens=2 * i,
                cost_usd=0.0,
                latency_ms=1.0,
                success=True,
                error=None,
                user_id=None,
                # Distinct, increasing timestamps so "newest-first" is well-defined.
                created_at=base + timedelta(minutes=i),
            )
            for i in range(20)
        ])
        s.commit()


def test_list_recent_applies_limit_and_orders_newest_first():
    factory = _factory()
    _seed(factory, 20)
    repo = LLMUsageLogRepository(session_factory=factory)

    rows = repo.list_recent(limit=5)

    # Only `limit` rows come back even though 20 exist.
    assert len(rows) == 5
    # Newest-first: created_at strictly descending.
    timestamps = [r.created_at for r in rows]
    assert timestamps == sorted(timestamps, reverse=True)
    # The 5 newest were minutes 19..15 (input_tokens carries the index).
    assert [r.input_tokens for r in rows] == [19, 18, 17, 16, 15]
