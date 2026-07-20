from __future__ import annotations

import pytest

from hiresense.research.domain import CompanyProfileStore
from hiresense.research.infrastructure import CompanyProfileFirmographicsAdapter


@pytest.mark.asyncio
async def test_fetch_maps_stored_profile_to_firmographics() -> None:
    store = CompanyProfileStore()
    store.record(
        company_name="BC Tecnología",
        source="getonboard",
        description="Consultora de TI",
        website="https://bc.cl",
        headquarters="Chile",
    )
    adapter = CompanyProfileFirmographicsAdapter(store)

    result = await adapter.fetch("BC Tecnología")

    assert result is not None
    assert result.description == "Consultora de TI"
    assert result.website == "https://bc.cl"
    assert result.headquarters == "Chile"
    # The store carries no industry/size — those come from the external provider.
    assert result.industry is None
    assert result.company_size is None


@pytest.mark.asyncio
async def test_fetch_returns_none_when_no_profile_captured() -> None:
    adapter = CompanyProfileFirmographicsAdapter(CompanyProfileStore())

    assert await adapter.fetch("Unknown") is None
