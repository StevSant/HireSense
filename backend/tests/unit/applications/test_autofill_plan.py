from __future__ import annotations

import uuid

import pytest

from hiresense.applications.domain.apply_service import ApplyService
from hiresense.profile.domain import CandidateProfile


class _Tracked:
    def __init__(self, url):
        self.url = url
        self.title = "Backend Engineer"
        self.company = "Acme"


class _Tracking:
    def __init__(self, by_id):
        self._by_id = by_id

    def get(self, app_id):
        if app_id not in self._by_id:
            raise ValueError("not found")
        return self._by_id[app_id]


class _Profile:
    def __init__(self, profile):
        self._profile = profile

    async def get_current_profile(self, language=None):
        return self._profile


def _svc(tracking, profile_service):
    return ApplyService(
        repository=None,
        cover_letter_generator=None,
        latex_compiler=None,
        profile_service=profile_service,
        tracking_service=tracking,
    )


def _profile():
    return CandidateProfile(id=str(uuid.uuid4()), name="Ada Lovelace", email="ada@example.com")


@pytest.mark.asyncio
async def test_autofill_plan_for_ats_job_returns_classification_and_fills():
    app_id = uuid.uuid4()
    svc = _svc(
        _Tracking({app_id: _Tracked("https://boards.greenhouse.io/acme/jobs/1")}),
        _Profile(_profile()),
    )

    plan = await svc.autofill_plan(app_id)

    assert plan.application_method == "ats_form"
    assert plan.ats_type == "greenhouse"
    assert plan.apply_url == "https://boards.greenhouse.io/acme/jobs/1"
    keys = {f.canonical_key for f in plan.fills}
    assert {"first_name", "last_name", "email"} <= keys


@pytest.mark.asyncio
async def test_autofill_plan_for_redirect_job_has_no_fills():
    app_id = uuid.uuid4()
    svc = _svc(
        _Tracking({app_id: _Tracked("https://remotive.com/remote-jobs/dev/1")}),
        _Profile(_profile()),
    )

    plan = await svc.autofill_plan(app_id)

    assert plan.application_method == "redirect"
    assert plan.ats_type is None
    assert plan.fills == []


@pytest.mark.asyncio
async def test_autofill_plan_missing_application_raises():
    svc = _svc(_Tracking({}), _Profile(_profile()))
    with pytest.raises(ValueError):
        await svc.autofill_plan(uuid.uuid4())


@pytest.mark.asyncio
async def test_autofill_plan_without_profile_returns_empty_fills():
    app_id = uuid.uuid4()
    svc = _svc(
        _Tracking({app_id: _Tracked("https://boards.greenhouse.io/acme/jobs/1")}),
        _Profile(None),
    )

    plan = await svc.autofill_plan(app_id)

    assert plan.application_method == "ats_form"
    assert plan.fills == []
