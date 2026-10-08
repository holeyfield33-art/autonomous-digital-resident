"""Public decision/action contract. No hidden reasoning is requested.

The provider is asked to decode against decision_schema(); parse_decision() still validates, and
applies only deterministic, recorded normalizations (never guesses at content).
"""

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

INTENTS = ("explore", "build", "continue", "abandon", "rest")
MAX_ACTIONS = 6


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=50)
    arguments: dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: str = Field(min_length=1, max_length=2000)
    direction: str = Field(min_length=1, max_length=500)
    intent: Literal["explore", "build", "continue", "abandon", "rest"]
    actions: list[Action] = Field(max_length=MAX_ACTIONS)
    next_wake_seconds: int = Field(default=300, ge=10, le=3600)


def decision_schema(tool_names=()):
    action = {
        "type": "object",
        "properties": {
            "name": {"type": "string", **({"enum": sorted(tool_names)} if tool_names else {})},
            "arguments": {"type": "object"},
        },
        "required": ["name", "arguments"],
    }
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "direction": {"type": "string"},
            "intent": {"type": "string", "enum": list(INTENTS)},
            "actions": {"type": "array", "items": action, "maxItems": MAX_ACTIONS},
            "next_wake_seconds": {"type": "integer", "minimum": 10, "maximum": 3600},
        },
        "required": ["summary", "direction", "intent", "actions", "next_wake_seconds"],
    }


def _load(raw, fixes):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    text = raw.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    if fence:
        text = fence.group(1)
        fixes.append("stripped_markdown_fence")
    start, end = text.find("{"), text.rfind("}")
    if start > 0 or (end != -1 and end < len(text) - 1):
        text = text[start : end + 1]
        fixes.append("trimmed_text_outside_object")
    try:
        # strict=False accepts raw newlines/tabs inside strings, the most common slip.
        data = json.loads(text, strict=False)
        fixes.append("allowed_control_characters_in_strings")
        return data
    except json.JSONDecodeError:
        pass
    trailing = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        data = json.loads(trailing, strict=False)
        fixes.append("removed_trailing_commas")
        return data
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Malformed JSON at char {exc.pos}: {exc.msg}. Return exactly one JSON object."
        ) from None


def _normalize(data, fixes):
    if not isinstance(data, dict):
        return data
    intent = data.get("intent")
    if isinstance(intent, str) and intent not in INTENTS:
        word = intent.strip().lower().split()[0] if intent.strip() else ""
        word = re.sub(r"[^a-z]", "", word)
        data["intent"] = word if word in INTENTS else "continue"
        fixes.append(f"intent {intent[:40]!r} -> {data['intent']!r}")
    if isinstance(data.get("next_wake_seconds"), (float, str)):
        try:
            data["next_wake_seconds"] = min(max(int(float(data["next_wake_seconds"])), 10), 3600)
            fixes.append("coerced_next_wake_seconds")
        except ValueError:
            data["next_wake_seconds"] = 300
    elif isinstance(data.get("next_wake_seconds"), int):
        data["next_wake_seconds"] = min(max(data["next_wake_seconds"], 10), 3600)
    for key in ("summary", "direction"):
        if not data.get(key):
            data[key] = "(none given)"
            fixes.append(f"filled_empty_{key}")
    actions = data.get("actions")
    if actions is None:
        data["actions"] = []
        fixes.append("missing_actions_as_empty")
    elif isinstance(actions, list):
        cleaned = []
        for item in actions:
            if isinstance(item, dict):
                if "tool" in item and "name" not in item:
                    item["name"] = item.pop("tool")
                    fixes.append("action.tool -> action.name")
                if "args" in item and "arguments" not in item:
                    item["arguments"] = item.pop("args")
                    fixes.append("action.args -> action.arguments")
                if item.get("arguments") is None:
                    item["arguments"] = {}
            cleaned.append(item)
        if len(cleaned) > MAX_ACTIONS:
            fixes.append(f"dropped_{len(cleaned) - MAX_ACTIONS}_actions_over_limit")
            cleaned = cleaned[:MAX_ACTIONS]
        data["actions"] = cleaned
    extra = set(data) - set(Decision.model_fields)
    for key in extra:
        data.pop(key)
        fixes.append(f"dropped_unknown_field_{key}")
    return data


def parse_decision(raw, fixes=None):
    """Return a Decision. Any normalization applied is appended to `fixes`."""
    fixes = [] if fixes is None else fixes
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 200_000:
        raise ValueError("Decision exceeds size limit")
    data = _normalize(_load(raw, fixes), fixes)
    try:
        return Decision.model_validate(data)
    except ValidationError as exc:
        details = []
        for err in exc.errors()[:5]:
            loc = ".".join(str(x) for x in err.get("loc", ()))
            details.append(f"{loc}: {err.get('msg')} (got {str(err.get('input'))[:80]!r})")
        raise ValueError("Decision schema rejected: " + "; ".join(details)) from None
