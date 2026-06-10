from __future__ import annotations

import re

# Legal-suffix tokens stripped from the END of company names, repeatedly
# ("Acme Holdings Inc." -> "acme holdings"). Lowercase, dot-free forms.
_LEGAL_SUFFIXES = frozenset(
    {
        "inc", "incorporated", "llc", "llp", "ltd", "limited", "corp",
        "corporation", "co", "company", "gmbh", "sa", "sas", "srl", "sl",
        "bv", "ag", "plc", "sa de cv", "cv", "de", "s", "a", "c", "v",
    }
)
_PARENS_RE = re.compile(r"\([^)]*\)")
_NON_WORD_RE = re.compile(r"[^a-z0-9 ]+")
_SPACES_RE = re.compile(r"\s+")


def normalize_company(raw: str) -> str:
    """Canonical company key for matching contacts to job postings.

    Lowercases, drops parentheticals and punctuation, collapses whitespace,
    and strips trailing legal suffixes (inc/llc/s.a./gmbh/...).
    """
    text = _PARENS_RE.sub(" ", raw.lower())
    text = _NON_WORD_RE.sub(" ", text)
    text = _SPACES_RE.sub(" ", text).strip()
    words = text.split(" ") if text else []
    while words and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)
