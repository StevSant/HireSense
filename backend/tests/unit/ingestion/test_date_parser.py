from __future__ import annotations

from datetime import datetime, timezone


from hiresense.ingestion.domain.date_parser import parse_iso_date


def test_parse_none_returns_none() -> None:
    assert parse_iso_date(None) is None


def test_parse_empty_string_returns_none() -> None:
    assert parse_iso_date("") is None
    assert parse_iso_date("   ") is None


def test_parse_date_only_string() -> None:
    result = parse_iso_date("2026-05-20")
    assert result == datetime(2026, 5, 20, tzinfo=timezone.utc)


def test_parse_iso_with_z_suffix() -> None:
    result = parse_iso_date("2026-05-20T12:30:00Z")
    assert result == datetime(2026, 5, 20, 12, 30, tzinfo=timezone.utc)


def test_parse_iso_with_offset() -> None:
    result = parse_iso_date("2026-05-20T12:30:00+00:00")
    assert result == datetime(2026, 5, 20, 12, 30, tzinfo=timezone.utc)


def test_parse_unix_epoch_seconds() -> None:
    result = parse_iso_date(1748776200)
    assert result is not None
    assert result.tzinfo is not None


def test_parse_garbage_string_returns_none() -> None:
    assert parse_iso_date("not a date") is None
    assert parse_iso_date("2026-99-99") is None


def test_parse_existing_datetime_adds_utc_if_naive() -> None:
    naive = datetime(2026, 5, 20, 12, 0)
    result = parse_iso_date(naive)
    assert result is not None
    assert result.tzinfo is not None


def test_parse_existing_datetime_preserves_tz() -> None:
    aware = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    result = parse_iso_date(aware)
    assert result is aware
