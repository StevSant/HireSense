from __future__ import annotations

import re

from hiresense.kernel.skill_aliases import SKILL_ALIASES

_PARENTHETICAL_RE = re.compile(r"\([^)]*\)")
_WHITESPACE_RE = re.compile(r"\s+")
# Punctuation we trim from the ends of a token, but never from the middle
# (so "node.js" and "c++" keep their internal characters).
_EDGE_PUNCT = " \t\r\n.,;:/|-"


def normalize_skill(raw: str) -> str:
    """Reduce a skill string to a canonical comparable form.

    Lowercases, drops parenthetical qualifiers (e.g. "Python (primary)" ->
    "python"), trims edge punctuation/whitespace, collapses internal runs of
    whitespace, then resolves known aliases to their canonical spelling.
    Shared by every module that compares or aggregates skills so all bounded
    contexts agree on canonical forms.
    """
    text = _PARENTHETICAL_RE.sub(" ", raw or "").lower()
    text = _WHITESPACE_RE.sub(" ", text).strip(_EDGE_PUNCT).strip()
    return SKILL_ALIASES.get(text, text)
