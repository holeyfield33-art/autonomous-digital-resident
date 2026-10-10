#!/usr/bin/env python3
"""
Write-path TOCTOU race stress test
==================================

Runs the vulnerable write-path sandbox (toctou_write_escape.py) many times
and measures how often the attacker successfully clobbers a file outside the
sandbox root, and how many attacker attempts each escape takes.

Usage:
    python3 write_stress_test.py [runs]
"""

import os
import sys
import tempfile
import threading
import time

# Reuse the vulnerable classes from the PoC module.
from toctou_write_escape import NaiveWriteSandbox, WriteAttacker


def single_run(deadline_seconds=3.0):
    """Run one race. Returns (escaped, attempts)."""
    workdir = tempfile.mkdtemp(prefix="toctou-write-stress-")
    root = os.path.join(workdir, "sandbox")
    os.makedirs(root)

    target_path = os.path.join(workdir, "config.ini")
    with open(target_path, "w") as f:
        f.write("mode=secure\n")

    victim_path = os.path.join(root, "data.txt")
    sandbox = NaiveWriteSandbox(root)
    attacker = WriteAttacker(root, victim_path, target_path)

    t = threading.Thread(target=attacker.run, daemon=True)
    t.start()

    escaped = False
    deadline = time.time() + deadline_seconds
    while time.time() < deadline and not escaped:
        try:
            sandbox.write_file(victim_path, "mode=compromised\n")
            with open(target_path, "r") as f:
                if "compromised" in f.read():
                    escaped = True
        except (PermissionError, FileNotFoundError):
            pass

    attacker.stop.set()
    t.join(timeout=1.0)
    return escaped, attacker.attempts


def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    wins = 0
    attempts_list = []
    min_attempts = None

    print(f"Running {runs} write-path races...")
    for i in range(runs):
        escaped, attempts = single_run()
        if escaped:
            wins += 1
            attempts_list.append(attempts)
            if min_attempts is None or attempts < min_attempts:
                min_attempts = attempts
        else:
            attempts_list.append(0)

    win_rate = 100.0 * wins / runs
    print(f"\nWrite-path escape rate: {wins}/{runs} = {win_rate:.1f}%")
    if attempts_list:
        print(f"Attacker attempts per run (escaped only): {attempts_list}")
        if min_attempts is not None:
            print(f"Fewest attempts to escape: {min_attempts}")


if __name__ == "__main__":
    main()
