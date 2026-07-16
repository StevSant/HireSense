from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from hiresense.admin.api import AdminProvider
from hiresense.admin.domain import (
    APIKeyCipher,
    LLMConfigService,
    LLMSettingsService,
    UsageAggregator,
    UsageRecorder,
)
from hiresense.admin.infrastructure import (
    LLMAuditLogRepository,
    LLMFactory,
    LLMFeatureOverrideRepository,
    LLMSettingsRepository,
    LLMTestRunner,
    LLMUsageLogRepository,
)
from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.bootstrap.tracked_factory import make_tracked
from hiresense.ports import LLMPort


@dataclass(frozen=True)
class AdminBuild:
    provider: AdminProvider
    tracked: Callable[[str], LLMPort | None]


def build_admin(infra: SharedInfra) -> AdminBuild:
    s = infra.settings
    settings_repo = LLMSettingsRepository(session_factory=infra.sync_session_factory)
    override_repo = LLMFeatureOverrideRepository(session_factory=infra.sync_session_factory)
    usage_repo = LLMUsageLogRepository(session_factory=infra.sync_session_factory)
    audit_repo = LLMAuditLogRepository(session_factory=infra.sync_session_factory)
    cipher = APIKeyCipher(s.llm_settings_encryption_key)
    factory = LLMFactory()
    config_service = LLMConfigService(
        settings_repo=settings_repo,
        override_repo=override_repo,
        cipher=cipher,
        env_provider=s.llm_provider,
        env_model=s.llm_model,
        env_api_key=s.llm_api_key,
        feature_default_models={
            "match_quick_scorer": s.match_quick_model,
            "match_deep_analyzer": s.match_deep_model,
        },
        default_max_tokens=s.llm_default_max_tokens,
        classifier_max_tokens=s.llm_classifier_max_tokens,
    )
    test_runner = LLMTestRunner(factory=factory)
    settings_service = LLMSettingsService(
        settings_repo=settings_repo,
        override_repo=override_repo,
        audit_repo=audit_repo,
        cipher=cipher,
        config_service=config_service,
        factory=factory,
        test_runner=test_runner,
        env_provider=s.llm_provider,
        env_model=s.llm_model,
        env_api_key=s.llm_api_key,
    )
    usage_recorder = UsageRecorder(repo=usage_repo)
    usage_aggregator = UsageAggregator(repo=usage_repo, recent_limit=s.admin_usage_recent_limit)
    provider = AdminProvider(
        settings_service=settings_service,
        usage_aggregator=usage_aggregator,
    )
    tracked = make_tracked(
        config_service=config_service,
        factory=factory,
        recorder=usage_recorder,
        settings=s,
    )
    return AdminBuild(provider=provider, tracked=tracked)
