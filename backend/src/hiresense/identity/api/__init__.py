from hiresense.identity.api.dependencies import (
    get_auth_service,
    get_current_user,
    require_admin,
    require_auth,
)
from hiresense.identity.api.routes import router

__all__ = [
    "get_auth_service",
    "get_current_user",
    "require_admin",
    "require_auth",
    "router",
]
