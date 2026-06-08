from __future__ import annotations

from pydantic import BaseModel

from hiresense.ingestion.domain.job_quality import JobQuality


class JobQualityVerdict(BaseModel):
    """The classifier's call on a single job: a quality bucket + a short reason.

    `reason` is None for OK jobs (nothing to explain) and a concise phrase for
    flagged ones (e.g. "Commission-only MLM pitch").
    """

    job_id: str
    quality: JobQuality
    reason: str | None = None
