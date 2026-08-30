from hiresense.submission.domain import AnswerSource, FieldAnswer, enforce_grounding


def _answer(value, *, key=None, source=AnswerSource.LLM, confidence=0.9):
    return FieldAnswer(
        selector="#f",
        canonical_key=key,
        value=value,
        confidence=confidence,
        source=source,
    )


def test_invented_years_of_experience_is_demoted():
    out = enforce_grounding(
        [_answer("8", key="years_of_experience")],
        prefill={"years_of_experience": 3},
        claim_texts=[],
        job_text="We want a senior engineer.",
    )
    assert out[0].confidence == 0.0
    assert out[0].rationale.startswith("ungrounded:")


def test_years_of_experience_matching_profile_survives():
    out = enforce_grounding(
        [_answer("3", key="years_of_experience")],
        prefill={"years_of_experience": 3},
        claim_texts=[],
        job_text="",
    )
    assert out[0].confidence == 0.9


def test_deterministic_answers_are_never_demoted():
    out = enforce_grounding(
        [_answer("a@b.c", key="email", source=AnswerSource.DETERMINISTIC_MAP, confidence=1.0)],
        prefill={},
        claim_texts=[],
        job_text="",
    )
    assert out[0].confidence == 1.0


def test_profile_sourced_answers_are_never_demoted():
    out = enforce_grounding(
        [_answer("42", key="years_of_experience", source=AnswerSource.PROFILE)],
        prefill={},
        claim_texts=[],
        job_text="",
    )
    assert out[0].confidence == 0.9


def test_value_grounded_in_a_verified_claim_survives():
    out = enforce_grounding(
        [_answer("AWS Certified Solutions Architect")],
        prefill={},
        claim_texts=["Holds the AWS Certified Solutions Architect credential since 2024."],
        job_text="",
    )
    assert out[0].confidence == 0.9


def test_free_text_prose_is_allowed_without_verbatim_match():
    out = enforce_grounding(
        [_answer("I am drawn to this role because it pairs backend depth with product ownership.")],
        prefill={},
        claim_texts=[],
        job_text="",
    )
    assert out[0].confidence == 0.9


def test_empty_answer_is_demoted():
    out = enforce_grounding([_answer("   ")], prefill={}, claim_texts=[], job_text="")
    assert out[0].confidence == 0.0


def test_absurdly_long_answer_is_demoted():
    out = enforce_grounding([_answer("x " * 1500)], prefill={}, claim_texts=[], job_text="")
    assert out[0].confidence == 0.0


def test_ungrounded_boolean_is_demoted():
    out = enforce_grounding(
        [_answer("yes", key="requires_visa_sponsorship")],
        prefill={},
        claim_texts=[],
        job_text="",
    )
    assert out[0].confidence == 0.0


def test_boolean_grounded_in_profile_survives():
    out = enforce_grounding(
        [_answer("yes", key="requires_visa_sponsorship")],
        prefill={"requires_visa_sponsorship": True},
        claim_texts=[],
        job_text="",
    )
    assert out[0].confidence == 0.9


def test_ungrounded_email_is_demoted():
    out = enforce_grounding(
        [_answer("someone.else@example.com", key="email")],
        prefill={"email": "me@example.com"},
        claim_texts=[],
        job_text="",
    )
    assert out[0].confidence == 0.0


def test_ungrounded_date_is_demoted():
    out = enforce_grounding(
        [_answer("2019-04-01", key="start_availability")],
        prefill={},
        claim_texts=[],
        job_text="",
    )
    assert out[0].confidence == 0.0


def test_value_grounded_in_job_text_survives():
    out = enforce_grounding(
        [_answer("120000", key="desired_salary")],
        prefill={},
        claim_texts=[],
        job_text="The budget for this role is 120000 EUR per year.",
    )
    assert out[0].confidence == 0.9
