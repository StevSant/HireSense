from __future__ import annotations

from hiresense.admin.domain.llm_config_service import LLMConfigService
from hiresense.admin.domain.llm_factory import LLMFactory
from hiresense.admin.domain.llm_settings_service import LLMSettingsService
from hiresense.admin.domain.usage_aggregator import UsageAggregator
from hiresense.admin.domain.usage_recorder import UsageRecorder


class AdminProvider:
    def __init__(
        self,
        *,
        settings_service: LLMSettingsService,
        config_service: LLMConfigService,
        factory: LLMFactory,
        usage_aggregator: UsageAggregator,
        usage_recorder: UsageRecorder,
    ) -> None:
        self._settings_service = settings_service
        self._config_service = config_service
        self._factory = factory
        self._usage_aggregator = usage_aggregator
        self._usage_recorder = usage_recorder

    def get_settings_service(self) -> LLMSettingsService:
        return self._settings_service

    def get_config_service(self) -> LLMConfigService:
        return self._config_service

    def get_factory(self) -> LLMFactory:
        return self._factory

    def get_usage_aggregator(self) -> UsageAggregator:
        return self._usage_aggregator

    def get_usage_recorder(self) -> UsageRecorder:
        return self._usage_recorder
