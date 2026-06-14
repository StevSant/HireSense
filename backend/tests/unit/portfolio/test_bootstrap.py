import pytest

from hiresense.bootstrap.portfolio import build_portfolio


class _Settings:
    portfolio_sources: list[str] = []
    portfolio_supabase_url = ""
    portfolio_supabase_anon_key = ""
    portfolio_github_username = ""
    portfolio_github_token = ""
    portfolio_github_api_url = "https://api.github.com"
    portfolio_github_max_repos = 30
    portfolio_github_include_private = False
    portfolio_profile_char_cap = 1200
    portfolio_public_url = ""
    portfolio_ref_prefix = "hiresense"
    portfolio_relevant_projects_top_n = 2
    portfolio_analytics_read_key = ""
    default_language = "en"


class _Infra:
    def __init__(self, settings):
        self.settings = settings
        self.http_client = object()
        self.sync_session_factory = object()


def test_returns_none_when_no_sources_configured() -> None:
    assert build_portfolio(_Infra(_Settings())) is None


def test_raises_when_supabase_enabled_without_keys() -> None:
    settings = _Settings()
    settings.portfolio_sources = ["supabase"]
    with pytest.raises(ValueError, match="PORTFOLIO_SUPABASE_URL"):
        build_portfolio(_Infra(settings))


def test_raises_on_unknown_source() -> None:
    settings = _Settings()
    settings.portfolio_sources = ["myspace"]
    with pytest.raises(ValueError, match="Unknown portfolio source"):
        build_portfolio(_Infra(settings))


def test_builds_provider_with_supabase() -> None:
    settings = _Settings()
    settings.portfolio_sources = ["supabase"]
    settings.portfolio_supabase_url = "https://xyz.supabase.co"
    settings.portfolio_supabase_anon_key = "anon"
    build = build_portfolio(_Infra(settings))
    assert build is not None
    assert build.provider.get_sync_service() is not None
    assert build.provider.get_enrichment_service() is not None
    assert build.provider.get_citation_service() is not None


def test_raises_when_github_enabled_without_username() -> None:
    settings = _Settings()
    settings.portfolio_sources = ["github"]
    with pytest.raises(ValueError, match="PORTFOLIO_GITHUB_USERNAME"):
        build_portfolio(_Infra(settings))


def test_raises_when_include_private_without_token() -> None:
    settings = _Settings()
    settings.portfolio_sources = ["github"]
    settings.portfolio_github_include_private = True
    # username set but no token — private mode requires the token instead
    settings.portfolio_github_username = "StevSant"
    with pytest.raises(ValueError, match="PORTFOLIO_GITHUB_TOKEN"):
        build_portfolio(_Infra(settings))


def test_builds_provider_with_private_github_via_token() -> None:
    settings = _Settings()
    settings.portfolio_sources = ["github"]
    settings.portfolio_github_include_private = True
    settings.portfolio_github_token = "ghp_token"  # no username needed
    build = build_portfolio(_Infra(settings))
    assert build is not None
    assert build.provider.get_sync_service() is not None


def test_builds_provider_with_github_and_supabase() -> None:
    settings = _Settings()
    settings.portfolio_sources = ["supabase", "github"]
    settings.portfolio_supabase_url = "https://xyz.supabase.co"
    settings.portfolio_supabase_anon_key = "anon"
    settings.portfolio_github_username = "StevSant"
    build = build_portfolio(_Infra(settings))
    assert build is not None
    assert build.provider.get_sync_service() is not None


def test_engagement_service_none_when_analytics_key_unset() -> None:
    settings = _Settings()
    settings.portfolio_sources = ["supabase"]
    settings.portfolio_supabase_url = "https://xyz.supabase.co"
    settings.portfolio_supabase_anon_key = "anon"
    # portfolio_analytics_read_key is "" by default
    build = build_portfolio(_Infra(settings))
    assert build is not None
    assert build.provider.get_engagement_service() is None


def test_engagement_service_built_when_key_and_url_set() -> None:
    settings = _Settings()
    settings.portfolio_sources = ["supabase"]
    settings.portfolio_supabase_url = "https://xyz.supabase.co"
    settings.portfolio_supabase_anon_key = "anon"
    settings.portfolio_analytics_read_key = "service_role_key"
    build = build_portfolio(_Infra(settings))
    assert build is not None
    assert build.provider.get_engagement_service() is not None
