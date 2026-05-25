from __future__ import annotations

from typing import Any

from sqlalchemy import select

from hiresense.admin.infrastructure.llm_settings_model import LLMSettings


class LLMSettingsRepository:
    """Single-row repository for the global LLM config."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def get(self) -> LLMSettings | None:
        with self._session_factory() as session:
            return session.scalars(select(LLMSettings).where(LLMSettings.id == 1)).first()

    def upsert(
        self,
        *,
        provider: str,
        model: str,
        api_key_encrypted: str | None,
        extra_params: dict,
        updated_by: str | None,
    ) -> LLMSettings:
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
            return row
