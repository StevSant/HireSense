from __future__ import annotations

from typing import Any

from hiresense.matching.domain import BatchEvaluationService, MatchingOrchestrator


class MatchingProvider:
    def __init__(
        self,
        orchestrator: MatchingOrchestrator,
        batch_evaluation_service: BatchEvaluationService,
    ) -> None:
        self._orchestrator = orchestrator
        self._batch_evaluation_service = batch_evaluation_service

    def get_orchestrator(self) -> MatchingOrchestrator:
        return self._orchestrator

    def get_batch_evaluation_service(self) -> BatchEvaluationService:
        return self._batch_evaluation_service
