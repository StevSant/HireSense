from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from hiresense.observability import (
    TraceContextFilter,
    get_tracer,
    request_id_var,
)
from hiresense.observability.middleware import RequestContextMiddleware


def _build_app_with_inmemory_tracing():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    captured: dict[str, object] = {}

    @app.get("/work")
    async def work() -> dict[str, str]:
        tracer = get_tracer("hiresense.test")
        with tracer.start_as_current_span("test.work"):
            record = logging.LogRecord(
                "hiresense.test", logging.INFO, __file__, 1, "doing work", (), None
            )
            TraceContextFilter().filter(record)
            captured["trace_id"] = record.trace_id
            captured["request_id"] = record.request_id
            captured["span_request_id"] = request_id_var.get()
        return {"ok": "1"}

    return app, exporter, captured


def test_request_produces_correlated_span_and_log():
    app, exporter, captured = _build_app_with_inmemory_tracing()
    client = TestClient(app)
    resp = client.get("/work", headers={"X-Request-ID": "req-123"})
    assert resp.status_code == 200

    # A span was exported for the in-handler work.
    spans = exporter.get_finished_spans()
    assert any(s.name == "test.work" for s in spans)

    # The log record captured a real trace id and the request id.
    assert captured["trace_id"]  # non-empty hex trace id
    assert captured["request_id"] == "req-123"
    assert captured["span_request_id"] == "req-123"
