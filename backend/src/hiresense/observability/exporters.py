from __future__ import annotations

from opentelemetry.sdk._logs.export import ConsoleLogExporter, LogExporter
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SpanExporter


def build_span_exporter(endpoint: str, insecure: bool = True) -> SpanExporter:
    """OTLP span exporter when an endpoint is set, else console."""
    if not endpoint:
        return ConsoleSpanExporter()
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    return OTLPSpanExporter(endpoint=endpoint, insecure=insecure)


def build_log_exporter(endpoint: str, insecure: bool = True) -> LogExporter:
    """OTLP log exporter when an endpoint is set, else console."""
    if not endpoint:
        return ConsoleLogExporter()
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

    return OTLPLogExporter(endpoint=endpoint, insecure=insecure)


def build_metric_reader(
    endpoint: str, insecure: bool = True
) -> PeriodicExportingMetricReader:
    """Periodic metric reader wrapping OTLP or console metric exporter."""
    if not endpoint:
        return PeriodicExportingMetricReader(ConsoleMetricExporter())
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )

    return PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=insecure)
    )
