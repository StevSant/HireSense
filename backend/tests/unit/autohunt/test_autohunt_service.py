import uuid as uuid_mod
from datetime import datetime, timezone

import pytest

from hiresense.autohunt.domain import Digest
from hiresense.autohunt.domain.autohunt_service import AutoHuntService


class _Job:
    def __init__(self, id, score):
        self.id = id
        self.title = f"Title {id}"
        self.company = "Acme"
        self.url = f"http://x/{id}"
        self.match_score = score
        # score_job_against_skills reads these; the fake pre-ranker ignores the
        # resulting skill_by_id and sorts by the preset match_score above.
        self.skills = []
        self.description = ""


class _FakeJobsRepo:
    def __init__(self, jobs):
        self._jobs = jobs
        self.since_called_with = None

    def list_since(self, cutoff, *, status="open"):
        self.since_called_with = cutoff
        return self._jobs


class _FakePreRanker:
    async def rerank(self, jobs, skill_by_id, candidate_skills, candidate_summary, bucket):
        # Pass through already-scored jobs (sorted desc by score).
        return sorted(jobs, key=lambda j: j.match_score or 0, reverse=True)


class _FakeProfile:
    def __init__(self, view):
        self._view = view

    def get_for_language(self, language):
        return self._view


class _View:
    skills = ["python"]
    summary = "backend engineer"


class _FakeDigestRepo:
    def __init__(self, latest=None):
        self._latest = latest
        self.added = []
        self.pruned_at = None

    def add(self, digest):
        saved = digest.model_copy(
            update={"id": uuid_mod.uuid4(), "created_at": datetime.now(timezone.utc)}
        )
        self.added.append(saved)
        self._latest = saved
        return saved

    def latest(self):
        return self._latest

    def prune_older_than(self, cutoff):
        self.pruned_at = cutoff
        return 0


def _service(jobs_repo, digest_repo, profile=_FakeProfile(_View()), top_n=5):
    return AutoHuntService(
        jobs_repo=jobs_repo,
        pre_ranker=_FakePreRanker(),
        profile_service=profile,
        digest_repo=digest_repo,
        top_n=top_n,
        min_score=0.6,
        initial_lookback_days=7,
        retention_days=90,
        language="en",
    )


@pytest.mark.asyncio
async def test_run_filters_floor_and_caps_top_n():
    jobs = [_Job("a", 0.9), _Job("b", 0.7), _Job("c", 0.5), _Job("d", None)]
    digest_repo = _FakeDigestRepo()
    svc = _service(_FakeJobsRepo(jobs), digest_repo)
    d = await svc.run()
    ids = [e.job_id for e in d.entries]
    assert ids == ["a", "b"]  # c below 0.6, d None → excluded
    assert d.job_count == 2


@pytest.mark.asyncio
async def test_run_top_n_cap():
    jobs = [_Job(c, 0.9) for c in "abcdefg"]
    svc = _service(_FakeJobsRepo(jobs), _FakeDigestRepo(), top_n=3)
    d = await svc.run()
    assert d.job_count == 3


@pytest.mark.asyncio
async def test_run_uses_latest_created_at_as_cutoff():
    prev = Digest(
        id=uuid_mod.uuid4(),
        created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        cutoff_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
    )
    jobs_repo = _FakeJobsRepo([])
    svc = _service(jobs_repo, _FakeDigestRepo(latest=prev))
    await svc.run()
    assert jobs_repo.since_called_with == prev.created_at


@pytest.mark.asyncio
async def test_run_no_profile_persists_empty_digest():
    jobs_repo = _FakeJobsRepo([_Job("a", 0.9)])
    digest_repo = _FakeDigestRepo()
    svc = _service(jobs_repo, digest_repo, profile=_FakeProfile(None))
    d = await svc.run()
    assert d.job_count == 0 and d.entries == []
