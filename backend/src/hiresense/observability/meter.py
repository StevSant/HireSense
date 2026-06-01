from __future__ import annotations

from opentelemetry import metrics


def get_meter(name: str) -> metrics.Meter:
    """Module-scoped meter. Safe to call before setup_telemetry — returns a
    no-op meter until a MeterProvider is installed."""
    return metrics.get_meter(name)
