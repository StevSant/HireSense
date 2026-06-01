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
