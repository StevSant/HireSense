from __future__ import annotations

from hiresense.research.domain.company_profile import CompanyProfile


class CompanyProfileStore:
    """In-process registry of source-provided company profiles.

    Written by ingestion adapters as they resolve companies, read by the research
    service to ground its prompt and surface an About block. Kept in process
    memory on purpose — like the embedding model and the semantic caches (see
    ARCHITECTURE.md "Scaling constraints"), it is rebuilt on the next ingestion
    run and is safe to lose on restart. Keyed case-insensitively by company name;
    the newest capture for a name wins.
    """

    def __init__(self) -> None:
        self._by_name: dict[str, CompanyProfile] = {}

    @staticmethod
    def _key(company_name: str) -> str:
        return company_name.lower().strip()

    def record(
        self,
        *,
        company_name: str,
        source: str,
        description: str | None = None,
        website: str | None = None,
        headquarters: str | None = None,
    ) -> None:
        name = company_name.strip()
        if not name:
            return
        self._by_name[self._key(name)] = CompanyProfile(
            company_name=name,
            source=source,
            description=description,
            website=website,
            headquarters=headquarters,
        )

    def get(self, company_name: str) -> CompanyProfile | None:
        return self._by_name.get(self._key(company_name))
