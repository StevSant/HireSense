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
