from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

from hiresense.observability.exporters import (
    build_log_exporter,
    build_metric_reader,
    build_span_exporter,
)
from hiresense.observability.instrumentation import instrument_app
from hiresense.observability.logging_config import configure_logging
from hiresense.observability.middleware import RequestContextMiddleware
from hiresense.observability.resource import build_resource

logger = logging.getLogger(__name__)


def setup_telemetry(app: FastAPI, settings: Any) -> None:
    """Initialize the OTel SDK (traces, metrics, logs), central logging, the
    request-context middleware, and auto-instrumentation. No-op when disabled.
    Every step is guarded so telemetry never blocks app boot."""
    if not settings.otel_enabled:
        # Still give the app readable default logging.
        try:
            configure_logging(settings, None)
        except Exception:  # pragma: no cover - defensive
            logging.basicConfig(level=settings.log_level)
        return

    endpoint = settings.otel_exporter_otlp_endpoint
    insecure = settings.otel_exporter_insecure
    resource = build_resource(settings)

    # Successfully-created providers, stored on app.state so the lifespan can
    # flush/shut them down cleanly on app teardown.
    providers: list[Any] = []

    # Traces
    try:
        provider = TracerProvider(
            resource=resource,
            sampler=ParentBasedTraceIdRatio(settings.otel_traces_sampler_ratio),
        )
        provider.add_span_processor(BatchSpanProcessor(build_span_exporter(endpoint, insecure)))
        trace.set_tracer_provider(provider)
        providers.append(provider)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Tracer provider setup failed")

    # Metrics
    try:
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[build_metric_reader(endpoint, insecure)],
        )
        metrics.set_meter_provider(meter_provider)
        providers.append(meter_provider)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Meter provider setup failed")

    # Logs (OTel) + central stdlib logging
    otel_handler: LoggingHandler | None = None
    try:
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(build_log_exporter(endpoint, insecure))
        )
        otel_handler = LoggingHandler(level=settings.log_level, logger_provider=logger_provider)
        providers.append(logger_provider)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Logger provider setup failed")
    configure_logging(settings, otel_handler)

    app.state.otel_providers = providers

    # Middleware + auto-instrumentation
    app.add_middleware(RequestContextMiddleware)
    instrument_app(app)

    logger.info(
        "Telemetry initialized (endpoint=%s, fallback=%s)",
        endpoint or "<console>",
        not endpoint,
    )
