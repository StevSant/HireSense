from hiresense.submission.domain import (
    AgentContext,
    AnswerSource,
    EscalateAction,
    FieldAnswer,
    FillFieldsAction,
    FormAgentService,
    FormField,
    PageObservation,
    SubmitAction,
    UploadFileAction,
)


class _Answerer:
    def __init__(self, answers=None):
        self.answers = answers or []
        self.calls = []

    async def answer(self, *, fields, job_text, prefill, claim_texts, screening_answers):
        self.calls.append([f.selector for f in fields])
        return self.answers


def _ctx(**kw):
    base = dict(
        prefill={},
        claim_texts=[],
        screening_answers=[],
        job_text="",
        needs_cv_upload=False,
        needs_letter_upload=False,
    )
    base.update(kw)
    return AgentContext(**base)


def _obs(fields, **kw):
    return PageObservation(url="https://x.test/apply", title="Apply", fields=fields, **kw)


def _svc(answerer=None, threshold=0.75, dry_run=True):
    return FormAgentService(
        answerer or _Answerer(), confidence_threshold=threshold, dry_run=dry_run
    )


async def test_captcha_escalates_before_anything_else():
    answerer = _Answerer()
    obs = _obs(
        [FormField(selector="#a", label="Email", field_type="text", required=True)],
        captcha_detected=True,
    )
    action = await _svc(answerer).next_action(
        observation=obs, context=_ctx(prefill={"email": "a@b.c"})
    )
    assert isinstance(action, EscalateAction)
    assert "captcha" in action.reason.lower()
    assert answerer.calls == []


async def test_deterministic_fields_never_reach_the_llm():
    answerer = _Answerer()
    obs = _obs(
        [
            FormField(selector="#e", label="Email", field_type="text", required=True),
            FormField(selector="#p", label="Phone", field_type="text", required=True),
        ]
    )
    action = await _svc(answerer).next_action(
        observation=obs, context=_ctx(prefill={"email": "a@b.c", "phone": "+34600"})
    )
    assert isinstance(action, FillFieldsAction)
    assert {f.canonical_key for f in action.fills} == {"email", "phone"}
    assert all(f.source is AnswerSource.DETERMINISTIC_MAP for f in action.fills)
    assert all(f.confidence == 1.0 for f in action.fills)
    assert answerer.calls == []


async def test_only_residual_required_fields_go_to_the_llm():
    answerer = _Answerer(
        [
            FieldAnswer(
                selector="#w",
                canonical_key=None,
                value="Because I like it.",
                confidence=0.8,
                source=AnswerSource.LLM,
            )
        ]
    )
    obs = _obs(
        [
            FormField(
                selector="#e",
                label="Email",
                field_type="text",
                required=True,
                current_value="a@b.c",
            ),
            FormField(
                selector="#w",
                label="Why do you want this role?",
                field_type="textarea",
                required=True,
            ),
            FormField(
                selector="#o",
                label="How did you hear about us?",
                field_type="text",
                required=False,
            ),
        ]
    )
    await _svc(answerer).next_action(observation=obs, context=_ctx(prefill={"email": "a@b.c"}))
    assert answerer.calls == [["#w"]]


async def test_low_confidence_escalates_naming_the_field():
    answerer = _Answerer(
        [
            FieldAnswer(
                selector="#s",
                canonical_key="desired_salary",
                value="90000",
                confidence=0.2,
                source=AnswerSource.LLM,
            )
        ]
    )
    obs = _obs([FormField(selector="#s", label="Desired salary", field_type="text", required=True)])
    action = await _svc(answerer).next_action(observation=obs, context=_ctx())
    assert isinstance(action, EscalateAction)
    assert action.fields == ["#s"]


async def test_ungrounded_answer_is_demoted_and_escalates():
    """The grounding rule and the confidence gate compose: an invented number
    is zeroed by grounding, which the gate then turns into an escalation even
    though the model reported high confidence.

    The label deliberately does not match the canonical field map, so the
    question reaches the model rather than being answered from the profile.
    """
    answerer = _Answerer(
        [
            FieldAnswer(
                selector="#y",
                canonical_key="years_of_experience",
                value="12",
                confidence=0.99,
                source=AnswerSource.LLM,
            )
        ]
    )
    obs = _obs(
        [
            FormField(
                selector="#y",
                label="How many years have you shipped Rust to production?",
                field_type="text",
                required=True,
            )
        ]
    )
    action = await _svc(answerer).next_action(observation=obs, context=_ctx())
    assert isinstance(action, EscalateAction)
    assert action.fields == ["#y"]


async def test_all_filled_and_confident_submits():
    obs = _obs(
        [
            FormField(
                selector="#e",
                label="Email",
                field_type="text",
                required=True,
                current_value="a@b.c",
            ),
            FormField(selector="#sub", label="Submit Application", field_type="submit"),
        ]
    )
    action = await _svc().next_action(observation=obs, context=_ctx(prefill={"email": "a@b.c"}))
    assert isinstance(action, SubmitAction)
    assert action.selector == "#sub"
    assert action.dry_run is True


async def test_live_mode_marks_submit_not_dry_run():
    obs = _obs(
        [
            FormField(
                selector="#e",
                label="Email",
                field_type="text",
                required=True,
                current_value="a@b.c",
            ),
            FormField(selector="#sub", label="Submit Application", field_type="submit"),
        ]
    )
    action = await _svc(dry_run=False).next_action(
        observation=obs, context=_ctx(prefill={"email": "a@b.c"})
    )
    assert isinstance(action, SubmitAction)
    assert action.dry_run is False


async def test_resume_file_input_requests_cv_upload():
    obs = _obs([FormField(selector="#cv", label="Resume/CV", field_type="file", required=True)])
    action = await _svc().next_action(observation=obs, context=_ctx(needs_cv_upload=True))
    assert isinstance(action, UploadFileAction)
    assert action.artifact == "cv"
    assert action.selector == "#cv"


async def test_cover_letter_file_input_requests_letter_upload():
    obs = _obs([FormField(selector="#cl", label="Cover Letter", field_type="file", required=False)])
    action = await _svc().next_action(observation=obs, context=_ctx(needs_letter_upload=True))
    assert isinstance(action, UploadFileAction)
    assert action.artifact == "cover_letter"


async def test_no_submit_control_escalates_rather_than_guessing():
    obs = _obs(
        [
            FormField(
                selector="#e",
                label="Email",
                field_type="text",
                required=True,
                current_value="a@b.c",
            )
        ]
    )
    action = await _svc().next_action(observation=obs, context=_ctx(prefill={"email": "a@b.c"}))
    assert isinstance(action, EscalateAction)
    assert "submit" in action.reason.lower()


async def test_llm_returning_nothing_for_a_required_field_escalates():
    answerer = _Answerer([])
    obs = _obs(
        [
            FormField(
                selector="#w", label="Why do you want this?", field_type="textarea", required=True
            )
        ]
    )
    action = await _svc(answerer).next_action(observation=obs, context=_ctx())
    assert isinstance(action, EscalateAction)
    assert action.fields == ["#w"]
