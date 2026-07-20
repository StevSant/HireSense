from __future__ import annotations

# Cap on the profile text embedded (skills + summary). Single source shared by
# every profile-embedding call so the cache key and the embedded text always
# agree — and so both scoring services embed the same profile identically (#161).
_PROFILE_TEXT_CHAR_LIMIT = 4000


def profile_text(skills: list[str], summary: str) -> str:
    """Deterministic embedding text for a candidate profile: skills + summary."""
    return f"{' '.join(skills)}\n{summary}"[:_PROFILE_TEXT_CHAR_LIMIT]
