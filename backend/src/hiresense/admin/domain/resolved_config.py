from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResolvedConfig:
    """The effective LLM configuration for a single call.

    The result of layering: feature override (provider/model/extra_params) on
    top of the global settings row, on top of `.env` fallbacks.
    """

    provider: str
    model: str
    api_key: str
    extra_params: dict = field(default_factory=dict)
    source: str = "env"  # "env" | "global" | "override"
