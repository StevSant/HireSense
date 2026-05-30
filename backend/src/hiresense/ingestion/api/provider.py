from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.portal_config import PortalsConfig
from hiresense.ingestion.domain.portal_scanner import PortalScanner
from hiresense.ingestion.domain.quick_scoring_service import QuickScoringService
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
    ) -> None:
        self._orchestrator = orchestrator
        self._portal_scanner = portal_scanner
        self._portals_config = portals_config
        self._semantic_scoring = semantic_scoring
        self._quick_scoring = quick_scoring
        self._deep_analysis = deep_analysis

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
