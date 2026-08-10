from __future__ import annotations

import hashlib

_FINGERPRINT_CHARS = 16


def prompt_fingerprint(prompt: str) -> str:
    """Short content hash identifying the exact prompt a cached result came from.

    Derived from the prompt text rather than a hand-maintained version integer
    on purpose: a `PROMPT_VERSION = 3` constant only invalidates the cache when
    someone remembers to bump it, and the failure mode of forgetting is silent —
    results scored under the old wording keep being served next to results
    scored under the new one, in the same list, with nothing to indicate they
    are not comparable. Deriving it from the text means editing the prompt IS
    the invalidation.
    """
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:_FINGERPRINT_CHARS]
