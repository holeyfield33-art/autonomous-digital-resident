#!/usr/bin/env python3
"""
Stress-test the TOCTOU race: measure the escape win-rate across many runs.

Quantifies how reliably the naive sandbox can be escaped on this machine,
which matters for assessing real-world exploitability (a race that wins 1 in
1000 is less severe than one that wins 1 in 2).
"""

import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from toctou_escape import NaiveSandbox, Attacker


def single_attempt(duration=0.5):
    """Run one race; return (escaped: bool, attempts: int)."""
    workdir = tempfile.mkdtemp(prefix="toctou-stress-")
    root = os.path.join(workdir, "sandbox")
    os.makedirs(root)

    secret_path = os.path.join(workdir, "secret.txt")
    with open(secret_path, "w") as f:
        f.write("TOP-SECRET\n")

    victim_path = os.path.join(root, "data.txt")
    sandbox = NaiveSandbox(root)
    attacker = Attacker(root, victim_path, secret_path)

    t = threading.Thread(target=attacker.run, daemon=True)
    t.start()

    leaked = False
    deadline = time.time() + duration
    while time.time() < deadline and not leaked:
        try:
            content = sandbox.read_file(victim_path)
            if "TOP-SECRET" in content:
                leaked = True
        except (PermissionError, FileNotFoundError):
            pass

    attacker.stop.set()
    t.join(timeout=1.0)
    return leaked, attacker.attempts


def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5

    wins = 0
    total_attempts = 0
    print(f"Running {runs} races ({duration}s each)...")
    for i in range(runs):
        escaped, attempts = single_attempt(duration)
        total_attempts += attempts
        if escaped:
            wins += 1
        print(f"  run {i+1:2d}: {'ESCAPED' if escaped else 'blocked':8s} ({attempts} swaps)")

    win_rate = wins / runs * 100
    print(f"\nResult: {wins}/{runs} escaped ({win_rate:.1f}% win rate)")
    print(f"Total attacker swaps across runs: {total_attempts}")


if __name__ == "__main__":
    main()
