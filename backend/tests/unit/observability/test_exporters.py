from __future__ import annotations

from opentelemetry.sdk._logs.export import ConsoleLogExporter
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

from hiresense.observability import (
    build_log_exporter,
    build_metric_reader,
    build_span_exporter,
)


def test_console_fallback_when_endpoint_empty():
    assert isinstance(build_span_exporter(""), ConsoleSpanExporter)
    assert isinstance(build_log_exporter(""), ConsoleLogExporter)
    reader = build_metric_reader("")
    assert isinstance(reader, PeriodicExportingMetricReader)


def test_otlp_exporters_when_endpoint_set():
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    endpoint = "http://localhost:4317"
    assert isinstance(build_span_exporter(endpoint), OTLPSpanExporter)
    assert isinstance(build_log_exporter(endpoint), OTLPLogExporter)
    reader = build_metric_reader(endpoint)
    assert isinstance(reader, PeriodicExportingMetricReader)
