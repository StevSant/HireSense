from __future__ import annotations

import pytest

from hiresense.ingestion.domain import classify_application
from hiresense.ingestion.domain.application_method import ApplicationMethod


@pytest.mark.parametrize(
    "url,expected_ats",
    [
        ("https://boards.greenhouse.io/gitlab/jobs/123", "greenhouse"),
        ("https://job-boards.greenhouse.io/gitlab/jobs/123", "greenhouse"),
        ("https://boards.eu.greenhouse.io/acme/jobs/9", "greenhouse"),
        ("https://jobs.lever.co/mistral/abc-def", "lever"),
        ("https://jobs.ashbyhq.com/openai/uuid", "ashby"),
        ("https://apply.workable.com/acme/j/ABC123", "workable"),
        ("https://jobs.smartrecruiters.com/Visa/744000", "smartrecruiters"),
        ("https://company.recruitee.com/o/backend-engineer", "recruitee"),
    ],
)
def test_known_ats_url_is_classified_as_ats_form(url: str, expected_ats: str) -> None:
    result = classify_application(url)

    assert result.application_method == ApplicationMethod.ATS_FORM
    assert result.ats_type == expected_ats
    assert result.apply_url == url


def test_portal_platform_overrides_when_url_is_generic() -> None:
    # A portal job whose hosted URL is not on a recognisable ATS host still gets
    # classified from its configured platform.
    result = classify_application(
        "https://careers.acme.com/jobs/42", platform="greenhouse"
    )

    assert result.application_method == ApplicationMethod.ATS_FORM
    assert result.ats_type == "greenhouse"
    assert result.apply_url == "https://careers.acme.com/jobs/42"


def test_aggregator_url_is_a_redirect() -> None:
    result = classify_application("https://remotive.com/remote-jobs/dev/123")

    assert result.application_method == ApplicationMethod.REDIRECT
    assert result.ats_type is None
    assert result.apply_url is None


def test_unrecognised_platform_falls_back_to_url_detection() -> None:
    result = classify_application(
        "https://jobs.lever.co/acme/x", platform="not-a-real-ats"
    )

    assert result.application_method == ApplicationMethod.ATS_FORM
    assert result.ats_type == "lever"


@pytest.mark.parametrize("url", ["", None])
def test_missing_url_is_unknown(url: str | None) -> None:
    result = classify_application(url)

    assert result.application_method == ApplicationMethod.UNKNOWN
    assert result.ats_type is None
    assert result.apply_url is None


def test_lookalike_host_is_not_a_false_positive() -> None:
    # "notgreenhouse.io" must not match the "greenhouse.io" suffix.
    result = classify_application("https://notgreenhouse.io/jobs/1")

    assert result.application_method == ApplicationMethod.REDIRECT
    assert result.ats_type is None
