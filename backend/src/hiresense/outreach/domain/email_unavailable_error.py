from __future__ import annotations


class EmailUnavailableError(RuntimeError):
    """Raised when outreach email can't be sent because SMTP isn't configured.

    The API layer maps this to HTTP 503, mirroring OutreachUnavailableError for
    message generation.
    """
