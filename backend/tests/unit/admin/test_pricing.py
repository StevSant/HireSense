from __future__ import annotations

from hiresense.admin.domain.pricing import estimate_cost_usd


def test_known_pair_uses_table() -> None:
    cost = estimate_cost_usd("anthropic", "claude-sonnet-4-6", 1_000_000, 1_000_000)
    assert cost == 3.0 + 15.0


def test_unknown_model_falls_through_to_zero() -> None:
    assert estimate_cost_usd("madeup", "no-such-model", 1000, 1000) == 0.0


def test_ollama_wildcard_zero() -> None:
    assert estimate_cost_usd("ollama", "llama3:8b", 1_000_000, 1_000_000) == 0.0


def test_partial_token_count_scales_linearly() -> None:
    full = estimate_cost_usd("anthropic", "claude-haiku-4-5", 1_000_000, 1_000_000)
    half = estimate_cost_usd("anthropic", "claude-haiku-4-5", 500_000, 500_000)
    assert half == full / 2
