from __future__ import annotations

import hashlib

from hiresense.ingestion.domain.embedding_text.profile_text import profile_text


def profile_key(skills: list[str], summary: str) -> str:
    """Stable content hash of the profile embedding text — the profile cache key.

    Derived from the SAME text that gets embedded (``profile_text``) so the key
    and the vector can never drift apart between services (#161).
    """
    raw = profile_text(skills, summary).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
