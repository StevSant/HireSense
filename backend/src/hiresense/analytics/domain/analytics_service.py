from __future__ import annotations

from typing import Any

from hiresense.analytics.domain.comp_benchmark_service import CompBenchmark, CompBenchmarkService
from hiresense.analytics.domain.funnel_service import FunnelMetrics, FunnelService
from hiresense.analytics.domain.market_service import MarketIntel, MarketIntelService
from hiresense.analytics.domain.search_focus_service import SearchFocus, SearchFocusService
from hiresense.analytics.domain.skill_gap_service import SkillGap, SkillGapService
from hiresense.analytics.domain.target_salary_service import TargetSalary, TargetSalaryService


class AnalyticsService:
    """Facade over the analytics query services. The API depends on this."""

    def __init__(
        self,
        *,
        funnel: FunnelService,
        market: MarketIntelService,
        skill_gap: SkillGapService,
        target_salary: TargetSalaryService,
        comp_benchmark: CompBenchmarkService,
        search_focus: SearchFocusService,
        profile_service: Any,
        cache: Any,
        language: str = "en",
    ) -> None:
        self._funnel = funnel
        self._market = market
        self._skill_gap = skill_gap
        self._target_salary = target_salary
        self._comp_benchmark = comp_benchmark
        self._search_focus = search_focus
        self._profile = profile_service
        self._cache = cache
        self._language = language

    def funnel(self) -> FunnelMetrics:
        return self._funnel.compute()

    def market(self) -> MarketIntel:
        return self._cache.get_or_compute("market", self._market.compute)

    def skill_gap(self) -> SkillGap:
        return self._skill_gap.compute(profile_skills=self._profile_skills())

    async def target_salary(self) -> TargetSalary:
        skills, summary = self._profile_skills_summary()
        return await self._target_salary.compute(profile_skills=skills, summary=summary)

    async def comp(self) -> CompBenchmark:
        skills, summary = self._profile_skills_summary()
        return await self._comp_benchmark.compute(profile_skills=skills, summary=summary)

    async def focus(self) -> SearchFocus:
        skills, summary = self._profile_skills_summary()
        return await self._search_focus.compute(profile_skills=skills, summary=summary)

    def _profile_skills(self) -> list[str]:
        view = self._profile.get_for_language(self._language)
        return list(view.skills) if view else []

    def _profile_skills_summary(self) -> tuple[list[str], str]:
        view = self._profile.get_for_language(self._language)
        skills = list(view.skills) if view else []
        summary = view.summary if view else ""
        return skills, summary
