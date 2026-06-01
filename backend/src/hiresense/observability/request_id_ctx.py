from __future__ import annotations

from contextvars import ContextVar

# Holds the per-request correlation id so log records can be tagged with it
# even outside the HTTP span (e.g. background tasks spawned from a request).
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
