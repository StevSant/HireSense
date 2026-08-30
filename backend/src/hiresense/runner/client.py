from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_ARTIFACT_PATHS = {
    "cv": "cv.pdf",
    "cover_letter": "cover-letter.pdf",
}


class SubmissionClient:
    """Thin HTTP client for the backend's /submission surface.

    The runner's only dependency on HireSense. It imports nothing from any
    module's domain layer, which is what lets it run as a separate process on
    the candidate's own machine.
    """

    def __init__(self, base_url: str, token: str, *, timeout: float = 60.0) -> None:
        self._base = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._http = httpx.AsyncClient(base_url=self._base, headers=headers, timeout=timeout)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def lease(self, runner_id: str, capacity: int) -> list[dict]:
        resp = await self._http.post(
            "/submission/lease", json={"runner_id": runner_id, "capacity": capacity}
        )
        resp.raise_for_status()
        return resp.json()

    async def observe(self, attempt_id: str, observation: dict) -> dict:
        resp = await self._http.post(
            f"/submission/attempts/{attempt_id}/observe", json={"observation": observation}
        )
        resp.raise_for_status()
        return resp.json()

    async def heartbeat(self, attempt_id: str) -> None:
        try:
            await self._http.post(f"/submission/attempts/{attempt_id}/heartbeat")
        except httpx.HTTPError:  # noqa: PERF203 - a missed beat is not fatal
            logger.warning("runner: heartbeat failed for %s", attempt_id)

    async def complete(self, attempt_id: str, status: str, evidence: dict[str, Any]) -> None:
        resp = await self._http.post(
            f"/submission/attempts/{attempt_id}/complete",
            json={"status": status, "evidence": evidence},
        )
        resp.raise_for_status()

    async def artifact(self, application_id: str, kind: str) -> str | None:
        """Download a generated PDF to a temp file for the browser to attach.

        Browsers forbid setting a file input's value from script, so the file
        genuinely has to exist on disk before Playwright can attach it.
        """
        suffix = _ARTIFACT_PATHS.get(kind)
        if suffix is None:
            return None
        try:
            resp = await self._http.get(f"/applications/{application_id}/{suffix}")
            resp.raise_for_status()
        except httpx.HTTPError:
            logger.exception("runner: could not download %s for %s", kind, application_id)
            return None

        target = Path(tempfile.gettempdir()) / f"hiresense_{application_id}_{suffix}"
        target.write_bytes(resp.content)
        return str(target)
