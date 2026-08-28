from __future__ import annotations

import dataclasses
from datetime import datetime

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.shared.kernel import as_utc


@dataclasses.dataclass(frozen=True)
class JobListCriteria:
    """Cheap, selective predicates a repository can evaluate DB-side.

    Deliberately limited to filters with direct column equivalents — the
    Python-only heuristics (keyword, seniority and opportunity detection, years
    extraction, international pathways, strict_location) stay in
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
        # Normalised on both sides: criteria dates arrive naive from query
        # params while posted_date is aware, and comparing them raises.
        posted = as_utc(job.posted_date)
        date_from = as_utc(self.date_from)
        date_to = as_utc(self.date_to)
        if date_from is not None and (posted is None or posted < date_from):
            return False
        if date_to is not None and (posted is None or posted > date_to):
            return False
        return True
