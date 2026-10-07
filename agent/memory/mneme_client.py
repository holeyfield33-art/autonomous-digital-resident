"""Authenticated local MCP sessions. Only this resident's exact memory keys are read."""

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class MnemeClient:
    def __init__(self, resident_id, base_url=None, api_key=None, config_path=None):
        config = {}
        if config_path:
            config = json.loads(Path(config_path).read_text(encoding="utf-8-sig"))
        self.base_url = (
            base_url
            or config.get("endpoint")
            or os.environ.get("MNEME_MCP_URL", "http://127.0.0.1:8010/mcp/")
        )
        self.api_key = (
            api_key
            or config.get("personal_api_key")
            or os.environ.get("MNEME_API_KEY")
            or os.environ.get("MNEME_LOCAL_API_KEY", "")
        )
        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username
        ):
            raise ValueError("This memory profile requires an authenticated loopback MCP endpoint")
        self.prefix = f"resident/{resident_id}/"

    async def _call_tool(self, name, arguments):
        if name not in {"store_memory", "get_memory", "verify_memory"}:
            raise ValueError("Memory capability not granted")
        if not arguments.get("key", "").startswith(self.prefix):
            raise ValueError("Foreign memory namespace rejected")
        if not self.api_key:
            raise RuntimeError("Mneme credential unavailable")
        # SDK performs initialize, session handling and JSON/SSE decoding.
        async with asyncio.timeout(15):
            async with streamablehttp_client(
                self.base_url, headers={"Authorization": f"Bearer {self.api_key}"}
            ) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)
                    if result.isError:
                        raise RuntimeError("Mneme tool refused request")
                    if result.structuredContent is not None:
                        value = result.structuredContent
                    else:
                        value = json.loads(next(item.text for item in result.content if item.type == "text"))
                    # Some MCP versions wrap non-object tool results.
                    return value.get("result", value) if isinstance(value, dict) else value

    async def get_memory(self, key):
        return await self._call_tool("get_memory", {"key": key})

    async def verify_memory(self, key):
        return await self._call_tool("verify_memory", {"key": key})

    async def ensure_memory(self, key, value):
        from agent.tools.filesystem import check_text

        check_text(value)
        previous = await self.get_memory(key)
        if isinstance(previous, dict) and previous.get("value") is not None:
            if previous["value"] != value:
                raise RuntimeError("Memory conflict; refusing overwrite")
        else:
            result = await self._call_tool(
                "store_memory", {"key": key, "value": value, "category": "resident", "attribution": "agent"}
            )
            if not isinstance(result, dict) or result.get("error"):
                raise RuntimeError("Mneme store failed")
        verification = await self.verify_memory(key)
        if not isinstance(verification, dict) or verification.get("valid") is not True:
            raise RuntimeError("Memory integrity verification failed")

    async def close(self):
        pass  # Each SDK session is closed in its originating async context.


async def sync_outbox(state, client):
    if client is None:
        return {"mode": "local", "synced": 0}
    count = 0
    for item in state.pending():
        try:
            await client.ensure_memory(item["key"], item["value"])
            state.memory_result(item["key"])
            count += 1
        except Exception as exc:
            state.memory_result(item["key"], type(exc).__name__)
            return {"mode": "degraded_local", "synced": count, "error_type": type(exc).__name__}
    return {"mode": "mneme", "synced": count}
