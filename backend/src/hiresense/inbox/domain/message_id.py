from __future__ import annotations

import hashlib
from datetime import datetime

_SYNTHETIC_PREFIX = "synthesized:"


def synthesize_message_id(
    *,
    from_address: str,
    subject: str,
    received_at: datetime,
    body: str,
) -> str:
    """Derive a stable dedup key for an email that arrived without a Message-ID.

    Header-less emails must not all collapse onto the empty-string key (which
    would let the first one poison the unique index and silently drop every
    later one). Hashing the sender, subject, receipt time and body yields an id
    that is unique per distinct message yet stable for the same message across
    re-fetches, so genuine dedup still works.
    """
    digest = hashlib.sha256(
        "\x00".join((from_address, subject, received_at.isoformat(), body)).encode("utf-8")
    ).hexdigest()
    return f"{_SYNTHETIC_PREFIX}{digest}"
