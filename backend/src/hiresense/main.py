from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.adapters.event_bus import InMemoryEventBus
from hiresense.adapters.latex import LatexCompiler
from hiresense.admin.api import AdminProvider, router as admin_router
from hiresense.admin.domain import (
    APIKeyCipher,
    LLMConfigService,
    LLMFactory,
    LLMSettingsService,
    LLMTestRunner,
    TrackedLLMAdapter,
    UsageAggregator,
    UsageRecorder,
)
from hiresense.admin.infrastructure import (
    LLMAuditLogRepository,
    LLMFeatureOverrideRepository,
    LLMSettingsRepository,
    LLMUsageLogRepository,
)
from hiresense.applications.api.provider import ApplicationsProvider
from hiresense.applications.api.routes import router as applications_router
from hiresense.applications.domain import ApplicationService, ArtifactService
from hiresense.applications.domain import SkillExtractor as ApplicationsSkillExtractor
from hiresense.applications.domain.apply_service import ApplyService
from hiresense.applications.domain.cover_letter_generator import CoverLetterGenerator
from hiresense.applications.infrastructure import ApplicationRepository
from hiresense.config import Settings
from hiresense.identity.api import router as auth_router
from hiresense.identity.api.provider import IdentityProvider
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
from hiresense.ingestion.api import router as ingestion_router
from hiresense.ingestion.api.provider import IngestionProvider
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
from hiresense.matching.api import router as matching_router
from hiresense.matching.api.provider import MatchingProvider
from hiresense.matching.domain import BatchEvaluationService, MatchingOrchestrator
from hiresense.matching.domain.scorers import (
    ApplicationStrengthScorer,
    CompensationScorer,
    CultureScorer,
    GrowthScorer,
    InterviewReadinessScorer,
    SeniorityScorer,
)
from hiresense.optimization.api import router as optimization_router
from hiresense.optimization.api.provider import OptimizationProvider
from hiresense.optimization.domain import CVOptimizer
from hiresense.profile.api import router as profile_router
from hiresense.profile.api.provider import ProfileProvider
from hiresense.profile.domain import LaTeXParser, PDFParser, ProfileService, SkillExtractor
from hiresense.profile.infrastructure import ProfileRepository
from hiresense.tracking.api import router as tracking_router
from hiresense.tracking.api.provider import TrackingProvider
from hiresense.tracking.domain import TrackingService
from hiresense.tracking.infrastructure import TrackingRepository
from hiresense.interview.api import router as interview_router
from hiresense.interview.api.provider import InterviewProvider
from hiresense.interview.domain import InterviewPrepService, StoryService
from hiresense.interview.infrastructure import StoryRepository
from hiresense.research.api import router as research_router
from hiresense.research.api.provider import ResearchProvider
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Settings ---
    app.state.settings = settings

    # --- Shared infrastructure ---
    event_bus = InMemoryEventBus()

    sync_db_url = settings.database_url.replace("+asyncpg", "")
    sync_engine = create_engine(sync_db_url, echo=settings.debug)
    sync_session_factory = sessionmaker(bind=sync_engine, expire_on_commit=False)

    # --- Admin: runtime LLM config, per-feature overrides, usage tracking ---
    llm_settings_repo = LLMSettingsRepository(session_factory=sync_session_factory)
    llm_override_repo = LLMFeatureOverrideRepository(session_factory=sync_session_factory)
    llm_usage_repo = LLMUsageLogRepository(session_factory=sync_session_factory)
    llm_audit_repo = LLMAuditLogRepository(session_factory=sync_session_factory)
    cipher = APIKeyCipher(settings.llm_settings_encryption_key)
    llm_factory = LLMFactory()
    llm_config_service = LLMConfigService(
        settings_repo=llm_settings_repo,
        override_repo=llm_override_repo,
        cipher=cipher,
        env_provider=settings.llm_provider,
        env_model=settings.llm_model,
        env_api_key=settings.llm_api_key,
    )
    llm_test_runner = LLMTestRunner(factory=llm_factory)
    llm_settings_service = LLMSettingsService(
        settings_repo=llm_settings_repo,
        override_repo=llm_override_repo,
        audit_repo=llm_audit_repo,
        cipher=cipher,
        config_service=llm_config_service,
        factory=llm_factory,
        test_runner=llm_test_runner,
        env_provider=settings.llm_provider,
        env_model=settings.llm_model,
        env_api_key=settings.llm_api_key,
    )
    usage_recorder = UsageRecorder(repo=llm_usage_repo)
    usage_aggregator = UsageAggregator(repo=llm_usage_repo)
    app.state.admin_provider = AdminProvider(
        settings_service=llm_settings_service,
        config_service=llm_config_service,
        factory=llm_factory,
        usage_aggregator=usage_aggregator,
        usage_recorder=usage_recorder,
    )
    app.include_router(admin_router)

    def _tracked(feature_key: str) -> TrackedLLMAdapter | None:
        if not settings.llm_api_key:
            return None
        return TrackedLLMAdapter(
            config_service=llm_config_service,
            factory=llm_factory,
            recorder=usage_recorder,
            feature_key=feature_key,
        )

    from hiresense.adapters.embedding import SentenceTransformerAdapter

    embedding = SentenceTransformerAdapter(
        model_name=settings.embedding_model,
        device=settings.embedding_device,
    )

    # --- Identity ---
    app.state.identity = IdentityProvider(
        username=settings.auth_username,
        password=settings.auth_password,
        jwt_secret=settings.jwt_secret_key,
    )
    app.include_router(auth_router)

    # --- Ingestion ---
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
            sources.append(LinkedInAdapter(
                http_client=http_client,
                base_url=settings.linkedin_jobs_url,
                detail_concurrency=settings.linkedin_detail_concurrency,
                detail_delay=settings.linkedin_detail_delay,
            ))
            normalizers["linkedin"] = LinkedInNormalizer()

    ingestion_orchestrator = IngestionOrchestrator(
        sources=sources,
        normalizers=normalizers,
        event_bus=event_bus,
        cooldown_seconds=settings.ingestion_cooldown_seconds,
    )

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

    from hiresense.ingestion.domain.semantic_scoring_service import SemanticScoringService
    semantic_scoring = SemanticScoringService(embedding_port=embedding)

    app.state.ingestion = IngestionProvider(
        orchestrator=ingestion_orchestrator,
        portal_scanner=portal_scanner,
        portals_config=portals_config,
        semantic_scoring=semantic_scoring,
    )
    app.include_router(ingestion_router)

    # --- Profile ---
    profile_repo = ProfileRepository(session_factory=sync_session_factory)
    latex_parser = LaTeXParser()
    pdf_parser = PDFParser(llm=_tracked("cv_parser"))
    skill_extractor = SkillExtractor()
    profile_service = ProfileService(
        parser=latex_parser,
        skill_extractor=skill_extractor,
        repository=profile_repo,
        pdf_parser=pdf_parser,
        cv_directory=settings.cv_directory,
    )
    app.state.profile = ProfileProvider(profile_service=profile_service)
    app.include_router(profile_router)

    # --- Matching ---
    dimension_scorers = [
        SeniorityScorer(llm=_tracked("seniority_scorer"), weight=settings.weight_seniority),
        CompensationScorer(llm=_tracked("compensation_scorer"), weight=settings.weight_compensation),
        GrowthScorer(llm=_tracked("growth_scorer"), weight=settings.weight_growth),
        CultureScorer(llm=_tracked("culture_scorer"), weight=settings.weight_culture),
        ApplicationStrengthScorer(
            llm=_tracked("application_strength_scorer"), weight=settings.weight_application,
        ),
        InterviewReadinessScorer(
            llm=_tracked("interview_readiness_scorer"), weight=settings.weight_interview,
        ),
    ]

    matching_orchestrator = MatchingOrchestrator(
        llm=_tracked("matching_reasoning"),
        event_bus=event_bus,
        dimension_scorers=dimension_scorers,
        embedding=embedding,
    )
    batch_evaluation_service = BatchEvaluationService(
        orchestrator=matching_orchestrator,
        concurrency=settings.batch_concurrency,
    )
    app.state.matching = MatchingProvider(
        orchestrator=matching_orchestrator,
        batch_evaluation_service=batch_evaluation_service,
    )
    app.include_router(matching_router)

    # --- Optimization ---
    cv_optimizer = CVOptimizer(llm=_tracked("cv_optimizer"))
    app.state.optimization = OptimizationProvider(cv_optimizer=cv_optimizer)
    app.include_router(optimization_router)

    # --- Tracking ---
    tracking_repo = TrackingRepository(session_factory=sync_session_factory)
    tracking_service = TrackingService(
        repository=tracking_repo,
        ingestion_orchestrator=ingestion_orchestrator,
    )
    app.state.tracking = TrackingProvider(tracking_service=tracking_service)
    app.include_router(tracking_router)

    # --- Interview ---
    story_repo = StoryRepository(session_factory=sync_session_factory)
    story_service = StoryService(repository=story_repo)
    interview_prep_service = InterviewPrepService(
        llm=_tracked("interview_prep"), story_repo=story_repo,
    )
    app.state.interview = InterviewProvider(
        story_service=story_service,
        interview_prep_service=interview_prep_service,
    )
    app.include_router(interview_router)

    # --- Applications ---
    application_repo = ApplicationRepository(session_factory=sync_session_factory)
    applications_skill_extractor = ApplicationsSkillExtractor(
        llm=_tracked("application_skill_extractor"),
    )
    application_service = ApplicationService(
        repository=application_repo,
        tracking_service=tracking_service,
        ingestion_orchestrator=ingestion_orchestrator,
        skill_extractor=applications_skill_extractor,
    )
    artifact_service = ArtifactService(
        repository=application_repo,
        matching_orchestrator=matching_orchestrator,
        cv_optimizer=cv_optimizer,
        interview_prep_service=interview_prep_service,
        profile_service=profile_service,
        tracking_service=tracking_service,
    )
    cover_letter_generator = CoverLetterGenerator(llm=_tracked("cover_letter"))
    latex_compiler = LatexCompiler(
        compiler=settings.latex_compiler,
        timeout_seconds=settings.latex_timeout_seconds,
    )
    apply_service = ApplyService(
        repository=application_repo,
        cover_letter_generator=cover_letter_generator,
        latex_compiler=latex_compiler,
        profile_service=profile_service,
        tracking_service=tracking_service,
    )
    app.state.applications_provider = ApplicationsProvider(
        application_service=application_service,
        artifact_service=artifact_service,
        apply_service=apply_service,
    )
    app.include_router(applications_router)

    # --- Research ---
    research_repo = CompanyResearchRepository(session_factory=sync_session_factory)
    research_service = CompanyResearchService(
        llm=_tracked("company_research"), repository=research_repo,
    )
    app.state.research = ResearchProvider(research_service=research_service)
    app.include_router(research_router)

    # --- Health check ---
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
