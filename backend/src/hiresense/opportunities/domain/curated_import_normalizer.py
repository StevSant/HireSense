from __future__ import annotations

from hiresense.opportunities.domain.cost import infer_attendance_cost
from hiresense.opportunities.domain.date_parser import parse_date
from hiresense.opportunities.domain.models import Opportunity, OpportunityKind, RawOpportunity
from hiresense.opportunities.domain.relevance import is_stale


_KIND_ALIASES = {
    "conference": OpportunityKind.CONFERENCE,
    "cfp": OpportunityKind.CFP,
    "grant": OpportunityKind.GRANT,
    "fellowship": OpportunityKind.FELLOWSHIP,
    "summer_school": OpportunityKind.SUMMER_SCHOOL,
    "summer-school": OpportunityKind.SUMMER_SCHOOL,
    "event": OpportunityKind.EVENT,
}


class CuratedImportNormalizer:
    """Map a curated YAML/JSONL opportunity record into an Opportunity."""

    def normalize(self, raw: RawOpportunity) -> Opportunity | None:
        data = raw.raw_data
        title = (data.get("title") or data.get("name") or "").strip()
        url = (data.get("url") or data.get("apply_url") or "").strip()
        if not title or not url:
            return None

        kind_raw = (data.get("kind") or data.get("type") or "event").strip().lower()
        kind = _KIND_ALIASES.get(kind_raw, OpportunityKind.EVENT)
        topics = data.get("topics") or data.get("tags") or []
        if isinstance(topics, str):
            topics = [t.strip() for t in topics.split(",") if t.strip()]
        else:
            topics = [str(t).strip() for t in topics if str(t).strip()]

        opp = Opportunity(
            kind=kind,
            title=title,
            organization=(data.get("organization") or data.get("organizer") or "").strip(),
            url=url,
            apply_url=(data.get("apply_url") or data.get("application_url") or "").strip() or None,
            description=(data.get("description") or "").strip(),
            topics=topics,
            country=(data.get("country") or "").strip() or None,
            city=(data.get("city") or "").strip() or None,
            start_date=parse_date(data.get("start_date") or data.get("startDate")),
            end_date=parse_date(data.get("end_date") or data.get("endDate")),
            cfp_deadline=parse_date(data.get("cfp_deadline") or data.get("cfpEndDate")),
            application_deadline=parse_date(
                data.get("application_deadline") or data.get("deadline")
            ),
            funding=(data.get("funding") or "").strip() or None,
            source=raw.source,
            source_id=raw.source_id,
            source_metadata={
                k: v
                for k, v in {
                    **{
                        meta_key: data.get(meta_key)
                        for meta_key in (
                            "notes",
                            "coverage",
                            "eligibility",
                            "location_notes",
                            "source_page",
                        )
                    },
                    "attendance_cost": infer_attendance_cost(
                        title=title,
                        description=(data.get("description") or "").strip(),
                        url=url,
                        apply_url=(data.get("apply_url") or data.get("application_url") or None),
                        funding=(data.get("funding") or None),
                        kind=kind.value,
                    ),
                }.items()
                if v
            },
        )
        if is_stale(opp):
            opp = opp.model_copy(update={"status": "closed"})
        return opp

