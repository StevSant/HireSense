from __future__ import annotations

from hiresense.admin.domain.llm_settings_service import LLMSettingsService
from hiresense.admin.domain.usage_aggregator import UsageAggregator


class AdminProvider:
    def __init__(
        self,
        *,
        settings_service: LLMSettingsService,
        usage_aggregator: UsageAggregator,
    ) -> None:
        self._settings_service = settings_service
        self._usage_aggregator = usage_aggregator

    def get_settings_service(self) -> LLMSettingsService:
        return self._settings_service

    def get_usage_aggregator(self) -> UsageAggregator:
        return self._usage_aggregator
