"""Bounded workspace IO. The local operator is trusted; model paths are not."""

import hashlib
import os
import re
import stat
from pathlib import Path, PurePosixPath

SECRET = re.compile(
    r"""(?i)(?:api[_-]?key|access[_-]?token|password|private[_-]?key)\s*[=:]\s*['"]?[^\s'"]{8,}|-----BEGIN .*PRIVATE KEY-----|\b(?:ghp_|github_pat_|sk-)[A-Za-z0-9_-]{20,}"""
)
MAX_FILE = 100_000


def check_text(text):
    if not isinstance(text, str) or len(text.encode()) > MAX_FILE or SECRET.search(text):
        raise ValueError("Text size or sensitive-content policy rejected input")


class FilesystemTools:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _safe(self, relative):
        if not isinstance(relative, str) or len(relative) > 240 or "\\" in relative or ":" in relative:
            raise ValueError("Invalid workspace path")
        parts = PurePosixPath(relative)
        if parts.is_absolute() or any(p == ".." or p.startswith(".") for p in parts.parts):
            raise ValueError("Workspace path rejected")
        target = self.workspace.joinpath(*parts.parts)
        current = self.workspace
        for part in parts.parts:
            current /= part
            if current.is_symlink():
                raise ValueError("Symlinks are not supported")
            if current.exists():
                info = current.lstat()
                if getattr(info, "st_file_attributes", 0) & getattr(
                    stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024
                ):
                    raise ValueError("Reparse points are not supported")
                if current.is_file() and info.st_nlink > 1:
                    raise ValueError("Hardlinked files are not supported")
        target.resolve().relative_to(self.workspace)
        return target

    def list_dir(self, relative="."):
        entries = []
        with os.scandir(self._safe(relative)) as scan:
            for entry in scan:
                if len(entries) >= 100:
                    break
                if not entry.name.startswith("."):
                    entries.append(
                        {
                            "name": entry.name,
                            "type": "link"
                            if entry.is_symlink()
                            else "dir"
                            if entry.is_dir(follow_symlinks=False)
                            else "file",
                        }
                    )
        return {"path": relative, "entries": sorted(entries, key=lambda e: e["name"]), "limit": 100}

    def read_file(self, relative, max_chars=12000):
        if type(max_chars) is not int or not 1 <= max_chars <= 16000:
            raise ValueError("Read limit must be 1..16000")
        with self._safe(relative).open("rb") as stream:
            raw = stream.read(MAX_FILE + 1)
        if len(raw) > MAX_FILE:
            raise ValueError("File exceeds read cap")
        text = raw.decode("utf-8")
        check_text(text)
        return {
            "path": relative,
            "content": text[:max_chars],
            "truncated": len(text) > max_chars,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    def _quota(self, size, target):
        count, total, directories = 0, size, 0
        for folder, dirs, files in os.walk(self.workspace, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(folder) / d).is_symlink()]
            directories += len(dirs)
            for name in files:
                path = Path(folder) / name
                count += 1
                if path != target:
                    total += path.lstat().st_size
            if count >= 1000 or total > 10_000_000 or directories >= 200:
                raise ValueError("Workspace quota reached")

    def write_file(self, relative, content, overwrite=False):
        check_text(content)
        if type(overwrite) is not bool:
            raise ValueError("overwrite must be boolean")
        path = self._safe(relative)
        if path.exists() and not overwrite:
            raise ValueError("File exists; explicitly set overwrite=true")
        self._quota(len(content.encode()), path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w" if overwrite else "x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        return {
            "path": relative,
            "bytes_written": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "status": "written",
        }

    def update_file(self, relative, content):
        check_text(content)
        path = self._safe(relative)
        if not path.is_file() or path.is_symlink():
            raise ValueError("Existing regular file required")
        self._quota(len(content.encode()), path)
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        return {
            "path": relative,
            "bytes_written": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "status": "updated",
        }

    def delete_file(self, relative):
        path = self._safe(relative)
        if not path.is_file() or path.is_symlink():
            raise ValueError("Existing regular file required")
        path.unlink()
        return {"path": relative, "status": "deleted"}

    def append_file(self, relative, content):
        path = self._safe(relative)
        old = ""
        if path.exists():
            if path.stat().st_size > MAX_FILE:
                raise ValueError("File exceeds cap")
            old = path.read_text(encoding="utf-8")
        return self.write_file(relative, old + content, overwrite=True)

    def mkdir(self, relative):
        self._quota(0, self._safe(relative))
        self._safe(relative).mkdir(parents=True, exist_ok=True)
        return {"path": relative, "status": "created"}

    def exists(self, relative):
        return {"path": relative, "exists": self._safe(relative).exists()}
