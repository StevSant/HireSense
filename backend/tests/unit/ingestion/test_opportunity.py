from hiresense.ingestion.domain.job_filter import JobQueryParams, filter_and_paginate
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.opportunity import (
    InternationalPathway,
    OpportunityType,
    classify_opportunity_type,
    international_pathways,
)


def _job(**overrides: object) -> NormalizedJob:
    values: dict[str, object] = {
        "id": "1",
        "title": "Software Engineer",
        "company": "Acme",
        "description": "Build useful software.",
        "source": "remotive",
        "source_type": "api",
        "url": "https://example.com/job",
    }
    values.update(overrides)
    return NormalizedJob(**values)


def test_internship_type_wins_over_generic_source_employment_type() -> None:
    assert (
        classify_opportunity_type("full_time", "Software Engineering Intern")
        == OpportunityType.INTERNSHIP
    )
    assert _job(
        employment_type="full_time", title="Software Engineering Intern"
    ).opportunity_type == ("internship")


def test_junior_role_without_explicit_employment_type_is_entry_level() -> None:
    assert classify_opportunity_type(None, "Junior Backend Engineer") == OpportunityType.ENTRY_LEVEL


def test_international_pathways_only_include_explicit_or_structured_routes() -> None:
    assert international_pathways(
        visa_sponsorship_available=True,
        remote_modality="on_site",
        countries=["United States"],
    ) == ["international", "visa_sponsorship"]
    assert international_pathways(
        visa_sponsorship_available=None,
        remote_modality="remote",
        countries=[],
    ) == ["international", "worldwide_remote"]
    assert (
        international_pathways(
            visa_sponsorship_available=None,
            remote_modality="on_site",
            countries=["United States"],
        )
        == []
    )


def test_filter_by_internship_and_international_pathway() -> None:
    jobs = [
        _job(id="intern", title="Software Engineering Intern", employment_type="full_time"),
        _job(
            id="sponsored",
            title="Software Engineer",
            visa_sponsorship_available=True,
            location="Berlin, Germany",
            remote_modality="on_site",
        ),
        _job(
            id="local",
            title="Software Engineer",
            location="New York, NY",
            remote_modality="on_site",
        ),
    ]

    internships = filter_and_paginate(
        jobs, JobQueryParams(opportunity_type=OpportunityType.INTERNSHIP)
    )
    assert [job.id for job in internships.jobs] == ["intern"]

    international = filter_and_paginate(
        jobs, JobQueryParams(international_pathway=InternationalPathway.INTERNATIONAL)
    )
    assert [job.id for job in international.jobs] == ["sponsored"]
