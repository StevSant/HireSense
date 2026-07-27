from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from hiresense.opportunities.domain.models import Opportunity, OpportunityKind
from hiresense.opportunities.domain.upsert_result import UpsertResult

# Tokens like "match_desc", "title_asc", "when_asc", "deadline_desc",
# plus legacy aliases "relevance_desc" / "date_asc".
OpportunitySort = str


@dataclass(frozen=True)
class UpsertOutcome:
    opportunity: Opportunity
    result: UpsertResult


class OpportunitiesRepositoryPort(Protocol):
    def get_by_id(self, id: uuid.UUID) -> Opportunity | None: ...

    def list(
        self,
        *,
        kind: OpportunityKind | None = None,
        topic: str | None = None,
        topics: list[str] | None = None,
        exclude_topics: list[str] | None = None,
        country: str | None = None,
        q: str | None = None,
        funded_only: bool = False,
        deadline_before: date | None = None,
        deadline_after: date | None = None,
        hide_stale: bool = True,
        status: str = "open",
        sort: OpportunitySort = "date_asc",
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Opportunity]: ...

    def count(
        self,
        *,
        kind: OpportunityKind | None = None,
        topic: str | None = None,
        topics: list[str] | None = None,
        exclude_topics: list[str] | None = None,
        country: str | None = None,
        q: str | None = None,
        funded_only: bool = False,
        deadline_before: date | None = None,
        deadline_after: date | None = None,
        hide_stale: bool = True,
        status: str = "open",
    ) -> int: ...

    def bulk_upsert(self, opportunities: list[Opportunity]) -> list[UpsertOutcome]: ...
