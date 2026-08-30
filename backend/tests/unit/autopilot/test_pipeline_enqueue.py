import uuid

from hiresense.autopilot.domain import AutopilotDraft, DraftStatus
from hiresense.autopilot.infrastructure import PacketApprovingEnqueuer


class _Quality:
    def __init__(self, ready):
        self.ready = ready
        self.warnings = [] if ready else ["A cover letter is required before approval."]


class _Packet:
    def __init__(self, ready):
        self.id = uuid.uuid4()
        self.quality_report = _Quality(ready)


class _PacketService:
    def __init__(self, ready=True):
        self.ready = ready
        self.approved = []
        self.created = []

    def create(self, application_id):
        self.created.append(application_id)
        return _Packet(self.ready)

    def approve(self, packet_id):
        self.approved.append(packet_id)
        packet = _Packet(True)
        packet.id = packet_id
        return packet


class _SubmissionService:
    def __init__(self):
        self.enqueued = []

    def enqueue(self, **kw):
        self.enqueued.append(kw)
        return object()


class _Boom(_SubmissionService):
    def enqueue(self, **kw):
        raise RuntimeError("db down")


class _Repo:
    def __init__(self, score=0.9):
        self.score = score

    def get_latest_match(self, application_id):
        return type("M", (), {"score": self.score, "id": uuid.uuid4()})()

    def get_snapshot(self, application_id):
        return type(
            "S", (), {"source": "greenhouse", "url": "https://boards.greenhouse.io/a/jobs/1"}
        )()


def _draft(status=DraftStatus.DRAFTED, application_id=True):
    return AutopilotDraft(
        id=uuid.uuid4(),
        job_id="j1",
        application_id=uuid.uuid4() if application_id else None,
        status=status,
    )


def _enq(packets=None, subs=None, repo=None, min_score=0.75):
    return PacketApprovingEnqueuer(
        packets or _PacketService(True),
        subs or _SubmissionService(),
        repo or _Repo(0.9),
        min_score=min_score,
    )


async def test_drafted_and_ready_is_approved_and_enqueued():
    packets, subs = _PacketService(ready=True), _SubmissionService()
    await _enq(packets, subs).enqueue_for_draft(_draft())
    assert len(packets.approved) == 1
    assert len(subs.enqueued) == 1
    assert subs.enqueued[0]["packet_id"] == packets.approved[0]
    assert subs.enqueued[0]["channel"] == "greenhouse"
    assert subs.enqueued[0]["target_url"] == "https://boards.greenhouse.io/a/jobs/1"


async def test_partial_draft_is_never_enqueued():
    packets, subs = _PacketService(ready=True), _SubmissionService()
    await _enq(packets, subs).enqueue_for_draft(_draft(DraftStatus.PARTIAL))
    assert subs.enqueued == []
    assert packets.approved == []
    assert packets.created == []


async def test_failed_draft_is_never_enqueued():
    packets, subs = _PacketService(ready=True), _SubmissionService()
    await _enq(packets, subs).enqueue_for_draft(_draft(DraftStatus.FAILED))
    assert subs.enqueued == []


async def test_draft_without_an_application_is_skipped():
    subs = _SubmissionService()
    await _enq(subs=subs).enqueue_for_draft(_draft(application_id=False))
    assert subs.enqueued == []


async def test_quality_failure_blocks_approval():
    packets, subs = _PacketService(ready=False), _SubmissionService()
    await _enq(packets, subs).enqueue_for_draft(_draft())
    assert packets.approved == []
    assert subs.enqueued == []


async def test_score_below_floor_blocks_approval():
    packets, subs = _PacketService(ready=True), _SubmissionService()
    await _enq(packets, subs, _Repo(0.4)).enqueue_for_draft(_draft())
    assert subs.enqueued == []
    assert packets.created == []


async def test_score_exactly_at_the_floor_is_accepted():
    subs = _SubmissionService()
    await _enq(subs=subs, repo=_Repo(0.75), min_score=0.75).enqueue_for_draft(_draft())
    assert len(subs.enqueued) == 1


async def test_missing_match_is_treated_as_zero_score():
    class _NoMatch(_Repo):
        def get_latest_match(self, application_id):
            return None

    subs = _SubmissionService()
    await _enq(subs=subs, repo=_NoMatch()).enqueue_for_draft(_draft())
    assert subs.enqueued == []


async def test_enqueue_failure_does_not_propagate():
    await _enq(subs=_Boom()).enqueue_for_draft(_draft())  # must not raise
