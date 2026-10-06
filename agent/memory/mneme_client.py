"""Client for Aletheia Mneme (https://github.com/holeyfield33-art/Mneme-).

Talks to the FastMCP HTTP endpoint with Bearer authentication.
Exposes the 16 tools the Resident needs for long-term memory.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


class MnemeClient:
    """Lightweight HTTP client for Aletheia Mneme MCP tools.

    In production this can be replaced by a full MCP client library;
    the current implementation uses the JSON-RPC style expected by
    streamable HTTP MCP endpoints for the core operations.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("MNEME_MCP_URL", "http://localhost:8000/mcp")).rstrip("/")
        self.api_key = api_key or os.environ.get("MNEME_API_KEY", "")
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Invoke an MCP tool via the streamable HTTP transport.

        Note: Exact payload shape may need adjustment once the live
        Mneme endpoint is confirmed. This is the canonical integration
        point.
        """
        # Minimal JSON-RPC style request used by many MCP HTTP bridges.
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        resp = await self._client.post(self.base_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Mneme tool error: {data['error']}")
        result = data.get("result", data)
        # FastMCP often wraps content; unwrap common shapes
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
            if isinstance(content, list) and content and "text" in content[0]:
                import json
                try:
                    return json.loads(content[0]["text"])
                except Exception:
                    return content[0]["text"]
        return result

    # ── Convenience wrappers matching Aletheia Mneme tools ──────────────

    async def store_memory(self, key: str, value: str, category: str = "general") -> dict:
        return await self._call_tool("store_memory", {"key": key, "value": value, "category": category})

    async def get_memory(self, key: str) -> dict:
        return await self._call_tool("get_memory", {"key": key})

    async def list_memories(self, category: str | None = None, limit: int = 50) -> list:
        args: dict[str, Any] = {"limit": limit}
        if category:
            args["category"] = category
        return await self._call_tool("list_memories", args)

    async def search_memory(self, query: str, limit: int = 10) -> list:
        return await self._call_tool("search_memory", {"query": query, "limit": limit})

    async def semantic_search(self, query: str, limit: int = 10) -> list:
        return await self._call_tool("semantic_search", {"query": query, "limit": limit})

    async def update_memory(self, key: str, value: str) -> dict:
        return await self._call_tool("update_memory", {"key": key, "value": value})

    async def forget_memory(self, key: str) -> dict:
        return await self._call_tool("forget_memory", {"key": key})

    async def reinforce(self, key: str, amount: float = 0.1) -> dict:
        return await self._call_tool("reinforce", {"key": key, "amount": amount})

    async def relate_memories(self, from_key: str, to_key: str, rel_type: str) -> dict:
        return await self._call_tool(
            "relate_memories", {"from_key": from_key, "to_key": to_key, "rel_type": rel_type}
        )

    async def get_related(self, key: str) -> list:
        return await self._call_tool("get_related", {"key": key})

    async def memory_history(self, key: str) -> list:
        return await self._call_tool("memory_history", {"key": key})

    async def verify_memory(self, key: str) -> dict:
        return await self._call_tool("verify_memory", {"key": key})

    async def get_stats(self) -> dict:
        return await self._call_tool("get_stats", {})

    async def export_memories(self) -> list:
        return await self._call_tool("export_memories", {})
