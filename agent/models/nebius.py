"""Controller-only, bounded no-retry Nemotron inference with durable reservations."""

import asyncio
import json
import os

import httpx
from openai import OpenAI

from agent.tools.filesystem import check_text

MODEL = "nvidia/nemotron-3-super-120b-a12b"
BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
MAX_REQUEST_BYTES = 400_000
MAX_OUTPUT_TOKENS = 8192
# Median decision latency is ~3s, but long outputs have taken ~50s and 60s timed out several wakes.
REQUEST_TIMEOUT = httpx.Timeout(180.0, connect=15.0)
# Conservative accounting ceiling, not a claim about current list pricing.
MICRO_USD_PER_TOKEN = 2


class NebiusClient:
    mode = "live"

    def __init__(self, state, api_key=None, client=None):
        self.state = state
        key = api_key or os.environ.get("NEBIUS_API_KEY", "")
        if not key and client is None:
            raise ValueError("NEBIUS_API_KEY required for explicitly selected live mode")
        self.client = client or OpenAI(
            api_key=key,
            base_url=BASE_URL,
            max_retries=0,
            timeout=REQUEST_TIMEOUT,
            http_client=httpx.Client(trust_env=False, follow_redirects=False),
        )
        self.last_usage = None

    async def chat(self, messages, cycle, schema=None):
        body = {
            "model": MODEL,
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        }
        if schema:
            # Provider-side constrained decoding: output must parse and match the decision schema.
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "decision", "schema": schema},
            }
        serialized = json.dumps(body, ensure_ascii=False)
        check_text(serialized)
        size = len(serialized.encode())
        if size > MAX_REQUEST_BYTES:
            raise ValueError(f"Request exceeds {MAX_REQUEST_BYTES}-byte context cap")
        input_bound = size + 8192
        reservation = self.state.reserve(cycle, (input_bound + MAX_OUTPUT_TOKENS) * MICRO_USD_PER_TOKEN)
        # Full request bodies grow with in-wake history; record the newest turn plus sizes.
        self.state.event(
            cycle,
            "request",
            {
                "bytes": size,
                "messages": len(messages),
                "schema": bool(schema),
                "last_message": messages[-1] if messages else None,
            },
        )
        try:
            response = await asyncio.to_thread(self.client.chat.completions.create, **body)
        except Exception as exc:
            self.state.event(
                cycle, "provider_error", {"type": type(exc).__name__, "reservation_retained": True}
            )
            raise RuntimeError("Provider request failed; reservation retained, no automatic retry") from None
        raw = response.model_dump(mode="json")
        usage = raw.get("usage") or {}
        prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if any(type(v) is not int or v < 0 for v in (prompt, completion)):
            raise RuntimeError("Missing usage; reservation retained")
        exceeded = prompt > input_bound or completion > MAX_OUTPUT_TOKENS
        accounted_tokens = (
            max(prompt + completion, input_bound + MAX_OUTPUT_TOKENS + 1) if exceeded else prompt + completion
        )
        self.state.settle(reservation, accounted_tokens * MICRO_USD_PER_TOKEN, raw.get("id", ""))
        if exceeded:
            raise RuntimeError("Usage exceeded token bound")
        choices = raw.get("choices") or []
        choice = choices[0] if choices else {}
        content = (choice.get("message") or {}).get("content") or ""
        check_text(content)
        self.last_usage = {
            "usage": usage,
            "provider_id": raw.get("id"),
            "model": raw.get("model"),
            "finish_reason": choice.get("finish_reason"),
        }
        self.state.event(cycle, "response", {**self.last_usage, "content": content})
        # A truncated ("length") reply is returned for parsing/repair rather than failing the wake.
        return content

    def close(self):
        self.client.close()

    def model_info(self):
        return {"model": MODEL, "provider": "Nebius Token Factory", "mode": self.mode}


class DemoModel:
    """Explicit canned transport demo. Never used as evidence of autonomous choice."""

    mode = "demo"

    def __init__(self):
        self.calls = 0

    async def chat(self, messages, cycle, schema=None):
        self.calls += 1
        feedback = json.loads(messages[-1]["content"])
        if feedback.get("tool_results") is not None:
            actions = []
            summary = "Observed the tool results; this canned demonstration step is complete."
        else:
            actions = [
                {
                    "name": "create_artifact",
                    "arguments": {
                        "name": f"continuity-{cycle}.md",
                        "kind": "note",
                        "content": f"Offline transport demo cycle {cycle}. Previous cycles observed: "
                        + str(len(feedback.get("recent_cycles", []))),
                    },
                }
            ]
            summary = "Canned demonstration: create a continuity artifact."
        return json.dumps(
            {
                "summary": summary,
                "direction": "Demonstrate restart continuity",
                "intent": "continue",
                "actions": actions,
                "next_wake_seconds": 10,
            }
        )

    def close(self):
        pass

    def model_info(self):
        return {"model": None, "mode": self.mode, "provider_calls": 0}
