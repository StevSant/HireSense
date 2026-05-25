from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select

from hiresense.admin.infrastructure.llm_feature_override_model import LLMFeatureOverride


class LLMFeatureOverrideRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def list(self) -> list[LLMFeatureOverride]:
        with self._session_factory() as session:
            return list(session.scalars(select(LLMFeatureOverride)).all())

    def get(self, feature_key: str) -> LLMFeatureOverride | None:
        with self._session_factory() as session:
            stmt = select(LLMFeatureOverride).where(LLMFeatureOverride.feature_key == feature_key)
            return session.scalars(stmt).first()

    def upsert(
        self,
        *,
        feature_key: str,
        provider: str | None,
        model: str | None,
        extra_params: dict,
        updated_by: str | None,
    ) -> LLMFeatureOverride:
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
            return row

    def delete(self, feature_key: str) -> bool:
        with self._session_factory() as session:
            result = session.execute(
                delete(LLMFeatureOverride).where(LLMFeatureOverride.feature_key == feature_key)
            )
            session.commit()
            return result.rowcount > 0
