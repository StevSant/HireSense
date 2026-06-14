from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.portfolio.domain import PortfolioProject, ProjectText
from hiresense.portfolio.infrastructure import PortfolioProjectOrm  # noqa: F401 (registers table)
from hiresense.portfolio.infrastructure import PortfolioProjectsRepository


@pytest.fixture
def repo():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield PortfolioProjectsRepository(session_factory=factory)
    Base.metadata.drop_all(engine)


def _project(key: str, source: str = "supabase") -> PortfolioProject:
    return PortfolioProject(
        id=f"id-{source}-{key}",
        source=source,
        source_key=key,
        tech=["python"],
        translations={"en": ProjectText(title=key.title(), description="d")},
    )


def test_replace_source_inserts_and_lists_roundtrip(repo) -> None:
    count = repo.replace_source("supabase", [_project("a"), _project("b")])
    assert count == 2
    stored = {p.source_key: p for p in repo.list_all()}
    assert set(stored) == {"a", "b"}
    assert stored["a"].translations["en"].title == "A"
    assert stored["a"].tech == ["python"]


def test_replace_source_only_touches_its_own_slice(repo) -> None:
    repo.replace_source("supabase", [_project("a")])
    repo.replace_source("github", [_project("r", source="github")])
    repo.replace_source("supabase", [_project("c")])
    by_source = {(p.source, p.source_key) for p in repo.list_all()}
    assert by_source == {("supabase", "c"), ("github", "r")}


def _project_ordered(
    key: str, *, pinned: bool = False, position: int | None = None
) -> PortfolioProject:
    return PortfolioProject(
        id=f"id-{key}",
        source="supabase",
        source_key=key,
        pinned=pinned,
        position=position,
        translations={"en": ProjectText(title=key.title())},
    )


def test_list_page_orders_pinned_first_then_position_then_source_key(repo) -> None:
    repo.replace_source(
        "supabase",
        [
            _project_ordered("zeta", position=5),
            _project_ordered("alpha", pinned=True, position=9),
            _project_ordered("beta", position=1),
            _project_ordered("noposition"),  # position None -> last
        ],
    )
    rows, total = repo.list_page(limit=10, offset=0)
    assert total == 4
    assert [p.source_key for p in rows] == ["alpha", "beta", "zeta", "noposition"]


def test_list_page_slices_with_limit_and_offset(repo) -> None:
    repo.replace_source(
        "supabase", [_project_ordered(k, position=i) for i, k in enumerate("abcde")]
    )
    rows, total = repo.list_page(limit=2, offset=2)
    assert total == 5
    assert [p.source_key for p in rows] == ["c", "d"]


def test_last_synced_at_none_then_set(repo) -> None:
    assert repo.last_synced_at() is None
    repo.replace_source("supabase", [_project("a")])
    assert isinstance(repo.last_synced_at(), datetime)
