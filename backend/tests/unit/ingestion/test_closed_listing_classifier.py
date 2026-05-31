from __future__ import annotations

from hiresense.ingestion.domain.closed_listing_classifier import (
    Verdict,
    classify_listing,
)

MARKERS = [
    "no longer accepting",
    "position has been filled",
    "this job is closed",
    "ya no está disponible",
]


def test_404_is_closed() -> None:
    assert classify_listing(status_code=404, body="", markers=MARKERS) == Verdict.CLOSED


def test_410_is_closed() -> None:
    assert classify_listing(status_code=410, body="x", markers=MARKERS) == Verdict.CLOSED


def test_200_with_marker_is_closed() -> None:
    body = "<h1>This Job Is Closed</h1>"
    assert classify_listing(status_code=200, body=body, markers=MARKERS) == Verdict.CLOSED


def test_200_with_spanish_marker_is_closed() -> None:
    body = "<p>Esta oferta YA NO ESTÁ DISPONIBLE.</p>"
    assert classify_listing(status_code=200, body=body, markers=MARKERS) == Verdict.CLOSED


def test_200_plain_is_open() -> None:
    assert classify_listing(status_code=200, body="Apply now!", markers=MARKERS) == Verdict.OPEN


def test_5xx_is_unknown() -> None:
    assert classify_listing(status_code=503, body="", markers=MARKERS) == Verdict.UNKNOWN


def test_empty_markers_keeps_200_open() -> None:
    assert classify_listing(status_code=200, body="filled", markers=[]) == Verdict.OPEN
