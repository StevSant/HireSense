from __future__ import annotations

from hiresense.ingestion.domain.embedding_backfill_service import EmbeddingBackfillService
from hiresense.ingestion.domain.job_revalidation_service import JobRevalidationService
from hiresense.ingestion.domain.portal_config import PortalsConfig
from hiresense.ingestion.domain.portal_scanner import PortalScanner
from hiresense.ingestion.domain.quick_scoring_service import QuickScoringService
from hiresense.ingestion.domain.semantic_pre_ranker import SemanticPreRanker
from hiresense.ingestion.domain.semantic_scoring_service import SemanticScoringService
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.matching.domain.deep_analysis_service import DeepAnalysisService


class IngestionProvider:
    def __init__(
        self,
        orchestrator: IngestionOrchestrator,
        portal_scanner: PortalScanner,
        portals_config: PortalsConfig,
        semantic_scoring: SemanticScoringService | None = None,
        quick_scoring: QuickScoringService | None = None,
        deep_analysis: DeepAnalysisService | None = None,
        pre_ranker: SemanticPreRanker | None = None,
        revalidation_service: JobRevalidationService | None = None,
        backfill_service: EmbeddingBackfillService | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._portal_scanner = portal_scanner
        self._portals_config = portals_config
        self._semantic_scoring = semantic_scoring
        self._quick_scoring = quick_scoring
        self._deep_analysis = deep_analysis
        self._pre_ranker = pre_ranker
        self._revalidation_service = revalidation_service
        self._backfill_service = backfill_service

    def get_orchestrator(self) -> IngestionOrchestrator:
        return self._orchestrator

    def get_portal_scanner(self) -> PortalScanner:
        return self._portal_scanner

    def get_portals_config(self) -> PortalsConfig:
        return self._portals_config

    def get_semantic_scoring(self) -> SemanticScoringService | None:
        return self._semantic_scoring

    def get_quick_scoring(self) -> QuickScoringService | None:
        return self._quick_scoring

    def get_deep_analysis(self) -> DeepAnalysisService | None:
        return self._deep_analysis

    def get_pre_ranker(self) -> SemanticPreRanker | None:
        return self._pre_ranker

    def get_revalidation_service(self) -> JobRevalidationService | None:
        return self._revalidation_service

    def get_backfill_service(self) -> EmbeddingBackfillService | None:
        return self._backfill_service
