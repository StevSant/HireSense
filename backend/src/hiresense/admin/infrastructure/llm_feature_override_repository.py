from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select

from hiresense.admin.domain import LLMFeatureOverrideRecord
from hiresense.admin.infrastructure.llm_feature_override_model import LLMFeatureOverride


def _to_domain(row: LLMFeatureOverride) -> LLMFeatureOverrideRecord:
    return LLMFeatureOverrideRecord(
        feature_key=row.feature_key,
        provider=row.provider,
        model=row.model,
        extra_params=dict(row.extra_params or {}),
        updated_by=row.updated_by,
        updated_at=row.updated_at,
        id=row.id,
    )


class LLMFeatureOverrideRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def list(self) -> list[LLMFeatureOverrideRecord]:
        with self._session_factory() as session:
            return [_to_domain(r) for r in session.scalars(select(LLMFeatureOverride)).all()]

    def get(self, feature_key: str) -> LLMFeatureOverrideRecord | None:
        with self._session_factory() as session:
            stmt = select(LLMFeatureOverride).where(LLMFeatureOverride.feature_key == feature_key)
            row = session.scalars(stmt).first()
            return _to_domain(row) if row is not None else None

    def upsert(
        self,
        *,
        feature_key: str,
        provider: str | None,
        model: str | None,
        extra_params: dict,
        updated_by: str | None,
    ) -> LLMFeatureOverrideRecord:
        with self._session_factory() as session:
            stmt = select(LLMFeatureOverride).where(LLMFeatureOverride.feature_key == feature_key)
            row = session.scalars(stmt).first()
            if row is None:
                row = LLMFeatureOverride(
                    feature_key=feature_key,
                    provider=provider,
                    model=model,
                    extra_params=extra_params,
                    updated_by=updated_by,
                )
                session.add(row)
            else:
                row.provider = provider
                row.model = model
                row.extra_params = extra_params
                row.updated_by = updated_by
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def delete(self, feature_key: str) -> bool:
        with self._session_factory() as session:
            result = session.execute(
                delete(LLMFeatureOverride).where(LLMFeatureOverride.feature_key == feature_key)
            )
            session.commit()
            return result.rowcount > 0
