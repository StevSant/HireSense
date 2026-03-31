from __future__ import annotations

from fastapi import FastAPI

from hiresense.adapters.event_bus.in_memory_bus import InMemoryEventBus
from hiresense.config import Settings
from hiresense.identity.api.dependencies import get_auth_service
from hiresense.identity.api.routes import router as auth_router
from hiresense.identity.services import AuthService


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    # --- Shared infrastructure ---
    event_bus = InMemoryEventBus()

    # --- Identity module ---
    auth_service = AuthService(
        username=settings.auth_username,
        password=settings.auth_password,
        jwt_secret=settings.jwt_secret_key,
    )
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.include_router(auth_router)

    # --- Health check ---
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
