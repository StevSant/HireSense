# Observability (OpenTelemetry) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full OpenTelemetry traceability (structured logs + traces + metrics) to the HireSense backend so any request can be followed end-to-end across ingestion → matching → LLM calls.

**Architecture:** A self-contained `hiresense/observability/` module initializes the OTel SDK programmatically via one `setup_telemetry(app, settings)` call in `create_app()`. Stdlib `logging` is kept (no call-site changes) but centrally configured with a JSON formatter and a filter that injects `trace_id`/`span_id`/`request_id`. FastAPI/SQLAlchemy/httpx are auto-instrumented; four domain seams (ingestion, matching, LLM, event bus) get hand-rolled spans/metrics. Exporters target a local `grafana/otel-lgtm` container over OTLP, falling back to console exporters when no endpoint is configured.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, httpx, pydantic-settings, OpenTelemetry SDK + OTLP exporter + FastAPI/SQLAlchemy/httpx instrumentation, `uv` for tooling, pytest.

---

## Conventions for this plan

- All Python commands use the uv-trampoline workaround: `uv run python -m pytest ...` (bare `uv run pytest` is broken on this machine).
- One class/function/constant per file. Every new file must be re-exported from its package `__init__.py`.
- No hardcoded values: every tunable is a `Settings` field mirrored in `backend/.env.example`.
- Run commands from `backend/` unless stated otherwise.
- Tests live under `backend/tests/unit/observability/` (create the package) and `backend/tests/integration/`.

## File structure

```
backend/src/hiresense/observability/
  __init__.py                  # re-exports public API
  request_id_ctx.py            # request_id_var: ContextVar[str | None]
  resource.py                  # build_resource(settings)
  exporters.py                 # build_span_exporter / build_metric_reader / build_log_exporter
  json_formatter.py            # JsonLogFormatter
  trace_context_filter.py      # TraceContextFilter
  logging_config.py            # configure_logging(settings)
  tracer.py                    # get_tracer(name)
  meter.py                     # get_meter(name)
  metrics.py                   # domain instruments (lazy singleton accessor)
  instrumentation.py           # instrument_app(app)
  setup.py                     # setup_telemetry(app, settings)
  middleware/
    __init__.py                # re-exports RequestContextMiddleware
    request_context.py         # RequestContextMiddleware

backend/tests/unit/observability/
  __init__.py
  test_resource.py
  test_exporters.py
  test_json_formatter.py
  test_trace_context_filter.py
  test_request_context_middleware.py
  test_setup_telemetry_disabled.py
  test_domain_metrics.py
backend/tests/integration/
  test_telemetry_request.py
```

Files touched (existing):
- `backend/pyproject.toml` (deps)
- `backend/src/hiresense/config.py` (settings)
- `backend/.env.example` (env docs)
- `backend/src/hiresense/main.py` (wire `setup_telemetry`)
- `backend/src/hiresense/admin/domain/usage_recorder.py` (LLM metrics)
- `backend/src/hiresense/ingestion/domain/services.py` (ingestion span/metrics)
- `backend/src/hiresense/matching/domain/services.py` (matching span/metrics)
- `backend/src/hiresense/adapters/event_bus/in_memory_bus.py` (event-bus span/metrics)
- `docker-compose.yml` (otel-lgtm service)

---

## Task 1: Dependencies, config fields, and .env.example

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/src/hiresense/config.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Add dependencies via uv**

Run (from `backend/`):
```bash
uv add opentelemetry-sdk opentelemetry-api opentelemetry-exporter-otlp \
  opentelemetry-instrumentation-fastapi \
  opentelemetry-instrumentation-sqlalchemy \
  opentelemetry-instrumentation-httpx
```
Expected: `pyproject.toml` `[project.dependencies]` gains the six packages; `uv.lock` updates; no errors.

- [ ] **Step 2: Add settings fields**

In `backend/src/hiresense/config.py`, add this block after the `# Core` group (after the `cors_origins` line, before `# Auth`):

```python
    # --- Observability (OpenTelemetry) ---
    # Master switch. When False, setup_telemetry() is a no-op and the app
    # boots with plain default logging.
    otel_enabled: bool = True
    # service.name resource attribute (shows up as the service in Grafana).
    otel_service_name: str = "hiresense-backend"
    # OTLP collector endpoint. EMPTY → console/terminal exporter fallback
    # (traces/metrics/logs print to stdout, no collector needed). Set to
    # http://otel-lgtm:4317 (compose) or http://localhost:4317 (host) to ship
    # to the LGTM stack.
    otel_exporter_otlp_endpoint: str = ""
    # deployment.environment resource attribute.
    deployment_environment: str = "development"
    # Root log level for the central dictConfig.
    log_level: str = "INFO"
    # "json" for structured logs (prod/LGTM) or "console" for human-readable
    # lines (local dev).
    log_format: str = "json"
    # Parent-based trace sampling ratio in [0.0, 1.0]. 1.0 = sample everything.
    otel_traces_sampler_ratio: float = 1.0
```

- [ ] **Step 3: Mirror into .env.example**

Append to `backend/.env.example`:

