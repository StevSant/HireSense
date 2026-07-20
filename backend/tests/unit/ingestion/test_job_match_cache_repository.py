from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.infrastructure.database import Base
from hiresense.ingestion.domain.quick_match_result import QuickMatchResult
from hiresense.ingestion.domain.quick_match_verdict import QuickMatchVerdict
from hiresense.ingestion.infrastructure.job_match_cache_model import JobMatchCache  # noqa: F401
from hiresense.ingestion.infrastructure.job_match_cache_repository import JobMatchCacheRepository

_PROFILE = "profile-hash-1"


def _make_repo() -> JobMatchCacheRepository:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return JobMatchCacheRepository(session_factory=session_factory)


def _result(job_id: str, score: float) -> QuickMatchResult:
    return QuickMatchResult(
        job_id=job_id,
        score=score,
        verdict=QuickMatchVerdict.STRONG,
        reasons=["good fit"],
        dealbreakers=[],
    )


def test_upsert_quick_bulk_writes_all_rows_in_one_call() -> None:
    repo = _make_repo()
    results = [_result("a", 0.9), _result("b", 0.5), _result("c", 0.1)]

    repo.upsert_quick_bulk(results, _PROFILE)

    hits = repo.get_quick_bulk(["a", "b", "c"], _PROFILE)
    assert set(hits) == {"a", "b", "c"}
    assert hits["a"].score == 0.9
    assert hits["b"].score == 0.5
    assert hits["c"].score == 0.1
    assert hits["a"].reasons == ["good fit"]


def test_upsert_quick_bulk_updates_existing_rows_in_place() -> None:
    repo = _make_repo()
    repo.upsert_quick_bulk([_result("a", 0.2)], _PROFILE)

    # Re-score the same job: must UPDATE, not insert a duplicate row.
    repo.upsert_quick_bulk([_result("a", 0.95)], _PROFILE)

    hits = repo.get_quick_bulk(["a"], _PROFILE)
    assert hits["a"].score == 0.95


def test_upsert_quick_bulk_mixes_inserts_and_updates_in_one_call() -> None:
    repo = _make_repo()
    repo.upsert_quick_bulk([_result("a", 0.3)], _PROFILE)  # pre-existing row

    # "a" is an update, "b" is a fresh insert — both land in one bulk call.
    repo.upsert_quick_bulk([_result("a", 0.7), _result("b", 0.4)], _PROFILE)

    hits = repo.get_quick_bulk(["a", "b"], _PROFILE)
    assert hits["a"].score == 0.7
    assert hits["b"].score == 0.4


def test_upsert_quick_bulk_scopes_rows_by_profile_hash() -> None:
    repo = _make_repo()
    repo.upsert_quick_bulk([_result("a", 0.9)], "profile-x")

    # Same job_id, different profile -> independent cache row.
    hits_other_profile = repo.get_quick_bulk(["a"], "profile-y")
    assert hits_other_profile == {}


def test_upsert_quick_bulk_empty_list_is_a_noop() -> None:
    repo = _make_repo()

    repo.upsert_quick_bulk([], _PROFILE)  # must not raise, must not touch the DB

    assert repo.get_quick_bulk(["a"], _PROFILE) == {}
