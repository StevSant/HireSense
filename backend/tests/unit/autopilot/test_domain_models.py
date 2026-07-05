import uuid

from hiresense.autopilot.domain import AutopilotDraft, DraftStatus, PipelineResult


def test_models_construct():
    d = AutopilotDraft(
        job_id="j1",
        application_id=uuid.uuid4(),
        job_title="Dev",
        company="Acme",
        status=DraftStatus.DRAFTED,
        detail=None,
    )
    assert d.status is DraftStatus.DRAFTED
    assert DraftStatus.PARTIAL.value == "partial"
    r = PipelineResult(created=1, skipped=2, drafts=[d])
    assert r.created == 1 and r.skipped == 2 and len(r.drafts) == 1
