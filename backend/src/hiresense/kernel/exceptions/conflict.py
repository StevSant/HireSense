from __future__ import annotations

from hiresense.kernel.exceptions.base import DomainError


class ConflictError(DomainError):
    """The request conflicts with the current state (e.g. a duplicate). Maps to HTTP 409."""
