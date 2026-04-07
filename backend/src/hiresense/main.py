from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.adapters.event_bus.in_memory_bus import InMemoryEventBus
from hiresense.config import Settings
from hiresense.identity.api.dependencies import get_auth_service
from hiresense.identity.api.routes import router as auth_router
from hiresense.identity.services import AuthService
from hiresense.ingestion.adapters.ashby_adapter import AshbyAdapter
from hiresense.ingestion.adapters.csv_import import CSVImportAdapter
from hiresense.ingestion.adapters.greenhouse_adapter import GreenhouseAdapter
from hiresense.ingestion.adapters.lever_adapter import LeverAdapter
from hiresense.ingestion.adapters.remoteok import RemoteOKAdapter
from hiresense.ingestion.adapters.remotive import RemotiveAdapter
from hiresense.ingestion.api.routes import get_ingestion_orchestrator, get_portal_scanner, get_portals_config
from hiresense.ingestion.api.routes import router as ingestion_router
from hiresense.ingestion.domain.normalizer import CSVNormalizer, RemoteOKNormalizer, RemotiveNormalizer
from hiresense.ingestion.domain.normalizers.ashby_normalizer import AshbyNormalizer
from hiresense.ingestion.domain.normalizers.greenhouse_normalizer import GreenhouseNormalizer
from hiresense.ingestion.domain.normalizers.lever_normalizer import LeverNormalizer
from hiresense.ingestion.domain.portal_config import load_portals_config
from hiresense.ingestion.domain.portal_scanner import PortalScanner
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.matching.api.dependencies import get_matching_orchestrator
from hiresense.matching.api.routes import router as matching_router
from hiresense.matching.domain.scorers.application_strength_scorer import ApplicationStrengthScorer
from hiresense.matching.domain.scorers.compensation_scorer import CompensationScorer
from hiresense.matching.domain.scorers.culture_scorer import CultureScorer
from hiresense.matching.domain.scorers.growth_scorer import GrowthScorer
from hiresense.matching.domain.scorers.interview_readiness_scorer import InterviewReadinessScorer
from hiresense.matching.domain.scorers.seniority_scorer import SeniorityScorer
from hiresense.matching.domain.services import MatchingOrchestrator
from hiresense.optimization.api.dependencies import get_cv_optimizer
from hiresense.optimization.api.routes import router as optimization_router
from hiresense.optimization.domain.services import CVOptimizer
from hiresense.profile.api.dependencies import get_profile_service
from hiresense.profile.api.routes import router as profile_router
from hiresense.profile.domain.latex_parser import LaTeXParser
from hiresense.profile.domain.services import ProfileService
from hiresense.profile.domain.skill_extractor import SkillExtractor
from hiresense.tracking.api.dependencies import get_tracking_service
from hiresense.tracking.api.routes import router as tracking_router
from hiresense.tracking.domain.services import TrackingService
from hiresense.tracking.infrastructure.repository import TrackingRepository
from hiresense.interview.api.dependencies import get_story_service, get_interview_prep_service
from hiresense.interview.api.routes import router as interview_router
from hiresense.interview.domain.services import InterviewPrepService, StoryService
from hiresense.interview.infrastructure.repository import StoryRepository


