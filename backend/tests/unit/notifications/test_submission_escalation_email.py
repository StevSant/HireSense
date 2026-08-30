from hiresense.notifications.domain import render_submission_escalation_email


class _Attempt:
    def __init__(self, job_id, reason):
        self.job_id = job_id
        self.escalation_reason = reason


def test_singular_subject_reads_correctly():
    subject, _ = render_submission_escalation_email([_Attempt("j1", "Desired salary")])
    assert subject == "HireSense: 1 application needs your answer before applying"


def test_plural_subject_reads_correctly():
    subject, _ = render_submission_escalation_email(
        [_Attempt("j1", "Desired salary"), _Attempt("j2", "Start date")]
    )
    assert subject == "HireSense: 2 applications need your answer before applying"


def test_body_names_each_job_and_reason():
    _, body = render_submission_escalation_email(
        [_Attempt("greenhouse:123", "Needs a human answer: Desired salary")]
    )
    assert "greenhouse:123" in body
    assert "Desired salary" in body


def test_body_explains_that_answers_are_remembered():
    _, body = render_submission_escalation_email([_Attempt("j1", "x")])
    assert "will not be asked again" in body


def test_long_lists_are_truncated_with_a_remainder_line():
    attempts = [_Attempt(f"job-{i}", "reason") for i in range(13)]
    _, body = render_submission_escalation_email(attempts)
    assert "job-9" in body
    assert "job-10" not in body
    assert "and 3 more" in body


def test_missing_reason_falls_back_to_a_readable_default():
    _, body = render_submission_escalation_email([_Attempt("j1", None)])
    assert "needs review" in body
