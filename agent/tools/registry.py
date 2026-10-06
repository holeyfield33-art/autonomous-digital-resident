"""Tool registry — discoverable tools available to the Resident."""

from __future__ import annotations

from typing import Any, Callable


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any], description: str = "") -> None:
        self._tools[name] = fn
        # description can later feed into model tool schemas

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())

    def get(self, name: str) -> Callable[..., Any] | None:
        return self._tools.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


def build_default_registry() -> ToolRegistry:
    """Populate with built-in tools (filesystem, shell, web, artifacts, mneme helpers)."""
    reg = ToolRegistry()
    # Concrete tool modules will register themselves here as they are implemented.
    return reg
