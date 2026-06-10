from __future__ import annotations

from dataclasses import dataclass

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.portfolio.adapters import GitHubPortfolioAdapter, SupabasePortfolioAdapter
from hiresense.portfolio.api.provider import PortfolioProvider
from hiresense.portfolio.domain import PortfolioEnrichmentService, PortfolioSyncService
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
            if not s.portfolio_github_username:
                raise ValueError(
                    "portfolio source 'github' is enabled but "
                    "PORTFOLIO_GITHUB_USERNAME is not set"
                )
            sources.append(
                GitHubPortfolioAdapter(
                    http_client=infra.http_client,
                    api_url=s.portfolio_github_api_url,
                    username=s.portfolio_github_username,
                    token=s.portfolio_github_token,
                    max_repos=s.portfolio_github_max_repos,
                )
            )
        else:
            raise ValueError(f"Unknown portfolio source: {name}")

    repository = PortfolioProjectsRepository(session_factory=infra.sync_session_factory)
    provider = PortfolioProvider(
        sync_service=PortfolioSyncService(sources=sources, repository=repository),
        repository=repository,
        enrichment_service=PortfolioEnrichmentService(
            repository=repository,
            language=s.default_language,
            char_cap=s.portfolio_profile_char_cap,
        ),
    )
    return PortfolioBuild(provider=provider)
