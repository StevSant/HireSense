from __future__ import annotations

from fastapi import Depends, Request

from hiresense.admin.api.provider import AdminProvider
from hiresense.admin.domain.llm_settings_service import LLMSettingsService
from hiresense.admin.domain.usage_aggregator import UsageAggregator
from hiresense.identity.api.dependencies import require_auth


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


# Single-user system: the only authenticated principal IS the admin.
# When proper RBAC lands, swap this for a role check; the rest of the
# admin routes already depend on this name.
require_admin = require_auth
