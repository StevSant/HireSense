"""Regression: previously Remotive/RemoteOK/CSV/LinkedIn passed raw HTML
through, causing <p>, <strong>, <br> to appear as literal text in the job
detail panel on the frontend.
"""

from __future__ import annotations

import pytest

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizer import (
    CSVNormalizer,
    RemoteOKNormalizer,
    RemotiveNormalizer,
)
from hiresense.ingestion.domain.normalizers.linkedin_normalizer import LinkedInNormalizer


HTML_SAMPLE = "<p><strong>About Acme</strong></p><p>Build APIs with FastAPI.<br/>We move fast.</p>"


def _raw(data: dict) -> RawJobListing:
    return RawJobListing(source="x", source_id="1", raw_data=data)


@pytest.mark.parametrize(
    "normalizer",
    [
        RemotiveNormalizer(),
        RemoteOKNormalizer(),
        CSVNormalizer(),
        LinkedInNormalizer(),
    ],
    ids=lambda n: type(n).__name__,
)
def test_normalizer_strips_html_from_description(normalizer) -> None:
    raw = _raw({"description": HTML_SAMPLE})
    description = normalizer.normalize(raw)["description"]
    assert "<p>" not in description
    assert "<strong>" not in description
    assert "<br" not in description
    assert "</p>" not in description
    assert "About Acme" in description
    assert "FastAPI" in description
