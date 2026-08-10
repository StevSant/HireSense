from pydantic_settings import BaseSettings


class OpportunitiesSettings(BaseSettings):
    """Opportunities ingestion (conferences, CFPs, grants, curated events)."""

    enabled_opportunity_sources: list[str] = ["confs_tech", "curated"]
    # Page size for GET /opportunities when the client omits ?page_size, and the
    # ceiling any explicit request is clamped to. Smaller than the global
    # DEFAULT_PAGE_SIZE/MAX_PAGE_SIZE because each row carries a match score.
    opportunities_default_page_size: int = 50
    opportunities_max_page_size: int = 100
    opportunities_schedule: str = "0 6 * * *"
    opportunities_import_dir: str = "./opportunity_imports"
    opportunities_import_filename: str = "opportunities.yml"
    confs_tech_base_url: str = (
        "https://raw.githubusercontent.com/tech-conferences/conference-data/main/conferences"
    )
    confs_tech_topics: list[str] = [
        "javascript",
        "python",
        "general",
        "devops",
        "data",
        "security",
        "ux",
        "ruby",
        "ios",
        "android",
        "golang",
        "rust",
        "cpp",
        "php",
        "dotnet",
        "elixir",
        "scala",
        "tech-comm",
    ]
    confs_tech_years: list[int] = [2026, 2027]