def create_app() -> FastAPI:
    settings = Settings()
    http_client = httpx.AsyncClient(timeout=settings.http_timeout)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await http_client.aclose()

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    # --- Shared infrastructure ---
    event_bus = InMemoryEventBus()

    # --- Identity module ---
    auth_service = AuthService(
        username=settings.auth_username,
        password=settings.auth_password,
        jwt_secret=settings.jwt_secret_key,
    )
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.include_router(auth_router)

    # --- Ingestion module ---
    sources = []
    normalizers = {}
    for source_name in settings.enabled_job_sources:
        if source_name == "remotive":
            sources.append(RemotiveAdapter(http_client=http_client))
            normalizers["remotive"] = RemotiveNormalizer()
        elif source_name == "remoteok":
            sources.append(RemoteOKAdapter(http_client=http_client))
            normalizers["remoteok"] = RemoteOKNormalizer()
        elif source_name == "csv":
            sources.append(CSVImportAdapter())
            normalizers["csv"] = CSVNormalizer()
    ingestion_orchestrator = IngestionOrchestrator(
        sources=sources,
        normalizers=normalizers,
        event_bus=event_bus,
    )
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: ingestion_orchestrator
    app.include_router(ingestion_router)

    # --- Portal scanning ---
    portals_config_path = Path(__file__).parent / settings.portals_config_path
    portals_config = load_portals_config(portals_config_path)

    portal_adapters = {
        "greenhouse": GreenhouseAdapter(
            http_client=http_client,
            base_url=settings.greenhouse_api_url,
            timeout=settings.portal_scan_timeout,
        ),
        "lever": LeverAdapter(
            http_client=http_client,
            base_url=settings.lever_api_url,
            timeout=settings.portal_scan_timeout,
        ),
        "ashby": AshbyAdapter(
            http_client=http_client,
            base_url=settings.ashby_api_url,
            timeout=settings.portal_scan_timeout,
        ),
    }

    portal_normalizers = {
        "greenhouse": GreenhouseNormalizer(),
        "lever": LeverNormalizer(),
        "ashby": AshbyNormalizer(),
    }

    portal_scanner = PortalScanner(
        config=portals_config,
        adapters=portal_adapters,
        normalizers=portal_normalizers,
        event_bus=event_bus,
    )

    app.dependency_overrides[get_portal_scanner] = lambda: portal_scanner
    app.dependency_overrides[get_portals_config] = lambda: portals_config

    # --- Profile module ---
    latex_parser = LaTeXParser()
    skill_extractor = SkillExtractor()
    profile_service = ProfileService(parser=latex_parser, skill_extractor=skill_extractor)
    app.dependency_overrides[get_profile_service] = lambda: profile_service
    app.include_router(profile_router)

    # --- Matching module ---
    llm = None
    if settings.llm_api_key:
        try:
            from anthropic import AsyncAnthropic
            from hiresense.adapters.llm.anthropic_adapter import AnthropicLLMAdapter
            anthropic_client = AsyncAnthropic(api_key=settings.llm_api_key)
            llm = AnthropicLLMAdapter(client=anthropic_client, model=settings.llm_model)
        except ImportError:
            pass

    dimension_scorers = [
        SeniorityScorer(llm=llm, weight=settings.weight_seniority),
        CompensationScorer(llm=llm, weight=settings.weight_compensation),
        GrowthScorer(llm=llm, weight=settings.weight_growth),
        CultureScorer(llm=llm, weight=settings.weight_culture),
        ApplicationStrengthScorer(llm=llm, weight=settings.weight_application),
        InterviewReadinessScorer(llm=llm, weight=settings.weight_interview),
    ]

    matching_orchestrator = MatchingOrchestrator(llm=llm, event_bus=event_bus, dimension_scorers=dimension_scorers)
    app.dependency_overrides[get_matching_orchestrator] = lambda: matching_orchestrator
    app.include_router(matching_router)

    # --- Optimization module ---
    cv_optimizer = CVOptimizer(llm=None)
    app.dependency_overrides[get_cv_optimizer] = lambda: cv_optimizer
    app.include_router(optimization_router)

    # --- Tracking module ---
    sync_db_url = settings.database_url.replace("+asyncpg", "")
    sync_engine = create_engine(sync_db_url, echo=settings.debug)
    sync_session_factory = sessionmaker(bind=sync_engine, expire_on_commit=False)
    tracking_repo = TrackingRepository(session_factory=sync_session_factory)
    tracking_service = TrackingService(
        repository=tracking_repo,
        ingestion_orchestrator=ingestion_orchestrator,
    )
    app.dependency_overrides[get_tracking_service] = lambda: tracking_service
    app.include_router(tracking_router)

    # --- Interview module ---
    story_repo = StoryRepository(session_factory=sync_session_factory)
    story_service = StoryService(repository=story_repo)
    interview_prep_service = InterviewPrepService(llm=llm, story_repo=story_repo)
    app.dependency_overrides[get_story_service] = lambda: story_service
    app.dependency_overrides[get_interview_prep_service] = lambda: interview_prep_service
    app.include_router(interview_router)

    # --- Health check ---
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
