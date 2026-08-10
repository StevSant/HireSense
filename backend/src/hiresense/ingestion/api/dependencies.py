from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from hiresense.ingestion.domain.embedding_backfill_service import EmbeddingBackfillService
from hiresense.ingestion.domain.job_query_service import JobQueryService
from hiresense.ingestion.domain.job_revalidation_service import JobRevalidationService
from hiresense.ingestion.domain.portal_config import PortalsConfig
from hiresense.ingestion.domain.portal_scanner import PortalScanner
from hiresense.ingestion.domain.quick_scoring_service import QuickScoringService
from hiresense.ingestion.domain.semantic_pre_ranker import SemanticPreRanker
from hiresense.ingestion.domain.semantic_scoring_service import SemanticScoringService
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.ingestion.api.job_feed_service import JobFeedService
from hiresense.matching.domain.deep_analysis_service import DeepAnalysisService
from hiresense.network.api.dependencies import get_contacts_repository
from hiresense.network.ports import ContactsRepositoryPort
from hiresense.portfolio.api.dependencies import get_portfolio_enrichment
from hiresense.portfolio.domain import PortfolioEnrichmentService
from hiresense.profile.api.dependencies import get_profile_service
from hiresense.profile.domain import ProfileService


def get_ingestion_orchestrator(request: Request) -> IngestionOrchestrator:
    return request.app.state.ingestion.get_orchestrator()


def get_job_query(request: Request) -> JobQueryService:
    return request.app.state.ingestion.get_job_query()


def get_portal_scanner(request: Request) -> PortalScanner:
    return request.app.state.ingestion.get_portal_scanner()


def get_portals_config(request: Request) -> PortalsConfig:
    return request.app.state.ingestion.get_portals_config()


def get_semantic_scoring(request: Request) -> SemanticScoringService | None:
    # Defensive: tests and bare apps without app.state.ingestion → None, matching
    # every other optional collaborator here. The return type was already
    # Optional and callers already handled None; only this one raised instead.
    ingestion = getattr(request.app.state, "ingestion", None)
    return ingestion.get_semantic_scoring() if ingestion is not None else None


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


def get_backfill_service(request: Request) -> EmbeddingBackfillService | None:
    # Defensive: tests and bare apps without app.state.ingestion → None.
    # The endpoint handles None with a 503 response.
    ingestion = getattr(request.app.state, "ingestion", None)
    return ingestion.get_backfill_service() if ingestion is not None else None


def get_job_feed(
    request: Request,
    job_query: Annotated[JobQueryService, Depends(get_job_query)],
    scanner: Annotated[PortalScanner, Depends(get_portal_scanner)],
    profile_service: Annotated[ProfileService, Depends(get_profile_service)],
    portfolio_enrichment: Annotated[
        PortfolioEnrichmentService | None, Depends(get_portfolio_enrichment)
    ],
    semantic_scoring: Annotated[SemanticScoringService | None, Depends(get_semantic_scoring)],
    quick_scoring: Annotated[QuickScoringService | None, Depends(get_quick_scoring)],
    pre_ranker: Annotated[SemanticPreRanker | None, Depends(get_pre_ranker)],
    network_repo: Annotated[ContactsRepositoryPort | None, Depends(get_contacts_repository)],
    deep_analysis: Annotated[DeepAnalysisService | None, Depends(get_deep_analysis)],
) -> JobFeedService:
    """Assemble the cross-context job-feed use case for one request.

    Declared as a nested dependency rather than built inside the route so the
    route stops importing matching/network/portfolio/profile internals, while
    `dependency_overrides` on any individual collaborator still applies — FastAPI
    resolves those before calling this.
    """
    return JobFeedService(
        job_query=job_query,
        scanner=scanner,
        profile_service=profile_service,
        portfolio_enrichment=portfolio_enrichment,
        semantic_scoring=semantic_scoring,
        quick_scoring=quick_scoring,
        pre_ranker=pre_ranker,
        network_repo=network_repo,
        deep_analysis=deep_analysis,
        settings=getattr(request.app.state, "settings", None),
    )
