# Observability & Traceability — OpenTelemetry Design

**Date:** 2026-05-31
**Status:** Approved (design)
**Scope:** Backend (`backend/src/hiresense`) + root `docker-compose.yml`

## Problem

The backend already calls `logging.getLogger(__name__)` in ~25 modules, but
**nothing configures the root logger** — there are no handlers, no formatter, no
level policy. In practice logs are unstructured text at the default level, with
no way to correlate lines belonging to one request or one ingestion run. There
is no tracing and no metrics. We cannot answer "what is happening in the system"
or "why was this request slow / why did this match fail" without guesswork.

## Goal

A full OpenTelemetry stack — **structured logs + distributed traces + metrics** —
that lets us follow any request end-to-end across `ingestion → matching → LLM
calls`, with all three signals sharing one trace context so a log line links to
its trace, which links to its DB and outbound-HTTP spans.

## Non-goals

- Frontend (Angular) instrumentation — backend only for this iteration.
- Alerting / SLOs / dashboards-as-code — Grafana ships with datasources wired;
  building saved dashboards is a later, separate effort.
- Migrating away from stdlib `logging` (see Decision 1).

## Key decisions

1. **Logging stays on stdlib `logging`.** We add one central
   `configure_logging()` that installs a `dictConfig` with a JSON formatter, a
   filter injecting `trace_id`/`span_id`, and an OTel `LoggingHandler` that ships
   logs via OTLP. The ~25 existing `logger.*` call sites are **not modified** —
   they automatically become structured and trace-correlated. Rejected:
   migrating to `structlog` (touches every call site, second idiom) and
   OTel-log-auto-instrumentation-only (logs stay unstructured).
2. **Local Grafana LGTM** via the single `grafana/otel-lgtm` container (bundles
   OTel Collector + Loki + Tempo + Prometheus + Grafana).
3. **Auto-instrumentation + key domain spans/metrics** — not exhaustive manual
   instrumentation. Auto for FastAPI/SQLAlchemy/httpx; hand-rolled spans+metrics
   only at the high-signal seams (ingestion, matching, LLM, event bus).
4. **Console/terminal exporter fallback.** When
   `otel_exporter_otlp_endpoint` is empty (no collector running), the SDK exports
   traces/metrics/logs to the console so local dev works with zero infra. A real
   OTLP endpoint switches to the LGTM backend.
5. **SDK initialized programmatically** in `setup.py` (not the
   `opentelemetry-instrument` CLI wrapper) so behavior is identical under uvicorn
   reload, tests, and the console fallback.
6. **Telemetry never breaks the app.** Each instrumentation step is guarded;
   exporter failures are swallowed by the SDK batch processors; the console
   fallback guarantees boot even with no collector.

## Architecture

A new self-contained module `hiresense/observability/` owns all telemetry.
`main.create_app()` calls `setup_telemetry(app, settings)` once, early.

```
backend/src/hiresense/observability/
  __init__.py              # re-exports the public API (package-reexport rule)
  setup.py                 # setup_telemetry(app, settings) — orchestrates all of the below
  resource.py              # build_resource(settings) -> Resource (service.name, version, deployment.environment)
  exporters.py             # OTLP-or-console exporter factories (the fallback lives here)
  logging_config.py        # configure_logging(settings) — dictConfig + handlers + OTel LoggingHandler
  json_formatter.py        # JsonLogFormatter (one class)
  trace_context_filter.py  # TraceContextFilter — injects trace_id/span_id/request_id into records
  instrumentation.py       # instrument_app(app, engine) — FastAPI / SQLAlchemy / httpx
  tracer.py                # get_tracer(name) helper
  meter.py                 # get_meter(name) helper
  metrics.py               # domain instrument definitions (counters / histograms)
  middleware/
    __init__.py            # re-exports RequestContextMiddleware
    request_context.py     # RequestContextMiddleware — request_id / correlation_id
```

Per the one-definition-per-file rule, each class/function lives in its own file;
`observability/__init__.py` re-exports `setup_telemetry`, `get_tracer`,
`get_meter`, the metric instruments, and `RequestContextMiddleware`.

### `setup_telemetry(app, settings)` responsibilities, in order

1. Build the shared `Resource` (`resource.py`).
2. Configure the `TracerProvider` with a `BatchSpanProcessor` wired to the span
   exporter from `exporters.py` (OTLP or console).
3. Configure the `MeterProvider` with a `PeriodicExportingMetricReader` + metric
   exporter (OTLP or console).
4. Configure the `LoggerProvider` (OTel logs) + console/OTLP log exporter, then
   call `configure_logging(settings)` to install the stdlib `dictConfig` that
   attaches the OTel `LoggingHandler`, the `JsonLogFormatter`, and the
   `TraceContextFilter`.
5. Add `RequestContextMiddleware` to the app.
6. Call `instrument_app(app, engine)` — FastAPI/SQLAlchemy/httpx auto-instr.

Each step wrapped so a failure logs a warning and continues.

## Data flow

```
HTTP request
  → RequestContextMiddleware  (assign request_id; honor inbound X-Request-ID / traceparent;
                               set response X-Request-ID; stash request_id in contextvar)
  → FastAPI auto-instrumentation opens the server span
      → route handlers  (existing logger.* lines now carry trace_id/span_id/request_id)
      → SQLAlchemy spans (every query) + httpx spans (every outbound source/LLM call)
      → key domain spans + metrics (table below)
  → BatchSpanProcessor / PeriodicMetricReader / LoggingHandler
      → OTLP exporter → otel-lgtm    (OR console exporter when no endpoint configured)
```

