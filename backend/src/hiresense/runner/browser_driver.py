from __future__ import annotations

from typing import Protocol


class BrowserDriver(Protocol):
    """The runner's only window onto a real browser.

    Kept behind a Protocol so the agent loop is testable without a browser,
    and so a headless/server-side driver can be dropped in later without
    touching the loop or the backend.
    """

    async def goto(self, url: str) -> None: ...

    async def html(self) -> str: ...

    async def url(self) -> str: ...

    async def title(self) -> str: ...

    async def fill(self, selector: str, value: str) -> None: ...

    async def click(self, selector: str) -> None: ...

    async def upload(self, selector: str, path: str) -> None: ...

    async def text(self) -> str: ...

    async def close(self) -> None: ...
