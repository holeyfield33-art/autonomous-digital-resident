#!/usr/bin/env python3
"""
Secure Sandbox: TOCTOU-safe file access
=======================================

Fixes the naive sandbox in toctou_escape.py. The key principle:

    NEVER resolve a user-supplied path and then re-open it by name.

Instead, open the sandbox root directory once, then walk the relative path
component-by-component, opening each directory with os.open() and O_NOFOLLOW
so symlinks are rejected. The final file is opened relative to an already-open
file descriptor, so there is no window in which an attacker can swap the path.

This is the same idea as openat()/O_NOFOLLOW in C, and the technique real
sandboxes (e.g. seccomp-based, container runtimes) use to avoid TOCTOU.
"""

import os
import sys
import tempfile


class SecureSandbox:
    """TOCTOU-safe sandbox using directory-relative opens with O_NOFOLLOW."""

    def __init__(self, root):
        self.root = os.path.abspath(root)

    def _open_relative(self, relpath, flags):
        """Open a file relative to the sandbox root, rejecting symlinks.

        Walks each path component with O_NOFOLLOW so no component can be a
        symlink, and everything is resolved relative to an already-open fd --
        there is no check-then-use window. Returns the open fd.
        """
        # Normalize: reject absolute paths and any '..' escape.
        if os.path.isabs(relpath):
            raise PermissionError("absolute paths not allowed")
        parts = relpath.split(os.sep)
        if any(p in ("", ".", "..") for p in parts):
            raise PermissionError(f"invalid path component: {relpath}")

        # Open the root directory once.
        root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fd = root_fd
            # Walk each component, opening directories with O_NOFOLLOW.
            for i, part in enumerate(parts):
                is_last = (i == len(parts) - 1)
                if is_last:
                    comp_flags = flags
                else:
                    comp_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
                try:
                    fd = os.open(part, comp_flags, dir_fd=fd)
                except FileNotFoundError:
                    raise
                except OSError as e:
                    # O_NOFOLLOW raises ELOOP for symlinks.
                    if e.errno == getattr(os, "ELOOP", 40):
                        raise PermissionError(
                            f"symlink not allowed: {part}") from e
                    raise
            return fd
        finally:
            os.close(root_fd)

    def read_file(self, relpath):
        """Read a file given a path RELATIVE to the sandbox root."""
        fd = self._open_relative(relpath, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "r") as f:
            return f.read()

    def write_file(self, relpath, content):
        """Write a file given a path RELATIVE to the sandbox root.

        Uses O_WRONLY|O_CREAT|O_TRUNC with O_NOFOLLOW, so a symlink at the
        final component is rejected (ELOOP) rather than followed.
        """
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
        fd = self._open_relative(relpath, flags)
        with os.fdopen(fd, "w") as f:
            f.write(content)


def main():
    workdir = tempfile.mkdtemp(prefix="toctou-secure-")
    root = os.path.join(workdir, "sandbox")
    os.makedirs(root)

    secret_path = os.path.join(workdir, "secret.txt")
    with open(secret_path, "w") as f:
        f.write("TOP-SECRET\n")

    sandbox = SecureSandbox(root)

    # 1. Legitimate read inside the sandbox works.
    with open(os.path.join(root, "data.txt"), "w") as f:
        f.write("hello\n")
    print("OK: read inside sandbox:", sandbox.read_file("data.txt").strip())

    # 2. A symlink inside the sandbox pointing outside is rejected.
    os.symlink(secret_path, os.path.join(root, "evil.txt"))
    try:
        sandbox.read_file("evil.txt")
        print("FAIL: symlink was not rejected")
        sys.exit(1)
    except PermissionError as e:
        print("OK: symlink rejected:", e)

    # 3. Path traversal is rejected.
    try:
        sandbox.read_file("../secret.txt")
        print("FAIL: traversal was not rejected")
        sys.exit(1)
    except PermissionError as e:
        print("OK: traversal rejected:", e)

    # 4. Writing inside the sandbox works.
    sandbox.write_file("out.txt", "written by sandbox\n")
    with open(os.path.join(root, "out.txt"), "r") as f:
        assert f.read() == "written by sandbox\n"
    print("OK: write inside sandbox works")

    # 5. Writing through a symlink pointing outside is rejected (ELOOP).
    os.symlink(secret_path, os.path.join(root, "evil_write.txt"))
    try:
        sandbox.write_file("evil_write.txt", "clobbered\n")
        print("FAIL: symlink write was not rejected")
        sys.exit(1)
    except PermissionError as e:
        print("OK: symlink write rejected:", e)
    # The secret must remain untouched.
    with open(secret_path, "r") as f:
        assert f.read() == "TOP-SECRET\n"
    print("OK: secret outside sandbox untouched")

    print("\nSecure sandbox: all checks passed.")


if __name__ == "__main__":
    main()
