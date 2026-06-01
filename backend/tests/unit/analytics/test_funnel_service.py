import uuid as uuid_mod
from datetime import datetime, timezone

from hiresense.analytics.domain import FunnelService
from hiresense.tracking.domain.status_transition import StatusTransition


class _FakeHistory:
    def __init__(self, rows):
        self._rows = rows

    def list_history(self):
        return self._rows

    def history_for(self, application_id):
        return [r for r in self._rows if r.application_id == application_id]


def _t(app, frm, to, day):
    return StatusTransition(
        application_id=app, from_status=frm, to_status=to,
        changed_at=datetime(2026, 5, day, tzinfo=timezone.utc),
    )


def test_reached_counts_and_conversion():
    a, b = uuid_mod.uuid4(), uuid_mod.uuid4()
    rows = [
        _t(a, None, "saved", 1), _t(a, "saved", "applied", 3), _t(a, "applied", "interviewing", 6),
        _t(b, None, "saved", 1), _t(b, "saved", "applied", 2), _t(b, "applied", "rejected", 5),
    ]
    m = FunnelService(_FakeHistory(rows)).compute()
    reached = {s.stage: s.reached for s in m.stages}
    assert reached["saved"] == 2
    assert reached["applied"] == 2
    assert reached["interviewing"] == 1   # only a (b went to rejected w/o interviewing)
    assert m.rejected == 1
    # conversion applied->interviewing = 1/2 = 0.5
    conv = {s.stage: s.conversion_from_prev for s in m.stages}
    assert conv["interviewing"] == 0.5


def test_time_in_stage_applied_median_days():
    a = uuid_mod.uuid4()
    rows = [_t(a, None, "saved", 1), _t(a, "saved", "applied", 3), _t(a, "applied", "interviewing", 8)]
    m = FunnelService(_FakeHistory(rows)).compute()
    times = {s.stage: s.median_days_in_stage for s in m.stages}
    # time in applied = day8 - day3 = 5 days
    assert times["applied"] == 5.0
