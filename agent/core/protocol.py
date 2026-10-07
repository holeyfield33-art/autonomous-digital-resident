"""Bounded public decision/action contract. No hidden reasoning is requested."""

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=50)
    arguments: dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: str = Field(min_length=1, max_length=1000)
    direction: str = Field(min_length=1, max_length=500)
    intent: Literal["explore", "build", "continue", "abandon", "rest"]
    actions: list[Action] = Field(max_length=4)
    next_wake_seconds: int = Field(default=300, ge=10, le=3600)


def parse_decision(raw: str) -> Decision:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 24000:
        raise ValueError("Decision exceeds size limit")
    # Strict JSON, no fences, prose extraction or silent repairs.
    return Decision.model_validate(json.loads(raw))
