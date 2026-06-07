from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from hiresense.admin.domain import LLMSettingsRecord


class LLMSettingsRepositoryPort(Protocol):
    """Single-row store for the global LLM config."""

    def get(self) -> LLMSettingsRecord | None: ...

    def upsert(
        self,
        *,
        provider: str,
        model: str,
        api_key_encrypted: str | None,
        extra_params: dict,
        updated_by: str | None,
    ) -> LLMSettingsRecord: ...
