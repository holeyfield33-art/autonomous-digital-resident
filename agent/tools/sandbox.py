"""The Resident's persistent Linux sandbox: a long-lived container with the workspace at /workspace.

Installed packages and files outside /workspace persist until the container is recreated.
Controller state, credentials and the Docker socket are never mounted.
"""

import shutil
import subprocess
from pathlib import Path, PurePosixPath

from agent.tools.filesystem import redact

IMAGE = "resident-sandbox:latest"
DOCKERFILE_DIR = Path(__file__).resolve().parents[2] / "sandbox"
MAX_OUTPUT = 20000


def _clip(data):
    text = data.decode("utf-8", errors="replace")
    if len(text) <= MAX_OUTPUT:
        return text, False
    half = MAX_OUTPUT // 2
    return text[:half] + f"\n... [{len(text) - MAX_OUTPUT} chars omitted] ...\n" + text[-half:], True


class Sandbox:
    def __init__(self, workspace, name="resident-sandbox", network=True, memory="2g", cpus="2"):
        self.workspace = Path(workspace).resolve()
        self.name, self.network, self.memory, self.cpus = name, network, memory, cpus
        self.docker = shutil.which("docker")

    def _docker(self, *args, timeout=60, stdin=None):
        if not self.docker:
            raise RuntimeError("Docker is not installed on the host")
        return subprocess.run(
            [self.docker, *args], input=stdin, capture_output=True, timeout=timeout, check=False
        )

    def image_exists(self):
        return self._docker("image", "inspect", IMAGE, timeout=30).returncode == 0

    def build(self):
        result = self._docker("build", "-t", IMAGE, str(DOCKERFILE_DIR), timeout=1800)
        if result.returncode:
            raise RuntimeError("Sandbox image build failed: " + result.stderr.decode(errors="replace")[-2000:])

    def running(self):
        result = self._docker("inspect", "-f", "{{.State.Running}}", self.name, timeout=30)
        return result.returncode == 0 and result.stdout.strip() == b"true"

    def ensure(self):
        if self.running():
            return
        self._docker("rm", "-f", self.name, timeout=30)
        if not self.image_exists():
            self.build()
        args = [
            "run", "-d", "--name", self.name,
            "--hostname", "resident",
            "--memory", self.memory, "--cpus", self.cpus, "--pids-limit", "512",
            "--security-opt", "no-new-privileges:true",
            "--mount", f"type=bind,source={self.workspace},target=/workspace",
            "--restart", "unless-stopped",
        ]
        if not self.network:
            args += ["--network", "none"]
        result = self._docker(*args, IMAGE, timeout=120)
        if result.returncode:
            raise RuntimeError("Sandbox start failed: " + result.stderr.decode(errors="replace")[-1000:])

    def status(self):
        try:
            return {
                "available": bool(self.docker),
                "running": self.running(),
                "image": IMAGE,
                "network": "internet" if self.network else "none",
                "workspace_mount": "/workspace",
            }
        except Exception as exc:
            return {"available": False, "error": f"{type(exc).__name__}: {exc}"}

    def _exec(self, argv, cwd, timeout, stdin=None):
        if type(timeout) is not int or not 1 <= timeout <= 900:
            raise ValueError("timeout must be 1..900 seconds")
        rel = PurePosixPath(cwd or ".")
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("cwd must be relative to /workspace")
        self.ensure()
        workdir = str(PurePosixPath("/workspace") / rel)
        try:
            result = self._docker(
                "exec", "-i", "-w", workdir, self.name, *argv, timeout=timeout + 5, stdin=stdin
            )
        except subprocess.TimeoutExpired:
            # Kill whatever is still running from this call; the container itself survives.
            self._docker("exec", self.name, "pkill", "-f", "-9", "resident-exec", timeout=15)
            return {"status": "timeout", "exit_code": None, "output": f"Timed out after {timeout}s"}
        output, clipped = _clip(result.stdout + (b"\n[stderr]\n" + result.stderr if result.stderr else b""))
        status = {0: "ok", 124: "timeout"}.get(result.returncode, "failed")
        return {
            "status": status,
            "exit_code": result.returncode,
            "output": redact(output),
            "output_clipped": clipped,
        }

    def shell(self, command: str, timeout: int = 120, cwd: str = "."):
        """Run a bash command in your Linux sandbox (cwd relative to /workspace). Internet, pip, apt, git available."""
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command must be a non-empty string")
        script = f"exec -a resident-exec timeout {timeout} bash -lc {_quote(command)}"
        return {"command": command, **self._exec(["bash", "-c", script], cwd, timeout)}

    def python(self, code: str, timeout: int = 120, cwd: str = "."):
        """Run Python source code in the sandbox (passed on stdin, so no shell quoting needed)."""
        if not isinstance(code, str) or not code.strip():
            raise ValueError("code must be non-empty Python source")
        return self._exec(
            ["timeout", str(timeout), "python", "-"], cwd, timeout, stdin=code.encode("utf-8")
        )


def _quote(text):
    return "'" + text.replace("'", "'\"'\"'") + "'"
