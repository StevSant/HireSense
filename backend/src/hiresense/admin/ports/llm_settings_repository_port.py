from __future__ import annotations

from typing import Protocol

from hiresense.admin.infrastructure import LLMSettings


class LLMSettingsRepositoryPort(Protocol):
    """Single-row store for the global LLM config."""

    def get(self) -> LLMSettings | None: ...

    def upsert(
        self,
        *,
        provider: str,
        model: str,
        api_key_encrypted: str | None,
        extra_params: dict,
        updated_by: str | None,
    ) -> LLMSettings: ...
