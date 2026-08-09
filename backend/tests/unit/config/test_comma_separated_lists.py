"""Comma-separated env values must populate every scalar list setting.

Regression guard: the splitter used to consult a hand-maintained name allowlist,
so any list field nobody remembered to register raised a raw pydantic
JSON-parse error at startup. ``ENABLED_OPPORTUNITY_SOURCES`` shipped that way in
``.env.example`` and broke a clean-clone boot outright.
"""

from typing import get_args, get_origin

import pytest


def _set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")


def test_opportunity_sources_accepts_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv("ENABLED_OPPORTUNITY_SOURCES", "confs_tech,curated")
    from hiresense.config import Settings

    assert Settings().enabled_opportunity_sources == ["confs_tech", "curated"]


def test_int_list_accepts_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv("CONFS_TECH_YEARS", "2026,2027")
    from hiresense.config import Settings

    assert Settings().confs_tech_years == [2026, 2027]


def test_json_array_notation_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON is pydantic's native form; splitting must not take it away."""
    _set_required(monkeypatch)
    monkeypatch.setenv("ENABLED_OPPORTUNITY_SOURCES", '["confs_tech", "curated"]')
    from hiresense.config import Settings

    assert Settings().enabled_opportunity_sources == ["confs_tech", "curated"]


def test_whitespace_around_separators_is_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv("OUTREACH_ALLOWED_RECIPIENT_DOMAINS", " example.com , test.dev ")
    from hiresense.config import Settings

    assert Settings().outreach_allowed_recipient_domains == ["example.com", "test.dev"]


def test_every_scalar_list_setting_accepts_commas(monkeypatch: pytest.MonkeyPatch) -> None:
    """No scalar list field may be left behind by the splitter.

    Walks the composed Settings model rather than a fixture list, so a list
    field added later is covered without touching this test.
    """
    _set_required(monkeypatch)
    from hiresense.config import Settings

    scalar_lists = {
        name: get_args(field.annotation)[0]
        for name, field in Settings.model_fields.items()
        if get_origin(field.annotation) is list
        and len(get_args(field.annotation)) == 1
        and get_args(field.annotation)[0] in (str, int, float)
    }
    assert scalar_lists, "expected Settings to declare scalar list fields"

    samples: dict[type, str] = {str: "alpha,beta", int: "1,2", float: "1.5,2.5"}
    expected: dict[type, list[object]] = {
        str: ["alpha", "beta"],
        int: [1, 2],
        float: [1.5, 2.5],
    }

    for name, element in scalar_lists.items():
        monkeypatch.setenv(name.upper(), samples[element])
        assert getattr(Settings(), name) == expected[element], name
        monkeypatch.delenv(name.upper())
