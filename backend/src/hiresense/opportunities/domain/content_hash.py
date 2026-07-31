from __future__ import annotations

import hashlib

from hiresense.opportunities.domain.models import Opportunity


def content_hash(opp: Opportunity) -> str:
    """sha256 over mutable human-facing fields that define 'has this changed?'."""
    parts = [
        opp.kind.value if hasattr(opp.kind, "value") else str(opp.kind),
        opp.title.strip(),
        (opp.organization or "").strip(),
        (opp.description or "").strip(),
        (opp.url or "").strip(),
        (opp.apply_url or "").strip(),
        (opp.country or "").strip(),
        (opp.city or "").strip(),
        (opp.funding or "").strip(),
        str(opp.start_date or ""),
        str(opp.end_date or ""),
        str(opp.cfp_deadline or ""),
        str(opp.application_deadline or ""),
        "|".join(sorted(t.strip().lower() for t in opp.topics)),
    ]
    raw = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
