"""Load and manage the Resident's persistent identity."""

from __future__ import annotations

from pathlib import Path


def load_soul(path: str | Path = "SOUL.md") -> str:
    """Read the current SOUL.md content."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"SOUL.md not found at {p.resolve()}")
    return p.read_text(encoding="utf-8")


def soul_summary(soul_text: str, max_chars: int = 1200) -> str:
    """Return a truncated but coherent summary for injection into prompts."""
    text = soul_text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20].rsplit("\n", 1)[0] + "\n\n[... identity continues ...]"
