import uuid
from datetime import datetime, timezone

import pytest

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
    )
    assert resp.status == ApplicationStatus.SAVED
    assert resp.job_id is None
