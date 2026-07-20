from __future__ import annotations

from hiresense.kernel.exceptions.base import DomainError


class ValidationError(DomainError):
    """The request is well-formed but semantically invalid or out of order. Maps to HTTP 400."""
