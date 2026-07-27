from __future__ import annotations

import hashlib

from hiresense.opportunities.domain.models import Opportunity


def identity_key(opp: Opportunity) -> str:
    """Stable identity: source_id (hashed if >64 chars) else sha256(url)."""
    if opp.source_id:
        if len(opp.source_id) <= 64:
            return opp.source_id
        return hashlib.sha256(opp.source_id.encode("utf-8")).hexdigest()
    return hashlib.sha256((opp.url or "").encode("utf-8")).hexdigest()
