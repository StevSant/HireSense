from __future__ import annotations

from hiresense.kernel.exceptions.base import DomainError


class NotFoundError(DomainError):
    """A requested resource does not exist. Maps to HTTP 404."""
