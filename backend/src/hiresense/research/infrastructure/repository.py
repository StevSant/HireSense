from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from hiresense.research.domain.models import CompanyResearch


class CompanyResearchRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def get_by_company_name(self, company_name: str) -> CompanyResearch | None:
        with self._session_factory() as session:
            stmt = select(CompanyResearch).where(
                func.lower(CompanyResearch.company_name) == company_name.lower().strip()
            )
            return session.scalars(stmt).first()

    def create(self, research: CompanyResearch) -> CompanyResearch:
        with self._session_factory() as session:
            session.add(research)
            session.commit()
            session.refresh(research)
            return research

    def save(self, research: CompanyResearch) -> CompanyResearch:
        with self._session_factory() as session:
            research = session.merge(research)
            session.commit()
            session.refresh(research)
            return research
