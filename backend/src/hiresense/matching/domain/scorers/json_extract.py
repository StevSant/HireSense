from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)
_SPAN_RE = re.compile(r"(\[.*\]|\{.*\})", re.DOTALL)


def extract_json(response: str) -> Any | None:
    """Parse JSON from an LLM response, tolerating markdown code fences.

    Handles both objects and arrays. Tries, in order: a direct parse, the
    contents of the first fenced ```json block, and the widest bracketed
    span found in the text. Returns the decoded value (dict/list/...) or
    None when nothing parses — callers decide how to degrade.
    """
    if not response:
        return None
    candidates: list[str] = [response]
    fence = _FENCE_RE.search(response)
    if fence:
        candidates.append(fence.group(1))
    span = _SPAN_RE.search(response)
    if span:
        candidates.append(span.group(1))
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
    return None
