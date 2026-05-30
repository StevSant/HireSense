from __future__ import annotations

import hashlib

from hiresense.ingestion.domain.models import NormalizedJob


def identity_key(job: NormalizedJob) -> str:
    """Stable identity: source_id (hashed if >64 chars) else sha256(url)."""
    if job.source_id:
        if len(job.source_id) <= 64:
            return job.source_id
        return hashlib.sha256(job.source_id.encode("utf-8")).hexdigest()
    return hashlib.sha256((job.url or "").encode("utf-8")).hexdigest()
