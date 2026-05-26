from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from hiresense.profile.domain.models import CandidateProfile, Profile
from hiresense.profile.domain.services import ProfileService


class _NullParser:
    def parse(self, content: str):
        raise NotImplementedError


class _NullSkillExtractor:
    def extract_from_tabular(self, content: str):
        return []


class FakeProfileRepository:
    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, Profile] = {}

    def get_by_id(self, id: uuid.UUID):
        return self._rows.get(id)

    def get_latest(self, language=None):
        rows = list(self._rows.values())
        if language:
            rows = [r for r in rows if r.language == language]
        return rows[-1] if rows else None

    def list_all(self):
        return list(self._rows.values())

    def create(self, profile: Profile):
        self._rows[profile.id] = profile
        return profile

    def update(self, id: uuid.UUID, fields):
        row = self._rows.get(id)
        if row is None:
            return None
        for key, value in fields.items():
            setattr(row, key, value)
        return row

    def update_all(self, fields):
        for row in self._rows.values():
            for key, value in fields.items():
                setattr(row, key, value)
        return len(self._rows)


def _make_orm() -> Profile:
    row = Profile(
        id=uuid.uuid4(),
        name="Parsed Name",
        email="parsed@example.com",
        phone="+1 555",
        location="Parsed City",
        sections=[],
        raw_tex="",
        language="en",
        skills=[],
    )
    row.created_at = datetime.now(timezone.utc)
    return row


def _service_with(orm: Profile) -> tuple[ProfileService, FakeProfileRepository]:
    repo = FakeProfileRepository()
    repo.create(orm)
    service = ProfileService(
        parser=_NullParser(),
        skill_extractor=_NullSkillExtractor(),
        repository=repo,
    )
    return service, repo


def test_update_manual_fields_overwrites_parsed_values() -> None:
    orm = _make_orm()
    service, _ = _service_with(orm)

    result = asyncio.run(
        service.update_manual_fields(
            str(orm.id),
            {
                "name": "Manual Name",
                "linkedin_url": "https://linkedin.com/in/me",
                "github_url": "  ",  # whitespace becomes None so UI can fall back
            },
        )
    )

    assert isinstance(result, CandidateProfile)
    assert result.name == "Manual Name"
    assert result.linkedin_url == "https://linkedin.com/in/me"
    assert result.github_url is None
    # Untouched fields keep their parsed values.
    assert result.email == "parsed@example.com"


def test_update_manual_fields_ignores_unknown_keys() -> None:
    orm = _make_orm()
    service, repo = _service_with(orm)

    asyncio.run(
        service.update_manual_fields(
            str(orm.id),
            {"name": "X", "raw_tex": "MALICIOUS", "skills": ["x"]},
        )
    )

    stored = repo.get_by_id(orm.id)
    assert stored is not None
    assert stored.name == "X"
    assert stored.raw_tex == ""
    assert stored.skills == []


def test_shared_links_broadcast_across_language_profiles() -> None:
    en = _make_orm()
    es = _make_orm()
    es.language = "es"
    repo = FakeProfileRepository()
    repo.create(en)
    repo.create(es)
    service = ProfileService(
        parser=_NullParser(),
        skill_extractor=_NullSkillExtractor(),
        repository=repo,
    )

    asyncio.run(
        service.update_manual_fields(
            str(en.id),
            {
                "name": "Only English Name",
                "linkedin_url": "https://linkedin.com/in/me",
            },
        )
    )

    # Per-language field stays scoped to the edited profile.
    assert repo.get_by_id(en.id).name == "Only English Name"
    assert repo.get_by_id(es.id).name == "Parsed Name"
    # Shared link is mirrored across all profiles.
    assert repo.get_by_id(en.id).linkedin_url == "https://linkedin.com/in/me"
    assert repo.get_by_id(es.id).linkedin_url == "https://linkedin.com/in/me"


def test_update_manual_fields_returns_none_for_missing_profile() -> None:
    orm = _make_orm()
    service, _ = _service_with(orm)

    result = asyncio.run(
        service.update_manual_fields(str(uuid.uuid4()), {"name": "X"})
    )
    assert result is None
