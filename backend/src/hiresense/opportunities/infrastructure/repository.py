from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import String, and_, cast, func, not_, or_, select

from hiresense.infrastructure import SqlRepository
from hiresense.opportunities.domain.content_hash import content_hash
from hiresense.opportunities.domain.identity import identity_key
from hiresense.opportunities.domain.models import Opportunity, OpportunityKind
from hiresense.opportunities.domain.upsert_result import UpsertResult
from hiresense.opportunities.infrastructure.orm import OpportunityOrm
from hiresense.opportunities.ports.repository import OpportunitySort, UpsertOutcome

_NOT_FUNDED = ("none", "n/a", "na", "no", "-", "unfunded", "self-funded")


def _to_domain(row: OpportunityOrm) -> Opportunity:
    return Opportunity(
        id=row.id,
        kind=OpportunityKind(row.kind),
        title=row.title,
        organization=row.organization,
        url=row.url,
        apply_url=row.apply_url,
        description=row.description or "",
        topics=list(row.topics or []),
        country=row.country,
        city=row.city,
        start_date=row.start_date,
        end_date=row.end_date,
        cfp_deadline=row.cfp_deadline,
        application_deadline=row.application_deadline,
        funding=row.funding,
        source=row.source,
        source_id=row.source_id or "",
        status=row.status,
        source_metadata=dict(row.source_metadata or {}),
        fetched_at=row.fetched_at,
        updated_at=row.updated_at,
    )


def _to_orm(opp: Opportunity) -> OpportunityOrm:
    kind = opp.kind.value if isinstance(opp.kind, OpportunityKind) else str(opp.kind)
    return OpportunityOrm(
        kind=kind,
        title=opp.title,
        organization=opp.organization or "",
        url=opp.url or "",
        apply_url=opp.apply_url,
        description=opp.description or "",
        topics=list(opp.topics or []),
        country=opp.country,
        city=opp.city,
        start_date=opp.start_date,
        end_date=opp.end_date,
        cfp_deadline=opp.cfp_deadline,
        application_deadline=opp.application_deadline,
        funding=opp.funding,
        source=opp.source,
        source_id=opp.source_id or "",
        identity_key=identity_key(opp),
        content_hash=content_hash(opp),
        status=opp.status or "open",
        source_metadata=dict(opp.source_metadata or {}),
        fetched_at=opp.fetched_at or datetime.now(timezone.utc),
    )


