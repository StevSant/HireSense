from __future__ import annotations

from fastapi import Depends, Request

from hiresense.admin.api.provider import AdminProvider
from hiresense.admin.domain.llm_settings_service import LLMSettingsService
from hiresense.admin.domain.usage_aggregator import UsageAggregator
from hiresense.identity.api.dependencies import require_admin, require_admin_actor


def _get_provider(request: Request) -> AdminProvider:
    provider = getattr(request.app.state, "admin_provider", None)
    if provider is None:
        raise RuntimeError("admin_provider not configured in app.state")
    return provider


def get_llm_settings_service(
    provider: AdminProvider = Depends(_get_provider),
) -> LLMSettingsService:
    return provider.get_settings_service()


def get_usage_aggregator(
    provider: AdminProvider = Depends(_get_provider),
) -> UsageAggregator:
    return provider.get_usage_aggregator()


# Admin gate (#38): re-exported from identity so the admin routers keep
# depending on this stable name, now enforcing the token's "role" claim
# (403 for non-admin, 401 for an invalid token). `require_admin_actor` is the
# same gate but yields the admin username (token `sub`) for audit fields (#138).
__all__ = [
    "get_llm_settings_service",
    "get_usage_aggregator",
    "require_admin",
    "require_admin_actor",
]
