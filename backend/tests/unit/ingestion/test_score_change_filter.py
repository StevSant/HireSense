from __future__ import annotations

from hiresense.ingestion.domain import changed_score_updates
from hiresense.ingestion.domain.models import NormalizedJob


def _job(job_id: str, match: float | None, semantic: float | None) -> NormalizedJob:
    return NormalizedJob(
        id=job_id,
        title="E",
        company="C",
        description="D",
        source="remotive",
        source_type="api",
        url=f"https://e.com/{job_id}",
        source_id=job_id,
        match_score=match,
        semantic_score=semantic,
    )


def test_emits_only_changed_rows() -> None:
    originals = {"a": (0.5, 0.2), "b": (0.3, None), "c": (0.9, 0.9)}
    jobs = [_job("a", 0.5, 0.2), _job("b", 0.3, 0.4), _job("c", 0.95, 0.9)]

    updates = changed_score_updates(jobs, originals)

    assert {u.job_id for u in updates} == {"b", "c"}  # "a" unchanged → not written
    by_id = {u.job_id: u for u in updates}
    assert by_id["b"].semantic_score == 0.4
    assert by_id["c"].match_score == 0.95


def test_unchanged_corpus_emits_nothing() -> None:
    # Steady state: a pagination / sort-only reload recomputes the same scores,
    # so NOT ONE row is written — write volume is proportional to changes (#132).
    originals = {f"j{i}": (0.1 * i, 0.2) for i in range(50)}
    jobs = [_job(f"j{i}", 0.1 * i, 0.2) for i in range(50)]

    assert changed_score_updates(jobs, originals) == []


def test_none_to_value_and_value_to_none_are_changes() -> None:
    originals = {"a": (None, None), "b": (0.5, 0.5)}
    jobs = [_job("a", 0.4, None), _job("b", None, 0.5)]

    assert {u.job_id for u in changed_score_updates(jobs, originals)} == {"a", "b"}


def test_unknown_id_is_persisted() -> None:
    updates = changed_score_updates([_job("new", 0.7, 0.3)], {})

    assert len(updates) == 1
    assert updates[0].job_id == "new"
