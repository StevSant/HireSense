"""Dice job source via the official MCP `search_jobs` tool."""

from __future__ import annotations

import json
import logging
from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType

logger = logging.getLogger(__name__)


def _parse_sse_jsonrpc(text: str) -> dict[str, Any]:
    """Extract the first JSON-RPC message from an MCP SSE or plain JSON body."""
    text = text.strip()
    if not text:
        raise ValueError("Empty MCP response")
    if text.startswith("{"):
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        raise ValueError("Unexpected MCP JSON payload")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if not payload:
                continue
            data = json.loads(payload)
            if isinstance(data, dict):
                return data
    raise ValueError("No JSON-RPC data frame in MCP response")


class DiceAdapter:
    """Official Dice Job Search MCP server (https://mcp.dice.com/mcp).

    Uses JSON-RPC `tools/call` for `search_jobs`. Public search requires no API
    key. Feed/search source — closure via URL revalidation.
    """

    def __init__(
        self,
        http_client: Any,
        *,
        mcp_url: str = "https://mcp.dice.com/mcp",
        query: str = "software engineer",
        location: str = "",
        remote_only: bool = False,
        page_limit: int = 3,
        jobs_per_page: int = 50,
        posted_date: str = "",
        employment_types: list[str] | None = None,
    ) -> None:
        self._http = http_client
        self._mcp_url = mcp_url.rstrip("/")
        self._query = query
        self._location = location
        self._remote_only = remote_only
        self._page_limit = max(1, page_limit)
        self._jobs_per_page = max(1, min(100, jobs_per_page))
        self._posted_date = posted_date
        self._employment_types = employment_types or []
        self.last_pages_fetched = 0
        self.last_rate_limited_count = 0
        self.last_parse_failures = 0
        self.last_rejected_malformed = 0

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "dice"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def _rpc(
        self, method: str, params: dict[str, Any] | None = None, *, rpc_id: int = 1
    ) -> dict:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
        if params is not None:
            payload["params"] = params
        response = await self._http.post(
            self._mcp_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        if getattr(response, "status_code", 200) == 429:
            self.last_rate_limited_count += 1
        response.raise_for_status()
        body = getattr(response, "text", None)
        if body is None and hasattr(response, "json"):
            data = response.json()
            if isinstance(data, dict):
                return data
            raise ValueError("Unexpected MCP JSON response")
        return _parse_sse_jsonrpc(body or "")

    async def fetch_jobs(self, filters: dict[str, Any] | None = None) -> list[RawJobListing]:
        self.last_pages_fetched = 0
        self.last_rate_limited_count = 0
        self.last_parse_failures = 0
        self.last_rejected_malformed = 0

        query = (filters or {}).get("search") or (filters or {}).get("q") or self._query
        location = (filters or {}).get("location") or self._location
        remote_only = bool((filters or {}).get("remote_only", self._remote_only))

        # Initialize session (MCP streamable HTTP may ignore this; safe no-op on errors).
        try:
            await self._rpc(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "hiresense", "version": "1.0"},
                },
                rpc_id=1,
            )
        except Exception:
            logger.debug(
                "Dice MCP initialize skipped/failed; continuing with tools/call", exc_info=True
            )

        jobs: list[RawJobListing] = []
        seen: set[str] = set()
        for page in range(1, self._page_limit + 1):
            arguments: dict[str, Any] = {
                "keyword": query,
                "jobs_per_page": self._jobs_per_page,
                "page_number": page,
            }
            if location:
                arguments["location"] = location
            if remote_only:
                arguments["workplace_types"] = ["Remote"]
            if self._posted_date:
                arguments["posted_date"] = self._posted_date
            if self._employment_types:
                arguments["employment_types"] = list(self._employment_types)

            try:
                result = await self._rpc(
                    "tools/call",
                    {"name": "search_jobs", "arguments": arguments},
                    rpc_id=page + 1,
                )
            except Exception:
                logger.exception("Dice MCP tools/call failed on page %s", page)
                raise

            self.last_pages_fetched += 1
            if "error" in result:
                raise RuntimeError(f"Dice MCP error: {result['error']}")

            content = (result.get("result") or {}).get("content") or []
            payload: dict[str, Any] = {}
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    try:
                        parsed = json.loads(block.get("text") or "")
                    except json.JSONDecodeError:
                        self.last_parse_failures += 1
                        continue
                    if isinstance(parsed, dict):
                        payload = parsed
                        break
            if not payload and isinstance(result.get("result"), dict):
                # Some MCP servers return the tool result directly.
                maybe = result["result"]
                if "data" in maybe:
                    payload = maybe

            page_jobs = payload.get("data") or []
            if not isinstance(page_jobs, list) or not page_jobs:
                break
            for item in page_jobs:
                if not isinstance(item, dict):
                    self.last_rejected_malformed += 1
                    continue
                source_id = str(
                    item.get("guid") or item.get("id") or item.get("jobId") or ""
                ).strip()
                if not source_id or source_id in seen:
                    if not source_id:
                        self.last_rejected_malformed += 1
                    continue
                seen.add(source_id)
                jobs.append(RawJobListing(source="dice", source_id=source_id, raw_data=item))

            meta = payload.get("meta") or {}
            page_count = meta.get("pageCount")
            if isinstance(page_count, int) and page >= page_count:
                break
            if len(page_jobs) < self._jobs_per_page:
                break
        return jobs
