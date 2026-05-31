from __future__ import annotations

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain import content_hash


def _job(**over) -> NormalizedJob:
    base = dict(
        id="x", title="Engineer", company="Acme", description="Build things",
        location="Remote", salary_range="$100k", skills=["python", "sql"],
        source="remotive", source_type="api", url="https://e.com/1",
    )
    base.update(over)
    return NormalizedJob(**base)


def test_same_content_same_hash() -> None:
    assert content_hash(_job()) == content_hash(_job())


def test_skill_order_does_not_change_hash() -> None:
    assert content_hash(_job(skills=["python", "sql"])) == content_hash(
        _job(skills=["sql", "python"])
    )


def test_changed_field_changes_hash() -> None:
    assert content_hash(_job()) != content_hash(_job(salary_range="$120k"))


def test_id_and_scores_do_not_affect_hash() -> None:
    assert content_hash(_job(id="a", match_score=0.9)) == content_hash(
        _job(id="b", match_score=0.1)
    )


def test_remote_modality_change_changes_hash() -> None:
    assert content_hash(_job(remote_modality="remote")) != content_hash(
        _job(remote_modality="on_site")
    )


def test_categories_change_changes_hash() -> None:
    assert content_hash(_job(categories=["engineering"])) != content_hash(
        _job(categories=["design"])
    )
