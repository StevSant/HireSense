from __future__ import annotations

from dataclasses import dataclass

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.portfolio.adapters import (
    GitHubPortfolioAdapter,
    SupabaseEngagementAdapter,
    SupabasePortfolioAdapter,
)
from hiresense.portfolio.api.provider import PortfolioProvider
from hiresense.portfolio.domain import (
    PortfolioCitationService,
    PortfolioEngagementService,
    PortfolioEnrichmentService,
    PortfolioSyncService,
    RelevantProjectSelector,
)
from hiresense.portfolio.infrastructure import PortfolioProjectsRepository


@dataclass(frozen=True)
class PortfolioBuild:
    provider: PortfolioProvider


def build_portfolio(infra: SharedInfra) -> PortfolioBuild | None:
    """None when no sources are configured — the module is fully optional."""
    s = infra.settings
    if not s.portfolio_sources:
        return None

    sources = []
    for name in s.portfolio_sources:
        if name == "supabase":
            if not s.portfolio_supabase_url or not s.portfolio_supabase_anon_key:
                raise ValueError(
                    "portfolio source 'supabase' is enabled but PORTFOLIO_SUPABASE_URL "
                    "and/or PORTFOLIO_SUPABASE_ANON_KEY are not set"
                )
            sources.append(
                SupabasePortfolioAdapter(
                    http_client=infra.http_client,
                    base_url=s.portfolio_supabase_url,
                    anon_key=s.portfolio_supabase_anon_key,
                )
            )
        elif name == "github":
            if s.portfolio_github_include_private:
                if not s.portfolio_github_token:
                    raise ValueError(
                        "portfolio source 'github' has "
                        "PORTFOLIO_GITHUB_INCLUDE_PRIVATE=true but "
                        "PORTFOLIO_GITHUB_TOKEN is not set (a token with the "
                        "`repo` scope is required to read private repos)"
                    )
            elif not s.portfolio_github_username:
                raise ValueError(
                    "portfolio source 'github' is enabled but PORTFOLIO_GITHUB_USERNAME is not set"
                )
            sources.append(
                GitHubPortfolioAdapter(
                    http_client=infra.http_client,
                    api_url=s.portfolio_github_api_url,
                    username=s.portfolio_github_username,
                    token=s.portfolio_github_token,
                    max_repos=s.portfolio_github_max_repos,
                    include_private=s.portfolio_github_include_private,
                )
            )
        else:
            raise ValueError(f"Unknown portfolio source: {name}")

    engagement_service: PortfolioEngagementService | None = None
    if s.portfolio_analytics_read_key and s.portfolio_supabase_url:
        engagement_service = PortfolioEngagementService(
            SupabaseEngagementAdapter(
                http_client=infra.http_client,
                base_url=s.portfolio_supabase_url,
                read_key=s.portfolio_analytics_read_key,
            ),
            ref_prefix=s.portfolio_ref_prefix,
        )

    repository = PortfolioProjectsRepository(session_factory=infra.sync_session_factory)
    provider = PortfolioProvider(
        sync_service=PortfolioSyncService(sources=sources, repository=repository),
        repository=repository,
        enrichment_service=PortfolioEnrichmentService(
            repository=repository,
            language=s.default_language,
            char_cap=s.portfolio_profile_char_cap,
        ),
        citation_service=PortfolioCitationService(
            repository=repository,
            selector=RelevantProjectSelector(),
            language=s.default_language,
            top_n=s.portfolio_relevant_projects_top_n,
            public_url=s.portfolio_public_url,
            ref_prefix=s.portfolio_ref_prefix,
        ),
        engagement_service=engagement_service,
    )
    return PortfolioBuild(provider=provider)
