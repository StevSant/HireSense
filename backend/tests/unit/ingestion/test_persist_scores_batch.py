"""Tests for persist_scores_batch on IngestionOrchestrator and PortalScanner (Work Unit G).

Written BEFORE implementation (TDD RED phase).
Verifies REQ-08: domain services expose a batched persist method that
delegates to repo.bulk_update_scores — eliminating any N+1 loop at the
call site.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, call

import pytest

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.portal_config import PortalEntry, PortalsConfig
from hiresense.ingestion.domain.portal_scanner import PortalScanner
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.ingestion.infrastructure import InMemoryJobsRepository
from hiresense.ingestion.ports.jobs_repository import ScoreUpdate


def _make_job(title: str = "SWE") -> NormalizedJob:
    return NormalizedJob(
        id=str(uuid.uuid4()),
        title=title,
        company="Acme",
        description="desc",
        source="test",
        source_type="api",
        url=f"https://x/{uuid.uuid4()}",
    )


class FakeEventBus:
    async def publish(self, event) -> None:  # noqa: ARG002
        pass


def _make_portal_scanner(repo: InMemoryJobsRepository) -> PortalScanner:
    return PortalScanner(
        config=PortalsConfig(portals=[]),
        adapters={},
        normalizers={},
        event_bus=FakeEventBus(),
        repository=repo,
    )


def _make_orchestrator(repo: InMemoryJobsRepository) -> IngestionOrchestrator:
    return IngestionOrchestrator(
        sources=[],
        normalizers={},
        event_bus=FakeEventBus(),
        repository=repo,
    )


# ---------------------------------------------------------------------------
# IngestionOrchestrator tests
# ---------------------------------------------------------------------------


class TestOrchestratorPersistScoresBatch:
    def test_persist_scores_batch_method_exists(self) -> None:
        """IngestionOrchestrator must have a persist_scores_batch method."""
        repo = InMemoryJobsRepository()
        orchestrator = _make_orchestrator(repo)
        assert hasattr(orchestrator, "persist_scores_batch"), (
            "IngestionOrchestrator must expose persist_scores_batch"
        )

    def test_orchestrator_persist_scores_batch_delegates_to_repo(self) -> None:
        """persist_scores_batch must call repo.bulk_update_scores exactly once."""
        mock_repo = MagicMock()
        mock_repo.bulk_update_scores = MagicMock()

        orchestrator = IngestionOrchestrator(
            sources=[],
            normalizers={},
            event_bus=FakeEventBus(),
            repository=mock_repo,
        )

        updates = [
            ScoreUpdate(job_id="a", match_score=0.8, semantic_score=0.9),
            ScoreUpdate(job_id="b", match_score=0.3, semantic_score=0.4),
        ]
        orchestrator.persist_scores_batch(updates)

        mock_repo.bulk_update_scores.assert_called_once_with(updates)

    def test_orchestrator_persist_scores_batch_with_real_repo(self) -> None:
        """End-to-end: persist_scores_batch reaches the in-memory store."""
        repo = InMemoryJobsRepository()
        job_a = _make_job("A")
        job_b = _make_job("B")
        repo.add_if_absent(job_a)
        repo.add_if_absent(job_b)

        orchestrator = _make_orchestrator(repo)
        updates = [
            ScoreUpdate(job_id=job_a.id, match_score=0.7, semantic_score=0.8),
            ScoreUpdate(job_id=job_b.id, match_score=0.2, semantic_score=0.3),
        ]
        orchestrator.persist_scores_batch(updates)

        stored_a = repo.get_by_id(job_a.id)
        stored_b = repo.get_by_id(job_b.id)
        assert stored_a is not None
        assert stored_b is not None
        assert stored_a.match_score == pytest.approx(0.7)
        assert stored_b.semantic_score == pytest.approx(0.3)

    def test_orchestrator_persist_scores_batch_empty_noop(self) -> None:
        """An empty update list must be accepted without error."""
        repo = InMemoryJobsRepository()
        orchestrator = _make_orchestrator(repo)
        orchestrator.persist_scores_batch([])  # must not raise


# ---------------------------------------------------------------------------
# PortalScanner tests
# ---------------------------------------------------------------------------


class TestPortalScannerPersistScoresBatch:
    def test_persist_scores_batch_method_exists(self) -> None:
        """PortalScanner must have a persist_scores_batch method."""
        repo = InMemoryJobsRepository()
        scanner = _make_portal_scanner(repo)
        assert hasattr(scanner, "persist_scores_batch"), (
            "PortalScanner must expose persist_scores_batch"
        )

    def test_portal_scanner_persist_scores_batch_delegates_to_repo(self) -> None:
        """persist_scores_batch must call repo.bulk_update_scores exactly once."""
        mock_repo = MagicMock()
        mock_repo.bulk_update_scores = MagicMock()

        scanner = PortalScanner(
            config=PortalsConfig(portals=[]),
            adapters={},
            normalizers={},
            event_bus=FakeEventBus(),
            repository=mock_repo,
        )

        updates = [
            ScoreUpdate(job_id="x", match_score=0.5, semantic_score=0.6),
        ]
        scanner.persist_scores_batch(updates)

        mock_repo.bulk_update_scores.assert_called_once_with(updates)

    def test_portal_scanner_persist_scores_batch_with_real_repo(self) -> None:
        """End-to-end: persist_scores_batch reaches the in-memory store."""
        repo = InMemoryJobsRepository()
        job = _make_job()
        repo.add_if_absent(job)

        scanner = _make_portal_scanner(repo)
        scanner.persist_scores_batch([
            ScoreUpdate(job_id=job.id, match_score=0.6, semantic_score=0.75),
        ])

        stored = repo.get_by_id(job.id)
        assert stored is not None
        assert stored.match_score == pytest.approx(0.6)
        assert stored.semantic_score == pytest.approx(0.75)

    def test_portal_scanner_persist_scores_batch_empty_noop(self) -> None:
        """An empty update list must be accepted without error."""
        repo = InMemoryJobsRepository()
        scanner = _make_portal_scanner(repo)
        scanner.persist_scores_batch([])  # must not raise
