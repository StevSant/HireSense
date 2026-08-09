from __future__ import annotations

import uuid

from hiresense.profile.domain import ApplyProfile, CandidateProfile
from hiresense.profile.infrastructure import InMemoryProfileRepository


def _profile(*, language: str = "en", **over) -> CandidateProfile:
    base = dict(id=str(uuid.uuid4()), name="Ada Lovelace", language=language)
    base.update(over)
    return CandidateProfile(**base)


def test_get_by_id_returns_the_stored_profile() -> None:
    repo = InMemoryProfileRepository()
    created = repo.create(_profile())

    assert repo.get_by_id(uuid.UUID(created.id)) == created


def test_get_by_id_returns_none_for_unknown_id() -> None:
    repo = InMemoryProfileRepository()
    repo.create(_profile())

    assert repo.get_by_id(uuid.uuid4()) is None


def test_list_all_returns_newest_first() -> None:
    """Matches ProfileRepository's `ORDER BY created_at DESC`."""
    repo = InMemoryProfileRepository()
    older = repo.create(_profile(name="Older"))
    newer = repo.create(_profile(name="Newer"))

    assert [p.id for p in repo.list_all()] == [newer.id, older.id]


def test_get_latest_returns_the_most_recently_created() -> None:
    repo = InMemoryProfileRepository()
    repo.create(_profile(name="Older"))
    newer = repo.create(_profile(name="Newer"))

    assert repo.get_latest() == newer


def test_get_latest_filters_by_language() -> None:
    repo = InMemoryProfileRepository()
    english = repo.create(_profile(language="en"))
    spanish = repo.create(_profile(language="es"))

    assert repo.get_latest(language="en") == english
    assert repo.get_latest(language="es") == spanish
    assert repo.get_latest(language="fr") is None


def test_get_latest_returns_none_when_empty() -> None:
    assert InMemoryProfileRepository().get_latest() is None


def test_update_applies_known_fields_and_returns_the_new_row() -> None:
    repo = InMemoryProfileRepository()
    created = repo.create(_profile(name="Parsed"))

    updated = repo.update(uuid.UUID(created.id), {"name": "Manual", "email": None})

    assert updated is not None
    assert updated.name == "Manual"
    assert repo.get_by_id(uuid.UUID(created.id)).name == "Manual"


def test_update_ignores_unknown_fields() -> None:
    """Mirrors the SQL repository's `hasattr` guard."""
    repo = InMemoryProfileRepository()
    created = repo.create(_profile())

    updated = repo.update(uuid.UUID(created.id), {"not_a_column": "x"})

    assert updated is not None
    assert not hasattr(updated, "not_a_column")


def test_update_does_not_mutate_the_originally_stored_object() -> None:
    repo = InMemoryProfileRepository()
    original = _profile(name="Parsed")
    repo.create(original)

    repo.update(uuid.UUID(original.id), {"name": "Manual"})

    assert original.name == "Parsed"


def test_update_returns_none_for_unknown_id() -> None:
    repo = InMemoryProfileRepository()
    repo.create(_profile())

    assert repo.update(uuid.uuid4(), {"name": "X"}) is None


def test_update_all_sets_the_field_on_every_row_and_returns_the_count() -> None:
    repo = InMemoryProfileRepository()
    english = repo.create(_profile(language="en"))
    spanish = repo.create(_profile(language="es"))

    count = repo.update_all({"linkedin_url": "https://linkedin.com/in/ada"})

    assert count == 2
    assert repo.get_by_id(uuid.UUID(english.id)).linkedin_url == "https://linkedin.com/in/ada"
    assert repo.get_by_id(uuid.UUID(spanish.id)).linkedin_url == "https://linkedin.com/in/ada"


def test_update_all_with_no_fields_reports_zero_rows() -> None:
    repo = InMemoryProfileRepository()
    repo.create(_profile())

    assert repo.update_all({}) == 0


def test_update_all_on_an_empty_repository_reports_zero_rows() -> None:
    assert InMemoryProfileRepository().update_all({"linkedin_url": "x"}) == 0


def test_written_apply_profile_dict_reads_back_as_a_model() -> None:
    """The SQL repository stores JSON and revalidates on read; the in-memory one
    must produce the same type so callers don't see a raw dict."""
    repo = InMemoryProfileRepository()
    created = repo.create(_profile())

    repo.update_all({"apply_profile": ApplyProfile(desired_salary="70k").model_dump()})

    stored = repo.get_by_id(uuid.UUID(created.id))
    assert stored is not None
    assert isinstance(stored.apply_profile, ApplyProfile)
    assert stored.apply_profile.desired_salary == "70k"


def test_create_overwrites_a_profile_stored_under_the_same_id() -> None:
    repo = InMemoryProfileRepository()
    first = _profile(name="First")
    repo.create(first)
    repo.create(_profile(id=first.id, name="Second"))

    assert repo.get_by_id(uuid.UUID(first.id)).name == "Second"
    assert len(repo.list_all()) == 1
