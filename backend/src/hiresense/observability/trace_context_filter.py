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
