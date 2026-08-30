import uuid

from hiresense.profile.domain import ApplyProfile, CandidateProfile, ScreeningAnswer
from hiresense.submission.infrastructure import ProfileAnswerBank


class _Profiles:
    def __init__(self, profile):
        self.profile = profile
        self.saved = None

    async def get_current_profile(self, language=None):
        return self.profile

    async def set_apply_profile(self, apply_profile):
        self.saved = apply_profile
        return self.profile


def _profile(answers=None):
    return CandidateProfile(
        id=str(uuid.uuid4()),
        name="Ada",
        apply_profile=ApplyProfile(screening_answers=answers or []),
    )


async def test_new_answer_is_appended():
    profiles = _Profiles(_profile())
    await ProfileAnswerBank(profiles).remember([("Desired salary", "70000 EUR")])
    assert [a.question for a in profiles.saved.screening_answers] == ["Desired salary"]
    assert profiles.saved.screening_answers[0].answer == "70000 EUR"


async def test_existing_question_is_updated_not_duplicated():
    existing = [ScreeningAnswer(question="Desired salary", answer="60000 EUR")]
    profiles = _Profiles(_profile(existing))
    await ProfileAnswerBank(profiles).remember([("desired SALARY", "70000 EUR")])
    assert len(profiles.saved.screening_answers) == 1
    assert profiles.saved.screening_answers[0].answer == "70000 EUR"


async def test_missing_profile_is_a_no_op():
    profiles = _Profiles(None)
    await ProfileAnswerBank(profiles).remember([("Q", "A")])
    assert profiles.saved is None


async def test_empty_answer_list_does_not_write():
    profiles = _Profiles(_profile())
    await ProfileAnswerBank(profiles).remember([])
    assert profiles.saved is None


async def test_profile_without_an_apply_profile_still_works():
    profiles = _Profiles(CandidateProfile(id=str(uuid.uuid4()), name="Ada"))
    await ProfileAnswerBank(profiles).remember([("Q", "A")])
    assert [a.question for a in profiles.saved.screening_answers] == ["Q"]
