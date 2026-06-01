from __future__ import annotations

from opentelemetry.sdk._logs.export import ConsoleLogExporter
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SpanExporter


def build_span_exporter(endpoint: str) -> SpanExporter:
    """OTLP span exporter when an endpoint is set, else console."""
    if not endpoint:
        return ConsoleSpanExporter()
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    return OTLPSpanExporter(endpoint=endpoint, insecure=True)


def build_log_exporter(endpoint: str):
    """OTLP log exporter when an endpoint is set, else console."""
    if not endpoint:
        return ConsoleLogExporter()
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

    return OTLPLogExporter(endpoint=endpoint, insecure=True)


def build_metric_reader(endpoint: str) -> PeriodicExportingMetricReader:
    """Periodic metric reader wrapping OTLP or console metric exporter."""
    if not endpoint:
        return PeriodicExportingMetricReader(ConsoleMetricExporter())
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )

    return PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint, insecure=True))
