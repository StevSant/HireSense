from __future__ import annotations

from hiresense.research.domain.company_profile_store import CompanyProfileStore
from hiresense.research.domain.firmographics import Firmographics


class CompanyProfileFirmographicsAdapter:
    """Firmographics from a source-captured company profile (in-process store).

    Turns a ``CompanyProfile`` recorded during ingestion into ``Firmographics``
    so the research service can ground its prompt and surface the About text.
    Returns ``None`` when no profile was captured for the company, so a composite
    can fall through to an external provider or the LLM.
    """

    def __init__(self, store: CompanyProfileStore) -> None:
        self._store = store

    async def fetch(self, company_name: str) -> Firmographics | None:
        profile = self._store.get(company_name)
        if profile is None:
            return None
        return Firmographics(
            description=profile.description,
            website=profile.website,
            headquarters=profile.headquarters,
        )
