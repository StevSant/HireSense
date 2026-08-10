from pydantic_settings import BaseSettings


class PortfolioSettings(BaseSettings):
    """External proof-of-work portfolio sources (Supabase, GitHub) + citation config."""

    # --- Portfolio (external proof-of-work sources) ---
    # Comma-separated adapter list (mirrors enabled_job_sources). Empty list
    # disables the portfolio module entirely: no provider is built and every
    # consumer (enrichment, endpoints, frontend card) degrades gracefully.
    portfolio_sources: list[str] = []
    # Supabase PostgREST base URL + public anon key (read-only by RLS) for the
    # "supabase" source adapter.
    portfolio_supabase_url: str = ""
    portfolio_supabase_anon_key: str = ""
    # GitHub source adapter: public repos of this user become portfolio
    # projects. Token is optional for public repos (raises the rate limit
    # 60 -> 5000 req/h).
    portfolio_github_username: str = ""
    portfolio_github_token: str = ""
    portfolio_github_api_url: str = "https://api.github.com"
    # When True the adapter reads the *token owner's* repos (GET /user/repos)
    # including private ones, instead of a username's public repos. Requires a
    # token with the `repo` scope; portfolio_github_username is then ignored.
    portfolio_github_include_private: bool = False
    # Repos kept after sorting by stars + recent push. Bounds the per-repo
    # languages calls (one HTTP request per kept repo).
    portfolio_github_max_repos: int = 30
    # Char cap for the "Portfolio projects" block appended to the matching
    # profile summary.
    portfolio_profile_char_cap: int = 1200
    # Default page size for the paginated GET /portfolio/projects endpoint.
    portfolio_projects_page_size: int = 12
    # Public portfolio site linked from generated artifacts. Empty disables
    # the tracked link (project citations still work).
    portfolio_public_url: str = ""
    # Slug prefix for per-application tracked links: ?ref=<prefix>-<application_id>.
    portfolio_ref_prefix: str = "hiresense"
    # How many relevant projects get cited per generated artifact.
    portfolio_relevant_projects_top_n: int = 2
    # Supabase service_role key for reading visitor analytics (Dashboard →
    # Settings → API). Empty disables engagement readback entirely.
    portfolio_analytics_read_key: str = ""
