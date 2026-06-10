from __future__ import annotations

from sqlalchemy import select

from hiresense.admin.domain import LLMSettingsRecord
from hiresense.admin.infrastructure.llm_settings_model import LLMSettings
from hiresense.infrastructure import SqlRepository


def _to_domain(row: LLMSettings) -> LLMSettingsRecord:
    return LLMSettingsRecord(
        provider=row.provider,
        model=row.model,
        api_key_encrypted=row.api_key_encrypted,
        extra_params=dict(row.extra_params or {}),
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


class LLMSettingsRepository(SqlRepository):
    """Single-row repository for the global LLM config."""

    def get(self) -> LLMSettingsRecord | None:
        return self._select_one(select(LLMSettings).where(LLMSettings.id == 1), _to_domain)

    def upsert(
        self,
        *,
        provider: str,
        model: str,
        api_key_encrypted: str | None,
        extra_params: dict,
        updated_by: str | None,
    ) -> LLMSettingsRecord:
        with self._session_factory() as session:
            row = session.scalars(select(LLMSettings).where(LLMSettings.id == 1)).first()
            if row is None:
                row = LLMSettings(
                    id=1,
                    provider=provider,
                    model=model,
                    api_key_encrypted=api_key_encrypted,
                    extra_params=extra_params,
                    updated_by=updated_by,
                )
                session.add(row)
            else:
                row.provider = provider
                row.model = model
                # api_key_encrypted=None means "leave existing key untouched".
                if api_key_encrypted is not None:
                    row.api_key_encrypted = api_key_encrypted
                row.extra_params = extra_params
                row.updated_by = updated_by
            session.commit()
            session.refresh(row)
            return _to_domain(row)