All three signals share one `Resource` and the same propagated trace context.

## Key domain spans & metrics

Added only at high-signal seams. `tracer`/`meter`/instruments come from the
`observability` package; domain modules import from it (no SDK leakage past the
seam).

| Flow | Span | Metrics |
|---|---|---|
| **Ingestion run** (ingestion orchestrator) | `ingestion.run` per source | `jobs_fetched_total{source}`, `jobs_scored_total{source}`, `ingestion_run_duration_ms` |
| **Match scoring** (matching orchestrator) | `matching.score` | `matches_completed_total`, `match_score` (histogram) |
| **LLM calls** (hook into existing `UsageRecorder` — single chokepoint) | `llm.call{feature_key,model}` | `llm_tokens_total{type=input\|output}`, `llm_cost_usd_total`, `llm_call_duration_ms`, `llm_errors_total` |
| **Event bus** (`InMemoryEventBus.publish` / `_safe_invoke`) | `event.dispatch{type}` | `events_published_total{type}`, `event_handler_errors_total{type}` |

`UsageRecorder.record(...)` already receives tokens/cost/latency/success per
call, so LLM metrics are recorded there; the LLM span is opened around the call
site that ultimately reports to the recorder. Where the exact span boundary is
awkward inside the tracked-LLM factory, prefer recording the metrics in
`UsageRecorder` and opening the span at the orchestrator seam — metrics are the
must-have, the span is best-effort.

## Configuration

All via `Settings` (pydantic-settings) + `.env.example`, no hardcoded values.
New fields:

| Field | Default | Notes |
|---|---|---|
| `otel_enabled` | `true` | Master switch; `false` makes `setup_telemetry` a no-op. |
| `otel_service_name` | `hiresense-backend` | `service.name` resource attr. |
| `otel_exporter_otlp_endpoint` | `""` | **Empty → console fallback.** Set to `http://otel-lgtm:4317` to use LGTM. |
| `otel_exporter_otlp_protocol` | `grpc` | `grpc` or `http/protobuf`. |
| `deployment_environment` | `development` | `deployment.environment` resource attr. |
| `log_level` | `INFO` | Root level for the dictConfig. |
| `log_format` | `json` | `json` or `console` (human-readable for local). |
| `otel_traces_sampler_ratio` | `1.0` | Parent-based ratio sampler. |

Mirrored into `backend/.env.example` with explanatory comments. The app's
`.env` (compose) sets `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-lgtm:4317`.

## Infrastructure

Add to root `docker-compose.yml`:

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

Add `lgtm:` to the top-level `volumes:`. `app` gains an optional `depends_on:
otel-lgtm` (not health-gated — telemetry is non-critical). Grafana at
`localhost:3000` ships with Loki/Tempo/Prometheus datasources pre-wired.

## Dependencies (via `uv add`)

- `opentelemetry-sdk`, `opentelemetry-api`
- `opentelemetry-exporter-otlp` (gRPC + HTTP)
- `opentelemetry-instrumentation-fastapi`
- `opentelemetry-instrumentation-sqlalchemy`
- `opentelemetry-instrumentation-httpx`
- `opentelemetry-instrumentation-logging` (or hand-rolled `TraceContextFilter`;
  we use our own filter for control, so this is optional)

## Testing

- **Unit**
  - `JsonLogFormatter` emits valid JSON containing `timestamp`, `level`,
    `logger`, `message`, and (when a span is active) `trace_id`/`span_id`.
  - `TraceContextFilter` injects ids when a span is active and degrades
    gracefully (no keys / empty) when none is.
  - `exporters.py` returns console exporters when the endpoint is empty and OTLP
    exporters when it is set (assert on exporter type).
  - `RequestContextMiddleware` sets a `request_id`, honors an inbound
    `X-Request-ID`, and echoes it on the response.
- **Integration**
  - A request through the app (with `InMemorySpanExporter` test harness) produces
    a server span carrying the `request_id` attribute, and a log record captured
    in the same context carries the matching `trace_id`.
  - `setup_telemetry` with `otel_enabled=false` is a no-op (no providers
    installed, app still boots).

Run with `uv run python -m pytest` (per the repo's uv-trampoline workaround).

## Error handling

- `setup_telemetry` guards each step in try/except; a failure logs a warning and
  continues so a bad exporter/instrumentation never blocks boot.
- SDK `BatchSpanProcessor` / `PeriodicExportingMetricReader` swallow export
  errors internally (they retry/drop, never raise into app code).
- Console fallback guarantees the app starts with no collector present.
- `otel_enabled=false` fully disables the stack.

## Rollout / build sequence (for the implementation plan)

1. Add deps + config fields + `.env.example` entries.
2. `observability` package skeleton: resource, exporters (with fallback),
   tracer/meter helpers.
3. Logging: `JsonLogFormatter`, `TraceContextFilter`, `configure_logging`.
4. `RequestContextMiddleware`.
5. `setup_telemetry` + auto-instrumentation; wire into `main.create_app()`.
6. Domain metrics module + the four seam spans/metrics.
7. `docker-compose.yml` `otel-lgtm` service.
8. Tests (unit + integration).
