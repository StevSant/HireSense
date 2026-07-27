from __future__ import annotations

from datetime import date

from hiresense.opportunities.domain.cost import infer_attendance_cost
from hiresense.opportunities.domain.date_parser import parse_date
from hiresense.opportunities.domain.models import Opportunity, OpportunityKind, RawOpportunity
from hiresense.opportunities.domain.relevance import is_stale


class ConfsTechNormalizer:
    """Map a confs.tech conference JSON record into an Opportunity."""

    def normalize(self, raw: RawOpportunity) -> Opportunity | None:
        data = raw.raw_data
        name = (data.get("name") or "").strip()
        url = (data.get("url") or "").strip()
        if not name or not url:
            return None

        cfp_url = (data.get("cfpUrl") or data.get("cfp_url") or "").strip() or None
        cfp_end = parse_date(data.get("cfpEndDate") or data.get("cfp_end_date"))
        # Still a conference; CFP means it currently accepts speaker/paper submissions.
        kind = OpportunityKind.CFP if cfp_url or cfp_end else OpportunityKind.CONFERENCE
        topic = (data.get("topic") or "").strip()
        topics = [topic] if topic else []
        for extra in data.get("topics") or []:
            if isinstance(extra, str) and extra.strip() and extra.strip() not in topics:
                topics.append(extra.strip())

        city = (data.get("city") or "").strip() or None
        country = (data.get("country") or "").strip() or None
        online = bool(data.get("online"))
        locales = data.get("locales")
        if isinstance(locales, list):
            locales_text = ", ".join(str(x) for x in locales if x)
        else:
            locales_text = str(locales).strip() if locales else ""

        description = self._build_description(
            kind=kind, topic=topic, cfp_end=cfp_end, has_cfp=bool(cfp_url or cfp_end)
        )
        attendance_cost = infer_attendance_cost(
            title=name,
            description=description,
            url=url,
            apply_url=cfp_url,
            kind=kind.value,
        )

        start_date = parse_date(data.get("startDate") or data.get("start_date"))
        end_date = parse_date(data.get("endDate") or data.get("end_date"))
        opp = Opportunity(
            kind=kind,
            title=name,
            organization="",
            url=url,
            apply_url=cfp_url,
            description=description,
            topics=topics,
            country=country,
            city=city,
            start_date=start_date,
            end_date=end_date,
            cfp_deadline=cfp_end,
            application_deadline=None,
            funding=None,
            source=raw.source,
            source_id=raw.source_id,
            source_metadata={
                k: v
                for k, v in {
                    "twitter": data.get("twitter"),
                    "bluesky": data.get("bluesky"),
                    "mastodon": data.get("mastodon"),
                    "cocUrl": data.get("cocUrl"),
                    "offersSignLanguageOrCC": data.get("offersSignLanguageOrCC"),
                    "online": online,
                    "locales": locales_text or None,
                    "year": data.get("year"),
                    "attendance_cost": attendance_cost,
                    "has_cfp": bool(cfp_url or cfp_end),
                }.items()
                if v not in (None, "", False)
            },
        )
        if is_stale(opp, today=date.today()):
            opp = opp.model_copy(update={"status": "closed"})
            # Past CFP links 404 often — keep the conference site as the useful URL.
            if opp.apply_url and (opp.cfp_deadline or opp.application_deadline):
                opp = opp.model_copy(update={"apply_url": None})
        return opp

    @staticmethod
    def _build_description(
        *,
        kind: OpportunityKind,
        topic: str,
        cfp_end: date | None,
        has_cfp: bool,
    ) -> str:
        focus = f" focused on {topic}" if topic and topic != "general" else ""
        if has_cfp or kind == OpportunityKind.CFP:
            base = f"Conference with an open call for papers/speakers{focus}"
            if cfp_end:
                return f"{base}. Submission deadline {cfp_end.isoformat()}."
            return f"{base}."
        return f"Conference{focus}."
