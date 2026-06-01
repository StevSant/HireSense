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
