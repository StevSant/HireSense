from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from hiresense.admin.api.dependencies import get_usage_aggregator, require_admin
from hiresense.admin.api.schemas import (
    BreakdownResponse,
    DashboardSummaryView,
    RecentCallsResponse,
    TimeseriesResponse,
    UsageBucketView,
    UsageCallView,
    UsageTotalsView,
)
from hiresense.admin.domain.usage_aggregator import UsageAggregator

router = APIRouter(
    prefix="/admin/usage",
    tags=["admin", "usage"],
    dependencies=[Depends(require_admin)],
)


@router.get("/summary", response_model=DashboardSummaryView)
def summary(
    aggregator: Annotated[UsageAggregator, Depends(get_usage_aggregator)],
) -> DashboardSummaryView:
    s = aggregator.summary()
    return DashboardSummaryView(
        today=_to_totals(s.today),
        this_month=_to_totals(s.this_month),
        all_time=_to_totals(s.all_time),
    )


@router.get("/timeseries", response_model=TimeseriesResponse)
def timeseries(
    aggregator: Annotated[UsageAggregator, Depends(get_usage_aggregator)],
    days: int = Query(30, ge=1, le=365),
) -> TimeseriesResponse:
    buckets = aggregator.timeseries(days=days)
    return TimeseriesResponse(days=days, buckets=[_to_bucket(b) for b in buckets])


@router.get("/breakdown", response_model=BreakdownResponse)
def breakdown(
    aggregator: Annotated[UsageAggregator, Depends(get_usage_aggregator)],
    dimension: str = Query("provider", pattern="^(provider|model|feature)$"),
    days: int | None = Query(30, ge=1, le=365),
) -> BreakdownResponse:
    buckets = aggregator.breakdown(dimension=dimension, days=days)
    return BreakdownResponse(dimension=dimension, days=days, buckets=[_to_bucket(b) for b in buckets])


@router.get("/calls", response_model=RecentCallsResponse)
def recent_calls(
    aggregator: Annotated[UsageAggregator, Depends(get_usage_aggregator)],
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    provider: str | None = None,
    model: str | None = None,
    feature_key: str | None = None,
    days: int | None = Query(None, ge=1, le=365),
    sort: str | None = None,
) -> RecentCallsResponse:
    rows = aggregator.recent_calls(
        limit=limit, offset=offset,
        provider=provider, model=model, feature_key=feature_key, days=days,
        sort=sort,
    )
    return RecentCallsResponse(
        limit=limit,
        offset=offset,
        calls=[
            UsageCallView(
                id=str(r.id),
                created_at=r.created_at.isoformat() if r.created_at else "",
                feature_key=r.feature_key,
                provider=r.provider,
                model=r.model,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                total_tokens=r.total_tokens,
                cost_usd=r.cost_usd,
                latency_ms=r.latency_ms,
                success=r.success,
                error=r.error,
            )
            for r in rows
        ],
    )


@router.get("/export")
def export_csv(
    aggregator: Annotated[UsageAggregator, Depends(get_usage_aggregator)],
    provider: str | None = None,
    model: str | None = None,
    feature_key: str | None = None,
    days: int | None = Query(90, ge=1, le=365),
) -> StreamingResponse:
    csv_text = aggregator.export_csv(
        provider=provider, model=model, feature_key=feature_key, days=days,
    )
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=llm_usage.csv"},
    )


def _to_totals(t) -> UsageTotalsView:
    return UsageTotalsView(
        total_calls=t.total_calls,
        total_input_tokens=t.total_input_tokens,
        total_output_tokens=t.total_output_tokens,
        total_tokens=t.total_tokens,
        total_cost_usd=t.total_cost_usd,
    )


def _to_bucket(b) -> UsageBucketView:
    return UsageBucketView(
        key=b.key,
        calls=b.calls,
        input_tokens=b.input_tokens,
        output_tokens=b.output_tokens,
        total_tokens=b.total_tokens,
        cost_usd=b.cost_usd,
    )