```dotenv

# --- Observability (OpenTelemetry) ---
# Master switch for the telemetry stack.
OTEL_ENABLED=true
# Service name shown in Grafana/Tempo.
OTEL_SERVICE_NAME=hiresense-backend
# OTLP endpoint. Leave EMPTY for console/terminal fallback (no collector).
# Use http://otel-lgtm:4317 under docker-compose, or http://localhost:4317 on host.
OTEL_EXPORTER_OTLP_ENDPOINT=
# Environment label resource attribute.
DEPLOYMENT_ENVIRONMENT=development
# Root log level (DEBUG/INFO/WARNING/ERROR).
LOG_LEVEL=INFO
# Log output format: json (structured) or console (human-readable).
LOG_FORMAT=json
# Trace sampling ratio 0.0-1.0.
OTEL_TRACES_SAMPLER_RATIO=1.0
```

- [ ] **Step 4: Verify settings load**

Run (from `backend/`):
```bash
uv run python -c "from hiresense.config import Settings; import os; os.environ.setdefault('AUTH_USERNAME','x'); os.environ.setdefault('AUTH_PASSWORD','x'); os.environ.setdefault('JWT_SECRET_KEY','x'); os.environ.setdefault('DATABASE_URL','postgresql+asyncpg://x:x@localhost/x'); os.environ.setdefault('LLM_API_KEY','x'); s=Settings(); print(s.otel_enabled, s.otel_service_name, repr(s.otel_exporter_otlp_endpoint), s.log_format)"
```
Expected: `True hiresense-backend '' json`

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/src/hiresense/config.py backend/.env.example
git commit -m "feat(observability): add OTel deps and config"
```

---

## Task 2: request_id context variable

**Files:**
- Create: `backend/src/hiresense/observability/__init__.py`
- Create: `backend/src/hiresense/observability/request_id_ctx.py`

- [ ] **Step 1: Create the package __init__**

Create `backend/src/hiresense/observability/__init__.py`:

```python
from __future__ import annotations

from hiresense.observability.request_id_ctx import request_id_var

__all__ = ["request_id_var"]
```

- [ ] **Step 2: Create the contextvar**

Create `backend/src/hiresense/observability/request_id_ctx.py`:

```python
from __future__ import annotations

from contextvars import ContextVar

# Holds the per-request correlation id so log records can be tagged with it
# even outside the HTTP span (e.g. background tasks spawned from a request).
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
```

- [ ] **Step 3: Verify import**

Run (from `backend/`):
```bash
uv run python -c "from hiresense.observability import request_id_var; print(request_id_var.get())"
```
Expected: `None`

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/observability/__init__.py backend/src/hiresense/observability/request_id_ctx.py
git commit -m "feat(observability): add request_id contextvar"
```

---

## Task 3: Resource builder

**Files:**
- Create: `backend/src/hiresense/observability/resource.py`
- Test: `backend/tests/unit/observability/__init__.py`, `backend/tests/unit/observability/test_resource.py`
- Modify: `backend/src/hiresense/observability/__init__.py`

- [ ] **Step 1: Create test package init**

Create `backend/tests/unit/observability/__init__.py` (empty file):

```python
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/unit/observability/test_resource.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/observability/test_resource.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_resource'`

- [ ] **Step 4: Implement build_resource**

Create `backend/src/hiresense/observability/resource.py`:

```python
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
```

- [ ] **Step 5: Re-export from package __init__**

Replace `backend/src/hiresense/observability/__init__.py` with:

```python
from __future__ import annotations

from hiresense.observability.request_id_ctx import request_id_var
from hiresense.observability.resource import build_resource

__all__ = ["request_id_var", "build_resource"]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/observability/test_resource.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/src/hiresense/observability/resource.py backend/src/hiresense/observability/__init__.py backend/tests/unit/observability/__init__.py backend/tests/unit/observability/test_resource.py
git commit -m "feat(observability): add resource builder"
```

---

## Task 4: Exporter factories with console fallback

**Files:**
- Create: `backend/src/hiresense/observability/exporters.py`
- Test: `backend/tests/unit/observability/test_exporters.py`
- Modify: `backend/src/hiresense/observability/__init__.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/observability/test_exporters.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/observability/test_exporters.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_span_exporter'`

- [ ] **Step 3: Implement exporters**

Create `backend/src/hiresense/observability/exporters.py`:

```python
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
```

- [ ] **Step 4: Re-export from package __init__**

Update `backend/src/hiresense/observability/__init__.py` to add the three names:

```python
from __future__ import annotations

from hiresense.observability.exporters import (
    build_log_exporter,
    build_metric_reader,
    build_span_exporter,
)
from hiresense.observability.request_id_ctx import request_id_var
from hiresense.observability.resource import build_resource

__all__ = [
    "request_id_var",
    "build_resource",
    "build_span_exporter",
    "build_log_exporter",
    "build_metric_reader",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/observability/test_exporters.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/observability/exporters.py backend/src/hiresense/observability/__init__.py backend/tests/unit/observability/test_exporters.py
git commit -m "feat(observability): add exporter factories with console fallback"
```

---

## Task 5: JSON log formatter

