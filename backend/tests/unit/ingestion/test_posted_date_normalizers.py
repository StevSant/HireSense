"""Regression: previously Remotive/RemoteOK/LinkedIn didn't surface posted_date,
so the ingestion table showed '—' for every job.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizer import RemoteOKNormalizer, RemotiveNormalizer
from hiresense.ingestion.domain.normalizers.linkedin_normalizer import LinkedInNormalizer


def _raw(data: dict) -> RawJobListing:
    return RawJobListing(source="x", source_id="1", raw_data=data)


def test_remotive_parses_publication_date() -> None:
    raw = _raw({"publication_date": "2026-03-28T12:00:00", "title": "x"})
    result = RemotiveNormalizer().normalize(raw)
    assert result["posted_date"] == datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)


def test_remotive_handles_missing_publication_date() -> None:
    raw = _raw({"title": "x"})
    result = RemotiveNormalizer().normalize(raw)
    assert result["posted_date"] is None


def test_remoteok_parses_date_field() -> None:
    raw = _raw({"position": "x", "date": "2026-03-27T10:00:00"})
    result = RemoteOKNormalizer().normalize(raw)
    assert result["posted_date"] == datetime(2026, 3, 27, 10, 0, tzinfo=timezone.utc)


def test_remoteok_handles_missing_date() -> None:
    raw = _raw({"position": "x"})
    result = RemoteOKNormalizer().normalize(raw)
    assert result["posted_date"] is None


def test_linkedin_parses_date_only_format() -> None:
    raw = _raw({"posted_date": "2026-05-20"})
    result = LinkedInNormalizer().normalize(raw)
    assert result["posted_date"] == datetime(2026, 5, 20, tzinfo=timezone.utc)


def test_linkedin_parses_iso_with_z_suffix() -> None:
    raw = _raw({"posted_date": "2026-05-20T08:00:00Z"})
    result = LinkedInNormalizer().normalize(raw)
    assert result["posted_date"] == datetime(2026, 5, 20, 8, 0, tzinfo=timezone.utc)


def test_linkedin_handles_empty_date() -> None:
    raw = _raw({"posted_date": ""})
    result = LinkedInNormalizer().normalize(raw)
    assert result["posted_date"] is None
