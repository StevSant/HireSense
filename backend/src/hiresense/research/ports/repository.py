from __future__ import annotations

from typing import Protocol

from hiresense.research.domain.models import CompanyResearch


class CompanyResearchRepositoryPort(Protocol):
    def get_by_company_name(self, company_name: str) -> CompanyResearch | None: ...

    def create(self, research: CompanyResearch) -> CompanyResearch: ...

    def save(self, research: CompanyResearch) -> CompanyResearch: ...
