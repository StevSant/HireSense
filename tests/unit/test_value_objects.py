import uuid

from hiresense.kernel.value_objects import (
    JobId,
    Language,
    MatchScore,
    Score,
    SkillTag,
    SourceType,
)


def test_job_id_creates_from_string() -> None:
    jid = JobId("abc-123")
    assert str(jid) == "abc-123"


def test_job_id_equality() -> None:
    a = JobId("x")
    b = JobId("x")
    assert a == b


def test_job_id_generates_new() -> None:
    jid = JobId.generate()
    uuid.UUID(str(jid))


def test_skill_tag_normalizes() -> None:
    tag = SkillTag("  FastAPI  ")
    assert tag.value == "fastapi"


def test_score_clamps_range() -> None:
    assert Score(150).value == 100
    assert Score(-10).value == 0
    assert Score(75).value == 75


def test_match_score_breakdown() -> None:
    ms = MatchScore(semantic=80, skill_match=60, experience=70, language=100)
    composite = ms.composite(w_semantic=30, w_skill=40, w_exp=20, w_lang=10)
    expected = (80 * 30 + 60 * 40 + 70 * 20 + 100 * 10) / 100
    assert composite == expected


def test_language_enum() -> None:
    assert Language.ENGLISH.value == "en"
    assert Language.SPANISH.value == "es"


def test_source_type_enum() -> None:
    assert SourceType.API.value == "api"
    assert SourceType.RSS.value == "rss"
    assert SourceType.SCRAPER.value == "scraper"
    assert SourceType.MANUAL.value == "manual"
