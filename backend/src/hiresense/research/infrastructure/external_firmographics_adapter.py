from __future__ import annotations

import logging

import httpx

from hiresense.research.domain.firmographics import Firmographics

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 8.0


class ExternalFirmographicsAdapter:
    """Calls a configurable firmographics provider. Returns None when the
    provider is unconfigured (local mode) or on any error/timeout — the service
    then falls back to the LLM."""

    def __init__(self, provider_url: str, api_key: str) -> None:
        self._provider_url = provider_url
        self._api_key = api_key

    async def fetch(self, company_name: str) -> Firmographics | None:
        if not self._provider_url or not self._api_key:
            return None
        try:
            headers = {"Authorization": f"Bearer {self._api_key}"}
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                resp = await client.get(
                    self._provider_url,
                    params={"company": company_name},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return Firmographics(
                    industry=data.get("industry"),
                    company_size=data.get("company_size") or data.get("size"),
                    headquarters=data.get("headquarters") or data.get("location"),
                    website=data.get("website") or data.get("domain"),
                )
        except Exception:
            logger.warning("firmographics provider failed for %s", company_name, exc_info=True)
            return None
