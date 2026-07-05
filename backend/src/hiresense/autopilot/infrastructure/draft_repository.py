from __future__ import annotations

from sqlalchemy import select

from hiresense.autopilot.domain import AutopilotDraft, DraftStatus
from hiresense.autopilot.infrastructure.autopilot_draft_orm import AutopilotDraftOrm
from hiresense.infrastructure import SqlRepository


def _to_domain(row: AutopilotDraftOrm) -> AutopilotDraft:
    return AutopilotDraft(
        id=row.id,
        job_id=row.job_id,
        application_id=row.application_id,
        job_title=row.job_title,
        company=row.company,
        status=DraftStatus(row.status),
        detail=row.detail,
        created_at=row.created_at,
    )


class DraftRepositoryImpl(SqlRepository):
    def add(self, draft: AutopilotDraft) -> AutopilotDraft:
        row = AutopilotDraftOrm(
            job_id=draft.job_id,
            application_id=draft.application_id,
            job_title=draft.job_title,
            company=draft.company,
            status=draft.status.value,
            detail=draft.detail,
        )
        return self._insert(row, _to_domain)

    def list(self, limit: int) -> list[AutopilotDraft]:
        stmt = select(AutopilotDraftOrm).order_by(AutopilotDraftOrm.created_at.desc()).limit(limit)
        return self._select_all(stmt, _to_domain)

    def exists_for_job(self, job_id: str) -> bool:
        with self._session_factory() as session:
            stmt = select(AutopilotDraftOrm.id).where(AutopilotDraftOrm.job_id == job_id).limit(1)
            return session.scalars(stmt).first() is not None
