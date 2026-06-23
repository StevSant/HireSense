import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.autopilot.api import router as autopilot_router
from hiresense.autopilot.api.dependencies import get_autopilot_provider
from hiresense.autopilot.api.provider import AutopilotProvider
from hiresense.autopilot.domain import AutopilotPipelineService, DraftStatus
from hiresense.identity.api.dependencies import require_admin, require_auth


class _Entry:
    def __init__(self, job_id):
        self.job_id = job_id
        self.title = "Dev"
        self.company = "Acme"


class _Repo:
    def __init__(self): self.added = []

    def add(self, d):
        d.id = uuid.uuid4()
        self.added.append(d)
        return d

    def list(self, limit): return self.added[:limit]
    def exists_for_job(self, job_id): return False


class _Drafter:
    async def draft(self, job_id): return uuid.uuid4(), DraftStatus.DRAFTED, None


def _build_app():
    repo = _Repo()
    service = AutopilotPipelineService(
        latest_digest=lambda: type("D", (), {"entries": [_Entry("j1")]})(),
        drafter=_Drafter(), repo=repo, top_n=3,
    )
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "u"
    app.dependency_overrides[require_admin] = lambda: {"role": "admin"}
    app.dependency_overrides[get_autopilot_provider] = lambda: AutopilotProvider(service=service, repo=repo)
    app.include_router(autopilot_router)
    return app, repo


@pytest.mark.asyncio
async def test_run_then_list():
    app, repo = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        run = await client.post("/autopilot/run")
        assert run.status_code == 200
        assert run.json()["created"] == 1
        lst = await client.get("/autopilot/drafts")
        assert lst.status_code == 200
        assert len(lst.json()) == 1
        assert lst.json()[0]["status"] == "drafted"
