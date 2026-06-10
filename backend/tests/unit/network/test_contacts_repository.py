from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.network.infrastructure import ContactsRepository, NetworkContactOrm  # noqa: F401 (registers table)


@pytest.fixture
def repo():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield ContactsRepository(session_factory=factory)
    Base.metadata.drop_all(engine)


def _contact(first: str, last: str, company: str, position: str = "Engineer"):
    from hiresense.network.domain import Contact

    return Contact(first_name=first, last_name=last, company=company, position=position)


def test_replace_all_inserts_and_lists_roundtrip(repo) -> None:
    contacts = [
        _contact("Jordan", "Lee", "Acme Inc."),
        _contact("Sam", "Diaz", "Globant S.A."),
    ]
    count = repo.replace_all(contacts)
    assert count == 2
    stored = repo.list_all()
    assert len(stored) == 2
    first_names = {c.first_name for c in stored}
    assert first_names == {"Jordan", "Sam"}


def test_replace_all_twice_keeps_only_second_snapshot(repo) -> None:
    repo.replace_all([_contact("Jordan", "Lee", "Acme Inc.")])
    count = repo.replace_all(
        [
            _contact("Sam", "Diaz", "Globant S.A."),
            _contact("Alex", "Ruiz", "Globant S.A.", "PM"),
        ]
    )
    assert count == 2
    stored = repo.list_all()
    assert len(stored) == 2
    assert {c.first_name for c in stored} == {"Sam", "Alex"}


def test_list_all_with_company_filter_matches_normalized(repo) -> None:
    repo.replace_all(
        [
            _contact("Jordan", "Lee", "Acme Inc."),
            _contact("Sam", "Diaz", "Globant S.A."),
        ]
    )
    # "ACME" normalizes to "acme"; "Acme Inc." also normalizes to "acme"
    results = repo.list_all(company="ACME")
    assert len(results) == 1
    assert results[0].first_name == "Jordan"


def test_find_by_company_normalized(repo) -> None:
    repo.replace_all(
        [
            _contact("Jordan", "Lee", "Acme Inc."),
            _contact("Sam", "Diaz", "Globant S.A."),
        ]
    )
    results = repo.find_by_company("acme")
    assert len(results) == 1
    assert results[0].first_name == "Jordan"


def test_count_by_companies_returns_counts_and_omits_missing(repo) -> None:
    repo.replace_all(
        [
            _contact("Jordan", "Lee", "Acme Inc."),
            _contact("Sam", "Diaz", "Acme Inc."),
            _contact("Alex", "Ruiz", "Globant S.A."),
        ]
    )
    counts = repo.count_by_companies(["acme", "globant", "missing"])
    assert counts == {"acme": 2, "globant": 1}


def test_count_by_companies_empty_list_returns_empty_dict(repo) -> None:
    repo.replace_all([_contact("Jordan", "Lee", "Acme Inc.")])
    assert repo.count_by_companies([]) == {}


def test_last_imported_at_none_then_set(repo) -> None:
    assert repo.last_imported_at() is None
    repo.replace_all([_contact("Jordan", "Lee", "Acme Inc.")])
    result = repo.last_imported_at()
    assert isinstance(result, datetime)
