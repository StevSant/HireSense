from __future__ import annotations

from hiresense.admin.infrastructure.llm_usage_log_repository import _calls_order_by


def test_default_and_invalid_fall_back_to_created_desc() -> None:
    assert "created_at DESC" in str(_calls_order_by(None))
    assert "created_at DESC" in str(_calls_order_by("nope_desc"))
    assert "created_at DESC" in str(_calls_order_by("cost_sideways"))


def test_known_field_sorts() -> None:
    assert "cost_usd ASC" in str(_calls_order_by("cost_asc"))
    assert "latency_ms DESC" in str(_calls_order_by("latency_desc"))
    assert "input_tokens ASC" in str(_calls_order_by("input_tokens_asc"))
    assert "output_tokens DESC" in str(_calls_order_by("output_tokens_desc"))
