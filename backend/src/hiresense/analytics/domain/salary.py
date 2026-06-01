from __future__ import annotations

import re
from dataclasses import dataclass

_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP", "usd": "USD", "eur": "EUR", "gbp": "GBP"}
_HOURS_PER_YEAR = 2080
_MONTHS_PER_YEAR = 12
# A number with optional thousands separators and an optional k/m suffix.
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*([kKmM])?"


@dataclass(frozen=True)
class ParsedSalary:
    currency: str
    min_annual: int
    max_annual: int


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


def _period_multiplier(text: str) -> int:
    t = text.lower()
    if "hour" in t or "/hr" in t or "/h" in t:
        return _HOURS_PER_YEAR
    if "month" in t or "/mo" in t:
        return _MONTHS_PER_YEAR
    return 1


class SalaryParser:
    """Best-effort free-text salary parser. Returns None on unparseable input.

    Handles $/€/£ (+ usd/eur/gbp), comma thousands, `k` suffixes, single value
    or range, and hourly/monthly→annual normalization. Lossy by design.
    """

    def parse(self, raw: str | None) -> ParsedSalary | None:
        if not raw or not raw.strip():
            return None
        currency = _detect_currency(raw)
        if currency is None:
            return None
        numbers = [_to_number(v, k) for v, k in re.findall(_NUM, raw)]
        numbers = [n for n in numbers if n > 0]
        if not numbers:
            return None
        mult = _period_multiplier(raw)
        annual = sorted(int(round(n * mult)) for n in numbers)
        return ParsedSalary(currency=currency, min_annual=annual[0], max_annual=annual[-1])
