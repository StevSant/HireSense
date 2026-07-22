import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from hiresense.tracking.api.schemas import (
    CreateApplicationRequest,
    TrackedApplicationResponse,
    UpdateApplicationRequest,
)
from hiresense.tracking.domain.models import ApplicationStatus


def test_create_request_with_job_id() -> None:
    req = CreateApplicationRequest(job_id=uuid.uuid4())
    assert req.job_id is not None
    assert req.title is None


def test_create_request_manual() -> None:
    req = CreateApplicationRequest(title="SWE", company="Acme", url="https://example.com")
    assert req.title == "SWE"
    assert req.company == "Acme"
    assert req.job_id is None


def test_update_request_status_only() -> None:
    req = UpdateApplicationRequest(status=ApplicationStatus.APPLIED)
    assert req.status == ApplicationStatus.APPLIED
    assert req.notes is None


def test_update_request_notes_only() -> None:
    req = UpdateApplicationRequest(notes="Great interview")
    assert req.notes == "Great interview"
    assert req.status is None


def test_create_request_normalizes_onsite_alias() -> None:
    req = CreateApplicationRequest(
        title="SWE",
        company="Acme",
        remote_modality="onsite",
        salary_range="USD 1,500/mo",
    )

    assert req.remote_modality == "on_site"
    assert req.salary_range == "USD 1,500/mo"


def test_update_request_tracks_explicit_null_for_clearing() -> None:
    req = UpdateApplicationRequest(location=None)

    assert "location" in req.model_fields_set
    assert req.model_dump(exclude_unset=True) == {"location": None}


@pytest.mark.parametrize("field", ["title", "company"])
def test_update_request_rejects_blank_or_null_required_identity(field: str) -> None:
    with pytest.raises(ValidationError):
        UpdateApplicationRequest(**{field: "   "})
    with pytest.raises(ValidationError):
        UpdateApplicationRequest(**{field: None})


def test_update_request_rejects_invalid_remote_modality() -> None:
    with pytest.raises(ValidationError):
        UpdateApplicationRequest(remote_modality="sometimes")


def test_response_model() -> None:
    now = datetime.now(timezone.utc)
    resp = TrackedApplicationResponse(
        id=uuid.uuid4(),
        job_id=None,
        title="SWE",
        company="Acme",
        url=None,
        status=ApplicationStatus.SAVED,
        notes=None,
        applied_at=None,
        created_at=now,
        updated_at=now,
        location="Quito",
        remote_modality="remote",
        salary_range="USD 1,500/mo",
        source="Referral",
        posted_date=now,
    )
    assert resp.status == ApplicationStatus.SAVED
    assert resp.job_id is None
    assert resp.remote_modality == "remote"
