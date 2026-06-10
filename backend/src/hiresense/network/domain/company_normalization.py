from __future__ import annotations

import re

# Legal-suffix tokens stripped from the END of company names, repeatedly
# ("Acme Holdings Inc." -> "acme holdings"). Lowercase, dot-free forms.
# Single letters are deliberately NOT in this set — "Studio C", "Plan A",
# "Tesla Model S" must survive; dotted acronyms (S.A., C.V., ...) are
# handled by _DOTTED_SUFFIX_RE while the dots still exist.
_LEGAL_SUFFIXES = frozenset(
    {
        "inc", "incorporated", "llc", "llp", "ltd", "limited", "corp",
        "corporation", "co", "company", "gmbh", "sa", "sas", "srl", "sl",
        "bv", "ag", "plc", "cv",
    }
)
# Dotted legal-acronym suffixes ("Globant S.A.", "... S.A. de C.V.") removed
# BEFORE punctuation stripping, so the dots disambiguate them from real
# single-letter words in company names.
_DOTTED_SUFFIX_RE = re.compile(
    r"\b(s\.a\.\s+de\s+c\.v\.|s\.a\.s?\.?|s\.r\.l\.|s\.l\.|b\.v\.|a\.g\.|p\.l\.c\.|c\.v\.)\s*$",
    re.IGNORECASE,
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
    for _ in range(2):
        text = _DOTTED_SUFFIX_RE.sub(" ", text)
    text = _NON_WORD_RE.sub(" ", text)
    text = _SPACES_RE.sub(" ", text).strip()
    words = text.split(" ") if text else []
    while words and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)
