from __future__ import annotations

import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def instrument_app(app: FastAPI) -> None:
    """Auto-instrument FastAPI, SQLAlchemy, and httpx. Each step is guarded so a
    failure in one never blocks the others or app boot."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception:  # pragma: no cover - defensive
        logger.exception("FastAPI instrumentation failed")

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        # No engine arg → patches engine creation, so engines built later in
        # build_shared_infra are traced. setup_telemetry must run before that.
        SQLAlchemyInstrumentor().instrument(enable_commenter=True)
    except Exception:  # pragma: no cover - defensive
        logger.exception("SQLAlchemy instrumentation failed")

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception:  # pragma: no cover - defensive
        logger.exception("httpx instrumentation failed")