**Files:**
- Create: `backend/src/hiresense/observability/json_formatter.py`
- Test: `backend/tests/unit/observability/test_json_formatter.py`
- Modify: `backend/src/hiresense/observability/__init__.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/observability/test_json_formatter.py`:

```python
from __future__ import annotations

import json
import logging

from hiresense.observability import JsonLogFormatter


def _record(**extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="hiresense.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_formatter_emits_valid_json_with_core_fields():
    formatted = JsonLogFormatter().format(_record())
    payload = json.loads(formatted)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "hiresense.test"
    assert payload["message"] == "hello world"
    assert "timestamp" in payload


def test_formatter_includes_trace_fields_when_present():
    record = _record(trace_id="abc123", span_id="def456", request_id="req-1")
    payload = json.loads(JsonLogFormatter().format(record))
    assert payload["trace_id"] == "abc123"
    assert payload["span_id"] == "def456"
    assert payload["request_id"] == "req-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/observability/test_json_formatter.py -v`
Expected: FAIL — `ImportError: cannot import name 'JsonLogFormatter'`

- [ ] **Step 3: Implement the formatter**

Create `backend/src/hiresense/observability/json_formatter.py`:

```python
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

# Attributes that LogRecord always carries; everything else added via the
# TraceContextFilter or `extra=` is surfaced into the JSON payload.
_OPTIONAL_FIELDS = ("trace_id", "span_id", "request_id")


class JsonLogFormatter(logging.Formatter):
    """Render log records as single-line JSON for structured ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _OPTIONAL_FIELDS:
            value = getattr(record, field, None)
            if value:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)
```

- [ ] **Step 4: Re-export from package __init__**

Add to `backend/src/hiresense/observability/__init__.py` imports and `__all__`:

```python
from hiresense.observability.json_formatter import JsonLogFormatter
```
and add `"JsonLogFormatter"` to `__all__`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/observability/test_json_formatter.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/observability/json_formatter.py backend/src/hiresense/observability/__init__.py backend/tests/unit/observability/test_json_formatter.py
git commit -m "feat(observability): add JSON log formatter"
```

---

## Task 6: Trace context filter

**Files:**
- Create: `backend/src/hiresense/observability/trace_context_filter.py`
- Test: `backend/tests/unit/observability/test_trace_context_filter.py`
- Modify: `backend/src/hiresense/observability/__init__.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/observability/test_trace_context_filter.py`:

```python
from __future__ import annotations

import logging

from hiresense.observability import TraceContextFilter, request_id_var


def _record() -> logging.LogRecord:
    return logging.LogRecord(
        name="hiresense.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="m",
        args=(),
        exc_info=None,
    )


def test_filter_sets_empty_fields_without_active_span():
    record = _record()
    assert TraceContextFilter().filter(record) is True
    assert record.trace_id == ""
    assert record.span_id == ""


def test_filter_injects_request_id_from_contextvar():
    token = request_id_var.set("req-xyz")
    try:
        record = _record()
        TraceContextFilter().filter(record)
        assert record.request_id == "req-xyz"
    finally:
        request_id_var.reset(token)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/observability/test_trace_context_filter.py -v`
Expected: FAIL — `ImportError: cannot import name 'TraceContextFilter'`

- [ ] **Step 3: Implement the filter**

Create `backend/src/hiresense/observability/trace_context_filter.py`:

```python
from __future__ import annotations

import logging

from opentelemetry import trace

from hiresense.observability.request_id_ctx import request_id_var


class TraceContextFilter(logging.Filter):
    """Inject trace_id/span_id (from the active span) and request_id (from the
    contextvar) onto every log record so the formatter can surface them."""

    def filter(self, record: logging.LogRecord) -> bool:
        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx and ctx.is_valid:
            record.trace_id = trace.format_trace_id(ctx.trace_id)
            record.span_id = trace.format_span_id(ctx.span_id)
        else:
            record.trace_id = ""
            record.span_id = ""
        record.request_id = request_id_var.get() or ""
        return True
```

- [ ] **Step 4: Re-export from package __init__**

Add to `backend/src/hiresense/observability/__init__.py`:

```python
from hiresense.observability.trace_context_filter import TraceContextFilter
```
and add `"TraceContextFilter"` to `__all__`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/observability/test_trace_context_filter.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/observability/trace_context_filter.py backend/src/hiresense/observability/__init__.py backend/tests/unit/observability/test_trace_context_filter.py
git commit -m "feat(observability): add trace-context log filter"
```

---

## Task 7: Central logging configuration

**Files:**
- Create: `backend/src/hiresense/observability/logging_config.py`
- Modify: `backend/src/hiresense/observability/__init__.py`

No new unit test file — `configure_logging` is exercised by the integration test in Task 17. It is a thin wiring function; we verify it imports and runs without error here.

- [ ] **Step 1: Implement configure_logging**

Create `backend/src/hiresense/observability/logging_config.py`:

