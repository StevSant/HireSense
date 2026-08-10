from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.shared.kernel import register_domain_exception_handlers
from hiresense.shared.kernel.exceptions import (
    ConflictError,
    DomainError,
    NotFoundError,
    UpstreamUnavailableError,
    ValidationError,
)
from hiresense.research.domain import CompanyResearchError


def _client_raising(exc: Exception) -> TestClient:
    app = FastAPI()
    register_domain_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise exc

    return TestClient(app)


@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (NotFoundError("missing"), 404),
        (ConflictError("dupe"), 409),
        (ValidationError("bad"), 400),
    ],
)
def test_typed_exception_maps_to_status(exc: DomainError, expected_status: int) -> None:
    resp = _client_raising(exc).get("/boom")

    assert resp.status_code == expected_status
    assert resp.json() == {"detail": str(exc)}


def test_domain_errors_subclass_value_error() -> None:
    # Backward compatibility: endpoints that still ``except ValueError`` keep
    # catching typed domain errors unchanged.
    assert issubclass(DomainError, ValueError)
    for exc_type in (NotFoundError, ConflictError, ValidationError):
        assert issubclass(exc_type, DomainError)


def test_upstream_unavailable_maps_to_503() -> None:
    """A feature whose upstream failed must answer 503, not hand back a
    fabricated result as a 200."""
    resp = _client_raising(UpstreamUnavailableError("company research failed")).get("/boom")

    assert resp.status_code == 503
    assert resp.json() == {"detail": "company research failed"}


def test_module_specific_subclasses_need_no_handler_of_their_own() -> None:
    resp = _client_raising(CompanyResearchError("company research failed")).get("/boom")

    assert resp.status_code == 503


def test_upstream_unavailable_is_not_a_value_error() -> None:
    """DomainError subclasses ValueError for backward compatibility; if this one
    did too, the many ``except ValueError`` router blocks would silently
    downgrade an outage to a misleading 400."""
    assert not issubclass(UpstreamUnavailableError, ValueError)
    assert not issubclass(UpstreamUnavailableError, DomainError)
