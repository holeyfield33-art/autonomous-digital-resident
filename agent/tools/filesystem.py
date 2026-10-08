"""Workspace IO. The local operator is trusted; model paths are not."""

import ast
import difflib
import fnmatch
import hashlib
import os
import re
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

SECRET = re.compile(
    r"""(?i)(?:api[_-]?key|access[_-]?token|password|private[_-]?key)\s*[=:]\s*['"]?[^\s'"]{8,}|-----BEGIN .*PRIVATE KEY-----|\b(?:ghp_|github_pat_|sk-)[A-Za-z0-9_-]{20,}"""
)
MAX_FILE = 1_000_000
MAX_READ = 40_000
QUOTA_FILES, QUOTA_BYTES, QUOTA_DIRS = 20_000, 500_000_000, 5_000


def check_text(text, limit=MAX_FILE):
    if not isinstance(text, str):
        raise ValueError("Text must be a string")
    if len(text.encode()) > limit:
        raise ValueError(f"Text exceeds {limit} bytes")
    if SECRET.search(text):
        raise ValueError("Text looks like it contains a credential (api_key=/password=/private key); rejected")


def redact(text):
    """Model-facing results keep their shape; credential-looking spans are masked."""
    return SECRET.sub("[REDACTED]", text) if isinstance(text, str) else text


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mtime(path):
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")


def _syntax(path, content):
    """Parse (never run) a written .py file so a broken write is reported in the same step."""
    if path.suffix != ".py":
        return {}
    try:
        ast.parse(content, filename=path.name)
    except SyntaxError as exc:
        return {
            "syntax": "error",
            "syntax_error": {
                "line": exc.lineno,
                "message": exc.msg,
                "text": redact((exc.text or "").rstrip()[:200]),
            },
            "hint": "The file was saved but does not parse; read_file around that line and fix it before running.",
        }
    return {"syntax": "ok"}


def _closest(text, old_text):
    """The file window most similar to old_text, for an actionable edit_file miss."""
    lines, wanted = text.splitlines(keepends=True), old_text.splitlines(keepends=True)
    size = max(1, len(wanted))
    if not lines or len(lines) > 20_000:
        return None
    best, best_ratio = None, 0.0
    matcher = difflib.SequenceMatcher(autojunk=False)
    matcher.set_seq2(old_text)
    for start in range(max(1, len(lines) - size + 1)):
        window = "".join(lines[start : start + size])
        matcher.set_seq1(window)
        if matcher.real_quick_ratio() <= best_ratio or matcher.quick_ratio() <= best_ratio:
            continue
        ratio = matcher.ratio()
        if ratio > best_ratio:
            best, best_ratio = (start, window), ratio
    if best is None or best_ratio < 0.5:
        return None
    start, window = best
    return {
        "closest_match": redact(window[:3000]),
        "closest_lines": [start + 1, min(start + size, len(lines))],
        "similarity": round(best_ratio, 2),
    }


