from __future__ import annotations

from sqlalchemy import select

from hiresense.admin.domain import LLMAuditEntry
from hiresense.admin.infrastructure.llm_audit_log_model import LLMAuditLog
from hiresense.infrastructure import SqlRepository


def _to_domain(row: LLMAuditLog) -> LLMAuditEntry:
    return LLMAuditEntry(
        actor=row.actor,
        action=row.action,
        target=row.target,
        changes=dict(row.changes or {}),
        created_at=row.created_at,
        id=row.id,
    )


class LLMAuditLogRepository(SqlRepository):
    def append(
        self,
        *,
        actor: str | None,
        action: str,
        target: str | None,
        changes: dict,
    ) -> LLMAuditEntry:
        entry = LLMAuditLog(actor=actor, action=action, target=target, changes=changes)
        return self._insert(entry, _to_domain)

    def list_recent(self, limit: int = 100) -> list[LLMAuditEntry]:
        stmt = select(LLMAuditLog).order_by(LLMAuditLog.created_at.desc()).limit(limit)
        return self._select_all(stmt, _to_domain)
