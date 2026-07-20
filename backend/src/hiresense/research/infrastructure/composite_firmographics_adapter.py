from __future__ import annotations

from hiresense.research.domain.firmographics import Firmographics
from hiresense.research.ports import FirmographicsPort


class CompositeFirmographicsAdapter:
    """Merges several firmographics providers, earliest-listed wins per field.

    Each provider is tried in order; the first non-empty value for a field is
    kept. This lets a source-captured profile (description/website/HQ) combine
    with an external provider (industry/size) into one ``Firmographics``. Returns
    ``None`` only when every provider returned nothing.
    """

    _FIELDS = ("industry", "company_size", "headquarters", "website", "description")

    def __init__(self, providers: list[FirmographicsPort]) -> None:
        self._providers = providers

    async def fetch(self, company_name: str) -> Firmographics | None:
        merged: dict[str, str] = {}
        for provider in self._providers:
            result = await provider.fetch(company_name)
            if result is None:
                continue
            for field in self._FIELDS:
                if field not in merged:
                    value = getattr(result, field)
                    if value:
                        merged[field] = value
        if not merged:
            return None
        return Firmographics(**merged)
