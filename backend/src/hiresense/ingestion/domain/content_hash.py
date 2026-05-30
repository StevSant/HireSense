from __future__ import annotations

import hashlib

from hiresense.ingestion.domain.models import NormalizedJob


def content_hash(job: NormalizedJob) -> str:
    """sha256 over the mutable fields that define 'has this posting changed?'.

    Excludes id, scores, timestamps, and identity/metadata fields (url, source,
    source_type, language, posted_date, department, platform, categories,
    countries, remote_modality) — only the human-facing content fields drive
    change detection. Skills are sorted so reordering does not register as a
    change.
    """
    parts = [
        job.title.strip(),
        job.company.strip(),
        job.description.strip(),
        job.location.strip(),
        (job.salary_range or "").strip(),
        "|".join(sorted(s.strip().lower() for s in job.skills)),
    ]
    raw = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
