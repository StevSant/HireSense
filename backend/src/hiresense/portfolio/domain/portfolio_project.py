from __future__ import annotations

from pydantic import BaseModel, Field

from hiresense.portfolio.domain.project_text import ProjectText


class PortfolioProject(BaseModel):
    """A normalized project from any portfolio source adapter."""

    id: str
    source: str
    source_key: str
    url: str | None = None
    demo_url: str | None = None
    pinned: bool = False
    position: int | None = None
    # When False, this project's tech tags + summary are excluded from
    # skill-matching enrichment (does not affect job-specific citations).
    include_in_matching: bool = True
    tech: list[str] = Field(default_factory=list)
    translations: dict[str, ProjectText] = Field(default_factory=dict)

    def text_for(self, language: str, fallback: str = "en") -> ProjectText | None:
        """Translation for `language`, else `fallback`, else any, else None."""
        return (
            self.translations.get(language)
            or self.translations.get(fallback)
            or next(iter(self.translations.values()), None)
        )
