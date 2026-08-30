import uuid
from datetime import datetime, timezone

import pytest

from hiresense.submission.domain import (
    AnswerSource,
    EscalateAction,
    FieldAnswer,
    FillFieldsAction,
    SubmissionService,
    SubmissionStatus,
    SubmitAction,
)


class _Repo:
    def __init__(self):
        self.rows = {}
        self.events = []
        self.created_today = 0

    def create(self, attempt):
        attempt = attempt.model_copy(
            update={"id": uuid.uuid4(), "created_at": datetime.now(timezone.utc)}
        )
        self.rows[attempt.id] = attempt
        self.created_today += 1
        return attempt

    def get(self, attempt_id):
        return self.rows.get(attempt_id)

    def update(self, attempt):
        self.rows[attempt.id] = attempt
        return attempt

    def has_live_attempt(self, application_id):
        return any(
            a.application_id == application_id and a.status not in SubmissionStatus.terminal()
            for a in self.rows.values()
        )

    def count_created_since(self, since):
        return self.created_today

    def append_event(self, event):
        self.events.append(event)
        return event

    def next_seq(self, attempt_id):
        return len([e for e in self.events if e.attempt_id == attempt_id])

    def expire_leases(self, now, max_attempts):
        return 0

    def lease(self, runner_id, capacity, lease_seconds, now):
        return []


class _Agent:
    def __init__(self, action=None):
        self.action = action

    async def next_action(self, *, observation, context):
        return self.action


class _Bank:
    def __init__(self, boom=False):
        self.remembered = []
        self.boom = boom

    async def remember(self, answers):
        if self.boom:
            raise RuntimeError("profile service down")
        self.remembered.extend(answers)


def _svc(repo=None, agent=None, bank=None, daily_cap=10):
    return SubmissionService(
        repo or _Repo(),
        agent or _Agent(),
        bank or _Bank(),
        daily_cap=daily_cap,
        lease_seconds=300,
        max_attempts=2,
    )


def _enqueue(svc, application_id=None):
    return svc.enqueue(
        application_id=application_id or uuid.uuid4(),
        job_id="j1",
        packet_id=uuid.uuid4(),
        channel="ats_form",
        target_url="https://x.test/apply",
    )


def test_daily_cap_blocks_further_enqueues():
    svc = _svc(daily_cap=1)
    assert _enqueue(svc) is not None
    assert _enqueue(svc) is None


def test_zero_daily_cap_disables_enqueue_entirely():
    assert _enqueue(_svc(daily_cap=0)) is None


def test_duplicate_live_attempt_is_refused():
    svc = _svc()
    app_id = uuid.uuid4()
    assert _enqueue(svc, app_id) is not None
    assert _enqueue(svc, app_id) is None


def test_terminal_attempt_does_not_block_a_new_one():
    repo = _Repo()
    svc = _svc(repo)
    app_id = uuid.uuid4()
    first = _enqueue(svc, app_id)
    repo.update(first.model_copy(update={"status": SubmissionStatus.FAILED}))
    assert _enqueue(svc, app_id) is not None


async def test_escalate_action_transitions_and_records_fields():
    repo = _Repo()
    svc = _svc(repo, agent=_Agent(EscalateAction(reason="no salary", fields=["#s"])))
    attempt = _enqueue(svc)
    action = await svc.observe(attempt.id, observation=None, context=None)
    assert isinstance(action, EscalateAction)
    stored = repo.get(attempt.id)
    assert stored.status is SubmissionStatus.ESCALATED
    assert stored.escalated_fields == ["#s"]
    assert stored.escalation_reason == "no salary"


async def test_observe_writes_an_audit_event():
    repo = _Repo()
    svc = _svc(repo, agent=_Agent(SubmitAction(selector="#go", dry_run=True)))
    attempt = _enqueue(svc)
    await svc.observe(attempt.id, observation=None, context=None)
    assert len(repo.events) == 1
    assert repo.events[0].payload["dry_run"] is True


async def test_pii_values_are_hashed_on_the_audit_tape():
    repo = _Repo()
    fills = [
        FieldAnswer(
            selector="#e",
            canonical_key="email",
            value="me@example.com",
            confidence=1.0,
            source=AnswerSource.DETERMINISTIC_MAP,
        ),
        FieldAnswer(
            selector="#w",
            canonical_key=None,
            value="I want this job because it is interesting.",
            confidence=0.9,
            source=AnswerSource.LLM,
        ),
    ]
    svc = _svc(repo, agent=_Agent(FillFieldsAction(fills=fills)))
    attempt = _enqueue(svc)
    await svc.observe(attempt.id, observation=None, context=None)

    recorded = repo.events[0].payload["fills"]
    assert recorded[0]["value"].startswith("sha256:")
    assert "me@example.com" not in recorded[0]["value"]
    # Free-text answers are kept verbatim: they went out under the user's name.
    assert recorded[1]["value"] == "I want this job because it is interesting."
    assert recorded[1]["generated"] is True


async def test_observe_on_a_missing_attempt_raises():
    with pytest.raises(ValueError):
        await _svc().observe(uuid.uuid4(), observation=None, context=None)


async def test_resume_writes_answers_to_the_bank_and_requeues():
    repo, bank = _Repo(), _Bank()
    svc = _svc(repo, bank=bank)
    attempt = _enqueue(svc)
    repo.update(
        attempt.model_copy(
            update={
                "status": SubmissionStatus.ESCALATED,
                "escalated_fields": ["#s"],
                "escalation_reason": "Desired salary",
            }
        )
    )
    resumed = await svc.resume(attempt.id, {"Desired salary": "70000 EUR"})
    assert resumed.status is SubmissionStatus.QUEUED
    assert resumed.escalated_fields == []
    assert resumed.escalation_reason is None
    assert bank.remembered == [("Desired salary", "70000 EUR")]


async def test_resume_still_requeues_when_the_write_back_fails():
    repo = _Repo()
    svc = _svc(repo, bank=_Bank(boom=True))
    attempt = _enqueue(svc)
    repo.update(attempt.model_copy(update={"status": SubmissionStatus.ESCALATED}))
    resumed = await svc.resume(attempt.id, {"Q": "A"})
    assert resumed.status is SubmissionStatus.QUEUED


async def test_resume_ignores_blank_answers():
    bank = _Bank()
    svc = _svc(bank=bank)
    attempt = _enqueue(svc)
    await svc.resume(attempt.id, {"Q": "   "})
    assert bank.remembered == []


def test_abandon_is_terminal():
    svc = _svc()
    attempt = _enqueue(svc)
    abandoned = svc.abandon(attempt.id)
    assert abandoned.status is SubmissionStatus.ABANDONED
    assert abandoned.finished_at is not None


def test_complete_records_evidence():
    svc = _svc()
    attempt = _enqueue(svc)
    done = svc.complete(
        attempt.id,
        status=SubmissionStatus.SUBMITTED,
        evidence={"final_url": "https://x.test/thanks"},
    )
    assert done.status is SubmissionStatus.SUBMITTED
    assert done.evidence["final_url"] == "https://x.test/thanks"
