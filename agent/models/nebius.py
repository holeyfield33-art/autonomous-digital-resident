"""Nebius Token Factory client — OpenAI-compatible access to NVIDIA Nemotron models."""

from __future__ import annotations

import os
from typing import Any, Sequence

from openai import OpenAI
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class NebiusClient:
    """Thin wrapper around the Nebius Token Factory OpenAI-compatible API.

    Ensures at least one NVIDIA open model is used meaningfully at runtime.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        primary_model: str | None = None,
        fallback_model: str | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("NEBIUS_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"
        )
        self.primary_model = primary_model or os.environ.get(
            "PRIMARY_MODEL", "nvidia/Nemotron-3_5-Lightning"
        )
        self.fallback_model = fallback_model or os.environ.get(
            "FALLBACK_MODEL", "nvidia/nemotron-3-super-120b-a12b"
        )

        if not self.api_key:
            raise ValueError(
                "NEBIUS_API_KEY is required. Get one at https://tokenfactory.nebius.com"
            )

        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(
        self,
        messages: Sequence[dict[str, str] | ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """Send a chat completion request. Returns the assistant message content."""
        model = model or self.primary_model
        payload = [
            m.model_dump() if isinstance(m, ChatMessage) else m for m in messages
        ]

        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=payload,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception:
            # Simple fallback to secondary Nemotron model
            if model != self.fallback_model:
                response = self._client.chat.completions.create(
                    model=self.fallback_model,
                    messages=payload,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            else:
                raise

        choice = response.choices[0]
        return choice.message.content or ""

    def model_info(self) -> dict[str, str]:
        return {
            "primary": self.primary_model,
            "fallback": self.fallback_model,
            "base_url": self.base_url,
            "provider": "Nebius Token Factory",
        }
