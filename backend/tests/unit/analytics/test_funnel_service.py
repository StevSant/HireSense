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
        application_id=app,
        from_status=frm,
        to_status=to,
        changed_at=datetime(2026, 5, day, tzinfo=timezone.utc),
    )


class _FakeApps:
    def __init__(self, apps):
        self._apps = apps

    def list(self):
        return self._apps


class _FakeCorpus:
    def __init__(self, rows):
        self._rows = rows  # id -> obj with .source

    def rows_for_ids(self, ids):
        return {i: self._rows[i] for i in ids if i in self._rows}


def _row(source):
    return type("Row", (), {"source": source})()


def _app(job_id, status):
    return type("App", (), {"job_id": job_id, "status": status})()


def test_by_source_groups_and_rates():
    apps = [
        _app("j1", "interviewing"),
        _app("j2", "applied"),
        _app("j3", "offered"),
        _app(None, "saved"),  # no job_id → ignored
    ]
    corpus = _FakeCorpus(
        {"j1": _row("getonboard"), "j2": _row("getonboard"), "j3": _row("linkedin")}
    )
    m = FunnelService(_FakeHistory([]), applications_read=_FakeApps(apps), corpus=corpus).compute()
    by_source = {o.source: o for o in m.by_source}
    assert by_source["getonboard"].applications == 2
    assert by_source["getonboard"].reached_interview == 1  # j1 interviewing, j2 only applied
    assert by_source["getonboard"].interview_rate == 0.5
    assert by_source["linkedin"].reached_interview == 1  # offered >= interviewing


def test_by_source_empty_without_deps():
    assert FunnelService(_FakeHistory([])).compute().by_source == []


def test_reached_counts_and_conversion():
    a, b = uuid_mod.uuid4(), uuid_mod.uuid4()
    rows = [
        _t(a, None, "saved", 1),
        _t(a, "saved", "applied", 3),
        _t(a, "applied", "interviewing", 6),
        _t(b, None, "saved", 1),
        _t(b, "saved", "applied", 2),
        _t(b, "applied", "rejected", 5),
    ]
    m = FunnelService(_FakeHistory(rows)).compute()
    reached = {s.stage: s.reached for s in m.stages}
    assert reached["saved"] == 2
    assert reached["applied"] == 2
    assert reached["interviewing"] == 1  # only a (b went to rejected w/o interviewing)
    assert m.rejected == 1
    # conversion applied->interviewing = 1/2 = 0.5
    conv = {s.stage: s.conversion_from_prev for s in m.stages}
    assert conv["interviewing"] == 0.5


def test_time_in_stage_applied_median_days():
    a = uuid_mod.uuid4()
    rows = [
        _t(a, None, "saved", 1),
        _t(a, "saved", "applied", 3),
        _t(a, "applied", "interviewing", 8),
    ]
    m = FunnelService(_FakeHistory(rows)).compute()
    times = {s.stage: s.median_days_in_stage for s in m.stages}
    # time in applied = day8 - day3 = 5 days
    assert times["applied"] == 5.0


def test_current_rejected_counted():
    a, b = uuid_mod.uuid4(), uuid_mod.uuid4()
    rows = [
        _t(a, None, "saved", 1),
        _t(a, "saved", "applied", 3),
        _t(a, "applied", "rejected", 5),
        _t(b, None, "saved", 1),
    ]
    m = FunnelService(_FakeHistory(rows)).compute()
    assert m.current_rejected == 1
    current_saved = next(s.current for s in m.stages if s.stage == "saved")
    assert current_saved == 1
