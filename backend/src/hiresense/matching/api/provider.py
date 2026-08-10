from __future__ import annotations


from hiresense.matching.domain import (
    BatchEvaluationService,
    DimensionEvaluator,
    MatchAnalyzer,
)


class MatchingProvider:
    def __init__(
        self,
        dimension_evaluator: DimensionEvaluator,
        match_analyzer: MatchAnalyzer,
        batch_evaluation_service: BatchEvaluationService,
    ) -> None:
        self._dimension_evaluator = dimension_evaluator
        self._match_analyzer = match_analyzer
        self._batch_evaluation_service = batch_evaluation_service

    def get_dimension_evaluator(self) -> DimensionEvaluator:
        return self._dimension_evaluator

    def get_match_analyzer(self) -> MatchAnalyzer:
        return self._match_analyzer

    def get_batch_evaluation_service(self) -> BatchEvaluationService:
        return self._batch_evaluation_service
