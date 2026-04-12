from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.adapters.event_bus import InMemoryEventBus
from hiresense.config import Settings
from hiresense.identity import AuthService
from hiresense.identity.api import get_auth_service
from hiresense.identity.api import router as auth_router
from hiresense.ingestion.adapters import (
    AshbyAdapter,
    CSVImportAdapter,
    GetOnBoardAdapter,
    GreenhouseAdapter,
    HimalayasAdapter,
    HNHiringAdapter,
    JobicyAdapter,
    LeverAdapter,
    LinkedInAdapter,
    RemoteOKAdapter,
    RemotiveAdapter,
    WeWorkRemotelyAdapter,
)
from hiresense.ingestion.api import get_ingestion_orchestrator, get_portal_scanner, get_portals_config
from hiresense.ingestion.api import router as ingestion_router
from hiresense.ingestion.domain import IngestionOrchestrator, PortalScanner, load_portals_config
from hiresense.ingestion.domain.normalizers import (
    AshbyNormalizer,
    CSVNormalizer,
    GetOnBoardNormalizer,
    GreenhouseNormalizer,
    HimalayasNormalizer,
    HNHiringNormalizer,
    JobicyNormalizer,
    LeverNormalizer,
    LinkedInNormalizer,
    RemoteOKNormalizer,
    RemotiveNormalizer,
    WeWorkRemotelyNormalizer,
)
from hiresense.matching.api import (
    get_batch_evaluation_service,
    get_ingestion_orchestrator_for_matching,
    get_matching_orchestrator,
    get_tracking_service_for_matching,
)
from hiresense.matching.api import router as matching_router
from hiresense.matching.domain import BatchEvaluationService, MatchingOrchestrator
from hiresense.matching.domain.scorers import (
    ApplicationStrengthScorer,
    CompensationScorer,
    CultureScorer,
    GrowthScorer,
    InterviewReadinessScorer,
    SeniorityScorer,
)
from hiresense.optimization.api import get_cv_optimizer
from hiresense.optimization.api import router as optimization_router
from hiresense.optimization.domain import CVOptimizer
from hiresense.profile.api import get_profile_service
from hiresense.profile.api import router as profile_router
from hiresense.profile.domain import LaTeXParser, ProfileService, SkillExtractor
from hiresense.tracking.api import get_tracking_service
from hiresense.tracking.api import router as tracking_router
from hiresense.tracking.domain import TrackingService
from hiresense.tracking.infrastructure import TrackingRepository
from hiresense.interview.api import get_interview_prep_service, get_story_service
from hiresense.interview.api import router as interview_router
from hiresense.interview.domain import InterviewPrepService, StoryService
from hiresense.interview.infrastructure import StoryRepository
from hiresense.research.api import get_company_research_service
from hiresense.research.api import router as research_router
from hiresense.research.domain import CompanyResearchService
from hiresense.research.infrastructure import CompanyResearchRepository


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
        elif source_name == "jobicy":
            sources.append(JobicyAdapter(http_client=http_client, base_url=settings.jobicy_api_url))
            normalizers["jobicy"] = JobicyNormalizer()
        elif source_name == "himalayas":
            sources.append(HimalayasAdapter(http_client=http_client, base_url=settings.himalayas_api_url))
            normalizers["himalayas"] = HimalayasNormalizer()
        elif source_name == "hn_hiring":
            sources.append(HNHiringAdapter(http_client=http_client, base_url=settings.hn_algolia_api_url))
            normalizers["hn_hiring"] = HNHiringNormalizer()
        elif source_name == "weworkremotely":
            sources.append(WeWorkRemotelyAdapter(http_client=http_client, rss_url=settings.weworkremotely_rss_url))
            normalizers["weworkremotely"] = WeWorkRemotelyNormalizer()
        elif source_name == "getonboard":
            sources.append(GetOnBoardAdapter(http_client=http_client, base_url=settings.getonboard_api_url))
            normalizers["getonboard"] = GetOnBoardNormalizer()
        elif source_name == "linkedin":
            sources.append(LinkedInAdapter(http_client=http_client, base_url=settings.linkedin_jobs_url))
            normalizers["linkedin"] = LinkedInNormalizer()
    ingestion_orchestrator = IngestionOrchestrator(
        sources=sources,
        normalizers=normalizers,
        event_bus=event_bus,
        cooldown_seconds=settings.ingestion_cooldown_seconds,
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

    batch_evaluation_service = BatchEvaluationService(
        orchestrator=matching_orchestrator,
        concurrency=settings.batch_concurrency,
    )
    app.dependency_overrides[get_batch_evaluation_service] = lambda: batch_evaluation_service

    app.include_router(matching_router)

    # --- Optimization module ---
    cv_optimizer = CVOptimizer(llm=llm)
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

    # --- Cross-module DI for batch evaluation ---
    app.dependency_overrides[get_tracking_service_for_matching] = lambda: tracking_service
    app.dependency_overrides[get_ingestion_orchestrator_for_matching] = lambda: ingestion_orchestrator

    # --- Interview module ---
    story_repo = StoryRepository(session_factory=sync_session_factory)
    story_service = StoryService(repository=story_repo)
    interview_prep_service = InterviewPrepService(llm=llm, story_repo=story_repo)
    app.dependency_overrides[get_story_service] = lambda: story_service
    app.dependency_overrides[get_interview_prep_service] = lambda: interview_prep_service
    app.include_router(interview_router)

    # --- Research module ---
    research_repo = CompanyResearchRepository(session_factory=sync_session_factory)
    research_service = CompanyResearchService(llm=llm, repository=research_repo)
    app.dependency_overrides[get_company_research_service] = lambda: research_service
    app.include_router(research_router)

    # --- Health check ---
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
