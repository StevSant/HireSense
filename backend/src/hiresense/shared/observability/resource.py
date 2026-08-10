from __future__ import annotations

from typing import Any

from opentelemetry.sdk.resources import Resource


def build_resource(settings: Any) -> Resource:
    """Shared OTel resource for traces, metrics, and logs."""
    return Resource.create(
        {
            "service.name": settings.otel_service_name,
            "deployment.environment": settings.deployment_environment,
        }
    )
