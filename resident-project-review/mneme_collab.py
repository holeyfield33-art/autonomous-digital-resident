"""Operator-authorized collaboration against the Resident Mneme namespace."""
import asyncio
import json
import sys
from pathlib import Path

from dotenv import dotenv_values
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parent.parent
    token = dotenv_values(root / ".env").get("MNEME_API_KEY")
    if not token:
        raise RuntimeError("Resident Mneme credential unavailable")
    requests = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    async with asyncio.timeout(45):
        async with streamablehttp_client(
            "http://127.0.0.1:8010/mcp/",
            headers={"Authorization": "Bearer " + token},
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                for request in requests:
                    result = await session.call_tool(request["tool"], request["arguments"])
                    values = [json.loads(c.text) for c in result.content if c.type == "text"]
                    print(json.dumps({"tool": request["tool"], "results": values}, ensure_ascii=True))
                    if result.isError or any(isinstance(v, dict) and v.get("error") for v in values):
                        raise RuntimeError("Mneme operation returned an error")


if __name__ == "__main__":
    asyncio.run(main())
