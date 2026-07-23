from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from hiresense.analytics.api.dependencies import get_analytics_service
from hiresense.analytics.domain import (
    AnalyticsService,
    CompBenchmark,
    FunnelMetrics,
    MarketIntel,
    SearchFocus,
    SkillGap,
    TargetSalary,
    UpskillingPlan,
)
from hiresense.identity.api.dependencies import require_auth

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_auth)])


@router.get("/funnel", response_model=FunnelMetrics)
def funnel(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> FunnelMetrics:
    try:
        return service.funnel(start=start, end=end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/market", response_model=MarketIntel)
def market(service: AnalyticsService = Depends(get_analytics_service)) -> MarketIntel:
    return service.market()


@router.get("/skill-gap", response_model=SkillGap)
def skill_gap(service: AnalyticsService = Depends(get_analytics_service)) -> SkillGap:
    return service.skill_gap()


@router.get("/upskilling-plan", response_model=UpskillingPlan)
def upskilling_plan(service: AnalyticsService = Depends(get_analytics_service)) -> UpskillingPlan:
    return service.upskilling_plan()


@router.get("/target-salary", response_model=TargetSalary)
async def target_salary(service: AnalyticsService = Depends(get_analytics_service)) -> TargetSalary:
    return await service.target_salary()


@router.get("/comp", response_model=CompBenchmark)
async def comp(service: AnalyticsService = Depends(get_analytics_service)) -> CompBenchmark:
    return await service.comp()


@router.get("/focus", response_model=SearchFocus)
async def focus(service: AnalyticsService = Depends(get_analytics_service)) -> SearchFocus:
    return await service.focus()
