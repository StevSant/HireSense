from __future__ import annotations

import dataclasses
from datetime import datetime

from hiresense.ingestion.domain.models import NormalizedJob


@dataclasses.dataclass(frozen=True)
class JobListCriteria:
    """Cheap, selective predicates a repository can evaluate DB-side.

    Deliberately limited to filters with direct column equivalents — the
    Python-only heuristics (keyword, seniority detection, years extraction,
    strict_location, the min_score semantic-None exemption) stay in
    filter_and_paginate, which re-applies these predicates idempotently.
    """

    include_closed: bool = False
    include_low_quality: bool = False
    source: str | None = None
    company: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None

    def matches(self, job: NormalizedJob) -> bool:
        """In-memory equivalent of the SQL predicates (used by the in-memory repo)."""
        if not self.include_closed and job.status == "closed":
            return False
        if not self.include_low_quality and (job.quality or "ok") != "ok":
            return False
        if self.source and job.source != self.source:
            return False
        if self.company and job.company.strip().lower() != self.company.strip().lower():
            return False
        if self.date_from and (job.posted_date is None or job.posted_date < self.date_from):
            return False
        if self.date_to and (job.posted_date is None or job.posted_date > self.date_to):
            return False
        return True
