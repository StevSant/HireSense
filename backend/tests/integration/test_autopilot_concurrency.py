import asyncio
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.autopilot.domain import AutopilotPipelineService, DraftStatus
from hiresense.autopilot.infrastructure import AutopilotDraftOrm, DraftRepositoryImpl  # noqa: F401
from hiresense.infrastructure.database import Base


class _Entry:
    def __init__(self, job_id):
        self.job_id = job_id
        self.title = "Dev"
        self.company = "Acme"


class _Digest:
    def __init__(self, entries):
        self.entries = entries


def _shared_repo(tmp_path):
    # A real file (not :memory:) so the two contending threads get distinct
    # connections and the unique index is enforced across them. The busy
    # timeout makes a lost write wait for the winner instead of erroring.
    url = f"sqlite:///{tmp_path / 'autopilot.sqlite'}"
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
    Base.metadata.create_all(engine)
    return DraftRepositoryImpl(session_factory=sessionmaker(bind=engine, expire_on_commit=False))


@pytest.mark.asyncio
async def test_concurrent_scheduled_and_manual_runs_draft_once(tmp_path):
    """A scheduled run() and a manual run-now (try_start + run_claimed) fire at
    the same instant against the same job. Two separate service instances defeat
    the in-process guard, leaving only the DB unique constraint to stop the
    duplicate. Exactly one draft row must exist and the expensive drafter must
    run exactly once (the loser skips before any LLM spend)."""
    repo = _shared_repo(tmp_path)

    draft_calls: list[str] = []

    class _CountingDrafter:
        async def draft(self, job_id):
            draft_calls.append(job_id)
            await asyncio.sleep(0.05)  # widen the TOCTOU window
            return uuid.uuid4(), DraftStatus.DRAFTED, None

    def _svc():
        return AutopilotPipelineService(
            latest_digest=lambda: _Digest([_Entry("job-1")]),
            drafter=_CountingDrafter(),
            repo=repo,  # shared persistence == the shared DB across both "processes"
            top_n=1,
        )

    scheduled, manual = _svc(), _svc()
    assert manual.try_start() is True  # the run-now route claims its slot first
    results = await asyncio.gather(scheduled.run(), manual.run_claimed())

    rows = repo.list(limit=10)
    assert len(rows) == 1
    assert rows[0].status is DraftStatus.DRAFTED
    assert len(draft_calls) == 1  # the losing run never reached the drafter

    assert sum(r.created for r in results) == 1
    assert sum(r.skipped for r in results) == 1
