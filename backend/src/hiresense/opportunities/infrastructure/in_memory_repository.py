from __future__ import annotations

import uuid
from datetime import date

from hiresense.opportunities.domain.models import Opportunity, OpportunityKind
from hiresense.opportunities.domain.relevance import is_funded, is_stale
from hiresense.opportunities.domain.sorting import parse_sort_token
from hiresense.opportunities.domain.upsert_result import UpsertResult
from hiresense.opportunities.ports.repository import OpportunitySort, UpsertOutcome


def _deadline(opp: Opportunity) -> date | None:
    return opp.application_deadline or opp.cfp_deadline


def _language(opp: Opportunity) -> str:
    locales = (opp.source_metadata or {}).get("locales")
    if isinstance(locales, list):
        return ", ".join(str(x) for x in locales if x).lower()
    return str(locales or "").lower()


def _cost_rank(opp: Opportunity) -> int:
    if is_funded(opp):
        return 3
    blob = f"{opp.title} {opp.description}".lower()
    if "free" in blob or "no fee" in blob:
        return 2
    if opp.kind.value == "cfp":
        return 1
    return 0


def _sort_key(opp: Opportunity, field: str):
    if field == "title":
        return (opp.title or "").lower()
    if field == "country":
        return (opp.country or "").lower()
    if field == "source":
        return (opp.source or "").lower()
    if field == "language":
        return _language(opp)
    if field == "cost":
        return _cost_rank(opp)
    if field == "deadline":
        return _deadline(opp) or date.max
    if field == "when":
        return opp.start_date or date.max
    return opp.start_date or date.max


class InMemoryOpportunitiesRepository:
    """Test double for OpportunitiesRepositoryPort."""

    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, Opportunity] = {}
        self._by_key: dict[tuple[str, str], uuid.UUID] = {}

    def get_by_id(self, id: uuid.UUID) -> Opportunity | None:
        return self._by_id.get(id)

    def _matches(
        self,
        opp: Opportunity,
        *,
        kind: OpportunityKind | None,
        topic: str | None,
        topics: list[str] | None,
        exclude_topics: list[str] | None,
        country: str | None,
        q: str | None,
        funded_only: bool,
        deadline_before: date | None,
        deadline_after: date | None,
        hide_stale: bool,
        status: str,
    ) -> bool:
        if status and opp.status != status:
            return False
        if kind is not None and opp.kind != kind:
            return False
        if country and (opp.country or "").lower() != country.lower():
            return False
        if funded_only and not is_funded(opp):
            return False
        if hide_stale and is_stale(opp):
            return False
        topic_needles = [t.lower() for t in ([topic] if topic else []) + list(topics or []) if t]
        for needle in topic_needles:
            if not any(needle in t.lower() for t in opp.topics):
                return False
        for excluded in exclude_topics or []:
            needle = excluded.lower()
            if needle and any(needle in t.lower() for t in opp.topics):
                return False
        if q:
            blob = " ".join(
                [
                    opp.title or "",
                    opp.organization or "",
                    opp.description or "",
                    " ".join(opp.topics or []),
                    opp.funding or "",
                ]
            ).lower()
            if q.lower() not in blob:
                return False
        deadline = _deadline(opp)
        if deadline_before is not None:
            if deadline is None or deadline > deadline_before:
                return False
        if deadline_after is not None:
            if deadline is None or deadline < deadline_after:
                return False
        return True

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
    ) -> list[Opportunity]:
        items = [
            o
            for o in self._by_id.values()
            if self._matches(
                o,
                kind=kind,
                topic=topic,
                topics=topics,
                exclude_topics=exclude_topics,
                country=country,
                q=q,
                funded_only=funded_only,
                deadline_before=deadline_before,
                deadline_after=deadline_after,
                hide_stale=hide_stale,
                status=status,
            )
        ]
        field, direction = parse_sort_token(sort)
        reverse = direction == "desc"
        sort_field = "when" if field == "match" else field

        def key_fn(o: Opportunity):
            value = _sort_key(o, sort_field)
            # For ascending date sorts, missing dates should sink to the end.
            if sort_field in {"when", "deadline"} and not reverse and value == date.max:
                return (1, value, o.id or uuid.UUID(int=0))
            if sort_field in {"when", "deadline"} and reverse and value == date.max:
                return (1, value, o.id or uuid.UUID(int=0))
            return (0, value, o.id or uuid.UUID(int=0))

        items.sort(key=key_fn, reverse=reverse)
        if offset:
            items = items[offset:]
        if limit is not None:
            items = items[:limit]
        return items

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
    ) -> int:
        return len(
            self.list(
                kind=kind,
                topic=topic,
                topics=topics,
                exclude_topics=exclude_topics,
                country=country,
                q=q,
                funded_only=funded_only,
                deadline_before=deadline_before,
                deadline_after=deadline_after,
                hide_stale=hide_stale,
                status=status,
            )
        )

    def bulk_upsert(self, opportunities: list[Opportunity]) -> list[UpsertOutcome]:
        from hiresense.opportunities.domain.content_hash import content_hash
        from hiresense.opportunities.domain.identity import identity_key

        outcomes: list[UpsertOutcome] = []
        for opp in opportunities:
            key = (opp.source, identity_key(opp))
            existing_id = self._by_key.get(key)
            status = opp.status or "open"
            if existing_id is None:
                new_id = uuid.uuid4()
                stored = opp.model_copy(update={"id": new_id, "status": status})
                self._by_id[new_id] = stored
                self._by_key[key] = new_id
                outcomes.append(UpsertOutcome(opportunity=stored, result=UpsertResult.INSERTED))
                continue
            existing = self._by_id[existing_id]
            new_hash = content_hash(opp)
            old_hash = content_hash(existing)
            was_closed = existing.status == "closed"
            if new_hash == old_hash and existing.status == status:
                outcomes.append(
                    UpsertOutcome(opportunity=existing, result=UpsertResult.UNCHANGED)
                )
                continue
            updated = opp.model_copy(update={"id": existing_id, "status": status})
            self._by_id[existing_id] = updated
            if was_closed and status == "open":
                result = UpsertResult.REOPENED
            else:
                result = UpsertResult.UPDATED
            outcomes.append(UpsertOutcome(opportunity=updated, result=result))
        return outcomes
