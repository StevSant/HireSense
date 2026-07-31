from __future__ import annotations

from typing import Protocol


class PageRendererPort(Protocol):
    async def render(self, url: str) -> str: ...
