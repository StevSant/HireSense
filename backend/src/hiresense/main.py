from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hiresense.admin.api import router as admin_router
from hiresense.analytics.api import router as analytics_router
from hiresense.applications.api.routes import router as applications_router
from hiresense.autohunt.api import router as autohunt_router
from hiresense.bootstrap import (
    MatchingDimensionScorerAdapter,
    build_admin,
    build_analytics,
    build_applications,
    build_autohunt,
    build_cover_letter_templates,
    build_identity,
    build_ingestion,
    build_interview,
    build_matching,
    build_network,
    build_optimization,
    build_outreach,
    build_portfolio,
    build_preference,
    build_profile,
    build_research,
    build_shared_infra,
    build_tracking,
)
from hiresense.config import Settings
from hiresense.observability import setup_telemetry
from hiresense.cover_letter_templates.api import router as cover_letter_templates_router
from hiresense.identity.api import router as auth_router
from hiresense.kernel import SlidingWindowRateLimiter
from hiresense.ingestion.api import router as ingestion_router
from hiresense.interview.api import router as interview_router
from hiresense.matching.api import router as matching_router
from hiresense.optimization.api import router as optimization_router
from hiresense.outreach.api import router as outreach_router
from hiresense.network.api import router as network_router
from hiresense.portfolio.api import router as portfolio_router
from hiresense.preference.api import router as preference_router
from hiresense.profile.api import router as profile_router
from hiresense.research.api import router as research_router
from hiresense.tracking.api import router as tracking_router


def create_app() -> FastAPI:
    settings = Settings()
    http_client = httpx.AsyncClient(timeout=settings.http_timeout)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        # Drain in-flight event handlers before tearing infrastructure down so
        # events published late in a request aren't silently dropped.
        event_bus = getattr(app.state, "event_bus", None)
        if event_bus is not None:
            await event_bus.aclose(timeout=settings.event_bus_drain_timeout_seconds)
        await http_client.aclose()
        # Flush and shut down any OTel providers set up by setup_telemetry. No-op
        # when telemetry is disabled (no providers were stored). Guarded so a
        # shutdown failure never breaks app teardown.
        for provider in getattr(app.state, "otel_providers", []):
            shutdown = getattr(provider, "shutdown", None)
            if shutdown is not None:
                try:
                    shutdown()
                except Exception:  # noqa: BLE001 - teardown must not raise
                    pass

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    app.state.settings = settings

    # Per-client-IP limiter for LLM/network-heavy endpoints (see
    # enforce_expensive_rate_limit). None disables enforcement.
    app.state.rate_limiter = (
        SlidingWindowRateLimiter(
            max_requests=settings.rate_limit_max_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )
        if settings.rate_limit_enabled
        else None
    )

    # Initialize observability (traces/metrics/logs) before any engine/client
    # is built so auto-instrumentation can hook them. No-op when disabled.
    setup_telemetry(app, settings)

    infra = build_shared_infra(settings, http_client)
    # Exposed for the lifespan drain above.
    app.state.event_bus = infra.event_bus

    # --- Admin (owns the tracked-LLM factory the other modules share) ---
    admin = build_admin(infra)
    tracked = admin.tracked
    app.state.admin_provider = admin.provider
    app.include_router(admin_router)

    # --- Identity ---
    app.state.identity = build_identity(settings)
    app.include_router(auth_router)

    # --- Preference (taste-vector learning; consumed by ingestion pre-ranking) ---
    preference = build_preference(infra, tracked)
    app.state.preference = preference.provider
    app.include_router(preference_router)

    # --- Ingestion (uses the tracked-LLM factory for match scoring) ---
    ingestion = build_ingestion(infra, tracked, preference_query=preference.service)
    app.state.ingestion = ingestion.provider
    app.include_router(ingestion_router)

    # Two-phase wiring: ingestion is built after preference, so attach the
    # job-title lookup used by the LLM explanation summary now.
    preference.service.attach_job_lookup(ingestion.orchestrator)

    # --- Profile ---
    profile = build_profile(infra, tracked)
    app.state.profile = profile.provider
    app.include_router(profile_router)

    # --- Portfolio (external proof-of-work sources; optional) ---
    portfolio = build_portfolio(infra)
    if portfolio is not None:
        app.state.portfolio = portfolio.provider
    # Router is always mounted: with no provider the endpoints degrade
    # (sync → 503, projects → empty) instead of 404ing the frontend card.
    app.include_router(portfolio_router)

    # --- Network (LinkedIn connections import; always built — upload-driven) ---
    network = build_network(infra)
    app.state.network = network.provider
    app.include_router(network_router)

    # --- Matching ---
    matching = build_matching(infra, tracked, preference=preference.service)
    app.state.matching = matching.provider
    app.include_router(matching_router)

    # Two-phase wiring (mirrors attach_job_lookup): matching is built after the
    # preference service, so attach the dimension scorer used to snapshot
    # per-job dimension scores onto outcome signals at record time. Absent this
    # (or when it returns None) no signal carries scores -> weight_overrides
    # stays empty -> matching composite is byte-identical to today.
    preference.service.attach_dimension_scorer(
        MatchingDimensionScorerAdapter(
            orchestrator=matching.orchestrator,
            job_lookup=ingestion.orchestrator,
            profile_service=profile.service,
        )
    )

    # --- Optimization ---
    optimization = build_optimization(tracked)
    app.state.optimization = optimization.provider
    app.include_router(optimization_router)

    # --- Tracking ---
    tracking = build_tracking(infra, ingestion.orchestrator)
    app.state.tracking = tracking.provider
    app.include_router(tracking_router)

    # --- Auto-Hunt (scheduled digest of new taste-ranked matches) ---
    autohunt = build_autohunt(infra, ingestion.boards_jobs_repo, ingestion.pre_ranker, profile.service)
    app.state.autohunt = autohunt.provider
    app.include_router(autohunt_router)

    # --- Analytics (read-only funnel + market + skill-gap) ---
    analytics = build_analytics(
        infra, profile.service, tracking.status_history_read, tracking_read=tracking.service
    )
    app.state.analytics = analytics.provider
    app.include_router(analytics_router)

    # --- Interview ---
    interview = build_interview(infra, tracked)
    app.state.interview = interview.provider
    app.include_router(interview_router)

    # --- Applications (depends on most of the above) ---
    app.state.applications_provider = build_applications(
        infra,
        tracked,
        tracking_service=tracking.service,
        ingestion_orchestrator=ingestion.orchestrator,
        matching_orchestrator=matching.orchestrator,
        cv_optimizer=optimization.cv_optimizer,
        interview_prep_service=interview.prep_service,
        profile_service=profile.service,
        portfolio_citation=portfolio.provider.get_citation_service() if portfolio is not None else None,
    )
    app.include_router(applications_router)

    # --- Cover letter templates ---
    app.state.cover_letter_templates = build_cover_letter_templates(infra)
    app.include_router(cover_letter_templates_router)

    # --- Research ---
    research = build_research(infra, tracked)
    app.state.research = research
    app.include_router(research_router)

    # --- Outreach (generation + outreach-event tracking + follow-up nudges) ---
    outreach = build_outreach(
        infra,
        tracked,
        tracking.service,
        profile.service,
        research.get_research_service(),
        portfolio_citation=portfolio.provider.get_citation_service() if portfolio is not None else None,
    )
    app.state.outreach = outreach.provider
    app.include_router(outreach_router)

    # --- Health check ---
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
