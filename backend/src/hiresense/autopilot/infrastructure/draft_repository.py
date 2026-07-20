from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

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


def _new_orm(draft: AutopilotDraft) -> AutopilotDraftOrm:
    return AutopilotDraftOrm(
        job_id=draft.job_id,
        application_id=draft.application_id,
        job_title=draft.job_title,
        company=draft.company,
        status=draft.status.value,
        detail=draft.detail,
    )


class DraftRepositoryImpl(SqlRepository):
    def add(self, draft: AutopilotDraft) -> AutopilotDraft:
        return self._insert(_new_orm(draft), _to_domain)

    def claim(self, draft: AutopilotDraft) -> AutopilotDraft | None:
        """Insert a reservation row for ``draft.job_id``; return ``None`` if the
        unique constraint rejects it (another run already reserved this job)."""
        try:
            return self._insert(_new_orm(draft), _to_domain)
        except IntegrityError:
            return None

    def finalize(self, draft: AutopilotDraft) -> AutopilotDraft:
        updated = self._update_by_pk(
            AutopilotDraftOrm,
            draft.id,
            {
                "application_id": draft.application_id,
                "status": draft.status.value,
                "detail": draft.detail,
            },
            _to_domain,
        )
        if updated is None:  # pragma: no cover - the claimed row always exists
            raise RuntimeError(f"autopilot draft {draft.id} vanished before finalize")
        return updated

    def list(self, limit: int) -> list[AutopilotDraft]:
        stmt = select(AutopilotDraftOrm).order_by(AutopilotDraftOrm.created_at.desc()).limit(limit)
        return self._select_all(stmt, _to_domain)

    def exists_for_job(self, job_id: str) -> bool:
        with self._session_factory() as session:
            stmt = select(AutopilotDraftOrm.id).where(AutopilotDraftOrm.job_id == job_id).limit(1)
            return session.scalars(stmt).first() is not None
