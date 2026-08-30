"""Apply-access: can a candidate actually reach the application form?"""

from __future__ import annotations

import pytest

from hiresense.ingestion.domain.apply_access import ApplyAccess
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.source_capabilities import (
    SOURCE_CAPABILITY_REGISTRY,
    source_apply_access,
    source_apply_access_note,
)
from hiresense.shared.config.groups import IngestionSettings


def _job(source: str, **overrides) -> NormalizedJob:
    return NormalizedJob(
        id="job-1",
        source=source,
        source_type="api",
        title="Engineer",
        company="Acme",
        description="d",
        url="https://board.example/jobs/1",
        **overrides,
    )


def test_no_registered_source_requires_a_paid_subscription() -> None:
    assert all(
        caps.apply_access is not ApplyAccess.PAID_REQUIRED
        for caps in SOURCE_CAPABILITY_REGISTRY.values()
    )


def test_no_paid_apply_source_is_enabled_by_default() -> None:
    default_sources = IngestionSettings.model_fields["enabled_job_sources"].default

    assert isinstance(default_sources, list)
    assert all(
        source_apply_access(source) is not ApplyAccess.PAID_REQUIRED for source in default_sources
    )


@pytest.mark.parametrize(
    "source", ["weworkremotely", "himalayas", "getonboard", "linkedin", "yc_jobs"]
)
def test_boards_that_wall_apply_behind_a_free_signup(source: str) -> None:
    assert source_apply_access(source) is ApplyAccess.ACCOUNT_REQUIRED
    assert source_apply_access_note(source), f"{source} needs a note for the UI"


@pytest.mark.parametrize("source", ["remotive", "themuse", "arbeitnow", "hn_hiring", "dice"])
def test_boards_whose_apply_hop_reaches_the_employer(source: str) -> None:
    assert source_apply_access(source) is ApplyAccess.DIRECT


def test_unregistered_source_is_unknown_rather_than_falsely_direct() -> None:
    assert source_apply_access("some-board-we-never-audited") is ApplyAccess.UNKNOWN
    assert source_apply_access_note("some-board-we-never-audited") == ""


def test_every_walled_source_explains_itself() -> None:
    """A warning with no note gives the user nothing to act on."""
    for caps in SOURCE_CAPABILITY_REGISTRY.values():
        if caps.apply_access in (ApplyAccess.PAID_REQUIRED, ApplyAccess.ACCOUNT_REQUIRED):
            assert caps.apply_access_note, f"{caps.source} is walled but has no note"


def test_job_exposes_apply_access_from_its_source() -> None:
    payload = _job("weworkremotely").model_dump(mode="json")

    assert payload["apply_access"] == "account_required"
    assert payload["apply_access_note"]


def test_preferred_apply_url_falls_back_to_the_listing_page() -> None:
    assert _job("remotive").preferred_apply_url == "https://board.example/jobs/1"


def test_preferred_apply_url_uses_a_board_supplied_direct_apply_url() -> None:
    job = _job(
        "arbeitnow",
        source_metadata={"application_url": "https://board.example/jobs/1/apply"},
    )

    assert job.preferred_apply_url == "https://board.example/jobs/1/apply"


def test_a_confirmed_ats_form_beats_a_board_supplied_url() -> None:
    job = _job(
        "arbeitnow",
        apply_url="https://job-boards.greenhouse.io/acme/jobs/9",
        source_metadata={"application_url": "https://board.example/jobs/1/apply"},
    )

    assert job.preferred_apply_url == "https://job-boards.greenhouse.io/acme/jobs/9"


def test_non_string_metadata_does_not_break_the_apply_url() -> None:
    job = _job("arbeitnow", source_metadata={"application_url": 42})

    assert job.preferred_apply_url == "https://board.example/jobs/1"


def test_crunchboard_is_disabled_because_its_feed_is_dead() -> None:
    caps = SOURCE_CAPABILITY_REGISTRY["crunchboard"]

    assert caps.enabled_by_default is False
    assert "jobboard.io" in caps.limitations
