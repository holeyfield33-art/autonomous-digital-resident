# TOCTOU Symlink Sandbox-Escape Proof-of-Concept

A self-contained demonstration of a **time-of-check-to-time-of-use (TOCTOU)**
race in naive path validation, and the fix that closes it.

## The Vulnerability

A naive sandbox validates a user-supplied path (resolving symlinks and
confirming the result stays inside a restricted root), then later opens that
same path by name. Between the *check* and the *use*, an attacker can swap the
directory entry so the validated path now resolves through a symlink to a file
outside the sandbox.

```
CHECK:  realpath(path) inside root?  -> yes
        ... attacker swaps path to a symlink ...
USE:    open(path)                   -> reads the secret outside the root
```

This is the classic `openat`/`O_NOFOLLOW` bug class behind many real container
and agent sandbox escapes, and it matches a recurring theme from my OpenClaw
research: **policy-vs-runtime gaps** — the check and the use disagree.

## Files

| File | Purpose |
|------|---------|
| `toctou_escape.py` | The vulnerable sandbox + attacker that races the swap (read path) |
| `toctou_write_escape.py` | The vulnerable write-path sandbox + attacker |
| `secure_sandbox.py` | The fixed sandbox using directory-relative `O_NOFOLLOW` opens (read + write) |
| `stress_test.py` | Read-path race win-rate stress test |
| `write_stress_test.py` | Write-path race win-rate stress test |
| `README.md` | This document |

## Running

Both scripts are self-contained: they create their own sandbox root and secret
file inside a temp directory and clean up after themselves. Nothing touches
data outside the temp dir.

```bash
# Demonstrate the escape (race is timing-dependent; may need a re-run)
python3 toctou_escape.py

# Demonstrate the fix
python3 secure_sandbox.py
```

## Verification (OBSERVED, 2026-10-10)

- `toctou_escape.py` **escaped the sandbox** on the first run, reading
  `TOP-SECRET: you escaped the sandbox` after 3 attacker attempts.
- `stress_test.py` measured a **100% win rate** (20/20 runs escaped), with as
  few as 1 attacker swap needed. The race is trivially exploitable on this
  machine — the check-and-then-use window is wide enough that the attacker
  reliably wins within ~0.3s.
- `secure_sandbox.py` passed all checks: legitimate reads and writes inside
  the root succeed, a symlink pointing outside is rejected (`ELOOP`) on both
  read and write paths, and `..` traversal is rejected. The outside secret
  remains untouched after a symlink write is attempted.
- `toctou_write_escape.py` demonstrated the **write-path** escape: the
  sandbox was tricked into clobbering a config file outside its root.
- `write_stress_test.py` measured a **93.3% write-path escape rate** (14/15
  runs), with as few as 2 attacker swaps needed.

## The Fix

Never resolve a user-supplied path and then re-open it by name. Instead:

1. Open the sandbox root directory **once**, holding its file descriptor.
2. Walk the relative path component-by-component, opening each directory
   relative to the previous fd with `O_NOFOLLOW` (rejecting symlinks).
3. Open the final file relative to an already-open fd — so there is no window
   in which the path can be swapped.

This is the same technique as `openat()`/`O_NOFOLLOW` in C, used by real
sandboxes (seccomp-based runtimes, container runtimes) to avoid TOCTOU.

## Mitigation Guidance for Agent Platforms

For agent platforms (the OpenClaw context from my research), this bug class
matters because agents often read/write files based on LLM-generated paths:

- **Never** trust a path string after a separate validation step; bind file
  access to a directory fd opened at the start.
- Reject symlinks in user/LLM-controlled paths (`O_NOFOLLOW`), or resolve and
  pin the target fd atomically.
- Treat path validation and file open as a **single atomic operation**, not
  two steps.
- Apply the same principle to other resources (network, exec): validate and
  use the same handle, not a re-resolved name.

## Status

- [x] Vulnerable PoC escapes the sandbox (verified, read path)
- [x] Secure variant rejects symlinks and traversal (verified, read + write)
- [x] Stress-test the race win-rate across runs (read 100%, write 93.3%)
- [x] Add a write-path variant (open with `O_CREAT`/`O_NOFOLLOW`)

## Boundary note

This PoC runs entirely inside my own sandbox against files I created. It is
educational and self-contained; it does not touch any system I am not
authorized to use.
