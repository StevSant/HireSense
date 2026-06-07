from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from hiresense.admin.domain import LLMFeatureOverrideRecord


class LLMFeatureOverrideRepositoryPort(Protocol):
    """Per-feature LLM config overrides."""

    def list(self) -> list[LLMFeatureOverrideRecord]: ...

    def get(self, feature_key: str) -> LLMFeatureOverrideRecord | None: ...

    def upsert(
        self,
        *,
        feature_key: str,
        provider: str | None,
        model: str | None,
        extra_params: dict,
        updated_by: str | None,
    ) -> LLMFeatureOverrideRecord: ...

    def delete(self, feature_key: str) -> bool: ...
