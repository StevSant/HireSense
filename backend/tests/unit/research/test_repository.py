from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.infrastructure.database import Base
from hiresense.research.domain.models import CompanyResearch
from hiresense.research.infrastructure.repository import CompanyResearchRepository


@pytest.fixture
def sync_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    Base.metadata.drop_all(engine)


@pytest.fixture
def repo(sync_session_factory):
    return CompanyResearchRepository(session_factory=sync_session_factory)


def _make_research(**kwargs) -> CompanyResearch:
    defaults = dict(
        company_name="Anthropic",
        funding_stage="Series D",
        tech_stack="Python, Rust",
        culture_summary="AI safety focused",
        growth_trajectory="Rapid growth",
        red_flags=None,
        pros="Great mission",
        cons="High intensity",
        raw_llm_response="{}",
    )
    defaults.update(kwargs)
    return CompanyResearch(**defaults)


def test_create_and_get_by_company_name(repo) -> None:
    research = _make_research(company_name="OpenAI")
    repo.create(research)
    result = repo.get_by_company_name("OpenAI")
    assert result is not None
    assert result.company_name == "OpenAI"
    assert result.funding_stage == "Series D"


def test_get_by_company_name_not_found(repo) -> None:
    result = repo.get_by_company_name("NonExistentCorp")
    assert result is None


def test_get_by_company_name_case_insensitive(repo) -> None:
    research = _make_research(company_name="Anthropic")
    repo.create(research)
    result = repo.get_by_company_name("anthropic")
    assert result is not None
    assert result.company_name == "Anthropic"


def test_save_updates_existing(repo) -> None:
    research = _make_research(company_name="DeepMind", funding_stage="Acquired")
    created = repo.create(research)
    created.funding_stage = "Post-acquisition"
    repo.save(created)
    result = repo.get_by_company_name("DeepMind")
    assert result is not None
    assert result.funding_stage == "Post-acquisition"
