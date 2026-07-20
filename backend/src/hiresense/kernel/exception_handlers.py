from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from hiresense.kernel.exceptions import (
    ConflictError,
    DomainError,
    NotFoundError,
    ValidationError,
)

# Single source of truth mapping a domain-error type to its HTTP status. New
# domain-error subclasses only need an entry here to become transport-aware —
# routers never restate the mapping.
_STATUS_BY_EXCEPTION: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    ValidationError: status.HTTP_400_BAD_REQUEST,
}


def register_domain_exception_handlers(app: FastAPI) -> None:
    """Register one handler per domain-error type so the HTTP status is derived
    from the exception's type, not from substring-matching its message.

    The response body mirrors FastAPI's own ``HTTPException`` rendering
    (``{"detail": <message>}``) so migrating an endpoint to raise a typed
    domain error leaves its response shape unchanged.
    """

    def _make_handler(status_code: int):
        async def _handler(_request: Request, exc: DomainError) -> JSONResponse:
            return JSONResponse(status_code=status_code, content={"detail": str(exc)})

        return _handler

    for exception_type, status_code in _STATUS_BY_EXCEPTION.items():
        app.add_exception_handler(exception_type, _make_handler(status_code))
