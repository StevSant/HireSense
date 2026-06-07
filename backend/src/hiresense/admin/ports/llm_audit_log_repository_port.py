from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from hiresense.admin.domain import LLMAuditEntry


class LLMAuditLogRepositoryPort(Protocol):
    """Append-only audit trail for admin LLM-config actions."""

    def append(
        self,
        *,
        actor: str | None,
        action: str,
        target: str | None,
        changes: dict,
    ) -> LLMAuditEntry: ...

    def list_recent(self, limit: int = 100) -> list[LLMAuditEntry]: ...
