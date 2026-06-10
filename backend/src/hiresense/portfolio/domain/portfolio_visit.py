from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PortfolioVisit(BaseModel):
    """Aggregated visit data for one tracked portfolio link (one ref)."""

    ref: str
    application_id: str | None = None
    first_seen: datetime
    last_seen: datetime
    page_views: int = 0
    cv_downloads: int = 0
    country: str | None = None
    organization: str | None = None
