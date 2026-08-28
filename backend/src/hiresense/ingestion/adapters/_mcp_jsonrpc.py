"""Small shared transport for streamable HTTP MCP job-source adapters."""

from __future__ import annotations

import json
from typing import Any


def parse_jsonrpc_response(text: str) -> dict[str, Any]:
    """Extract the first JSON-RPC message from JSON or an SSE response."""
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


class McpJsonRpcClient:
    """JSON-RPC client for the streamable HTTP transport used by job boards."""

    def __init__(self, http_client: Any, url: str) -> None:
        self._http = http_client
        self._url = url.rstrip("/")
        self._session_id: str | None = None
        self.last_rate_limited_count = 0

    def reset_metrics(self) -> None:
        self.last_rate_limited_count = 0
        self._session_id = None

    async def call(
        self, method: str, params: dict[str, Any] | None = None, *, rpc_id: int = 1
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
        if params is not None:
            payload["params"] = params
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        response = await self._http.post(
            self._url,
            json=payload,
            headers=headers,
        )
        if getattr(response, "status_code", 200) == 429:
            self.last_rate_limited_count += 1
        response.raise_for_status()
        body = getattr(response, "text", None)
        if body is None and hasattr(response, "json"):
            data = response.json()
            if isinstance(data, dict):
                self._remember_session(response, method)
                return data
            raise ValueError("Unexpected MCP JSON response")
        data = parse_jsonrpc_response(body or "")
        self._remember_session(response, method)
        return data

    def _remember_session(self, response: Any, method: str) -> None:
        if method != "initialize":
            return
        response_headers = getattr(response, "headers", {})
        session_id = response_headers.get("mcp-session-id")
        if session_id:
            self._session_id = str(session_id)
