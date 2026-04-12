"""Backward-compatible re-export. Import from hiresense.identity.domain instead."""

from hiresense.identity.domain.services import AuthService

__all__ = ["AuthService"]
