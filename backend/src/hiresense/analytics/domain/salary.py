from __future__ import annotations

import re
from dataclasses import dataclass

_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP", "usd": "USD", "eur": "EUR", "gbp": "GBP"}
_HOURS_PER_YEAR = 2080
_MONTHS_PER_YEAR = 12
# Fallback floor when no config-driven value is injected. The app path injects
# settings.salary_annual_floor via bootstrap; this default only backs bare
# SalaryParser() construction (e.g. in tests).
_DEFAULT_ANNUAL_FLOOR = 12000
# A number with optional thousands separators and an optional k/m suffix.
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*([kKmM])?"


@dataclass(frozen=True)
class ParsedSalary:
    currency: str
    min_annual: int
    max_annual: int
    # Detected (or inferred) SOURCE period. "unknown" == no keyword found and the
    # figure was plausible for annual, so annual was assumed.
    period: str


def _detect_currency(text: str) -> str | None:
    for token, code in _CURRENCY.items():
        if token in text.lower() if token.isalpha() else token in text:
            return code
    return None


def _to_number(value: str, suffix: str | None) -> float:
    n = float(value.replace(",", ""))
    if suffix in ("k", "K"):
        n *= 1000
    elif suffix in ("m", "M"):
        n *= 1_000_000
    return n


def _keyword_period(text: str) -> str | None:
    t = text.lower()
    if "hour" in t or "/hr" in t or "/h" in t:
        return "hourly"
    if "month" in t or "/mo" in t:
        return "monthly"
    return None


class SalaryParser:
    """Best-effort free-text salary parser. Returns None on unparseable input.

    Handles $/€/£ (+ usd/eur/gbp), comma thousands, `k`/`m` suffixes, single
    value or range, and hourly/monthly→annual normalization. Records the source
    `period`. When no period keyword is present, an implausibly-low figure (below
    `annual_floor`) is inferred as monthly; an otherwise-plausible figure is
    assumed annual and flagged `"unknown"`. Lossy by design.
    """

    def __init__(self, annual_floor: int = _DEFAULT_ANNUAL_FLOOR) -> None:
        self._annual_floor = annual_floor

    def parse(self, raw: str | None) -> ParsedSalary | None:
        if not raw or not raw.strip():
            return None
        currency = _detect_currency(raw)
        if currency is None:
            return None
        raw_numbers = [_to_number(v, k) for v, k in re.findall(_NUM, raw)]
        raw_numbers = [n for n in raw_numbers if n > 0]
        if not raw_numbers:
            return None

        keyword = _keyword_period(raw)
        if keyword == "hourly":
            period, mult = "hourly", _HOURS_PER_YEAR
        elif keyword == "monthly":
            period, mult = "monthly", _MONTHS_PER_YEAR
        elif min(raw_numbers) < self._annual_floor:
            period, mult = "monthly", _MONTHS_PER_YEAR
        else:
            period, mult = "unknown", 1

        annual = sorted(int(round(n * mult)) for n in raw_numbers)
        return ParsedSalary(
            currency=currency, min_annual=annual[0], max_annual=annual[-1], period=period,
        )
