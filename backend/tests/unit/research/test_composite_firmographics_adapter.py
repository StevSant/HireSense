from __future__ import annotations

import pytest

from hiresense.research.domain import Firmographics
from hiresense.research.infrastructure import CompositeFirmographicsAdapter


class _Fixed:
    def __init__(self, result: Firmographics | None) -> None:
        self._result = result

    async def fetch(self, company_name: str) -> Firmographics | None:
        return self._result


@pytest.mark.asyncio
async def test_earliest_provider_wins_per_field_and_gaps_fill_from_later() -> None:
    source = _Fixed(Firmographics(description="About us", website="https://a.co"))
    external = _Fixed(
        Firmographics(industry="SaaS", company_size="51-200", website="https://ignored")
    )
    composite = CompositeFirmographicsAdapter([source, external])

    result = await composite.fetch("Acme")

    assert result is not None
    assert result.description == "About us"  # only source has it
    assert result.website == "https://a.co"  # earliest (source) wins
    assert result.industry == "SaaS"  # gap filled by external
    assert result.company_size == "51-200"


@pytest.mark.asyncio
async def test_returns_none_when_all_providers_empty() -> None:
    composite = CompositeFirmographicsAdapter([_Fixed(None), _Fixed(None)])

    assert await composite.fetch("Acme") is None


@pytest.mark.asyncio
async def test_skips_none_providers_and_returns_remaining() -> None:
    composite = CompositeFirmographicsAdapter([_Fixed(None), _Fixed(Firmographics(industry="AI"))])

    result = await composite.fetch("Acme")

    assert result is not None
    assert result.industry == "AI"
