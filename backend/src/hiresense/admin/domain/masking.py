from __future__ import annotations


def mask_api_key(key: str | None) -> str:
    """Return a UI-safe preview of an API key: prefix + asterisks + last 4.

    Empty / None inputs become an empty string. Short keys are fully masked
    so we never leak the whole thing.
    """
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    prefix_len = 4 if not key.startswith("sk-") else 7
    if len(key) <= prefix_len + 4:
        return "*" * len(key)
    return f"{key[:prefix_len]}{'*' * 11}{key[-4:]}"
