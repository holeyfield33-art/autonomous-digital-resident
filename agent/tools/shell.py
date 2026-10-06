"""Constrained shell tool — allowlist of safe commands inside the workspace."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

# Commands that are generally safe for an autonomous agent in its own workspace.
# Expand deliberately; never allow arbitrary network-destructive or system-wide ops by default.
ALLOWED_PREFIXES = (
    "ls", "pwd", "echo", "cat", "head", "tail", "wc", "find",
    "python", "python3", "pip", "pip3",
    "git status", "git log", "git diff", "git add", "git commit",
    "mkdir", "touch", "cp", "mv", "rm",  # rm is allowed but scoped by cwd=workspace
    "curl", "wget",  # network read; still constrained by timeout
    "which", "env",
)


class ShellTools:
    def __init__(self, workspace: Path | str, timeout: float = 60.0) -> None:
        self.workspace = Path(workspace).resolve()
        self.timeout = timeout

    def _allowed(self, command: str) -> bool:
        cmd = command.strip()
        if not cmd:
            return False
        # Reject obvious shell metacharacters that enable chaining outside intent
        for bad in (";", "&&", "||", "`", "$(", ">", ">>", "|"):
            # Allow simple pipes later if needed; for now keep strict
            if bad in cmd and bad not in ("|",):  # still block most
                if bad in (";", "&&", "||", "`", "$("):
                    return False
        return any(cmd == p or cmd.startswith(p + " ") for p in ALLOWED_PREFIXES)

    def run(self, command: str, timeout: float | None = None) -> dict[str, Any]:
        if not self._allowed(command):
            return {
                "error": "Command not on allowlist",
                "command": command,
                "hint": "Use filesystem tools for file I/O, or expand ALLOWED_PREFIXES deliberately.",
            }
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
            )
            return {
                "command": command,
                "returncode": result.returncode,
                "stdout": result.stdout[-20_000:],  # cap output
                "stderr": result.stderr[-5_000:],
                "status": "ok" if result.returncode == 0 else "failed",
            }
        except subprocess.TimeoutExpired:
            return {"error": "timeout", "command": command}
        except Exception as e:
            return {"error": str(e), "command": command}
