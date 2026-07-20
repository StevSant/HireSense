from __future__ import annotations

from hiresense.research.domain import CompanyProfileStore


def test_record_and_get_roundtrip() -> None:
    store = CompanyProfileStore()
    store.record(
        company_name="BC Tecnología",
        source="getonboard",
        description="Consultora de TI",
        website="https://bc.cl",
        headquarters="Chile",
    )

    profile = store.get("BC Tecnología")

    assert profile is not None
    assert profile.company_name == "BC Tecnología"
    assert profile.source == "getonboard"
    assert profile.description == "Consultora de TI"
    assert profile.website == "https://bc.cl"
    assert profile.headquarters == "Chile"


def test_get_is_case_and_whitespace_insensitive() -> None:
    store = CompanyProfileStore()
    store.record(company_name="BC Tecnología", source="getonboard")

    assert store.get("  bc tecnología  ") is not None


def test_get_returns_none_for_unknown_company() -> None:
    assert CompanyProfileStore().get("Nope") is None


def test_latest_record_wins() -> None:
    store = CompanyProfileStore()
    store.record(company_name="Acme", source="getonboard", description="old")
    store.record(company_name="acme", source="getonboard", description="new")

    profile = store.get("Acme")

    assert profile is not None
    assert profile.description == "new"


def test_blank_company_name_is_ignored() -> None:
    store = CompanyProfileStore()
    store.record(company_name="   ", source="getonboard", description="x")

    assert store.get("") is None
