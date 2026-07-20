from __future__ import annotations

import logging
from typing import Any

from hiresense.ingestion.domain.embedding_text.profile_key import profile_key
from hiresense.ingestion.domain.embedding_text.profile_text import profile_text
from hiresense.kernel import LRUCache

logger = logging.getLogger(__name__)


async def embed_profile_cached(
    embedding: Any,
    cache: LRUCache[str, list[float]],
    skills: list[str],
    summary: str,
    *,
    log_label: str = "Profile embedding failed",
) -> list[float] | None:
    """Embed a candidate profile once and cache the vector by content hash.

    Shared "embed the profile once, cache by hash, degrade on empty/failure"
    flow used by both SemanticScoringService and SemanticPreRanker (#161). The
    cache is not internally synchronized — callers serialize concurrent access
    via their own asyncio.Lock.

    Returns None (caller degrades to its skill-only / passthrough path) when the
    profile text is empty, the embedding call fails, or the port yields no usable
    vector.
    """
    key = profile_key(skills, summary)
    cached = cache.get(key)
    if cached is not None:
        return cached
    text = profile_text(skills, summary)
    if not text.strip():
        return None
    try:
        vectors = await embedding.embed([text])
    except Exception:
        logger.exception(log_label)
        return None
    if not vectors:
        return None
    vec = vectors[0]
    if not vec:
        return None
    cache[key] = vec
    return vec
