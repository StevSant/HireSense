from hiresense.profile.domain.models import CandidateProfile
from hiresense.profile.infrastructure.repository import _to_domain, _to_orm


def test_candidate_profile_defaults_machine_translated_false() -> None:
    profile = CandidateProfile(id="1", name="x")
    assert profile.machine_translated is False


def test_to_orm_and_back_preserves_machine_translated() -> None:
    profile = CandidateProfile(
        id="123e4567-e89b-12d3-a456-426614174000",
        name="x",
        machine_translated=True,
    )
    orm = _to_orm(profile)
    assert orm.machine_translated is True
    restored = _to_domain(orm)
    assert restored.machine_translated is True