```python
from __future__ import annotations

import logging
from logging.config import dictConfig
from typing import Any

from opentelemetry.sdk._logs import LoggingHandler

from hiresense.observability.trace_context_filter import TraceContextFilter


def configure_logging(settings: Any, otel_handler: LoggingHandler | None) -> None:
    """Install a root dictConfig: a stdout handler (JSON or console) plus the
    OTel LoggingHandler (when provided). Both carry the TraceContextFilter so
    every record gets trace_id/span_id/request_id."""
    if settings.log_format == "json":
        formatter = {
            "()": "hiresense.observability.json_formatter.JsonLogFormatter",
        }
    else:
        formatter = {
            "format": "%(asctime)s %(levelname)s [%(name)s] "
            "[trace=%(trace_id)s req=%(request_id)s] %(message)s",
        }

    handlers: dict[str, Any] = {
        "stdout": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "filters": ["trace_context"],
            "stream": "ext://sys.stdout",
        }
    }
    root_handlers = ["stdout"]

    config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "trace_context": {"()": "hiresense.observability.trace_context_filter.TraceContextFilter"},
        },
        "formatters": {"default": formatter},
        "handlers": handlers,
        "root": {"level": settings.log_level, "handlers": root_handlers},
    }
    dictConfig(config)

    # The OTel LoggingHandler is attached imperatively (it is an instance, not a
    # dotted path dictConfig can construct). It carries the same filter so the
    # exported log records also include request_id.
    if otel_handler is not None:
        otel_handler.addFilter(TraceContextFilter())
        otel_handler.setLevel(settings.log_level)
        logging.getLogger().addHandler(otel_handler)
```

- [ ] **Step 2: Re-export from package __init__**

Add to `backend/src/hiresense/observability/__init__.py`:

```python
from hiresense.observability.logging_config import configure_logging
```
and add `"configure_logging"` to `__all__`.

- [ ] **Step 3: Smoke test it runs**

Run (from `backend/`):
```bash
uv run python -c "
from hiresense.observability import configure_logging
import logging
class S: log_format='json'; log_level='INFO'
configure_logging(S(), None)
logging.getLogger('hiresense.smoke').info('hello %s', 'world')
"
```
Expected: one JSON line containing `"message": "hello world"` and `"level": "INFO"`.

- [ ] **Step 4: Commit**

```bash
git add backend/src/hiresense/observability/logging_config.py backend/src/hiresense/observability/__init__.py
git commit -m "feat(observability): add central logging configuration"
```

---

## Task 8: Request context middleware

**Files:**
- Create: `backend/src/hiresense/observability/middleware/__init__.py`
- Create: `backend/src/hiresense/observability/middleware/request_context.py`
- Test: `backend/tests/unit/observability/test_request_context_middleware.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/observability/test_request_context_middleware.py`:

```python
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.observability.middleware import RequestContextMiddleware
from hiresense.observability import request_id_var


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/echo")
    async def echo() -> dict[str, str]:
        return {"request_id": request_id_var.get() or ""}

    return app


def test_generates_request_id_and_echoes_header():
    client = TestClient(_app())
    resp = client.get("/echo")
    assert resp.status_code == 200
    rid = resp.headers["X-Request-ID"]
    assert rid
    assert resp.json()["request_id"] == rid


def test_honors_inbound_request_id():
    client = TestClient(_app())
    resp = client.get("/echo", headers={"X-Request-ID": "client-supplied"})
    assert resp.headers["X-Request-ID"] == "client-supplied"
    assert resp.json()["request_id"] == "client-supplied"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/observability/test_request_context_middleware.py -v`
Expected: FAIL — `ModuleNotFoundError: hiresense.observability.middleware`

- [ ] **Step 3: Implement the middleware**

Create `backend/src/hiresense/observability/middleware/request_context.py`:

```python
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from hiresense.observability.request_id_ctx import request_id_var

_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign/propagate a per-request correlation id.

    Honors an inbound X-Request-ID, otherwise generates one. Stores it in the
    request_id contextvar (so log records pick it up) and echoes it on the
    response.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(_HEADER) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[_HEADER] = request_id
        return response
```

- [ ] **Step 4: Create middleware package __init__ (re-export)**

Create `backend/src/hiresense/observability/middleware/__init__.py`:

```python
from __future__ import annotations

from hiresense.observability.middleware.request_context import RequestContextMiddleware

__all__ = ["RequestContextMiddleware"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/observability/test_request_context_middleware.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/observability/middleware/
git add backend/tests/unit/observability/test_request_context_middleware.py
git commit -m "feat(observability): add request-context middleware"
```

---

## Task 9: tracer/meter helpers and auto-instrumentation

**Files:**
- Create: `backend/src/hiresense/observability/tracer.py`
- Create: `backend/src/hiresense/observability/meter.py`
- Create: `backend/src/hiresense/observability/instrumentation.py`
- Modify: `backend/src/hiresense/observability/__init__.py`

- [ ] **Step 1: Implement tracer helper**

Create `backend/src/hiresense/observability/tracer.py`:

```python
from __future__ import annotations

from opentelemetry import trace


def get_tracer(name: str) -> trace.Tracer:
    """Module-scoped tracer. Safe to call before setup_telemetry — returns a
    no-op tracer until a TracerProvider is installed."""
    return trace.get_tracer(name)
```

- [ ] **Step 2: Implement meter helper**

Create `backend/src/hiresense/observability/meter.py`:

