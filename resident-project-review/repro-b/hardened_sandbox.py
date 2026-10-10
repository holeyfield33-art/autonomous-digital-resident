"""Reference file boundary for the Agent B TOCTOU reproduction.

Linux only. The root is pinned once, path components are opened relative to
directory descriptors, every intermediate descriptor is closed, and regular
files with multiple hard links are rejected.
"""

from __future__ import annotations

import errno
import os
import stat


_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class HardenedSandbox:
    def __init__(self, root: str):
        flags = os.O_RDONLY | os.O_DIRECTORY | _NOFOLLOW | _CLOEXEC
        self._root_fd = os.open(os.path.abspath(root), flags)

    def close(self):
        if self._root_fd is not None:
            os.close(self._root_fd)
            self._root_fd = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    @staticmethod
    def _parts(relpath: str) -> list[str]:
        if os.path.isabs(relpath):
            raise PermissionError("absolute paths not allowed")
        parts = relpath.split(os.sep)
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise PermissionError(f"invalid path: {relpath}")
        return parts

    def _open_parent(self, relpath: str):
        if self._root_fd is None:
            raise RuntimeError("sandbox is closed")
        parts = self._parts(relpath)
        parent_fd = os.dup(self._root_fd)
        try:
            for part in parts[:-1]:
                next_fd = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | _NOFOLLOW | _CLOEXEC,
                    dir_fd=parent_fd,
                )
                os.close(parent_fd)
                parent_fd = next_fd
            return parent_fd, parts[-1]
        except BaseException:
            os.close(parent_fd)
            raise

    @staticmethod
    def _validate_file(fd: int):
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise PermissionError("only regular files are allowed")
        if info.st_nlink != 1:
            raise PermissionError("hard-linked files are not allowed")

    def read_file(self, relpath: str) -> str:
        parent_fd, leaf = self._open_parent(relpath)
        try:
            fd = os.open(leaf, os.O_RDONLY | _NOFOLLOW | _CLOEXEC, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)
        try:
            self._validate_file(fd)
            with os.fdopen(fd, "r") as stream:
                fd = -1
                return stream.read()
        finally:
            if fd >= 0:
                os.close(fd)

    def write_file(self, relpath: str, content: str):
        parent_fd, leaf = self._open_parent(relpath)
        fd = -1
        try:
            try:
                # Open without truncating, validate the inode, then truncate.
                fd = os.open(leaf, os.O_WRONLY | _NOFOLLOW | _CLOEXEC, dir_fd=parent_fd)
            except FileNotFoundError:
                try:
                    fd = os.open(
                        leaf,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
                        0o600,
                        dir_fd=parent_fd,
                    )
                except FileExistsError as exc:
                    raise PermissionError("file changed during creation") from exc
            self._validate_file(fd)
            os.ftruncate(fd, 0)
            with os.fdopen(fd, "w") as stream:
                fd = -1
                stream.write(content)
        finally:
            if fd >= 0:
                os.close(fd)
            os.close(parent_fd)
