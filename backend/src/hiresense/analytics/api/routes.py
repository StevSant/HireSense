from __future__ import annotations

from fastapi import APIRouter, Depends

from hiresense.analytics.api.dependencies import get_analytics_service
from hiresense.analytics.domain import AnalyticsService, FunnelMetrics, MarketIntel, SkillGap, TargetSalary
from hiresense.identity.api.dependencies import require_auth

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_auth)])


@router.get("/funnel", response_model=FunnelMetrics)
def funnel(service: AnalyticsService = Depends(get_analytics_service)) -> FunnelMetrics:
    return service.funnel()


@router.get("/market", response_model=MarketIntel)
def market(service: AnalyticsService = Depends(get_analytics_service)) -> MarketIntel:
    return service.market()


@router.get("/skill-gap", response_model=SkillGap)
def skill_gap(service: AnalyticsService = Depends(get_analytics_service)) -> SkillGap:
    return service.skill_gap()


@router.get("/target-salary", response_model=TargetSalary)
async def target_salary(service: AnalyticsService = Depends(get_analytics_service)) -> TargetSalary:
    return await service.target_salary()
