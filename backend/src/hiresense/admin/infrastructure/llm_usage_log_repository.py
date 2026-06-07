from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import String, and_, cast, func, select

from hiresense.admin.domain import UsageBucket, UsageRecord, UsageTotals
from hiresense.admin.infrastructure.llm_usage_log_model import LLMUsageLog


def _to_domain(row: LLMUsageLog) -> UsageRecord:
    return UsageRecord(
        feature_key=row.feature_key,
        provider=row.provider,
        model=row.model,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        total_tokens=row.total_tokens,
        cost_usd=row.cost_usd,
        latency_ms=row.latency_ms,
        success=row.success,
        error=row.error,
        user_id=row.user_id,
        created_at=row.created_at,
        id=row.id,
    )


class LLMUsageLogRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def insert(
        self,
        *,
        feature_key: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost_usd: float,
        latency_ms: float,
        success: bool,
        error: str | None,
        user_id: str | None,
    ) -> None:
        with self._session_factory() as session:
            entry = LLMUsageLog(
                feature_key=feature_key,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                success=success,
                error=error,
                user_id=user_id,
            )
            session.add(entry)
            session.commit()

    def totals(self, since: datetime | None = None) -> UsageTotals:
        with self._session_factory() as session:
            stmt = select(
                func.count(LLMUsageLog.id),
                func.coalesce(func.sum(LLMUsageLog.input_tokens), 0),
                func.coalesce(func.sum(LLMUsageLog.output_tokens), 0),
                func.coalesce(func.sum(LLMUsageLog.total_tokens), 0),
                func.coalesce(func.sum(LLMUsageLog.cost_usd), 0.0),
            )
            if since is not None:
                stmt = stmt.where(LLMUsageLog.created_at >= since)
            row = session.execute(stmt).one()
            return UsageTotals(
                total_calls=int(row[0] or 0),
                total_input_tokens=int(row[1] or 0),
                total_output_tokens=int(row[2] or 0),
                total_tokens=int(row[3] or 0),
                total_cost_usd=float(row[4] or 0.0),
            )

    def timeseries_daily(self, since: datetime) -> list[UsageBucket]:
        """Per-day buckets for the dashboard chart, ordered by day asc."""
        with self._session_factory() as session:
            day = cast(func.date_trunc("day", LLMUsageLog.created_at), String).label("day")
            stmt = (
                select(
                    day,
                    func.count(LLMUsageLog.id),
                    func.coalesce(func.sum(LLMUsageLog.input_tokens), 0),
                    func.coalesce(func.sum(LLMUsageLog.output_tokens), 0),
                    func.coalesce(func.sum(LLMUsageLog.total_tokens), 0),
                    func.coalesce(func.sum(LLMUsageLog.cost_usd), 0.0),
                )
                .where(LLMUsageLog.created_at >= since)
                .group_by(day)
                .order_by(day.asc())
            )
            rows = session.execute(stmt).all()
            return [
                UsageBucket(
                    key=str(r[0]),
                    calls=int(r[1] or 0),
                    input_tokens=int(r[2] or 0),
                    output_tokens=int(r[3] or 0),
                    total_tokens=int(r[4] or 0),
                    cost_usd=float(r[5] or 0.0),
                )
                for r in rows
            ]

    def breakdown(self, dimension: str, since: datetime | None = None) -> list[UsageBucket]:
        """Aggregate by 'provider', 'model', or 'feature_key'."""
        column_map = {
            "provider": LLMUsageLog.provider,
            "model": LLMUsageLog.model,
            "feature": LLMUsageLog.feature_key,
            "feature_key": LLMUsageLog.feature_key,
        }
        col = column_map.get(dimension)
        if col is None:
            raise ValueError(f"unknown breakdown dimension: {dimension}")
        with self._session_factory() as session:
            stmt = select(
                col,
                func.count(LLMUsageLog.id),
                func.coalesce(func.sum(LLMUsageLog.input_tokens), 0),
                func.coalesce(func.sum(LLMUsageLog.output_tokens), 0),
                func.coalesce(func.sum(LLMUsageLog.total_tokens), 0),
                func.coalesce(func.sum(LLMUsageLog.cost_usd), 0.0),
            )
            if since is not None:
                stmt = stmt.where(LLMUsageLog.created_at >= since)
            stmt = stmt.group_by(col).order_by(func.sum(LLMUsageLog.cost_usd).desc())
            rows = session.execute(stmt).all()
            return [
                UsageBucket(
                    key=str(r[0] or ""),
                    calls=int(r[1] or 0),
                    input_tokens=int(r[2] or 0),
                    output_tokens=int(r[3] or 0),
                    total_tokens=int(r[4] or 0),
                    cost_usd=float(r[5] or 0.0),
                )
                for r in rows
            ]

    def list_recent(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        provider: str | None = None,
        model: str | None = None,
        feature_key: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[UsageRecord]:
        with self._session_factory() as session:
            conditions = []
            if provider:
                conditions.append(LLMUsageLog.provider == provider)
            if model:
                conditions.append(LLMUsageLog.model == model)
            if feature_key:
                conditions.append(LLMUsageLog.feature_key == feature_key)
            if since is not None:
                conditions.append(LLMUsageLog.created_at >= since)
            if until is not None:
                conditions.append(LLMUsageLog.created_at < until)
            stmt = select(LLMUsageLog)
            if conditions:
                stmt = stmt.where(and_(*conditions))
            stmt = stmt.order_by(LLMUsageLog.created_at.desc()).limit(limit).offset(offset)
            return [_to_domain(r) for r in session.scalars(stmt).all()]
