"""Tests for ScoreUpdate value type and bulk_update_scores port method (Work Unit C).

Written BEFORE implementation (TDD RED phase).
Verifies REQ-08: batched score persistence — no N+1 per-job update loop.
"""

from __future__ import annotations

import uuid

import pytest

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.infrastructure import InMemoryJobsRepository


def _make_job(title: str = "SWE", url: str | None = None) -> NormalizedJob:
    return NormalizedJob(
        id=str(uuid.uuid4()),
        title=title,
        company="Acme",
        description="desc",
        source="test",
        source_type="api",
        url=url or f"https://x/{uuid.uuid4()}",
    )


def _seed_job(job_id: str) -> NormalizedJob:
    """A job with an explicit primary-key id, for lock-order assertions."""
    return NormalizedJob(
        id=job_id,
        title="SWE",
        company="Acme",
        description="desc",
        source="test",
        source_type="api",
        url=f"https://x/{job_id}",
    )


class TestScoreUpdateValueType:
    def test_score_update_is_importable(self) -> None:
        """ScoreUpdate must be importable from the ports module."""
        from hiresense.ingestion.ports.jobs_repository import ScoreUpdate  # noqa: F401

    def test_score_update_is_frozen_dataclass(self) -> None:
        """ScoreUpdate must be a frozen dataclass (immutable value object)."""
        from hiresense.ingestion.ports.jobs_repository import ScoreUpdate

        su = ScoreUpdate(job_id="abc", match_score=0.5, semantic_score=0.7)
        assert su.job_id == "abc"
        assert su.match_score == pytest.approx(0.5)
        assert su.semantic_score == pytest.approx(0.7)

    def test_score_update_is_immutable(self) -> None:
        """Frozen dataclass must raise on field assignment."""
        from hiresense.ingestion.ports.jobs_repository import ScoreUpdate
        import dataclasses

        su = ScoreUpdate(job_id="abc", match_score=0.5, semantic_score=0.7)
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            su.job_id = "different"  # type: ignore[misc]

    def test_score_update_allows_none_scores(self) -> None:
        """Both score fields may be None (partial update)."""
        from hiresense.ingestion.ports.jobs_repository import ScoreUpdate

        su = ScoreUpdate(job_id="x", match_score=None, semantic_score=None)
        assert su.match_score is None
        assert su.semantic_score is None


class TestInMemoryBulkUpdateScores:
    def test_bulk_update_scores_updates_match_and_semantic_in_one_call(self) -> None:
        """Bulk update writes match_score and semantic_score for all provided IDs."""
        from hiresense.ingestion.ports.jobs_repository import ScoreUpdate

        repo = InMemoryJobsRepository()
        job_a = _make_job("A")
        job_b = _make_job("B")
        repo.upsert(job_a)
        repo.upsert(job_b)

        updates = [
            ScoreUpdate(job_id=job_a.id, match_score=0.8, semantic_score=0.9),
            ScoreUpdate(job_id=job_b.id, match_score=0.3, semantic_score=0.4),
        ]
        repo.bulk_update_scores(updates)

        stored_a = repo.get_by_id(job_a.id)
        stored_b = repo.get_by_id(job_b.id)
        assert stored_a is not None
        assert stored_b is not None
        assert stored_a.match_score == pytest.approx(0.8)
        assert stored_a.semantic_score == pytest.approx(0.9)
        assert stored_b.match_score == pytest.approx(0.3)
        assert stored_b.semantic_score == pytest.approx(0.4)

    def test_bulk_update_scores_ignores_foreign_ids(self) -> None:
        """Unknown job IDs in the update list must be silently skipped."""
        from hiresense.ingestion.ports.jobs_repository import ScoreUpdate

        repo = InMemoryJobsRepository()
        job = _make_job()
        repo.upsert(job)

        updates = [
            ScoreUpdate(job_id=job.id, match_score=0.5, semantic_score=0.6),
            ScoreUpdate(job_id="non-existent-id", match_score=0.9, semantic_score=0.9),
        ]
        # Should not raise
        repo.bulk_update_scores(updates)

        stored = repo.get_by_id(job.id)
        assert stored is not None
        assert stored.match_score == pytest.approx(0.5)

    def test_bulk_update_scores_empty_list_noop(self) -> None:
        """An empty update list must be a no-op (no error, no mutation)."""
        repo = InMemoryJobsRepository()
        job = _make_job()
        repo.upsert(job)

        # Should not raise
        repo.bulk_update_scores([])

        stored = repo.get_by_id(job.id)
        assert stored is not None
        assert stored.match_score is None  # unchanged

    def test_bulk_update_preserves_unmentioned_jobs(self) -> None:
        """Jobs not in the update list must retain their original scores."""
        from hiresense.ingestion.ports.jobs_repository import ScoreUpdate

        repo = InMemoryJobsRepository()
        job_a = _make_job("A")
        job_b = _make_job("B")
        repo.upsert(job_a)
        repo.upsert(job_b)
        # Pre-set a score on job_b via the single-item method
        repo.update_scores(job_b.id, match_score=0.99, semantic_score=0.88)

        # Only update job_a
        repo.bulk_update_scores([ScoreUpdate(job_id=job_a.id, match_score=0.5, semantic_score=0.5)])

        stored_b = repo.get_by_id(job_b.id)
        assert stored_b is not None
        assert stored_b.match_score == pytest.approx(0.99)
        assert stored_b.semantic_score == pytest.approx(0.88)


