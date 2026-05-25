from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    """USD per 1M tokens. Adjust here when providers change pricing."""

    input_per_1m: float
    output_per_1m: float


# Best-effort defaults. The admin can later override these via a settings
# table if desired (Issue #15 follow-up). Anything not in this map costs 0.
DEFAULT_PRICING: dict[tuple[str, str], ModelPricing] = {
    # Anthropic Claude family
    ("anthropic", "claude-opus-4-7"): ModelPricing(15.0, 75.0),
    ("anthropic", "claude-opus-4-6"): ModelPricing(15.0, 75.0),
    ("anthropic", "claude-sonnet-4-6"): ModelPricing(3.0, 15.0),
    ("anthropic", "claude-sonnet-4-5"): ModelPricing(3.0, 15.0),
    ("anthropic", "claude-haiku-4-5-20251001"): ModelPricing(0.80, 4.00),
    ("anthropic", "claude-haiku-4-5"): ModelPricing(0.80, 4.00),
    # OpenAI
    ("openai", "gpt-4o"): ModelPricing(2.50, 10.00),
    ("openai", "gpt-4o-mini"): ModelPricing(0.15, 0.60),
    ("openai", "gpt-4-turbo"): ModelPricing(10.0, 30.0),
    # Groq (rough public pricing)
    ("groq", "llama-3.3-70b-versatile"): ModelPricing(0.59, 0.79),
    ("groq", "llama-3.1-8b-instant"): ModelPricing(0.05, 0.08),
    # Self-hosted: free at the API layer
    ("ollama", "*"): ModelPricing(0.0, 0.0),
}


def estimate_cost_usd(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    pricing = DEFAULT_PRICING.get((provider, model))
    if pricing is None:
        pricing = DEFAULT_PRICING.get((provider, "*"))
    if pricing is None:
        return 0.0
    return (
        (input_tokens / 1_000_000.0) * pricing.input_per_1m
        + (output_tokens / 1_000_000.0) * pricing.output_per_1m
    )
