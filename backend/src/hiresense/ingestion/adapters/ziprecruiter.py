"""ZipRecruiter job source via the official Job Search MCP tool."""

from __future__ import annotations

import json
import logging
from typing import Any

from hiresense.ingestion.adapters._mcp_jsonrpc import McpJsonRpcClient
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.shared.kernel.value_objects import SourceType

logger = logging.getLogger(__name__)


def _json_payload(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _extract_jobs(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Read common MCP tool-result shapes without depending on one transport."""
    result = response.get("result")
    candidates: list[Any] = [response.get("structuredContent"), result]
    if isinstance(result, dict):
        candidates.extend((result.get("structuredContent"), result.get("content")))

    for candidate in candidates:
        candidate = _json_payload(candidate)
        if (
            isinstance(candidate, list)
            and candidate
            and all(isinstance(item, dict) for item in candidate)
            and not any("type" in item and "text" in item for item in candidate)
        ):
            return candidate
        if not isinstance(candidate, dict):
            continue
        for key in ("jobs", "results", "listings", "data"):
            items = _json_payload(candidate.get(key))
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        content = candidate.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "text":
                    continue
                nested = _json_payload(block.get("text"))
                if isinstance(nested, (dict, list)):
                    jobs = _extract_jobs({"result": nested})
                    if jobs:
                        return jobs
    return []


class ZipRecruiterAdapter:
    """Official ZipRecruiter Job Search MCP server.

    The public MCP surface is read-only and does not require a partner API key.
    It returns at most five listings per call and exposes a small offset window,
    so ``page_limit`` is deliberately capped at six.
    """

    _PAGE_SIZE = 5
    _MAX_PAGES = 6

    def __init__(
        self,
        http_client: Any,
        *,
        mcp_url: str = "https://api.ziprecruiter.com/mcp",
        query: str = "software engineer",
        location: str = "",
        country: str = "",
        remote_only: bool = False,
        page_limit: int = 6,
    ) -> None:
        self._mcp = McpJsonRpcClient(http_client, mcp_url)
        self._query = query
        self._location = location
        self._country = country
        self._remote_only = remote_only
        self._page_limit = max(1, min(self._MAX_PAGES, page_limit))
        self.last_pages_fetched = 0
        self.last_rate_limited_count = 0
        self.last_parse_failures = 0
        self.last_rejected_malformed = 0

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "ziprecruiter"

    def source_type(self) -> SourceType:
        return SourceType.API

    async def _rpc(
        self, method: str, params: dict[str, Any] | None = None, *, rpc_id: int = 1
    ) -> dict[str, Any]:
        try:
            return await self._mcp.call(method, params, rpc_id=rpc_id)
        finally:
            self.last_rate_limited_count = self._mcp.last_rate_limited_count

    def _search_arguments(self, filters: dict[str, Any] | None, offset: int) -> dict[str, Any]:
        active_filters = filters or {}
        query = active_filters.get("search") or active_filters.get("q") or self._query
        location = active_filters.get("location") or self._location
        country = active_filters.get("country") or self._country
        remote_only = bool(active_filters.get("remote_only", self._remote_only))
        arguments: dict[str, Any] = {"keyword": query, "offset": offset}
        if location:
            arguments["location"] = location
        if country:
            arguments["country"] = country
        if remote_only:
            arguments["workplace_type"] = "remote"
        return arguments

    async def _initialize(self) -> None:
        try:
            await self._rpc(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "hiresense", "version": "1.0"},
                },
            )
        except Exception:
            logger.debug("ZipRecruiter MCP initialize skipped/failed", exc_info=True)

    async def _fetch_page(self, offset: int, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        result = await self._rpc(
            "tools/call",
            {"name": "search_jobs", "arguments": arguments},
            rpc_id=offset + 2,
        )
        if result.get("error"):
            raise RuntimeError(f"ZipRecruiter MCP error: {result['error']}")
        tool_result = result.get("result")
        if isinstance(tool_result, dict) and tool_result.get("isError"):
            raise RuntimeError("ZipRecruiter MCP search_jobs returned an error")
        return _extract_jobs(result)

    @staticmethod
    def _source_id(item: dict[str, Any]) -> str:
        return str(
            item.get("job_id")
            or item.get("jobId")
            or item.get("jid")
            or item.get("id")
            or item.get("guid")
            or item.get("reference_number")
            or item.get("url")
            or item.get("job_url")
            or item.get("jobUrl")
            or ""
        ).strip()

    async def fetch_jobs(self, filters: dict[str, Any] | None = None) -> list[RawJobListing]:
        self.last_pages_fetched = 0
        self.last_rate_limited_count = 0
        self.last_parse_failures = 0
        self.last_rejected_malformed = 0
        self._mcp.reset_metrics()

        await self._initialize()

        jobs: list[RawJobListing] = []
        seen: set[str] = set()
        for page in range(self._page_limit):
            arguments = self._search_arguments(filters, page)

            try:
                page_jobs = await self._fetch_page(page, arguments)
            except Exception:
                logger.exception("ZipRecruiter MCP tools/call failed at offset %s", page)
                self.last_parse_failures += 1
                if jobs:
                    break
                raise

            self.last_pages_fetched += 1
            if not page_jobs:
                break
            for item in page_jobs:
                source_id = self._source_id(item)
                if not source_id:
                    self.last_rejected_malformed += 1
                    continue
                if source_id in seen:
                    continue
                seen.add(source_id)
                jobs.append(
                    RawJobListing(source="ziprecruiter", source_id=source_id, raw_data=item)
                )

            if len(page_jobs) < self._PAGE_SIZE:
                break
        return jobs
