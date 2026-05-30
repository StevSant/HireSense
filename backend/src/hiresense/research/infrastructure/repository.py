from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from hiresense.research.domain.models import CompanyResearch
from hiresense.research.infrastructure.orm import CompanyResearchOrm

_CONTENT_FIELDS = (
    "company_name",
    "funding_stage",
    "tech_stack",
    "culture_summary",
    "growth_trajectory",
    "red_flags",
    "pros",
    "cons",
    "raw_llm_response",
)


def _to_domain(row: CompanyResearchOrm) -> CompanyResearch:
    return CompanyResearch.model_validate(row)


class CompanyResearchRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def get_by_company_name(self, company_name: str) -> CompanyResearch | None:
        with self._session_factory() as session:
            stmt = select(CompanyResearchOrm).where(
                func.lower(CompanyResearchOrm.company_name) == company_name.lower().strip()
            )
            row = session.scalars(stmt).first()
            return _to_domain(row) if row is not None else None

    def create(self, research: CompanyResearch) -> CompanyResearch:
        with self._session_factory() as session:
            row = CompanyResearchOrm(
                **{field: getattr(research, field) for field in _CONTENT_FIELDS}
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def save(self, research: CompanyResearch) -> CompanyResearch:
        with self._session_factory() as session:
            row = session.get(CompanyResearchOrm, research.id) if research.id else None
            if row is None:
                row = CompanyResearchOrm(
                    **{field: getattr(research, field) for field in _CONTENT_FIELDS}
                )
                session.add(row)
            else:
                for field in _CONTENT_FIELDS:
                    setattr(row, field, getattr(research, field))
            session.commit()
            session.refresh(row)
            return _to_domain(row)
