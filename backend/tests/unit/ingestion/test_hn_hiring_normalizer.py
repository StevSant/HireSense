from __future__ import annotations

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers.hn_hiring_normalizer import (
    HNHiringNormalizer,
)


def _raw(text: str, comment_id: int = 1) -> RawJobListing:
    return RawJobListing(
        source="hn_hiring",
        source_id=str(comment_id),
        raw_data={"text": text, "id": comment_id, "created_at": ""},
    )


def test_role_location_mode_header() -> None:
    n = HNHiringNormalizer()
    out = n.normalize(_raw("Stripe | Software Engineer | San Francisco, CA | REMOTE"))
    assert out["company"] == "Stripe"
    assert out["title"] == "Software Engineer"
    # REMOTE is appended to the SF location parenthetically.
    assert "San Francisco" in out["location"]
    assert "REMOTE" in out["location"]


def test_location_first_role_second_does_not_steal_title() -> None:
    """Real bug from prod: 'NetBird | Berlin, Germany | ONSITE & Remote ...'

    The old parser put `Berlin, Germany` into the title because it was
    positionally second. The new parser sees no role keyword in any field,
    falls back to treating it as a location, and leaves title blank.
    """
    n = HNHiringNormalizer()
    out = n.normalize(_raw("NetBird | Berlin, Germany | ONSITE & Remote for some roles"))
    assert out["company"] == "NetBird"
    assert out["title"] == ""
    assert "Berlin" in out["location"]


def test_us_state_in_location_does_not_become_title() -> None:
    n = HNHiringNormalizer()
    out = n.normalize(_raw("CodeWeavers | St Paul, MN, USA | Full Time (REMOTE)"))
    assert out["company"] == "CodeWeavers"
    assert out["title"] == ""
    assert "St Paul" in out["location"]


def test_role_token_wins_when_ambiguous() -> None:
    n = HNHiringNormalizer()
    out = n.normalize(_raw("Acme | Senior Backend Engineer | Remote (US/EU)"))
    assert out["title"] == "Senior Backend Engineer"
    assert "Remote" in out["location"]


def test_description_kept_below_header() -> None:
    n = HNHiringNormalizer()
    out = n.normalize(
        _raw("Acme | Designer | Remote\nWe build cool things.\nApply via email.")
    )
    assert "We build cool things." in out["description"]
    assert "Apply via email." in out["description"]


def test_employment_type_not_used_as_title() -> None:
    """Regression: 'Smarkets | Full Time | Hybrid - Onsite (London, UK)'
    used to put 'Full Time' into the title via the fallback path."""
    n = HNHiringNormalizer()
    out = n.normalize(_raw("Smarkets | Full Time | Hybrid - Onsite (London, UK)"))
    assert out["company"] == "Smarkets"
    assert out["title"] == ""
    assert "Hybrid" in out["location"]


def test_url_not_used_as_title() -> None:
    """Regression: 'FUTO | https://futo.tech | Austin, TX (Remote or Onsite)'
    used to put the URL in the title field."""
    n = HNHiringNormalizer()
    out = n.normalize(_raw("FUTO | https://futo.tech | Austin, TX (Remote or Onsite)"))
    assert out["company"] == "FUTO"
    assert out["title"] == ""
    assert "Austin" in out["location"]


def test_multiple_roles_marker_not_used_as_title() -> None:
    n = HNHiringNormalizer()
    out = n.normalize(_raw("Aqora | Paris, France / US / Remote (EU) | Multiple roles"))
    assert out["company"] == "Aqora"
    assert out["title"] == ""
    assert "Remote" in out["location"]
