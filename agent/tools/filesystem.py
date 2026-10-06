"""Filesystem tools — the Resident can inspect and write its workspace."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class FilesystemTools:
    def __init__(self, workspace: Path | str) -> None:
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _safe(self, relative: str) -> Path:
        """Resolve a path under workspace; reject escapes."""
        target = (self.workspace / relative).resolve()
        if not str(target).startswith(str(self.workspace)):
            raise ValueError(f"Path escapes workspace: {relative}")
        return target

    def list_dir(self, relative: str = ".") -> dict[str, Any]:
        path = self._safe(relative)
        if not path.exists():
            return {"error": f"Not found: {relative}"}
        if not path.is_dir():
            return {"error": f"Not a directory: {relative}"}
        entries = []
        for p in sorted(path.iterdir()):
            entries.append({
                "name": p.name,
                "type": "dir" if p.is_dir() else "file",
                "size": p.stat().st_size if p.is_file() else None,
            })
        return {"path": relative, "entries": entries}

    def read_file(self, relative: str, max_chars: int = 50_000) -> dict[str, Any]:
        path = self._safe(relative)
        if not path.exists() or not path.is_file():
            return {"error": f"File not found: {relative}"}
        text = path.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > max_chars
        return {
            "path": relative,
            "content": text[:max_chars],
            "truncated": truncated,
            "chars": len(text),
        }

    def write_file(self, relative: str, content: str, overwrite: bool = True) -> dict[str, Any]:
        path = self._safe(relative)
        if path.exists() and not overwrite:
            return {"error": f"File exists and overwrite=False: {relative}"}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"path": relative, "bytes_written": len(content.encode("utf-8")), "status": "ok"}

    def append_file(self, relative: str, content: str) -> dict[str, Any]:
        path = self._safe(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(content)
        return {"path": relative, "status": "appended"}

    def mkdir(self, relative: str) -> dict[str, Any]:
        path = self._safe(relative)
        path.mkdir(parents=True, exist_ok=True)
        return {"path": relative, "status": "ok"}

    def exists(self, relative: str) -> dict[str, Any]:
        path = self._safe(relative)
        return {
            "path": relative,
            "exists": path.exists(),
            "is_file": path.is_file() if path.exists() else False,
            "is_dir": path.is_dir() if path.exists() else False,
        }
