from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hiresense.portfolio.domain import PortfolioVisit
from hiresense.portfolio.domain.engagement_service import PortfolioEngagementService


def _visit(ref: str, last_seen: datetime) -> PortfolioVisit:
    return PortfolioVisit(
        ref=ref,
        first_seen=datetime(2026, 1, 1, tzinfo=timezone.utc),
        last_seen=last_seen,
    )


class _FakeSource:
    def __init__(self, visits: list[PortfolioVisit], *, raise_on_fetch: bool = False) -> None:
        self._visits = visits
        self._raise = raise_on_fetch

    async def fetch_visits(self, ref_prefix: str) -> list[PortfolioVisit]:
        if self._raise:
            raise RuntimeError("network down")
        return self._visits


@pytest.mark.asyncio
async def test_prefix_parsed_into_application_id() -> None:
    v = _visit("hiresense-abc123", datetime(2026, 6, 1, tzinfo=timezone.utc))
    svc = PortfolioEngagementService(_FakeSource([v]), ref_prefix="hiresense")
    visits = await svc.visits()
    assert len(visits) == 1
    assert visits[0].application_id == "abc123"


@pytest.mark.asyncio
async def test_foreign_ref_yields_none_application_id() -> None:
    v = _visit("other-abc123", datetime(2026, 6, 1, tzinfo=timezone.utc))
    svc = PortfolioEngagementService(_FakeSource([v]), ref_prefix="hiresense")
    visits = await svc.visits()
    assert visits[0].application_id is None


@pytest.mark.asyncio
async def test_sorted_by_last_seen_desc() -> None:
    v1 = _visit("hiresense-a", datetime(2026, 6, 1, tzinfo=timezone.utc))
    v2 = _visit("hiresense-b", datetime(2026, 6, 3, tzinfo=timezone.utc))
    v3 = _visit("hiresense-c", datetime(2026, 6, 2, tzinfo=timezone.utc))
    svc = PortfolioEngagementService(_FakeSource([v1, v2, v3]), ref_prefix="hiresense")
    visits = await svc.visits()
    assert [v.ref for v in visits] == ["hiresense-b", "hiresense-c", "hiresense-a"]


@pytest.mark.asyncio
async def test_source_exception_returns_empty_list() -> None:
    svc = PortfolioEngagementService(_FakeSource([], raise_on_fetch=True), ref_prefix="hiresense")
    visits = await svc.visits()
    assert visits == []


@pytest.mark.asyncio
async def test_original_visit_unchanged_by_service() -> None:
    """model_copy is used; original model instance should not be mutated."""
    v = _visit("hiresense-xyz", datetime(2026, 6, 1, tzinfo=timezone.utc))
    svc = PortfolioEngagementService(_FakeSource([v]), ref_prefix="hiresense")
    await svc.visits()
    assert v.application_id is None
