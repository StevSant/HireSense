from __future__ import annotations


class UpstreamUnavailableError(RuntimeError):
    """A dependency a feature needs (LLM provider, external API, vector store)
    failed, so the feature produced no result at all.

    Domain services raise this instead of returning a plausible-looking
    placeholder. A fabricated result is indistinguishable from a real one: it
    is served as a 200, it gets persisted, and it hides genuine bugs and
    outages (issues #147/#142). The shared handlers map this to HTTP 503, so
    the client is told the feature is temporarily unavailable rather than being
    handed an invented answer.

    Deliberately NOT a ``DomainError``: that base subclasses ``ValueError`` for
    backward compatibility, and the many ``except ValueError`` blocks in the
    routers would silently downgrade an upstream outage to a misleading 400.
    """
