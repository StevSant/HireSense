from __future__ import annotations

from typing import Protocol

from hiresense.admin.infrastructure import LLMAuditLog


class LLMAuditLogRepositoryPort(Protocol):
    """Append-only audit trail for admin LLM-config actions."""

    def append(
        self,
        *,
        actor: str | None,
        action: str,
        target: str | None,
        changes: dict,
    ) -> LLMAuditLog: ...

    def list_recent(self, limit: int = 100) -> list[LLMAuditLog]: ...
