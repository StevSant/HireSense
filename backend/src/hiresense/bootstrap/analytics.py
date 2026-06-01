from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hiresense.analytics.api.provider import AnalyticsProvider
from hiresense.analytics.domain import (
    AnalyticsService,
    FunnelService,
    MarketIntelService,
    SalaryParser,
    SkillGapService,
    SkillNormalizer,
    TargetSalaryService,
    TtlCache,
)
from hiresense.analytics.infrastructure import CorpusAnalyticsRepository
from hiresense.bootstrap.shared_infra import SharedInfra


@dataclass(frozen=True)
class AnalyticsBuild:
    provider: AnalyticsProvider
    service: AnalyticsService


def build_analytics(infra: SharedInfra, profile_service: Any, status_history_read: Any) -> AnalyticsBuild:
    s = infra.settings
    corpus = CorpusAnalyticsRepository(session_factory=infra.sync_session_factory)
    normalizer = SkillNormalizer()
    salary_parser = SalaryParser()
    service = AnalyticsService(
        funnel=FunnelService(status_history_read),
        market=MarketIntelService(corpus, normalizer, salary_parser),
        skill_gap=SkillGapService(corpus, normalizer),
        target_salary=TargetSalaryService(
            embedding=infra.embedding,
            vector_store=infra.vector_store,
            corpus=corpus,
            salary_parser=salary_parser,
            top_k=s.analytics_target_salary_top_k,
            min_sample=s.analytics_target_salary_min_sample,
        ),
        profile_service=profile_service,
        cache=TtlCache(ttl_seconds=s.analytics_cache_ttl_seconds),
    )
    return AnalyticsBuild(provider=AnalyticsProvider(analytics_service=service), service=service)