```python
from __future__ import annotations

from opentelemetry import metrics


def get_meter(name: str) -> metrics.Meter:
    """Module-scoped meter. Safe to call before setup_telemetry — returns a
    no-op meter until a MeterProvider is installed."""
    return metrics.get_meter(name)
```

- [ ] **Step 3: Implement auto-instrumentation**

Create `backend/src/hiresense/observability/instrumentation.py`:

```python
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
```

- [ ] **Step 4: Re-export tracer/meter from package __init__**

Add to `backend/src/hiresense/observability/__init__.py`:

```python
from hiresense.observability.tracer import get_tracer
from hiresense.observability.meter import get_meter
from hiresense.observability.instrumentation import instrument_app
```
and add `"get_tracer"`, `"get_meter"`, `"instrument_app"` to `__all__`.

- [ ] **Step 5: Verify imports**

Run (from `backend/`):
```bash
uv run python -c "from hiresense.observability import get_tracer, get_meter, instrument_app; print(get_tracer('x'), get_meter('x'))"
```
Expected: prints two objects (no-op tracer/meter), no errors.

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/observability/tracer.py backend/src/hiresense/observability/meter.py backend/src/hiresense/observability/instrumentation.py backend/src/hiresense/observability/__init__.py
git commit -m "feat(observability): add tracer/meter helpers and auto-instrumentation"
```

---

## Task 10: setup_telemetry and wiring into create_app

**Files:**
- Create: `backend/src/hiresense/observability/setup.py`
- Modify: `backend/src/hiresense/observability/__init__.py`
- Modify: `backend/src/hiresense/main.py`
- Test: `backend/tests/unit/observability/test_setup_telemetry_disabled.py`

- [ ] **Step 1: Write the failing test (disabled no-op path)**

Create `backend/tests/unit/observability/test_setup_telemetry_disabled.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/observability/test_setup_telemetry_disabled.py -v`
Expected: FAIL — `ImportError: cannot import name 'setup_telemetry'`

- [ ] **Step 3: Implement setup_telemetry**

Create `backend/src/hiresense/observability/setup.py`:

```python
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
    resource = build_resource(settings)

    # Traces
    try:
        provider = TracerProvider(
            resource=resource,
            sampler=ParentBasedTraceIdRatio(settings.otel_traces_sampler_ratio),
        )
        provider.add_span_processor(BatchSpanProcessor(build_span_exporter(endpoint)))
        trace.set_tracer_provider(provider)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Tracer provider setup failed")

    # Metrics
    try:
        meter_provider = MeterProvider(
            resource=resource, metric_readers=[build_metric_reader(endpoint)]
        )
        metrics.set_meter_provider(meter_provider)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Meter provider setup failed")

    # Logs (OTel) + central stdlib logging
    otel_handler: LoggingHandler | None = None
    try:
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(build_log_exporter(endpoint))
        )
        otel_handler = LoggingHandler(
            level=settings.log_level, logger_provider=logger_provider
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("Logger provider setup failed")
    configure_logging(settings, otel_handler)

    # Middleware + auto-instrumentation
    app.add_middleware(RequestContextMiddleware)
    instrument_app(app)

    logger.info(
        "Telemetry initialized (endpoint=%s, fallback=%s)",
        endpoint or "<console>",
        not endpoint,
    )
```

- [ ] **Step 4: Re-export from package __init__**

Add to `backend/src/hiresense/observability/__init__.py`:

```python
from hiresense.observability.setup import setup_telemetry
```
and add `"setup_telemetry"` to `__all__`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/observability/test_setup_telemetry_disabled.py -v`
Expected: PASS

- [ ] **Step 6: Wire into create_app**

In `backend/src/hiresense/main.py`, add the import near the other imports:

```python
from hiresense.observability import setup_telemetry
```

Then insert the call immediately after `app.state.settings = settings` (line 60) and BEFORE `infra = build_shared_infra(...)` (line 62), so SQLAlchemy instrumentation patches engine creation before the engine is built:

```python
    app.state.settings = settings

    # Initialize observability (traces/metrics/logs) before any engine/client
    # is built so auto-instrumentation can hook them. No-op when disabled.
    setup_telemetry(app, settings)

    infra = build_shared_infra(settings, http_client)
```

- [ ] **Step 7: Verify the app still builds**

Run (from `backend/`), with OTLP unset so the console fallback path runs:
```bash
uv run python -c "
import os
os.environ['OTEL_EXPORTER_OTLP_ENDPOINT']=''
from hiresense.main import create_app
app = create_app()
print('app built:', app.title)
"
```
Expected: prints `app built: HireSense` and a telemetry-initialized log line; no exceptions.

- [ ] **Step 8: Commit**

```bash
git add backend/src/hiresense/observability/setup.py backend/src/hiresense/observability/__init__.py backend/src/hiresense/main.py backend/tests/unit/observability/test_setup_telemetry_disabled.py
git commit -m "feat(observability): add setup_telemetry and wire into app"
```

---

## Task 11: Domain metrics module

**Files:**
- Create: `backend/src/hiresense/observability/metrics.py`
- Test: `backend/tests/unit/observability/test_domain_metrics.py`
- Modify: `backend/src/hiresense/observability/__init__.py`

This module exposes a lazily-created singleton holding the domain instruments, so importing it never forces a MeterProvider at module-load time.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/observability/test_domain_metrics.py`:

```python
from __future__ import annotations

from hiresense.observability import get_domain_metrics


def test_domain_metrics_singleton_exposes_instruments():
    m1 = get_domain_metrics()
    m2 = get_domain_metrics()
    assert m1 is m2  # singleton
    # Instruments exist and recording does not raise (no-op meter is fine).
    m1.jobs_fetched_total.add(3, {"source": "remotive"})
    m1.jobs_scored_total.add(2, {"source": "remotive"})
    m1.ingestion_run_duration_ms.record(120.5, {"source": "remotive"})
    m1.matches_completed_total.add(1)
    m1.match_score.record(0.82)
    m1.llm_tokens_total.add(50, {"type": "input"})
    m1.llm_cost_usd_total.add(0.001)
    m1.llm_call_duration_ms.record(900.0, {"model": "claude-haiku-4-5"})
    m1.llm_errors_total.add(0)
    m1.events_published_total.add(1, {"type": "jobs_ingested"})
    m1.event_handler_errors_total.add(0, {"type": "jobs_ingested"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/unit/observability/test_domain_metrics.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_domain_metrics'`

- [ ] **Step 3: Implement domain metrics**

Create `backend/src/hiresense/observability/metrics.py`:

```python
from __future__ import annotations

from hiresense.observability.meter import get_meter


class DomainMetrics:
    """Holds the hand-rolled business metric instruments. Created lazily so
    import never forces a MeterProvider."""

    def __init__(self) -> None:
        meter = get_meter("hiresense.domain")

        self.jobs_fetched_total = meter.create_counter(
            "hiresense.jobs_fetched_total", unit="1",
            description="Jobs fetched per ingestion source",
        )
        self.jobs_scored_total = meter.create_counter(
            "hiresense.jobs_scored_total", unit="1",
            description="Jobs scored per ingestion source",
        )
        self.ingestion_run_duration_ms = meter.create_histogram(
            "hiresense.ingestion_run_duration_ms", unit="ms",
            description="Wall-clock duration of an ingestion run",
        )
        self.matches_completed_total = meter.create_counter(
            "hiresense.matches_completed_total", unit="1",
            description="Match evaluations completed",
        )
        self.match_score = meter.create_histogram(
            "hiresense.match_score", unit="1",
            description="Distribution of computed match scores",
        )
        self.llm_tokens_total = meter.create_counter(
            "hiresense.llm_tokens_total", unit="1",
            description="LLM tokens consumed (type=input|output)",
        )
        self.llm_cost_usd_total = meter.create_counter(
            "hiresense.llm_cost_usd_total", unit="USD",
            description="Estimated LLM spend",
        )
        self.llm_call_duration_ms = meter.create_histogram(
            "hiresense.llm_call_duration_ms", unit="ms",
            description="LLM call latency",
        )
        self.llm_errors_total = meter.create_counter(
            "hiresense.llm_errors_total", unit="1",
            description="Failed LLM calls",
        )
        self.events_published_total = meter.create_counter(
            "hiresense.events_published_total", unit="1",
            description="Domain events published",
        )
        self.event_handler_errors_total = meter.create_counter(
            "hiresense.event_handler_errors_total", unit="1",
            description="Domain event handler failures",
        )


_INSTANCE: DomainMetrics | None = None


def get_domain_metrics() -> DomainMetrics:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = DomainMetrics()
    return _INSTANCE
```

- [ ] **Step 4: Re-export from package __init__**

Add to `backend/src/hiresense/observability/__init__.py`:

```python
from hiresense.observability.metrics import DomainMetrics, get_domain_metrics
```
and add `"DomainMetrics"`, `"get_domain_metrics"` to `__all__`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run python -m pytest tests/unit/observability/test_domain_metrics.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/hiresense/observability/metrics.py backend/src/hiresense/observability/__init__.py backend/tests/unit/observability/test_domain_metrics.py
git commit -m "feat(observability): add domain metric instruments"
```

---

## Task 12: LLM metrics in UsageRecorder

**Files:**
- Modify: `backend/src/hiresense/admin/domain/usage_recorder.py`

The recorder is the single chokepoint that already receives tokens/cost/latency/success per LLM call — record metrics here. No span here (the recorder runs off the hot path); the LLM span comes from httpx auto-instrumentation around the actual HTTP call.

- [ ] **Step 1: Add metrics recording to `record`**

In `backend/src/hiresense/admin/domain/usage_recorder.py`, add the import at the top (after the existing imports):

```python
from hiresense.observability import get_domain_metrics
```

Then, inside `record(...)`, at the very start of the method body (before the `async def _persist()` definition), add:

```python
        try:
            m = get_domain_metrics()
            m.llm_tokens_total.add(input_tokens, {"type": "input", "model": model})
            m.llm_tokens_total.add(output_tokens, {"type": "output", "model": model})
            m.llm_cost_usd_total.add(cost_usd, {"model": model, "feature": feature_key})
            m.llm_call_duration_ms.record(latency_ms, {"model": model})
            if not success:
                m.llm_errors_total.add(1, {"model": model, "feature": feature_key})
        except Exception:  # pragma: no cover - telemetry must never break recording
            logger.debug("LLM metric recording failed", exc_info=True)
```

- [ ] **Step 2: Run the existing usage tests to confirm no regression**

Run: `uv run python -m pytest tests/unit/admin -v`
Expected: PASS (all existing admin tests still pass).

- [ ] **Step 3: Commit**

```bash
git add backend/src/hiresense/admin/domain/usage_recorder.py
git commit -m "feat(observability): record LLM metrics in UsageRecorder"
```

---

## Task 13: Ingestion run span and metrics

**Files:**
- Modify: `backend/src/hiresense/ingestion/domain/services.py`

The `IngestionOrchestrator.run(...)` method (starts at line 50) is the seam. Wrap its body in a span and record fetched/scored counts + duration. We instrument without changing the method's return contract.

- [ ] **Step 1: Read the run() method to find the count/return points**

Run: `uv run python -c "import inspect, hiresense.ingestion.domain.services as s; print(inspect.getsource(s.IngestionOrchestrator.run))"`
Expected: prints the method. Note the local variable(s) holding fetched jobs and the scored result so the metric `.add()` calls use real numbers. If a single total isn't readily available, count `len(...)` on the relevant collection just before `return`.

- [ ] **Step 2: Add imports**

At the top of `backend/src/hiresense/ingestion/domain/services.py` (the file already has `import logging`), add:

```python
import time

from opentelemetry import trace

from hiresense.observability import get_domain_metrics, get_tracer

_tracer = get_tracer("hiresense.ingestion")
```

- [ ] **Step 3: Wrap run() in a span + metrics**

Restructure the body of `async def run(self, ...)` so its existing logic executes inside a span context manager, and emit metrics around it. Concretely, wrap the existing body like this (keep the existing logic verbatim inside the `with` block; only the span/metrics lines and the timing are added):

```python
    async def run(self, ...):  # keep the existing signature
        metrics = get_domain_metrics()
        started = time.perf_counter()
        with _tracer.start_as_current_span("ingestion.run") as span:
            try:
                # <<< existing run() body goes here, unchanged >>>
                # Before each existing `return result`, add (using the real
                # fetched/scored locals or len() of the relevant collection):
                #     span.set_attribute("ingestion.jobs_fetched", fetched_count)
                #     span.set_attribute("ingestion.jobs_scored", scored_count)
                #     metrics.jobs_fetched_total.add(fetched_count)
                #     metrics.jobs_scored_total.add(scored_count)
                #     metrics.ingestion_run_duration_ms.record(
                #         (time.perf_counter() - started) * 1000.0
                #     )
                #     return result
                ...
            except Exception:
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                raise
```

If `run()` iterates per-source, set the `{"source": <name>}` attribute on the `.add()`/`.record()` calls; otherwise emit them once with no labels. Preserve all existing behavior and the return value exactly.

- [ ] **Step 4: Run ingestion tests**

Run: `uv run python -m pytest tests/unit/ingestion -v`
Expected: PASS (existing ingestion behavior unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/ingestion/domain/services.py
git commit -m "feat(observability): add ingestion run span and metrics"
```

---

## Task 14: Matching span and metrics

**Files:**
- Modify: `backend/src/hiresense/matching/domain/services.py`

`MatchingOrchestrator.evaluate(...)` (line 50) returns an `EvaluationResult`. Wrap it in a span and record completion + score histogram.

- [ ] **Step 1: Add imports**

At the top of `backend/src/hiresense/matching/domain/services.py` (already has `import logging`), add:

```python
from opentelemetry import trace

from hiresense.observability import get_domain_metrics, get_tracer

_tracer = get_tracer("hiresense.matching")
```

- [ ] **Step 2: Wrap evaluate() in a span + metrics**

Restructure `async def evaluate(self, job, profile=None, dimension_scorers=None) -> EvaluationResult:` so the existing body runs inside a span, and record metrics just before returning. Keep all existing logic; add only the span/metrics:

```python
    async def evaluate(self, job, profile=None, dimension_scorers=None) -> EvaluationResult:
        metrics = get_domain_metrics()
        with _tracer.start_as_current_span("matching.score") as span:
            try:
                # <<< existing evaluate() body, unchanged, producing `result` >>>
                ...
                metrics.matches_completed_total.add(1)
                # Use the result's overall score field. Inspect EvaluationResult
                # for the correct attribute (e.g. result.total_score or
                # result.score); record it normalized to 0..1 if it is a 0..100
                # percentage.
                score_value = getattr(result, "total_score", None)
                if score_value is None:
                    score_value = getattr(result, "score", 0)
                span.set_attribute("matching.score", float(score_value))
                metrics.match_score.record(float(score_value))
                return result
            except Exception:
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                raise
```

- [ ] **Step 3: Confirm the score attribute name**

Run: `uv run python -c "import inspect, hiresense.matching.domain.services as s; print(inspect.getsource(s.EvaluationResult))"`
Expected: prints the model. Adjust the `getattr` in Step 2 to the real overall-score field name; if it is a 0–100 percentage, divide by 100 before `record(...)` so the histogram is in 0–1.

- [ ] **Step 4: Run matching tests**

Run: `uv run python -m pytest tests/unit/matching -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/matching/domain/services.py
git commit -m "feat(observability): add matching span and metrics"
```

---

## Task 15: Event-bus span and metrics

**Files:**
- Modify: `backend/src/hiresense/adapters/event_bus/in_memory_bus.py`

- [ ] **Step 1: Add imports**

At the top of `backend/src/hiresense/adapters/event_bus/in_memory_bus.py` (already has `import logging`), add:

```python
from opentelemetry import trace

from hiresense.observability import get_domain_metrics, get_tracer

_tracer = get_tracer("hiresense.events")
```

- [ ] **Step 2: Instrument publish()**

Replace the existing `publish` method with:

```python
    async def publish(self, event: DomainEvent) -> None:
        metrics = get_domain_metrics()
        metrics.events_published_total.add(1, {"type": event.event_type})
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            asyncio.create_task(self._safe_invoke(handler, event))
```

- [ ] **Step 3: Instrument _safe_invoke()**

Replace the existing `_safe_invoke` method with:

```python
    async def _safe_invoke(
        self,
        handler: Callable[[DomainEvent], Awaitable[None]],
        event: DomainEvent,
    ) -> None:
        with _tracer.start_as_current_span(
            "event.dispatch", attributes={"event.type": event.event_type}
        ) as span:
            try:
                await handler(event)
            except Exception:
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                get_domain_metrics().event_handler_errors_total.add(
                    1, {"type": event.event_type}
                )
                logger.exception("Event handler failed for %s", event.event_type)
```

- [ ] **Step 4: Run the full unit suite**

Run: `uv run python -m pytest tests/unit -q`
Expected: PASS (no regressions across modules).

- [ ] **Step 5: Commit**

```bash
git add backend/src/hiresense/adapters/event_bus/in_memory_bus.py
git commit -m "feat(observability): add event-bus span and metrics"
```

---

## Task 16: docker-compose otel-lgtm service

**Files:**
- Modify: `docker-compose.yml`
- Modify: `backend/.env.example` (note the compose endpoint)

- [ ] **Step 1: Add the otel-lgtm service**

In `docker-compose.yml`, add this service under `services:` (sibling of `db`/`app`/`frontend`):

```yaml
  otel-lgtm:
    image: grafana/otel-lgtm
    ports:
      - "3000:3000"   # Grafana UI
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
    volumes:
      - lgtm:/data
```

- [ ] **Step 2: Add the volume and depends_on**

In the top-level `volumes:` block, add `lgtm:` alongside `pgdata:`:

```yaml
volumes:
  pgdata:
  lgtm:
```

In the `app` service, add `otel-lgtm` to `depends_on` (not health-gated — telemetry is non-critical):

```yaml
    depends_on:
      db:
        condition: service_healthy
      otel-lgtm:
        condition: service_started
```

- [ ] **Step 3: Document the compose endpoint**

In `backend/.env.example`, update the OTLP line's comment to make the compose value explicit (the value stays empty by default for host/console dev):

```dotenv
# OTLP endpoint. Leave EMPTY for console/terminal fallback (no collector).
# Under docker-compose set: OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-lgtm:4317
OTEL_EXPORTER_OTLP_ENDPOINT=
```

- [ ] **Step 4: Validate compose file**

Run (from repo root): `docker compose config -q`
Expected: no output, exit 0 (compose file is valid). If Docker is not available, skip and note it.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml backend/.env.example
git commit -m "feat(observability): add grafana/otel-lgtm compose service"
```

---

## Task 17: Integration test — span ↔ log correlation

**Files:**
- Create: `backend/tests/integration/test_telemetry_request.py`

This verifies the end-to-end wiring: a request produces a span carrying the `request_id`, and a log emitted in-handler carries the matching `trace_id`. Uses OTel's `InMemorySpanExporter` so no collector is needed.

- [ ] **Step 1: Write the test**

Create `backend/tests/integration/test_telemetry_request.py`:

```python
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
```

- [ ] **Step 2: Run the integration test**

Run: `uv run python -m pytest tests/integration/test_telemetry_request.py -v`
Expected: PASS.

- [ ] **Step 3: Run the whole suite once**

Run: `uv run python -m pytest -q`
Expected: PASS (all unit + integration tests green).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/integration/test_telemetry_request.py
git commit -m "test(observability): add span/log correlation integration test"
```

---

## Final verification

- [ ] **Run the full suite:** `uv run python -m pytest -q` → all green.
- [ ] **Console fallback boot:** build the app with `OTEL_EXPORTER_OTLP_ENDPOINT` empty and confirm a `Telemetry initialized (endpoint=<console>, fallback=True)` log line and no exceptions.
- [ ] **LGTM smoke (optional, needs Docker):** `docker compose up -d otel-lgtm`, set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`, run the app, hit `/health` a few times, open Grafana at `http://localhost:3000` and confirm traces appear in Tempo and the `hiresense.*` metrics in the metrics explorer.
- [ ] **lint/format if the repo uses ruff:** `uv run python -m ruff check src/hiresense/observability` → clean.
