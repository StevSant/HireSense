from __future__ import annotations


class RecipientNotAllowedError(ValueError):
    """Raised when an outreach send targets a recipient outside the allowed set.

    Subclasses ValueError so existing ``except ValueError`` handlers still catch
    it, while the route layer can map it to a 400 distinct from the 404 used for
    a missing application.
    """
