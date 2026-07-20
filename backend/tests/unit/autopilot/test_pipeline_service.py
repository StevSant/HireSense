import asyncio
import uuid

import pytest

from hiresense.autopilot.domain import AutopilotPipelineService, DraftStatus


class _Entry:
    def __init__(self, job_id, title="Dev", company="Acme"):
        self.job_id = job_id
        self.title = title
        self.company = company


class _Digest:
    def __init__(self, entries):
        self.entries = entries


class _Repo:
    def __init__(self, drafted=()):
        self.added = []
        self._claimed = set()
        self._drafted = set(drafted)

    def add(self, draft):
        draft.id = uuid.uuid4()
        self.added.append(draft)
        return draft

    def claim(self, draft):
        if draft.job_id in self._claimed:
            return None
        self._claimed.add(draft.job_id)
        draft.id = uuid.uuid4()
        return draft

    def finalize(self, draft):
        self.added.append(draft)
        return draft

    def list(self, limit):
        return self.added[:limit]

    def exists_for_job(self, job_id):
        return job_id in self._drafted


class _Drafter:
    def __init__(self, raise_on=None):
        self.calls = []
        self._raise_on = raise_on

    async def draft(self, job_id):
        self.calls.append(job_id)
        if self._raise_on == job_id:
            raise RuntimeError("boom")
        return uuid.uuid4(), DraftStatus.DRAFTED, None


class _Notifier:
    def __init__(self):
        self.calls = []

    async def notify_pipeline_drafts(self, count):
        self.calls.append(count)
        return True


def _svc(entries, repo, drafter, top_n=3, notifier=None):
    return AutopilotPipelineService(
        latest_digest=lambda: _Digest(entries),
        drafter=drafter,
        repo=repo,
        top_n=top_n,
        notifier=notifier,
    )


@pytest.mark.asyncio
async def test_drafts_top_n_and_records():
    repo, drafter = _Repo(), _Drafter()
    result = await _svc(
        [_Entry("a"), _Entry("b"), _Entry("c"), _Entry("d")], repo, drafter, top_n=2
    ).run()
    assert result.created == 2
    # top_n picks the first two entries; drafting runs concurrently so the order
    # of draft() calls is not guaranteed.
    assert sorted(drafter.calls) == ["a", "b"]
    assert len(repo.added) == 2


@pytest.mark.asyncio
async def test_skips_already_drafted():
    repo, drafter = _Repo(drafted={"a"}), _Drafter()
    result = await _svc([_Entry("a"), _Entry("b")], repo, drafter).run()
    assert drafter.calls == ["b"]
    assert result.created == 1
    assert result.skipped == 1


@pytest.mark.asyncio
async def test_drafter_exception_records_failed_and_continues():
    repo, drafter = _Repo(), _Drafter(raise_on="a")
    result = await _svc([_Entry("a"), _Entry("b")], repo, drafter).run()
    assert result.created == 1  # only b succeeded
    statuses = {d.job_id: d.status for d in repo.added}
    assert statuses["a"] is DraftStatus.FAILED
    assert statuses["b"] is DraftStatus.DRAFTED


@pytest.mark.asyncio
async def test_notifies_only_when_created():
    notifier = _Notifier()
    await _svc([_Entry("a")], _Repo(), _Drafter(), notifier=notifier).run()
    assert notifier.calls == [1]
    notifier2 = _Notifier()
    await _svc([], _Repo(), _Drafter(), notifier=notifier2).run()
    assert notifier2.calls == []


@pytest.mark.asyncio
async def test_no_digest_returns_empty():
    svc = AutopilotPipelineService(
        latest_digest=lambda: None, drafter=_Drafter(), repo=_Repo(), top_n=3
    )
    result = await svc.run()
    assert result.created == 0 and result.drafts == []


@pytest.mark.asyncio
async def test_draft_concurrency_is_bounded():
    current = 0
    max_concurrent = 0

    class _ConcurrentDrafter:
        async def draft(self, job_id):
            nonlocal current, max_concurrent
            current += 1
            max_concurrent = max(max_concurrent, current)
            await asyncio.sleep(0.01)
            current -= 1
            return uuid.uuid4(), DraftStatus.DRAFTED, None

    entries = [_Entry(str(i)) for i in range(6)]
    svc = AutopilotPipelineService(
        latest_digest=lambda: _Digest(entries),
        drafter=_ConcurrentDrafter(),
        repo=_Repo(),
        top_n=6,
        concurrency=2,
    )
    result = await svc.run()
    assert result.created == 6
    assert max_concurrent == 2


@pytest.mark.asyncio
async def test_run_is_a_noop_while_already_in_flight():
    """The guard `run()` uses must cover both the scheduler AND a manual
    run-now — simulate that by claiming the slot out-of-band first."""
    repo = _Repo()
    svc = _svc([_Entry("a")], repo, _Drafter())

    assert svc.try_start() is True
    result = await svc.run()  # a concurrent caller already holds the slot
    assert result.created == 0
    assert result.skipped == 0
    assert repo.added == []
    assert svc.is_running is True

    svc._finish()
    assert svc.try_start() is True  # slot free again once released
