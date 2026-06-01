from __future__ import annotations

from fastapi import FastAPI

from hiresense.observability import setup_telemetry


class _Settings:
    otel_enabled = False
    otel_service_name = "hiresense-backend"
    deployment_environment = "test"
    otel_exporter_otlp_endpoint = ""
    log_level = "INFO"
    log_format = "json"
    otel_traces_sampler_ratio = 1.0


def test_setup_telemetry_disabled_is_noop():
    app = FastAPI()
    # Must not raise and must return without installing instrumentation.
    setup_telemetry(app, _Settings())