class FilesystemTools:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _safe(self, relative):
        if not isinstance(relative, str) or len(relative) > 240 or "\\" in relative or ":" in relative:
            raise ValueError("Invalid path: use a workspace-relative path with forward slashes, e.g. notes/a.md")
        relative = relative.strip() or "."
        if relative.startswith("/workspace/") or relative == "/workspace":
            relative = relative[len("/workspace") :].lstrip("/") or "."
        parts = PurePosixPath(relative)
        if parts.is_absolute() or any(p == ".." or (p.startswith(".") and p != ".") for p in parts.parts):
            raise ValueError("Path rejected: must stay inside the workspace and not use hidden (.name) parts")
        target = self.workspace.joinpath(*[p for p in parts.parts if p != "."])
        current = self.workspace
        for part in parts.parts:
            if part == ".":
                continue
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

    def _rel(self, path):
        return path.relative_to(self.workspace).as_posix() or "."

    def _walk(self, root):
        for folder, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not (Path(folder) / d).is_symlink())
            for name in sorted(files):
                if not name.startswith("."):
                    yield Path(folder) / name

    def _missing(self, path, relative, kind="File"):
        if not path.exists():
            parent = path.parent
            nearby = []
            if parent.is_dir():
                nearby = sorted(p.name for p in parent.iterdir() if not p.name.startswith("."))[:20]
            raise FileNotFoundError(
                f"{kind} not found: {relative}. Entries in {self._rel(parent) if parent.is_dir() else '?'}: {nearby}"
            )

    def _quota(self, size, target):
        count, total, directories = 0, size, 0
        for folder, dirs, files in os.walk(self.workspace, followlinks=False):
            directories += len(dirs)
            for name in files:
                path = Path(folder) / name
                count += 1
                if path != target:
                    total += path.lstat().st_size
            if count >= QUOTA_FILES or total > QUOTA_BYTES or directories >= QUOTA_DIRS:
                raise ValueError("Workspace quota reached; delete or consolidate files")

    def list_dir(self, path: str = ".", depth: int = 1):
        """List a directory. depth>1 shows nested entries (max 4)."""
        if type(depth) is not int or not 1 <= depth <= 4:
            raise ValueError("depth must be 1..4")
        root = self._safe(path)
        self._missing(root, path, "Directory")
        if not root.is_dir():
            raise NotADirectoryError(f"{path} is a file; use read_file")
        entries = []

        def visit(folder, level):
            for entry in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
                if entry.name.startswith(".") or len(entries) >= 300:
                    continue
                item = {"path": self._rel(entry), "type": "dir" if entry.is_dir() else "file"}
                if entry.is_file():
                    item["bytes"] = entry.stat().st_size
                    item["modified"] = _mtime(entry)
                entries.append(item)
                if entry.is_dir() and not entry.is_symlink() and level < depth:
                    visit(entry, level + 1)

        visit(root, 1)
        return {"path": path, "entries": entries, "truncated": len(entries) >= 300}

    def read_file(self, path: str, start_line: int = 1, end_line: int = 0, max_chars: int = 20000):
        """Read a text file. Optional 1-based start_line/end_line (0 = to end). Lines are not numbered."""
        if type(max_chars) is not int or not 1 <= max_chars <= MAX_READ:
            raise ValueError(f"max_chars must be 1..{MAX_READ}")
        if type(start_line) is not int or type(end_line) is not int or start_line < 1 or end_line < 0:
            raise ValueError("start_line must be >=1 and end_line >=0 (0 means end of file)")
        target = self._safe(path)
        self._missing(target, path)
        if target.is_dir():
            raise IsADirectoryError(f"{path} is a directory; use list_dir")
        raw = target.read_bytes()
        if len(raw) > MAX_FILE:
            raise ValueError("File exceeds 1MB read cap; use search_text or the sandbox")
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines(keepends=True)
        selected = "".join(lines[start_line - 1 : end_line or None])
        return {
            "path": path,
            "content": redact(selected[:max_chars]),
            "total_lines": len(lines),
            "start_line": start_line,
            "end_line": min(end_line or len(lines), len(lines)),
            "truncated": len(selected) > max_chars,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    def _write(self, target, content):
        self._quota(len(content.encode()), target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        return {
            "path": self._rel(target),
            "bytes": target.stat().st_size,
            "sha256": _sha(target),
            **_syntax(target, content),
        }

    def write_file(self, path: str, content: str, overwrite: bool = False):
        """Create a file (parents created). Set overwrite=true to replace an existing file."""
        check_text(content)
        if type(overwrite) is not bool:
            raise ValueError("overwrite must be true or false")
        target = self._safe(path)
        if target.is_dir():
            raise IsADirectoryError(f"{path} is a directory")
        if target.exists() and not overwrite:
            raise FileExistsError(
                f"{path} already exists. Use overwrite=true to replace it, edit_file to change part of it, "
                "or append_file to add to it."
            )
        existed = target.exists()
        return {**self._write(target, content), "status": "overwritten" if existed else "created"}

    def update_file(self, path: str, content: str):
        """Replace the entire content of an existing file."""
        check_text(content)
        target = self._safe(path)
        self._missing(target, path)
        if not target.is_file():
            raise IsADirectoryError(f"{path} is not a regular file")
        return {**self._write(target, content), "status": "updated"}

    def append_file(self, path: str, content: str):
        """Append text to a file, creating it if needed."""
        check_text(content)
        target = self._safe(path)
        old = target.read_text(encoding="utf-8") if target.is_file() else ""
        return {**self._write(target, old + content), "status": "appended"}

    def edit_file(self, path: str, old_text: str, new_text: str, replace_all: bool = False):
        """Replace exact old_text with new_text. old_text must match once unless replace_all=true."""
        check_text(new_text)
        if not isinstance(old_text, str) or not old_text:
            raise ValueError("old_text must be a non-empty exact excerpt of the file")
        target = self._safe(path)
        self._missing(target, path)
        text = target.read_text(encoding="utf-8")
        count = text.count(old_text)
        if count == 0:
            near = _closest(text, old_text)
            error = ValueError(
                f"old_text not found in {path}; "
                + ("copy closest_match exactly as old_text" if near else "read_file it and copy the exact text")
            )
            error.details = near or {}
            raise error
        if count > 1 and not replace_all:
            raise ValueError(f"old_text matches {count} places; include more context or set replace_all=true")
        updated = text.replace(old_text, new_text) if replace_all else text.replace(old_text, new_text, 1)
        check_text(updated)
        return {**self._write(target, updated), "replacements": count if replace_all else 1, "status": "edited"}

    def move(self, source: str, destination: str, overwrite: bool = False):
        """Move or rename a file or directory."""
        src, dst = self._safe(source), self._safe(destination)
        self._missing(src, source, "Source")
        if dst.exists():
            if not overwrite or dst.is_dir():
                raise FileExistsError(f"{destination} exists; choose another name (or overwrite=true for a file)")
            dst.unlink()
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return {"source": source, "destination": destination, "status": "moved"}

    def copy(self, source: str, destination: str, overwrite: bool = False):
        """Copy a file or directory."""
        src, dst = self._safe(source), self._safe(destination)
        self._missing(src, source, "Source")
        if dst.exists() and not overwrite:
            raise FileExistsError(f"{destination} exists; set overwrite=true or choose another name")
        size = sum(p.stat().st_size for p in self._walk(src)) if src.is_dir() else src.stat().st_size
        self._quota(size, dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=overwrite)
        else:
            shutil.copy2(src, dst)
        return {"source": source, "destination": destination, "status": "copied"}

    def delete(self, path: str, recursive: bool = False):
        """Delete a file, an empty directory, or (recursive=true) a directory tree."""
        target = self._safe(path)
        if target == self.workspace:
            raise ValueError("Refusing to delete the workspace root")
        self._missing(target, path, "Path")
        if target.is_dir():
            if any(target.iterdir()) and not recursive:
                raise OSError(f"{path} is a non-empty directory; set recursive=true to delete it and its contents")
            shutil.rmtree(target) if recursive else target.rmdir()
            return {"path": path, "status": "deleted_directory"}
        target.unlink()
        return {"path": path, "status": "deleted"}

    def mkdir(self, path: str):
        """Create a directory (and parents)."""
        target = self._safe(path)
        self._quota(0, target)
        existed = target.is_dir()
        target.mkdir(parents=True, exist_ok=True)
        return {"path": path, "status": "exists" if existed else "created"}

    def exists(self, path: str):
        """Check whether a path exists and what it is."""
        target = self._safe(path)
        kind = "dir" if target.is_dir() else "file" if target.is_file() else None
        return {"path": path, "exists": kind is not None, "type": kind}

    def file_info(self, path: str):
        """Size, line count, modified time and sha256 of a file."""
        target = self._safe(path)
        self._missing(target, path)
        if target.is_dir():
            files = list(self._walk(target))
            return {"path": path, "type": "dir", "files": len(files), "bytes": sum(f.stat().st_size for f in files)}
        raw = target.read_bytes()
        return {
            "path": path,
            "type": "file",
            "bytes": len(raw),
            "lines": raw.count(b"\n") + (1 if raw and not raw.endswith(b"\n") else 0),
            "modified": _mtime(target),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    def find_files(self, pattern: str = "*", path: str = "."):
        """Find files whose path or name matches a glob, e.g. '*.py' or 'notes/*.md'."""
        root = self._safe(path)
        self._missing(root, path, "Directory")
        matches = []
        for file in self._walk(root):
            rel = self._rel(file)
            if fnmatch.fnmatch(file.name, pattern) or fnmatch.fnmatch(rel, pattern):
                matches.append({"path": rel, "bytes": file.stat().st_size, "modified": _mtime(file)})
                if len(matches) >= 200:
                    break
        return {"pattern": pattern, "matches": matches, "truncated": len(matches) >= 200}

    def search_text(self, query: str, path: str = ".", regex: bool = False, file_glob: str = "*", max_results: int = 50):
        """Search file contents (case-insensitive). Returns path, line number and line text."""
        if not isinstance(query, str) or not query:
            raise ValueError("query must be non-empty")
        if type(max_results) is not int or not 1 <= max_results <= 200:
            raise ValueError("max_results must be 1..200")
        pattern = re.compile(query if regex else re.escape(query), re.IGNORECASE)
        root = self._safe(path)
        self._missing(root, path, "Path")
        files = [root] if root.is_file() else self._walk(root)
        hits, scanned = [], 0
        for file in files:
            if not fnmatch.fnmatch(file.name, file_glob) or file.stat().st_size > MAX_FILE:
                continue
            scanned += 1
            try:
                text = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    hits.append({"path": self._rel(file), "line": number, "text": redact(line.strip()[:300])})
                    if len(hits) >= max_results:
                        return {"query": query, "hits": hits, "files_scanned": scanned, "truncated": True}
        return {"query": query, "hits": hits, "files_scanned": scanned, "truncated": False}

    def snapshot(self):
        """Controller-only: size/mtime fingerprint for change detection."""
        result = {}
        for file in self._walk(self.workspace):
            if len(result) >= QUOTA_FILES:
                break
            info = file.stat()
            result[self._rel(file)] = (info.st_size, info.st_mtime_ns)
        return result

    def diff(self, before, after):
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
        hashed = {}
        for rel in (added + changed)[:200]:
            try:
                hashed[rel] = _sha(self.workspace / rel)
            except OSError:
                pass
        return {
            "added": [{"path": p, "sha256": hashed.get(p)} for p in added[:200]],
            "modified": [{"path": p, "sha256": hashed.get(p)} for p in changed[:200]],
            "deleted": removed[:200],
        }

    def summary(self, recent=10):
        files = list(self._walk(self.workspace))
        top = sorted(
            (p.name + ("/" if p.is_dir() else "") for p in self.workspace.iterdir() if not p.name.startswith(".")),
        )
        newest = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)[:recent]
        return {
            "files": len(files),
            "bytes": sum(f.stat().st_size for f in files),
            "top_level": top[:80],
            "recently_modified": [{"path": self._rel(f), "modified": _mtime(f)} for f in newest],
        }
