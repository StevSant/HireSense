from __future__ import annotations

from typing import Any

from sqlalchemy import select

from hiresense.admin.domain import LLMAuditEntry
from hiresense.admin.infrastructure.llm_audit_log_model import LLMAuditLog


def _to_domain(row: LLMAuditLog) -> LLMAuditEntry:
    return LLMAuditEntry(
        actor=row.actor,
        action=row.action,
        target=row.target,
        changes=dict(row.changes or {}),
        created_at=row.created_at,
        id=row.id,
    )


class LLMAuditLogRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def append(
        self,
        *,
        actor: str | None,
        action: str,
        target: str | None,
        changes: dict,
    ) -> LLMAuditEntry:
        with self._session_factory() as session:
            entry = LLMAuditLog(actor=actor, action=action, target=target, changes=changes)
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return _to_domain(entry)

    def list_recent(self, limit: int = 100) -> list[LLMAuditEntry]:
        with self._session_factory() as session:
            stmt = select(LLMAuditLog).order_by(LLMAuditLog.created_at.desc()).limit(limit)
            return [_to_domain(r) for r in session.scalars(stmt).all()]
