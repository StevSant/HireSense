from __future__ import annotations

import hashlib

# Mirrors the char cap used by the semantic scorer's profile text so the same
# profile content hashes identically across both subsystems.
_TEXT_CHAR_LIMIT = 4000


def score_profile_hash(skills: list[str], summary: str) -> str:
    """Stable content hash of the candidate profile, used to key match caches.

    Editing the CV (skills or section text) changes this hash, which
    transparently invalidates any cached quick/deep match scores for that
    profile — a later request recomputes against the new content. The
    normalization matches the semantic scorer's profile key so identical
    content always yields the same hash.
    """
    raw = f"{' '.join(skills)}\n{summary}"[:_TEXT_CHAR_LIMIT].encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
