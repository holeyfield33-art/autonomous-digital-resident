"""The Resident's persistent Linux sandbox: a long-lived container with the workspace at /workspace.

pip and npm installs go to a per-sandbox volume at /opt/deps and survive container recreation;
apt installs and other files outside /workspace last until the container is recreated.
Controller state, credentials and the Docker socket are never mounted.
"""

import os
import re
import shutil
import subprocess
import time
from pathlib import Path, PurePosixPath

from agent.tools.filesystem import redact

IMAGE = "resident-sandbox:latest"
DOCKERFILE_DIR = Path(__file__).resolve().parents[2] / "sandbox"
MAX_OUTPUT = 20000
READY_SECONDS = 300  # trust a verified-running container this long before inspecting again
EXEC_OVERHEAD = 30  # host-side slack beyond the in-container timeout; Docker Desktop can be slow
GONE = (b"No such container", b"is not running", b"is paused")
NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}$")
DEPS = "/opt/deps"
DEPS_ENV = {
    "PIP_USER": "1",
    "PYTHONUSERBASE": f"{DEPS}/python",
    "NPM_CONFIG_PREFIX": f"{DEPS}/npm",
    "NODE_PATH": f"{DEPS}/npm/lib/node_modules",
    # The sandbox is root by design; these warnings only cost the model tokens.
    "PIP_ROOT_USER_ACTION": "ignore",
    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
}
# Login shells reset PATH from /etc/profile, so the deps bin dirs are added via profile.d.
DEPS_PROFILE = f"export PATH={DEPS}/python/bin:{DEPS}/npm/bin:$PATH\n"


def _same_path(a, b):
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


def _clip(data):
    text = data.decode("utf-8", errors="replace")
    if len(text) <= MAX_OUTPUT:
        return text, False
    half = MAX_OUTPUT // 2
    return text[:half] + f"\n... [{len(text) - MAX_OUTPUT} chars omitted] ...\n" + text[-half:], True


class Sandbox:
    def __init__(self, workspace, name="resident-sandbox", network=True, memory="2g", cpus="2"):
        if not isinstance(name, str) or not NAME.match(name):
            raise ValueError("Sandbox name must be 1-63 characters: letters, digits, '_', '.', '-'")
        self.workspace = Path(workspace).resolve()
        self.name, self.network, self.memory, self.cpus = name, network, memory, cpus
        self.volume = f"{name}-deps"
        self.docker = shutil.which("docker")
        self._ready_at = None

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

    def _inspect(self):
        """(exists, running, host path mounted at /workspace) for this sandbox's container."""
        template = '{{.State.Running}}|{{range .Mounts}}{{if eq .Destination "/workspace"}}{{.Source}}{{end}}{{end}}'
        try:
            result = self._docker("inspect", "-f", template, self.name, timeout=60)
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "Docker did not answer within 60s (the host is busy); the sandbox was not changed. "
                "Retry the command in a later step."
            ) from None
        if result.returncode:
            return False, False, None
        running, _, source = result.stdout.decode(errors="replace").strip().partition("|")
        return True, running == "true", source or None

    def running(self):
        return self._inspect()[1]

    def ensure(self):
        if self._ready_at is not None and time.monotonic() - self._ready_at < READY_SECONDS:
            return
        exists, running, source = self._inspect()
        if exists and not (source and _same_path(source, self.workspace)):
            # Another resident's sandbox: never run in it, and never remove it.
            raise RuntimeError(
                f"Container {self.name!r} belongs to a different workspace ({source}); "
                "give this resident its own sandbox name"
            )
        if running:
            self._ready_at = time.monotonic()
            return
        self._ready_at = None
        if exists:
            self._docker("rm", "-f", self.name, timeout=30)
        if not self.image_exists():
            self.build()
        args = [
            "run", "-d", "--name", self.name,
            "--hostname", "resident",
            "--memory", self.memory, "--cpus", self.cpus, "--pids-limit", "512",
            "--security-opt", "no-new-privileges:true",
            "--mount", f"type=bind,source={self.workspace},target=/workspace",
            "--mount", f"type=volume,source={self.volume},target={DEPS}",
            "--restart", "unless-stopped",
        ]
        for key, value in DEPS_ENV.items():
            args += ["-e", f"{key}={value}"]
        if not self.network:
            args += ["--network", "none"]
        result = self._docker(*args, IMAGE, timeout=120)
        if result.returncode:
            raise RuntimeError("Sandbox start failed: " + result.stderr.decode(errors="replace")[-1000:])
        self._docker(
            "exec", "-i", self.name, "sh", "-c", "cat > /etc/profile.d/resident-deps.sh",
            stdin=DEPS_PROFILE.encode(), timeout=60,
        )
        self._ready_at = time.monotonic()

    def status(self):
        try:
            return {
                "available": bool(self.docker),
                "name": self.name,
                "running": self.running(),
                "image": IMAGE,
                "deps_volume": self.volume,
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
        workdir = str(PurePosixPath("/workspace") / rel)
        for attempt in range(2):
            self.ensure()
            try:
                result = self._docker(
                    "exec", "-i", "-w", workdir, self.name, *argv, timeout=timeout + EXEC_OVERHEAD, stdin=stdin
                )
            except subprocess.TimeoutExpired:
                # Kill whatever is still running from this call; the container itself survives.
                try:
                    self._docker("exec", self.name, "pkill", "-f", "-9", "resident-exec", timeout=30)
                except subprocess.TimeoutExpired:
                    pass
                return {"status": "timeout", "exit_code": None, "output": f"Timed out after {timeout}s"}
            if attempt == 0 and result.returncode and any(marker in result.stderr for marker in GONE):
                self._ready_at = None  # container stopped since it was verified; recreate and retry once
                continue
            break
        output, clipped = _clip(result.stdout + (b"\n[stderr]\n" + result.stderr if result.stderr else b""))
        status = {0: "ok", 124: "timeout"}.get(result.returncode, "failed")
        return {
            "status": status,
            "exit_code": result.returncode,
            "output": redact(output),
            "output_clipped": clipped,
        }

    def shell(self, command: str, timeout: int = 120, cwd: str = "."):
        """Run a bash command in your Linux sandbox (cwd relative to /workspace). Internet, pip, npm, apt, git available.
        `pip install` and `npm install -g` persist in /opt/deps across sandbox resets; apt installs may not."""
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command must be a non-empty string")
        script = f"exec -a resident-exec timeout {timeout} bash -lc {_quote(command)}"
        return {"command": command, **self._exec(["bash", "-c", script], cwd, timeout)}

    def python(self, code: str, timeout: int = 120, cwd: str = "."):
        """Run Python source code in the sandbox (passed on stdin, so no shell quoting needed)."""
        if not isinstance(code, str) or not code.strip():
            raise ValueError("code must be non-empty Python source")
        script = f"exec -a resident-exec timeout {timeout} python -"
        return self._exec(["bash", "-c", script], cwd, timeout, stdin=code.encode("utf-8"))


def _quote(text):
    return "'" + text.replace("'", "'\"'\"'") + "'"