class TestBulkUpdateScoresLockOrder:
    """The SQL repository must issue per-row UPDATEs ordered by primary key so
    that concurrent bulk updates over the same corpus acquire row locks in a
    single global order — otherwise Postgres deadlocks (regression: two racing
    list_jobs requests each persisting scores in a different sort order)."""

    def _make_sql_repo(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from hiresense.infrastructure.database import Base
        from hiresense.ingestion.infrastructure.jobs_repository import JobsRepository
        from hiresense.ingestion.infrastructure.models import IngestedJob  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        base_factory = sessionmaker(bind=engine, expire_on_commit=False)
        captured: list[list[str]] = []

        class _SpySession:
            def __enter__(self_inner):
                self_inner._s = base_factory()
                return self_inner

            def __exit__(self_inner, *exc):
                self_inner._s.close()
                return False

            def execute(self_inner, stmt, params=None):
                if isinstance(params, list):
                    captured.append([p["id"] for p in params])
                return self_inner._s.execute(stmt, params)

            def __getattr__(self_inner, name):
                return getattr(self_inner._s, name)

        return JobsRepository(session_factory=_SpySession, bucket="boards"), captured

    def test_bulk_update_scores_orders_by_job_id(self) -> None:
        from hiresense.ingestion.ports.jobs_repository import ScoreUpdate

        repo, captured = self._make_sql_repo()
        for jid in ("a", "b", "c"):
            repo.upsert(_seed_job(jid))
        captured.clear()  # ignore seeding writes; only inspect the bulk update

        repo.bulk_update_scores(
            [
                ScoreUpdate(job_id="c", match_score=0.1, semantic_score=0.1),
                ScoreUpdate(job_id="a", match_score=0.2, semantic_score=0.2),
                ScoreUpdate(job_id="b", match_score=0.3, semantic_score=0.3),
            ]
        )
        assert captured, "executemany was never issued"
        assert captured[0] == ["a", "b", "c"], (
            "bulk_update_scores must order rows by job_id to avoid deadlocks"
        )

    def test_bulk_update_quality_orders_by_job_id(self) -> None:
        from hiresense.ingestion.ports.jobs_repository import QualityUpdate

        repo, captured = self._make_sql_repo()
        for jid in ("a", "m", "z"):
            repo.upsert(_seed_job(jid))
        captured.clear()

        repo.bulk_update_quality(
            [
                QualityUpdate(job_id="z", quality="spam", quality_reason="x"),
                QualityUpdate(job_id="m", quality="ok", quality_reason=None),
                QualityUpdate(job_id="a", quality="low_quality", quality_reason="y"),
            ]
        )
        assert captured, "executemany was never issued"
        assert captured[0] == ["a", "m", "z"], (
            "bulk_update_quality must order rows by job_id to avoid deadlocks"
        )


class TestJobsRepositoryPortHasBulkUpdateScores:
    def test_protocol_exposes_bulk_update_scores(self) -> None:
        """JobsRepositoryPort Protocol must declare bulk_update_scores."""
        from hiresense.ingestion.ports.jobs_repository import JobsRepositoryPort

        assert hasattr(JobsRepositoryPort, "bulk_update_scores"), (
            "JobsRepositoryPort must declare bulk_update_scores"
        )
