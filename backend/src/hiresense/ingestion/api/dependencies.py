from __future__ import annotations

from fastapi import Request

from hiresense.ingestion.domain.portal_config import PortalsConfig
from hiresense.ingestion.domain.portal_scanner import PortalScanner
from hiresense.ingestion.domain.semantic_scoring_service import SemanticScoringService
from hiresense.ingestion.domain.services import IngestionOrchestrator


def get_ingestion_orchestrator(request: Request) -> IngestionOrchestrator:
    return request.app.state.ingestion.get_orchestrator()


def get_portal_scanner(request: Request) -> PortalScanner:
    return request.app.state.ingestion.get_portal_scanner()


def get_portals_config(request: Request) -> PortalsConfig:
    return request.app.state.ingestion.get_portals_config()


def get_semantic_scoring(request: Request) -> SemanticScoringService | None:
    return request.app.state.ingestion.get_semantic_scoring()
