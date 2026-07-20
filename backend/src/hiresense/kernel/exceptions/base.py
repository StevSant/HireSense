from __future__ import annotations


class DomainError(ValueError):
    """Base class for domain errors that carry an HTTP intent.

    Subclasses map one-to-one onto an HTTP status via the shared exception
    handlers (see ``hiresense.kernel.register_domain_exception_handlers``), so
    the transport status is derived from the exception *type* rather than from
    matching substrings in its message.

    Subclasses ``ValueError`` for backward compatibility: existing
    ``except ValueError`` handlers keep catching these unchanged, so endpoints
    that have not migrated to the shared handlers behave exactly as before.
    """
