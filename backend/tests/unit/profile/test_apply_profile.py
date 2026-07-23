from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.profile.domain import (
    ApplyProfile,
    CandidateProfile,
    WorkAuthorizationStatus,
    build_prefill,
)
from hiresense.profile.domain.screening_answer import ScreeningAnswer
from hiresense.profile.infrastructure.orm import ProfileOrm  # noqa: F401 (registers table)
from hiresense.profile.infrastructure.repository import ProfileRepository


def _profile(**over) -> CandidateProfile:
    base = dict(id=str(uuid.uuid4()), name="Ada Lovelace")
    base.update(over)
    return CandidateProfile(**base)


def test_apply_profile_defaults_are_empty() -> None:
    ap = ApplyProfile()
    assert ap.requires_visa_sponsorship is None
    assert ap.work_authorization_status is WorkAuthorizationStatus.UNKNOWN
    assert ap.screening_answers == []


def test_build_prefill_splits_name_and_includes_contact_and_links() -> None:
    profile = _profile(
        name="Ada Lovelace",
        email="ada@example.com",
        phone="+44 20 7946 0958",
        location="London, UK",
        linkedin_url="https://linkedin.com/in/ada",
        github_url=None,
    )

    out = build_prefill(profile)

    assert out["full_name"] == "Ada Lovelace"
    assert out["first_name"] == "Ada"
    assert out["last_name"] == "Lovelace"
    assert out["email"] == "ada@example.com"
    assert out["phone"] == "+44 20 7946 0958"
    assert out["location"] == "London, UK"
    assert out["linkedin_url"] == "https://linkedin.com/in/ada"
    # None/blank fields are omitted, not emitted as empty.
    assert "github_url" not in out


def test_build_prefill_single_word_name_has_no_last_name() -> None:
    out = build_prefill(_profile(name="Cher"))
    assert out["first_name"] == "Cher"
    assert "last_name" not in out


def test_build_prefill_includes_apply_profile_answers_with_types_preserved() -> None:
    profile = _profile(
        apply_profile=ApplyProfile(
            work_authorization="EU work permit",
            requires_visa_sponsorship=False,
            desired_salary="€70k",
            years_of_experience=8,
            willing_to_relocate=True,
            start_availability="2 weeks notice",
        )
    )

    out = build_prefill(profile)

    assert out["work_authorization"] == "EU work permit"
    assert out["requires_visa_sponsorship"] is False  # bool preserved, not stringified
    assert out["desired_salary"] == "€70k"
    assert out["years_of_experience"] == 8
    assert out["willing_to_relocate"] is True
    assert out["start_availability"] == "2 weeks notice"


def test_build_prefill_omits_apply_profile_when_absent() -> None:
    out = build_prefill(_profile())
    assert "work_authorization" not in out
    assert "requires_visa_sponsorship" not in out


@pytest.fixture
def repo():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield ProfileRepository(session_factory=factory)
    Base.metadata.drop_all(engine)


def test_apply_profile_round_trips_through_json_column(repo) -> None:
    created = repo.create(
        _profile(
            apply_profile=ApplyProfile(
                work_authorization="US Citizen",
                requires_visa_sponsorship=False,
                work_authorization_status=WorkAuthorizationStatus.AUTHORIZED,
                screening_answers=[ScreeningAnswer(question="Why us?", answer="Mission fit.")],
            )
        )
    )

    stored = repo.get_by_id(uuid.UUID(created.id))

    assert stored is not None
    assert stored.apply_profile is not None
    assert stored.apply_profile.work_authorization == "US Citizen"
    assert stored.apply_profile.requires_visa_sponsorship is False
    assert stored.apply_profile.work_authorization_status is WorkAuthorizationStatus.AUTHORIZED
    assert stored.apply_profile.screening_answers[0].question == "Why us?"


def test_profile_without_apply_profile_round_trips_as_none(repo) -> None:
    created = repo.create(_profile())
    stored = repo.get_by_id(uuid.UUID(created.id))
    assert stored is not None
    assert stored.apply_profile is None
