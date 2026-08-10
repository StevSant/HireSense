from __future__ import annotations

from hiresense.shared.kernel.exceptions import UpstreamUnavailableError


class CompanyResearchError(UpstreamUnavailableError):
    """Raised when company research fails (LLM error, unparseable response,
    persistence failure).

    The service must NOT swallow the failure and return the "Research
    unavailable" placeholder: every generated field carries that literal
    string, the record is served as a 200, and its shape is identical both to a
    real result and to the deliberate "LLM not configured" state — so an outage
    is indistinguishable from a genuine answer. Raising surfaces a 503 and
    keeps the placeholder out of the response.
    """
