from __future__ import annotations

from hiresense.ingestion.domain import is_dead_end_redirect

MARKERS = ["trk=expired_jd_redirect"]


def test_redirect_to_site_root_is_a_dead_end() -> None:
    assert is_dead_end_redirect("https://e.com/remote-jobs/x", "https://e.com/", MARKERS)


def test_root_without_trailing_slash_is_a_dead_end() -> None:
    assert is_dead_end_redirect("https://e.com/remote-jobs/x", "https://e.com", MARKERS)


def test_configured_marker_is_a_dead_end_even_on_a_real_path() -> None:
    assert is_dead_end_redirect(
        "https://e.com/jobs/view/x",
        "https://e.com/jobs/java-jobs?trk=expired_jd_redirect",
        MARKERS,
    )


def test_canonical_rewrite_is_not_a_dead_end() -> None:
    """A tidier URL for the same live listing must never close the job."""
    assert not is_dead_end_redirect(
        "https://e.com/jobs/x", "https://e.com/jobs/programming/x", MARKERS
    )


def test_another_listing_path_is_not_a_dead_end() -> None:
    assert not is_dead_end_redirect("https://e.com/jobs/x", "https://e.com/jobs/y", MARKERS)


def test_identical_url_is_not_a_dead_end() -> None:
    assert not is_dead_end_redirect("https://e.com/jobs/x", "https://e.com/jobs/x", MARKERS)


def test_probe_that_started_at_the_root_has_no_listing_to_lose() -> None:
    """Without this guard, a source whose job URL *is* the site root would be
    closed wholesale on any redirect."""
    assert not is_dead_end_redirect("https://e.com/", "https://e.com/es/", MARKERS)


def test_empty_markers_still_detect_a_root_redirect() -> None:
    assert is_dead_end_redirect("https://e.com/jobs/x", "https://e.com/", [])


def test_missing_urls_are_not_a_dead_end() -> None:
    assert not is_dead_end_redirect("", "https://e.com/", MARKERS)
    assert not is_dead_end_redirect("https://e.com/jobs/x", "", MARKERS)
