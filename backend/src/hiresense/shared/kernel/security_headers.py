from __future__ import annotations

from typing import Any, Awaitable, Callable

# Baseline hardening headers for an API: stop MIME sniffing, forbid framing
# (the API serves no embeddable content), and never leak referrer URLs.
_SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
]


class SecurityHeadersMiddleware:
    """Pure-ASGI middleware that appends security headers to every HTTP
    response. Framework-free so it can live in the kernel."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self._app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def send_with_headers(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.extend(_SECURITY_HEADERS)
                message["headers"] = headers
            await send(message)

        await self._app(scope, receive, send_with_headers)
