from __future__ import annotations

from typing import Any

from sqlalchemy import select

from hiresense.admin.infrastructure.llm_audit_log_model import LLMAuditLog


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
    ) -> LLMAuditLog:
        with self._session_factory() as session:
            entry = LLMAuditLog(actor=actor, action=action, target=target, changes=changes)
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return entry

    def list_recent(self, limit: int = 100) -> list[LLMAuditLog]:
        with self._session_factory() as session:
            stmt = select(LLMAuditLog).order_by(LLMAuditLog.created_at.desc()).limit(limit)
            return list(session.scalars(stmt).all())
