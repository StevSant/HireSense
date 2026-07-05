"""Himalayas exposes per-job unix timestamps: `pubDate` (posted) and
`expiryDate`. The latter drives expiry-based closure since its public listing
pages block URL probes (403), so the normalizer must surface both.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import HimalayasNormalizer


def _raw(data: dict) -> RawJobListing:
    return RawJobListing(source="himalayas", source_id="1", raw_data=data)


def test_parses_pubdate_and_expirydate_unix_timestamps() -> None:
    # 2026-07-04T00:00:00Z and one day later, as unix seconds.
    posted = int(datetime(2026, 7, 4, tzinfo=timezone.utc).timestamp())
    expiry = int(datetime(2026, 7, 5, tzinfo=timezone.utc).timestamp())
    result = HimalayasNormalizer().normalize(
        _raw({"title": "x", "pubDate": posted, "expiryDate": expiry})
    )
    assert result["posted_date"] == datetime(2026, 7, 4, tzinfo=timezone.utc)
    assert result["expiry_date"] == datetime(2026, 7, 5, tzinfo=timezone.utc)


def test_missing_expirydate_is_none() -> None:
    result = HimalayasNormalizer().normalize(_raw({"title": "x"}))
    assert result["expiry_date"] is None
    assert result["posted_date"] is None


def test_unparseable_timestamp_is_none_not_error() -> None:
    result = HimalayasNormalizer().normalize(_raw({"title": "x", "expiryDate": "not-a-date"}))
    assert result["expiry_date"] is None
