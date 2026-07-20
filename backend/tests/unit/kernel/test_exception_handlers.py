from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.kernel import register_domain_exception_handlers
from hiresense.kernel.exceptions import (
    ConflictError,
    DomainError,
    NotFoundError,
    ValidationError,
)


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
