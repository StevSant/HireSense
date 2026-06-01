from __future__ import annotations

from opentelemetry import trace


def get_tracer(name: str) -> trace.Tracer:
    """Module-scoped tracer. Safe to call before setup_telemetry — returns a
    no-op tracer until a TracerProvider is installed."""
    return trace.get_tracer(name)
