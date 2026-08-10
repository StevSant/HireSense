from __future__ import annotations

from hiresense.shared.kernel.exceptions import UpstreamUnavailableError


class LLMNotConfiguredError(UpstreamUnavailableError):
    """Raised when a feature needs an LLM but none is configured.

    This is a *deliberate degraded mode*, not an outage: in ``APP_MODE=local``
    a blank ``LLM_API_KEY`` is the expected setup, and LLM-backed features are
    meant to be unavailable rather than broken.

    It subclasses ``UpstreamUnavailableError`` for two reasons:

    * **Transport.** The client sees the same thing either way — the feature is
      unavailable — and the shared handler is registered on the base type, so
      this maps to HTTP 503 with no extra wiring.
    * **Diagnosis.** The two conditions still need telling apart. An outage is
      transient and worth retrying; a missing API key never resolves itself, so
      retry/backoff logic and operational alerting can catch this narrower type
      and treat it as a configuration task instead of an incident.

    Raising is the point: it keeps the "no LLM" policy in one place instead of
    each caller inventing its own not-configured stand-in (``[]``, ``None``,
    ``0.5``, a fabricated object) that reads downstream as a real result.
    """
