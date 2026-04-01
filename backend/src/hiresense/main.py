from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from hiresense.adapters.event_bus.in_memory_bus import InMemoryEventBus
from hiresense.config import Settings
from hiresense.identity.api.dependencies import get_auth_service
from hiresense.identity.api.routes import router as auth_router
from hiresense.identity.services import AuthService
from hiresense.ingestion.api.routes import get_ingestion_orchestrator
from hiresense.ingestion.api.routes import router as ingestion_router
from hiresense.ingestion.adapters.remotive import RemotiveAdapter
from hiresense.ingestion.adapters.remoteok import RemoteOKAdapter
from hiresense.ingestion.adapters.csv_import import CSVImportAdapter
from hiresense.ingestion.domain.normalizer import CSVNormalizer, RemoteOKNormalizer, RemotiveNormalizer
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.matching.api.dependencies import get_matching_orchestrator
from hiresense.matching.api.routes import router as matching_router
from hiresense.matching.domain.services import MatchingOrchestrator
from hiresense.optimization.api.dependencies import get_cv_optimizer
from hiresense.optimization.api.routes import router as optimization_router
from hiresense.optimization.domain.services import CVOptimizer
from hiresense.profile.api.dependencies import get_profile_service
from hiresense.profile.api.routes import router as profile_router
from hiresense.profile.domain.latex_parser import LaTeXParser
from hiresense.profile.domain.services import ProfileService
from hiresense.profile.domain.skill_extractor import SkillExtractor


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

    # --- Profile module ---
    latex_parser = LaTeXParser()
    skill_extractor = SkillExtractor()
    profile_service = ProfileService(parser=latex_parser, skill_extractor=skill_extractor)
    app.dependency_overrides[get_profile_service] = lambda: profile_service
    app.include_router(profile_router)

    # --- Matching module ---
    # LLM adapter placeholder — real adapter needs API keys
    matching_orchestrator = MatchingOrchestrator(llm=None, event_bus=event_bus)
    app.dependency_overrides[get_matching_orchestrator] = lambda: matching_orchestrator
    app.include_router(matching_router)

    # --- Optimization module ---
    cv_optimizer = CVOptimizer(llm=None)
    app.dependency_overrides[get_cv_optimizer] = lambda: cv_optimizer
    app.include_router(optimization_router)

    # --- Health check ---
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
