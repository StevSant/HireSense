from hiresense.preference.domain import FeedbackKind, status_to_feedback_kind


def test_status_to_feedback_kind_mapping():
    assert status_to_feedback_kind("applied") == FeedbackKind.APPLIED
    assert status_to_feedback_kind("interviewing") == FeedbackKind.INTERVIEWING
    assert status_to_feedback_kind("offered") == FeedbackKind.OFFERED
    assert status_to_feedback_kind("accepted") == FeedbackKind.ACCEPTED
    assert status_to_feedback_kind("rejected") == FeedbackKind.REJECTED


def test_saved_status_has_no_signal():
    assert status_to_feedback_kind("saved") is None
    assert status_to_feedback_kind("unknown") is None
