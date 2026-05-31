from __future__ import annotations

from fastapi import Request

from hiresense.ingestion.domain.job_revalidation_service import JobRevalidationService
from hiresense.ingestion.domain.portal_config import PortalsConfig
from hiresense.ingestion.domain.portal_scanner import PortalScanner
from hiresense.ingestion.domain.quick_scoring_service import QuickScoringService
from hiresense.ingestion.domain.semantic_pre_ranker import SemanticPreRanker
from hiresense.ingestion.domain.semantic_scoring_service import SemanticScoringService
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.matching.domain.deep_analysis_service import DeepAnalysisService


def get_ingestion_orchestrator(request: Request) -> IngestionOrchestrator:
    return request.app.state.ingestion.get_orchestrator()


def get_portal_scanner(request: Request) -> PortalScanner:
    return request.app.state.ingestion.get_portal_scanner()


def get_portals_config(request: Request) -> PortalsConfig:
    return request.app.state.ingestion.get_portals_config()


def get_semantic_scoring(request: Request) -> SemanticScoringService | None:
    return request.app.state.ingestion.get_semantic_scoring()


def get_quick_scoring(request: Request) -> QuickScoringService | None:
    # Defensive: tests mount the router on a bare app without app.state.ingestion.
    # Returning None there makes the list endpoint fall back to heuristic scores.
    ingestion = getattr(request.app.state, "ingestion", None)
    return ingestion.get_quick_scoring() if ingestion is not None else None


def get_deep_analysis(request: Request) -> DeepAnalysisService | None:
    ingestion = getattr(request.app.state, "ingestion", None)
    return ingestion.get_deep_analysis() if ingestion is not None else None


def get_pre_ranker(request: Request) -> SemanticPreRanker | None:
    # Defensive: tests and bare apps without app.state.ingestion → None.
    # Routes receiving None must fall back to skill-only ordering (never crash).
    ingestion = getattr(request.app.state, "ingestion", None)
    return ingestion.get_pre_ranker() if ingestion is not None else None


def get_revalidation_service(request: Request) -> JobRevalidationService | None:
    ingestion = getattr(request.app.state, "ingestion", None)
    return ingestion.get_revalidation_service() if ingestion is not None else None
