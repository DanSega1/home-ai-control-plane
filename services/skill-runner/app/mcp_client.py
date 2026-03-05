"""
Minimal async MCP (Model Context Protocol) SSE client.

Connects to an MCP server over SSE, performs the initialize handshake,
lists available tools, and executes tool calls.

Spec: https://spec.modelcontextprotocol.io/specification/
"""

from __future__ import annotations

import json
import logging
from typing import Any
import uuid

import httpx

log = logging.getLogger("skill-runner.mcp")


class MCPError(Exception):
    pass


class MCPClient:
    """
    Stateless async MCP client for SSE transport.

    Usage:
        async with MCPClient(server_url, token) as mcp:
            tools = await mcp.list_tools()
            result = await mcp.call_tool("create_raindrop", {"link": "https://..."})
    """

    def __init__(self, server_url: str, token: str = "") -> None:
        self.server_url = server_url.rstrip("/")
        self.token = token
        self._tools_cache: list[dict[str, Any]] | None = None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a JSON-RPC 2.0 request to the MCP server."""
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.server_url}",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()

            # MCP servers may return SSE or plain JSON
            content_type = resp.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                return self._parse_sse(resp.text)
            else:
                data = resp.json()
                if "error" in data:
                    raise MCPError(f"MCP error: {data['error']}")
                return data.get("result")

    @staticmethod
    def _parse_sse(raw: str) -> Any:
        """Extract the first data line from an SSE response."""
        for line in raw.splitlines():
            if line.startswith("data:"):
                payload = line[5:].strip()
                try:
                    obj = json.loads(payload)
                    if "error" in obj:
                        raise MCPError(f"MCP error: {obj['error']}")
                    return obj.get("result")
                except json.JSONDecodeError:
                    return payload
        return None

    async def initialize(self) -> dict[str, Any]:
        """Perform the MCP initialize handshake."""
        result = await self._rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "home-ai-skill-runner", "version": "0.1.0"},
            },
        )
        return result or {}

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return the list of tools exposed by the MCP server."""
        if self._tools_cache is not None:
            return self._tools_cache
        result = await self._rpc("tools/list")
        self._tools_cache = (result or {}).get("tools", [])
        log.info("MCP server at %s exposes %d tools", self.server_url, len(self._tools_cache))
        return self._tools_cache

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Invoke an MCP tool and return its content."""
        result = await self._rpc(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
        )
        if result is None:
            return None
        content = result.get("content", [])
        # Flatten text content blocks to a single string for simplicity
        parts = []
        for block in content:
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif block.get("type") == "json":
                parts.append(json.dumps(block.get("json", {})))
        return "\n".join(parts) if parts else result

    async def tools_as_openai_spec(self) -> list[dict[str, Any]]:
        """
        Convert MCP tool definitions to OpenAI function-calling spec
        so LiteLLM can use them as tools in an LLM call.
        """
        tools = await self.list_tools()
        result = []
        for t in tools:
            schema = t.get("inputSchema", {"type": "object", "properties": {}})
            # OpenAI requires 'properties' to be present on any object-type schema
            if isinstance(schema, dict) and schema.get("type") == "object":
                schema = dict(schema)
                schema.setdefault("properties", {})
            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": schema,
                    },
                }
            )
        return result

    async def __aenter__(self) -> MCPClient:
        await self.initialize()
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass
