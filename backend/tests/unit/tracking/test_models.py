import uuid

from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication


def test_application_status_values() -> None:
    assert ApplicationStatus.SAVED == "saved"
    assert ApplicationStatus.APPLIED == "applied"
    assert ApplicationStatus.INTERVIEWING == "interviewing"
    assert ApplicationStatus.OFFERED == "offered"
    assert ApplicationStatus.ACCEPTED == "accepted"
    assert ApplicationStatus.REJECTED == "rejected"


def test_tracked_application_creation() -> None:
    app = TrackedApplication(
        title="Backend Engineer",
        company="Anthropic",
        url="https://example.com/job",
        status=ApplicationStatus.SAVED,
    )
    assert app.title == "Backend Engineer"
    assert app.company == "Anthropic"
    assert app.status == ApplicationStatus.SAVED
    assert app.job_id is None
    assert app.notes is None
    assert app.applied_at is None


def test_tracked_application_with_job_id() -> None:
    job_id = uuid.uuid4()
    app = TrackedApplication(
        job_id=job_id,
        title="ML Engineer",
        company="OpenAI",
        status=ApplicationStatus.APPLIED,
    )
    assert app.job_id == job_id


def test_tracked_application_default_status() -> None:
    app = TrackedApplication(title="SWE", company="Acme")
    assert app.status == ApplicationStatus.SAVED
