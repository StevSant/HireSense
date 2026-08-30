import uuid

import pytest
from pydantic import TypeAdapter, ValidationError

from hiresense.submission.domain import (
    AgentAction,
    AnswerSource,
    EscalateAction,
    FieldAnswer,
    FillFieldsAction,
    FormField,
    PageObservation,
    SubmissionAttempt,
    SubmissionStatus,
)


def test_terminal_statuses():
    assert SubmissionStatus.SUBMITTED in SubmissionStatus.terminal()
    assert SubmissionStatus.QUEUED not in SubmissionStatus.terminal()


def test_required_fields_filters():
    obs = PageObservation(
        url="https://boards.greenhouse.io/acme/jobs/1",
        title="Apply",
        fields=[
            FormField(selector="#a", label="First Name", field_type="text", required=True),
            FormField(selector="#b", label="Referral", field_type="text", required=False),
        ],
    )
    assert [f.selector for f in obs.required_fields] == ["#a"]


def test_is_filled_ignores_whitespace():
    field = FormField(selector="#a", label="Email", field_type="text", current_value="   ")
    assert field.is_filled is False


def test_confidence_is_bounded():
    with pytest.raises(ValidationError):
        FieldAnswer(
            selector="#a",
            canonical_key="email",
            value="x",
            confidence=1.4,
            source=AnswerSource.LLM,
        )


def test_agent_action_union_discriminates():
    adapter = TypeAdapter(AgentAction)
    parsed = adapter.validate_python({"kind": "escalate", "reason": "no salary", "fields": ["#s"]})
    assert isinstance(parsed, EscalateAction)
    parsed = adapter.validate_python(
        {
            "kind": "fill_fields",
            "fills": [
                {
                    "selector": "#a",
                    "canonical_key": "email",
                    "value": "a@b.c",
                    "confidence": 1.0,
                    "source": "deterministic_map",
                },
            ],
        }
    )
    assert isinstance(parsed, FillFieldsAction)


def test_attempt_defaults():
    attempt = SubmissionAttempt(
        application_id=uuid.uuid4(),
        job_id="j1",
        channel="ats_form",
        target_url="https://example.test/apply",
    )
    assert attempt.status is SubmissionStatus.QUEUED
    assert attempt.attempt_no == 1
    assert attempt.escalated_fields == []
    assert attempt.evidence == {}
