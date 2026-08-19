from __future__ import annotations

import hashlib

from hiresense.ingestion.domain.embedding_text.job_text import job_text
from hiresense.ingestion.domain.models import NormalizedJob


def job_text_hash(job: NormalizedJob) -> str:
    """sha256 of the exact text that gets embedded.

    Distinct from ``content_hash``, which answers "did the posting change?" over
    the fields that drive change detection and filtering. This answers the
    narrower question the indexer needs: "would embedding this job produce a
    different vector than the one already stored?" A job that closes and reopens,
    or whose non-embedded fields shift, hashes the same and is skipped.
    """
    return hashlib.sha256(job_text(job).encode("utf-8")).hexdigest()
