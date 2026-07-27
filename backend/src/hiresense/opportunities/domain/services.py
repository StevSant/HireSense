from __future__ import annotations

import logging
from datetime import date
from typing import Any, Protocol

from hiresense.opportunities.domain.models import Opportunity, OpportunityKind, RawOpportunity
from hiresense.opportunities.domain.relevance import matches_profile, score_opportunity_relevance
from hiresense.opportunities.domain.sorting import parse_sort_token, requires_memory_sort
from hiresense.opportunities.domain.upsert_result import UpsertResult
from hiresense.opportunities.ports.opportunity_source import OpportunitySourcePort
from hiresense.opportunities.ports.repository import OpportunitiesRepositoryPort, OpportunitySort

logger = logging.getLogger(__name__)


class OpportunityNormalizer(Protocol):
    def normalize(self, raw: RawOpportunity) -> Opportunity | None: ...


class OpportunityIngestionService:
    """Fetch → normalize → upsert opportunities from enabled sources."""

    def __init__(
        self,
        *,
        sources: list[OpportunitySourcePort],
        normalizers: dict[str, OpportunityNormalizer],
        repository: OpportunitiesRepositoryPort,
    ) -> None:
        self._sources = sources
        self._normalizers = normalizers
        self._repository = repository

    async def run(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "sources": {},
            "inserted": 0,
            "updated": 0,
            "reopened": 0,
            "unchanged": 0,
            "errors": [],
        }
        for source in self._sources:
            name = source.source_name()
            normalizer = self._normalizers.get(name)
            if normalizer is None:
                summary["errors"].append({"source": name, "error": "no normalizer registered"})
                continue
            try:
                raw_items = await source.fetch(filters)
            except Exception as exc:  # noqa: BLE001 — per-source isolation
                logger.exception("Opportunity source %s failed", name)
                summary["errors"].append({"source": name, "error": str(exc)})
                summary["sources"][name] = {"fetched": 0, "upserted": 0, "error": str(exc)}
                continue

            normalized: list[Opportunity] = []
            for raw in raw_items:
                try:
                    opp = normalizer.normalize(raw)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Normalize failed for %s/%s: %s", name, raw.source_id, exc)
                    continue
                if opp is not None:
                    normalized.append(opp)

            outcomes = self._repository.bulk_upsert(normalized)
            counts = {
                UpsertResult.INSERTED.value: 0,
                UpsertResult.UPDATED.value: 0,
                UpsertResult.REOPENED.value: 0,
                UpsertResult.UNCHANGED.value: 0,
            }
            for outcome in outcomes:
                counts[outcome.result.value] = counts.get(outcome.result.value, 0) + 1
                summary[outcome.result.value] = summary.get(outcome.result.value, 0) + 1
            summary["sources"][name] = {
                "fetched": len(raw_items),
                "normalized": len(normalized),
                "upserted": len(outcomes),
                **counts,
            }
        return summary

    def _base_kwargs(
        self,
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
    ) -> dict[str, Any]:
        return {
            "kind": kind,
            "topic": topic,
            "topics": topics,
            "exclude_topics": exclude_topics,
            "country": country,
            "q": q,
            "funded_only": funded_only,
            "deadline_before": deadline_before,
            "deadline_after": deadline_after,
            "hide_stale": hide_stale,
            "status": status,
        }

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
        matched_only: bool = False,
        candidate_skills: list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[tuple[Opportunity, float | None]]:
        skill_set = {s.lower() for s in (candidate_skills or []) if s}
        base = self._base_kwargs(
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
        field, direction = parse_sort_token(sort)
        needs_memory = matched_only or requires_memory_sort(sort)
        if needs_memory:
            items = self._repository.list(**base, sort="when_asc")
            scored = [
                (opp, score_opportunity_relevance(opp, skill_set) if skill_set else None)
                for opp in items
            ]
            if matched_only:
                scored = [
                    pair for pair in scored if matches_profile(pair[0], skill_set or set())
                ]
            reverse = direction == "desc"

            def sort_key(pair: tuple[Opportunity, float | None]):
                opp, score = pair
                if field == "match":
                    # Missing scores always sink to the end, for both directions.
                    if score is None:
                        sentinel = float("-inf") if reverse else float("inf")
                        return (sentinel, opp.start_date or date.max, str(opp.id or ""))
                    return (score, opp.start_date or date.max, str(opp.id or ""))
                if field == "title":
                    return ((opp.title or "").lower(), str(opp.id or ""))
                if field == "country":
                    return ((opp.country or "").lower(), str(opp.id or ""))
                if field == "source":
                    return ((opp.source or "").lower(), str(opp.id or ""))
                if field == "language":
                    locales = (opp.source_metadata or {}).get("locales") or ""
                    if isinstance(locales, list):
                        locales = ", ".join(str(x) for x in locales if x)
                    return (str(locales).lower(), str(opp.id or ""))
                if field == "cost":
                    label = (opp.source_metadata or {}).get("attendance_cost")
                    if not label:
                        if opp.funding or opp.kind.value in {"grant", "fellowship"}:
                            label = "Funded"
                        else:
                            label = "Unknown"
                    rank = {
                        "Funded": 4,
                        "Free": 3,
                        "Paid": 2,
                        "Likely paid": 1,
                        "Unknown": 0,
                    }.get(str(label), 0)
                    return (rank, str(opp.id or ""))
                if field == "deadline":
                    deadline = opp.application_deadline or opp.cfp_deadline or date.max
                    return (deadline, str(opp.id or ""))
                # when / default
                return (opp.start_date or date.max, str(opp.id or ""))

            scored.sort(key=sort_key, reverse=reverse)
            if offset:
                scored = scored[offset:]
            if limit is not None:
                scored = scored[:limit]
            return scored

        items = self._repository.list(
            **base,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        return [
            (opp, score_opportunity_relevance(opp, skill_set) if skill_set else None)
            for opp in items
        ]

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
        matched_only: bool = False,
        candidate_skills: list[str] | None = None,
    ) -> int:
        base = self._base_kwargs(
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
        if not matched_only:
            return self._repository.count(**base)
        skill_set = {s.lower() for s in (candidate_skills or []) if s}
        items = self._repository.list(**base, sort="date_asc")
        return sum(1 for opp in items if matches_profile(opp, skill_set or set()))

    def get(self, opportunity_id) -> Opportunity | None:
        return self._repository.get_by_id(opportunity_id)
