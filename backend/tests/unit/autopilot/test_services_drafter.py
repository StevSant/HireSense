import uuid

import pytest

from hiresense.autopilot.domain import DraftStatus
from hiresense.autopilot.infrastructure import ServicesApplicationDrafter


class _Agg:
    def __init__(self): self.id = uuid.uuid4()


class _Match:
    def __init__(self): self.id = uuid.uuid4()


class _AppSvc:
    def __init__(self, agg=None, raise_exc=None):
        self._agg = agg or _Agg()
        self._raise = raise_exc
    async def create_from_ingested(self, job_id):
        if self._raise: raise self._raise
        return self._agg


class _ArtifactSvc:
    def __init__(self, opt_raise=None):
        self.calls = []
        self._opt_raise = opt_raise
    async def generate_match(self, application_id, cv_language=""):
        self.calls.append("match"); return _Match()
    async def generate_optimization(self, application_id, cv_language="", match_id=None):
        self.calls.append("optimize")
        if self._opt_raise: raise self._opt_raise


class _ApplySvc:
    def __init__(self): self.calls = []
    async def generate_cover_letter(self, application_id, cv_language="", tone=None):
        self.calls.append("cover")


def _drafter(app_svc, artifact_svc, apply_svc):
    return ServicesApplicationDrafter(
        application_service=app_svc, artifact_service=artifact_svc,
        apply_service=apply_svc, cv_language="en",
    )


@pytest.mark.asyncio
async def test_full_success_is_drafted():
    art = _ArtifactSvc(); apply = _ApplySvc()
    app_id, status, detail = await _drafter(_AppSvc(), art, apply).draft("j1")
    assert status is DraftStatus.DRAFTED
    assert app_id is not None
    assert art.calls == ["match", "optimize"]
    assert apply.calls == ["cover"]


@pytest.mark.asyncio
async def test_create_failure_is_failed():
    app_id, status, detail = await _drafter(
        _AppSvc(raise_exc=ValueError("Job not found")), _ArtifactSvc(), _ApplySvc()).draft("j1")
    assert status is DraftStatus.FAILED
    assert app_id is None
    assert "not found" in (detail or "").lower()


@pytest.mark.asyncio
async def test_artifact_failure_after_create_is_partial():
    app_id, status, detail = await _drafter(
        _AppSvc(), _ArtifactSvc(opt_raise=RuntimeError("LLM down")), _ApplySvc()).draft("j1")
    assert status is DraftStatus.PARTIAL
    assert app_id is not None  # application kept
