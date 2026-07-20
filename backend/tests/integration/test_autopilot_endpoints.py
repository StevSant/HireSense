import asyncio
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
    def __init__(self):
        self.added = []

    def add(self, d):
        d.id = uuid.uuid4()
        self.added.append(d)
        return d

    def claim(self, d):
        if any(x.job_id == d.job_id for x in self.added):
            return None
        return self.add(d)

    def finalize(self, d):
        for i, x in enumerate(self.added):
            if x.id == d.id:
                self.added[i] = d
                return d
        raise RuntimeError(f"draft {d.id} was never claimed")

    def list(self, limit):
        return self.added[:limit]

    def exists_for_job(self, job_id):
        return False


class _Drafter:
    async def draft(self, job_id):
        return uuid.uuid4(), DraftStatus.DRAFTED, None


class _GatedDrafter:
    """Blocks inside draft() until `release` is set, so a test can hold a run
    open long enough to exercise the concurrent-run-now rejection."""

    def __init__(self):
        self.release = asyncio.Event()
        self.entered = asyncio.Event()

    async def draft(self, job_id):
        self.entered.set()
        await self.release.wait()
        return uuid.uuid4(), DraftStatus.DRAFTED, None


def _build_app(drafter=None):
    repo = _Repo()
    service = AutopilotPipelineService(
        latest_digest=lambda: type("D", (), {"entries": [_Entry("j1")]})(),
        drafter=drafter or _Drafter(),
        repo=repo,
        top_n=3,
    )
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "u"
    app.dependency_overrides[require_admin] = lambda: {"role": "admin"}
    app.dependency_overrides[get_autopilot_provider] = lambda: AutopilotProvider(
        service=service, repo=repo
    )
    app.include_router(autopilot_router)
    return app, repo, service


@pytest.mark.asyncio
async def test_run_now_returns_202_and_drafts_in_background():
    app, repo, service = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        run = await client.post("/autopilot/run")
        assert run.status_code == 202
        assert run.json() == {"status": "started"}

        # The background task was scheduled via create_task, not awaited by
        # the request; give the event loop turns so it can run to completion.
        # The claim-first flow inserts a PENDING reservation before drafting,
        # so wait for the row to be finalized, not merely present.
        for _ in range(50):
            if (
                repo.added
                and repo.added[0].status is not DraftStatus.PENDING
                and not service.is_running
            ):
                break
            await asyncio.sleep(0.01)
        assert repo.added, "background run never completed"
        assert repo.added[0].status is DraftStatus.DRAFTED
        assert not service.is_running

        lst = await client.get("/autopilot/drafts")
        assert lst.status_code == 200
        assert len(lst.json()) == 1
        assert lst.json()[0]["status"] == "drafted"


@pytest.mark.asyncio
async def test_run_now_rejects_concurrent_second_call():
    drafter = _GatedDrafter()
    app, repo, service = _build_app(drafter=drafter)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        first = await client.post("/autopilot/run")
        assert first.status_code == 202

        await drafter.entered.wait()  # first run is now genuinely in flight

        second = await client.post("/autopilot/run")
        assert second.status_code == 409
        assert second.json() == {"status": "already_running"}

        drafter.release.set()
        for _ in range(50):
            if repo.added:
                break
            await asyncio.sleep(0.01)
        assert len(repo.added) == 1

        # Once the first run has finished, the guard is free again.
        third = await client.post("/autopilot/run")
        assert third.status_code in (202, 409)
