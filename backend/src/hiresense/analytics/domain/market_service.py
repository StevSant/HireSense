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
    week: str       # ISO year-week, e.g. "2026-W18"
    count: int


class SalaryDistribution(BaseModel):
    currency: str | None
    min_annual: int | None
    median_annual: int | None
    max_annual: int | None
    parsed_count: int
    unparsed_count: int
    other_currency_count: int


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
        strings, _total = self._corpus.open_salary_strings()
        by_currency: dict[str, list[int]] = {}
        unparsed = 0
        for s in strings:
            parsed = self._salary.parse(s)
            if parsed is None:
                unparsed += 1
                continue
            mid = (parsed.min_annual + parsed.max_annual) // 2
            by_currency.setdefault(parsed.currency, []).append(mid)
        if not by_currency:
            return SalaryDistribution(
                currency=None, min_annual=None, median_annual=None, max_annual=None,
                parsed_count=0, unparsed_count=unparsed, other_currency_count=0,
            )
        dominant = max(by_currency, key=lambda c: len(by_currency[c]))
        vals = sorted(by_currency[dominant])
        other = sum(len(v) for c, v in by_currency.items() if c != dominant)
        return SalaryDistribution(
            currency=dominant, min_annual=vals[0],
            median_annual=int(statistics.median(vals)), max_annual=vals[-1],
            parsed_count=len(vals), unparsed_count=unparsed, other_currency_count=other,
        )
