from __future__ import annotations

from hiresense.observability import build_resource


class _FakeSettings:
    otel_service_name = "hiresense-backend"
    deployment_environment = "test-env"


def test_build_resource_sets_service_and_environment():
    resource = build_resource(_FakeSettings())
    attrs = resource.attributes
    assert attrs["service.name"] == "hiresense-backend"
    assert attrs["deployment.environment"] == "test-env"