class OpportunitiesRepository(SqlRepository):
    def get_by_id(self, id: uuid.UUID) -> Opportunity | None:
        return self._get_by_pk(OpportunityOrm, id, _to_domain)

    def _filter_stmt(
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
    ):
        stmt = select(OpportunityOrm)
        if status:
            stmt = stmt.where(OpportunityOrm.status == status)
        if kind is not None:
            stmt = stmt.where(OpportunityOrm.kind == kind.value)
        if country:
            stmt = stmt.where(OpportunityOrm.country.ilike(country))
        if funded_only:
            funding_l = func.lower(func.trim(OpportunityOrm.funding))
            stmt = stmt.where(
                or_(
                    OpportunityOrm.kind.in_(
                        [OpportunityKind.GRANT.value, OpportunityKind.FELLOWSHIP.value]
                    ),
                    and_(
                        OpportunityOrm.funding.is_not(None),
                        OpportunityOrm.funding != "",
                        not_(funding_l.in_(_NOT_FUNDED)),
                    ),
                )
            )
        if deadline_before is not None:
            stmt = stmt.where(
                or_(
                    OpportunityOrm.cfp_deadline.is_not(None)
                    & (OpportunityOrm.cfp_deadline <= deadline_before),
                    OpportunityOrm.application_deadline.is_not(None)
                    & (OpportunityOrm.application_deadline <= deadline_before),
                )
            )
        if deadline_after is not None:
            stmt = stmt.where(
                or_(
                    OpportunityOrm.cfp_deadline.is_not(None)
                    & (OpportunityOrm.cfp_deadline >= deadline_after),
                    OpportunityOrm.application_deadline.is_not(None)
                    & (OpportunityOrm.application_deadline >= deadline_after),
                )
            )
        if hide_stale:
            today = date.today()
            deadline = func.coalesce(
                OpportunityOrm.application_deadline,
                OpportunityOrm.cfp_deadline,
            )
            event_end = func.coalesce(OpportunityOrm.end_date, OpportunityOrm.start_date)
            stmt = stmt.where(
                and_(
                    or_(deadline.is_(None), deadline >= today),
                    or_(event_end.is_(None), event_end >= today),
                )
            )
        topic_needles = [t for t in ([topic] if topic else []) + list(topics or []) if t]
        for needle in topic_needles:
            stmt = stmt.where(cast(OpportunityOrm.topics, String).ilike(f"%{needle}%"))
        for excluded in exclude_topics or []:
            if excluded:
                stmt = stmt.where(
                    not_(cast(OpportunityOrm.topics, String).ilike(f"%{excluded}%"))
                )
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    OpportunityOrm.title.ilike(like),
                    OpportunityOrm.organization.ilike(like),
                    OpportunityOrm.description.ilike(like),
                    cast(OpportunityOrm.topics, String).ilike(like),
                    OpportunityOrm.funding.ilike(like),
                )
            )
        return stmt

    def _order_by(self, sort: OpportunitySort):
        from hiresense.opportunities.domain.sorting import parse_sort_token

        field, direction = parse_sort_token(sort)
        descending = direction == "desc"

        def orient(column):
            return column.desc().nullslast() if descending else column.asc().nullslast()

        if field == "title":
            primary = orient(OpportunityOrm.title)
        elif field == "country":
            primary = orient(OpportunityOrm.country)
        elif field == "source":
            primary = orient(OpportunityOrm.source)
        elif field == "deadline":
            deadline = func.coalesce(
                OpportunityOrm.application_deadline,
                OpportunityOrm.cfp_deadline,
            )
            primary = orient(deadline)
        elif field == "cost":
            # Funded rows first when descending; unspecified last.
            primary = orient(OpportunityOrm.funding)
        else:
            # when / default
            primary = orient(OpportunityOrm.start_date)
        return (primary, OpportunityOrm.id)

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
        stmt = self._filter_stmt(
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
        ).order_by(*self._order_by(sort))
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return self._select_all(stmt, _to_domain)

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
        base = self._filter_stmt(
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
        stmt = select(func.count()).select_from(base.subquery())
        with self._session_factory() as session:
            return int(session.scalar(stmt) or 0)

    def _apply_to_row(
        self,
        row: OpportunityOrm,
        opp: Opportunity,
        new_hash: str,
        now: datetime,
    ) -> UpsertResult:
        was_closed = row.status == "closed"
        new_status = opp.status or "open"
        if row.content_hash == new_hash and row.status == new_status:
            row.fetched_at = now
            return UpsertResult.UNCHANGED

        kind = opp.kind.value if isinstance(opp.kind, OpportunityKind) else str(opp.kind)
        row.kind = kind
        row.title = opp.title
        row.organization = opp.organization or ""
        row.url = opp.url or ""
        row.apply_url = opp.apply_url
        row.description = opp.description or ""
        row.topics = list(opp.topics or [])
        row.country = opp.country
        row.city = opp.city
        row.start_date = opp.start_date
        row.end_date = opp.end_date
        row.cfp_deadline = opp.cfp_deadline
        row.application_deadline = opp.application_deadline
        row.funding = opp.funding
        row.source_id = opp.source_id or ""
        row.content_hash = new_hash
        row.source_metadata = dict(opp.source_metadata or {})
        row.fetched_at = now
        row.status = new_status
        if was_closed and new_status == "open":
            return UpsertResult.REOPENED
        return UpsertResult.UPDATED

    def bulk_upsert(self, opportunities: list[Opportunity]) -> list[UpsertOutcome]:
        if not opportunities:
            return []
        now = datetime.now(timezone.utc)
        idents = [identity_key(o) for o in opportunities]
        with self._session_factory() as session:
            rows = session.scalars(
                select(OpportunityOrm).where(
                    OpportunityOrm.source.in_({o.source for o in opportunities}),
                    OpportunityOrm.identity_key.in_(idents),
                )
            ).all()
            by_key: dict[tuple[str, str], OpportunityOrm] = {
                (r.source, r.identity_key): r for r in rows
            }
            outcomes: list[UpsertOutcome] = []
            for opp, ident in zip(opportunities, idents):
                key = (opp.source, ident)
                row = by_key.get(key)
                if row is None:
                    orm = _to_orm(opp)
                    orm.fetched_at = now
                    session.add(orm)
                    by_key[key] = orm
                    outcomes.append(
                        UpsertOutcome(opportunity=opp, result=UpsertResult.INSERTED)
                    )
                    continue
                resolved = opp.model_copy(update={"id": row.id})
                result = self._apply_to_row(row, resolved, content_hash(resolved), now)
                outcomes.append(UpsertOutcome(opportunity=resolved, result=result))
            session.commit()
        return outcomes
