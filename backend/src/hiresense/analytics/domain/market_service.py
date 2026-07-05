from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

from pydantic import BaseModel


class SkillCount(BaseModel):
    skill: str
    count: int
    pct: float


class TrendPoint(BaseModel):
    week: str  # ISO year-week, e.g. "2026-W18"
    count: int


class SalaryDistribution(BaseModel):
    """Salary stats for the dominant currency among open postings.

    `min_annual`/`max_annual` are the true low/high bounds across postings
    (lowest advertised minimum, highest advertised maximum). `median_annual`
    is the median of per-posting midpoints — a representative "typical" figure.
    `disclosed_pct` is the share of open postings that advertised any salary.
    """

    currency: str | None
    min_annual: int | None
    median_annual: int | None
    max_annual: int | None
    parsed_count: int
    unparsed_count: int
    other_currency_count: int
    disclosed_pct: float
    # Postings (dominant currency) whose figure had no explicit period keyword
    # and was assumed annual (parsed.period == "unknown"). Lets the UI caveat
    # the band as based partly on unlabeled figures.
    inferred_count: int = 0


class MarketIntel(BaseModel):
    top_skills: list[SkillCount]
    remote_mix: dict[str, int]
    posting_trend: list[TrendPoint]
    salary_distribution: SalaryDistribution


class MarketIntelService:
    def __init__(self, corpus: Any, normalizer: Any, salary_parser: Any) -> None:
        self._corpus = corpus
        self._norm = normalizer
        self._salary = salary_parser

    def compute(self, *, top_skills: int = 20) -> MarketIntel:
        return MarketIntel(
            top_skills=self._top_skills(top_skills),
            remote_mix=self._corpus.remote_modality_counts(),
            posting_trend=self._trend(),
            salary_distribution=self._salary_distribution(),
        )

    def _top_skills(self, limit: int) -> list[SkillCount]:
        counter: Counter[str] = Counter()
        n_jobs = 0
        for skills in self._corpus.open_skill_lists():
            n_jobs += 1
            seen = {self._norm.normalize(s) for s in skills if s and s.strip()}
            seen.discard("")
            counter.update(seen)
        total = max(n_jobs, 1)
        return [
            SkillCount(skill=skill, count=count, pct=round(100.0 * count / total, 1))
            for skill, count in counter.most_common(limit)
        ]

    def _trend(self) -> list[TrendPoint]:
        weeks: Counter[str] = Counter()
        for d in self._corpus.posting_dates():
            iso = d.isocalendar()
            weeks[f"{iso[0]}-W{iso[1]:02d}"] += 1
        return [TrendPoint(week=w, count=c) for w, c in sorted(weeks.items())]

    def _salary_distribution(self) -> SalaryDistribution:
        strings, total_open = self._corpus.open_salary_strings()
        # Per currency: midpoints (for the median) + true low/high bounds.
        midpoints: dict[str, list[int]] = {}
        bounds: dict[str, list[int]] = {}  # [min_of_mins, max_of_maxes]
        # Per-currency count of postings whose period was "unknown" (no keyword
        # found; figure assumed annual). Surfaced as inferred_count for the
        # dominant currency only.
        inferred: dict[str, int] = {}
        unparsed = 0
        for s in strings:
            parsed = self._salary.parse(s)
            if parsed is None:
                unparsed += 1
                continue
            midpoints.setdefault(parsed.currency, []).append(
                (parsed.min_annual + parsed.max_annual) // 2
            )
            b = bounds.setdefault(parsed.currency, [parsed.min_annual, parsed.max_annual])
            b[0] = min(b[0], parsed.min_annual)
            b[1] = max(b[1], parsed.max_annual)
            if parsed.period == "unknown":
                inferred[parsed.currency] = inferred.get(parsed.currency, 0) + 1
        disclosed_pct = round(100.0 * len(strings) / total_open, 1) if total_open else 0.0
        if not midpoints:
            return SalaryDistribution(
                currency=None,
                min_annual=None,
                median_annual=None,
                max_annual=None,
                parsed_count=0,
                unparsed_count=unparsed,
                other_currency_count=0,
                disclosed_pct=disclosed_pct,
            )
        dominant = max(midpoints, key=lambda c: len(midpoints[c]))
        mids = midpoints[dominant]
        other = sum(len(v) for c, v in midpoints.items() if c != dominant)
        return SalaryDistribution(
            currency=dominant,
            min_annual=bounds[dominant][0],
            median_annual=int(statistics.median(mids)),
            max_annual=bounds[dominant][1],
            parsed_count=len(mids),
            unparsed_count=unparsed,
            other_currency_count=other,
            disclosed_pct=disclosed_pct,
            inferred_count=inferred.get(dominant, 0),
        )
