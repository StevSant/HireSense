from __future__ import annotations

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers import GetOnBoardNormalizer


def _raw(attributes: dict, source_id: str = "1") -> RawJobListing:
    return RawJobListing(
        source="getonboard",
        source_id=source_id,
        raw_data={
            "attributes": attributes,
            "links": {"public_url": "https://www.getonbrd.com/jobs/x"},
            "relationships": {"tags": {"data": []}},
        },
    )


def test_remote_local_captures_country_restriction() -> None:
    """getonbrd 'remote_local' = remote but restricted to listed countries
    ("Remote (Chile)"). The normalizer must keep the country so strict-location
    filtering can hide it for users elsewhere."""
    out = GetOnBoardNormalizer().normalize(
        _raw(
            {
                "title": "Desarrollador Multi Agente IA",
                "company_name": "jurispeed",
                "remote": True,
                "remote_modality": "remote_local",
                "countries": ["Chile"],
                "description": "desc",
            }
        )
    )
    assert out["remote_modality"] == "remote"
    assert out["countries"] == ["Chile"]
    assert out["location"] == "Chile (Remote)"


def test_worldwide_remote_has_no_country_restriction() -> None:
    out = GetOnBoardNormalizer().normalize(
        _raw(
            {
                "title": "Backend Engineer",
                "company_name": "acme",
                "remote": True,
                "remote_modality": "remote_local",
                "countries": [],
                "description": "desc",
            }
        )
    )
    assert out["remote_modality"] == "remote"
    assert out["countries"] == []
    assert out["location"] == "Remote"
