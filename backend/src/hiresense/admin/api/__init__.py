from fastapi import APIRouter

from hiresense.admin.api.dependencies import (
    get_llm_settings_service,
    get_usage_aggregator,
    require_admin,
)
from hiresense.admin.api.provider import AdminProvider
from hiresense.admin.api.routes_llm_settings import router as _llm_settings_router
from hiresense.admin.api.routes_usage import router as _usage_router

router = APIRouter()
router.include_router(_llm_settings_router)
router.include_router(_usage_router)

__all__ = [
    "AdminProvider",
    "get_llm_settings_service",
    "get_usage_aggregator",
    "require_admin",
    "router",
]
