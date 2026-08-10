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
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
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
