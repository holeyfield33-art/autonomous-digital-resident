"""Check release candidates against local credentials without printing values."""
import json
import subprocess
from pathlib import Path

from dotenv import dotenv_values


def main():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                            cwd=root, capture_output=True, check=True)
    paths = [p for p in result.stdout.decode().split("\0") if p]
    env = dotenv_values(root / ".env", interpolate=False) if (root / ".env").exists() else {}
    secrets = [value.encode() for key, value in env.items() if "KEY" in key and value and len(value) >= 12]
    forbidden, matches = [], []
    for relative in paths:
        if relative.startswith((".resident/", ".venv/", "workspace/")) and not relative.endswith(".gitkeep"):
            forbidden.append(relative)
        if relative == ".env" or relative.endswith((".sqlite", ".log")):
            forbidden.append(relative)
        raw = (root / relative).read_bytes()
        if any(secret in raw for secret in secrets):
            matches.append(relative)
    print(json.dumps({"files_checked": len(paths), "forbidden_files": forbidden,
                      "credential_match_files": matches,
                      "limitation": "Known local credential matching, not universal secret detection"}))
    if forbidden or matches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
