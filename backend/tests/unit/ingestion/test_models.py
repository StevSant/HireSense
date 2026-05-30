from datetime import datetime, timezone

from hiresense.ingestion.domain.models import NormalizedJob, RawJobListing


def test_raw_job_listing_creation() -> None:
    raw = RawJobListing(
        source="remotive",
        source_id="123",
        raw_data={"title": "Backend Engineer", "company": "Acme"},
    )
    assert raw.source == "remotive"
    assert raw.raw_data["title"] == "Backend Engineer"


def test_normalized_job_from_raw() -> None:
    job = NormalizedJob(
        id="job-1",
        title="Backend Engineer",
        company="Acme Corp",
        description="Build scalable APIs with FastAPI",
        skills=["python", "fastapi", "postgresql"],
        location="Remote",
        salary_range="$80k-$120k",
        source="remotive",
        source_type="api",
        language="en",
        url="https://example.com/job/1",
        posted_date=datetime(2026, 3, 30, tzinfo=timezone.utc),
    )
    assert job.title == "Backend Engineer"
    assert "fastapi" in job.skills


def test_normalized_job_has_platform_and_categories() -> None:
    job = NormalizedJob(
        id="job-2",
        title="AI Researcher",
        company="DeepMind",
        description="Research on large language models",
        source="greenhouse",
        source_type="portal",
        language="en",
        url="https://boards.greenhouse.io/deepmind/jobs/2",
        platform="greenhouse",
        categories=["ai-research"],
    )
    assert job.platform == "greenhouse"
    assert job.categories == ["ai-research"]


def test_normalized_job_defaults_platform_and_categories() -> None:
    job = NormalizedJob(
        id="job-3",
        title="Backend Engineer",
        company="Acme Corp",
        description="Build APIs",
        source="remotive",
        source_type="api",
        language="en",
        url="https://example.com/job/3",
    )
    assert job.platform is None
    assert job.categories == []


def test_normalized_job_deduplication_key() -> None:
    job = NormalizedJob(
        id="job-1",
        title="Backend Engineer",
        company="Acme Corp",
        description="Build APIs",
        skills=[],
        location="Remote",
        source="remotive",
        source_type="api",
        language="en",
        url="https://example.com/job/1",
    )
    key = job.dedup_key()
    assert isinstance(key, str)
    assert len(key) > 0


def test_normalized_job_lifecycle_field_defaults() -> None:
    job = NormalizedJob(
        id="1", title="T", company="C", description="D",
        source="remotive", source_type="api", url="https://e.com/1",
    )
    assert job.source_id is None
    assert job.status == "open"
