from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from hiresense.shared.infrastructure.database import Base
from hiresense.ingestion.domain.quick_match_result import QuickMatchResult
from hiresense.ingestion.domain.quick_match_verdict import QuickMatchVerdict
from hiresense.ingestion.infrastructure.job_match_cache_model import JobMatchCache
from hiresense.ingestion.infrastructure.job_match_cache_repository import JobMatchCacheRepository

_FINGERPRINT = "fp-current"
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

    repo.upsert_quick_bulk(results, _PROFILE, _FINGERPRINT)

    hits = repo.get_quick_bulk(["a", "b", "c"], _PROFILE, _FINGERPRINT)
    assert set(hits) == {"a", "b", "c"}
    assert hits["a"].score == 0.9
    assert hits["b"].score == 0.5
    assert hits["c"].score == 0.1
    assert hits["a"].reasons == ["good fit"]


def test_upsert_quick_bulk_updates_existing_rows_in_place() -> None:
    repo = _make_repo()
    repo.upsert_quick_bulk([_result("a", 0.2)], _PROFILE, _FINGERPRINT)

    # Re-score the same job: must UPDATE, not insert a duplicate row.
    repo.upsert_quick_bulk([_result("a", 0.95)], _PROFILE, _FINGERPRINT)

    hits = repo.get_quick_bulk(["a"], _PROFILE, _FINGERPRINT)
    assert hits["a"].score == 0.95


def test_upsert_quick_bulk_mixes_inserts_and_updates_in_one_call() -> None:
    repo = _make_repo()
    repo.upsert_quick_bulk([_result("a", 0.3)], _PROFILE, _FINGERPRINT)  # pre-existing row

    # "a" is an update, "b" is a fresh insert — both land in one bulk call.
    repo.upsert_quick_bulk([_result("a", 0.7), _result("b", 0.4)], _PROFILE, _FINGERPRINT)

    hits = repo.get_quick_bulk(["a", "b"], _PROFILE, _FINGERPRINT)
    assert hits["a"].score == 0.7
    assert hits["b"].score == 0.4


def test_upsert_quick_bulk_scopes_rows_by_profile_hash() -> None:
    repo = _make_repo()
    repo.upsert_quick_bulk([_result("a", 0.9)], "profile-x", _FINGERPRINT)

    # Same job_id, different profile -> independent cache row.
    hits_other_profile = repo.get_quick_bulk(["a"], "profile-y", _FINGERPRINT)
    assert hits_other_profile == {}


def test_upsert_quick_bulk_empty_list_is_a_noop() -> None:
    repo = _make_repo()

    repo.upsert_quick_bulk([], _PROFILE, _FINGERPRINT)  # must not raise, must not touch the DB

    assert repo.get_quick_bulk(["a"], _PROFILE, _FINGERPRINT) == {}


def test_quick_results_scored_under_a_different_prompt_are_not_served() -> None:
    """Editing a scoring prompt must invalidate its own cached results.

    The cache key was (job_id, profile_hash) alone, so a prompt edit left old
    scores in place and one list mixed results from two different rubrics with
    nothing to indicate they were not comparable.
    """
    repo = _make_repo()
    repo.upsert_quick_bulk([_result("a", 0.9)], _PROFILE, "fp-old")

    assert repo.get_quick_bulk(["a"], _PROFILE, "fp-old") != {}
    assert repo.get_quick_bulk(["a"], _PROFILE, "fp-new") == {}


def test_deep_results_scored_under_a_different_prompt_are_not_served() -> None:
    repo = _make_repo()
    repo.upsert_deep("a", _PROFILE, {"overall_score": 0.8}, "fp-old")

    assert repo.get_deep("a", _PROFILE, "fp-old") == {"overall_score": 0.8}
    assert repo.get_deep("a", _PROFILE, "fp-new") is None


def test_rows_written_before_fingerprinting_existed_are_treated_as_misses() -> None:
    # Every row that predates this column has a NULL fingerprint and cannot be
    # attributed to a prompt, so it must miss rather than be served blindly.
    repo = _make_repo()
    repo.upsert_quick_bulk([_result("a", 0.9)], _PROFILE, "fp-old")
    with repo._session_factory() as session:
        row = session.scalars(select(JobMatchCache).where(JobMatchCache.job_id == "a")).one()
        row.quick_prompt_fingerprint = None
        session.commit()

    assert repo.get_quick_bulk(["a"], _PROFILE, "fp-old") == {}
