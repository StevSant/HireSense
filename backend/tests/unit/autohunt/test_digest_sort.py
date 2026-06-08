from __future__ import annotations

from hiresense.autohunt.infrastructure.repository import _digest_order_by


def test_default_and_invalid_fall_back_to_created_desc() -> None:
    assert "created_at DESC" in str(_digest_order_by(None))
    assert "created_at DESC" in str(_digest_order_by("bogus_desc"))
    assert "created_at DESC" in str(_digest_order_by("count_sideways"))


def test_created_and_count_sorts() -> None:
    assert "created_at ASC" in str(_digest_order_by("created_asc"))
    assert "job_count DESC" in str(_digest_order_by("count_desc"))
    assert "job_count ASC" in str(_digest_order_by("count_asc"))
