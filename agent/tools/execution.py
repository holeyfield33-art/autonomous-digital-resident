"""Opt-in ephemeral Docker execution. No host shell or writable host mount."""

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

from agent.tools.filesystem import FilesystemTools, check_text


class PythonRunner:
    def __init__(self, workspace, image=None):
        self.fs = FilesystemTools(workspace)
        self.image = image
        self.docker = shutil.which("docker")
        if image and not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise ValueError("Execution requires a locally inspected immutable Docker image ID")

    def run_python(self, relative):
        if not self.image or not self.docker:
            return {
                "error": "execution_unavailable",
                "detail": "Operator must configure a local Docker image ID",
            }
        source = self.fs.read_file(relative, max_chars=16000)
        if source["truncated"] or not relative.endswith(".py"):
            raise ValueError("Execution supports one UTF-8 Python file up to 16000 characters")
        check_text(source["content"])
        name = "resident-run-" + uuid.uuid4().hex
        environment = {
            k: v
            for k, v in os.environ.items()
            if k in {"PATH", "SystemRoot", "TEMP", "TMP", "HOME", "USERPROFILE"}
        }
        with tempfile.TemporaryDirectory(prefix="resident-input-") as folder:
            path = Path(folder) / "main.py"
            path.write_text(source["content"], encoding="utf-8", newline="\n")
            argv = [
                self.docker,
                "run",
                "--name",
                name,
                "--pull=never",
                "--network=none",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "--user=65534:65534",
                "--pids-limit=32",
                "--memory=128m",
                "--memory-swap=128m",
                "--cpus=0.5",
                "--ulimit=nofile=64:64",
                "--ulimit=cpu=5:5",
                "--tmpfs=/tmp:rw,noexec,nosuid,size=16m,nr_inodes=256",
                "--log-driver=none",
                "--mount",
                f"type=bind,source={folder},target=/input,readonly",
                "--workdir=/tmp",
                self.image,
                "python",
                "-I",
                "-B",
                "/input/main.py",
            ]
            output = bytearray()
            overflow = threading.Event()
            process = None
            try:
                process = subprocess.Popen(
                    argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=environment
                )

                def drain():
                    while True:
                        chunk = process.stdout.read(1024)
                        if not chunk:
                            break
                        available = 16000 - len(output)
                        output.extend(chunk[: max(0, available)])
                        if len(chunk) > available:
                            overflow.set()

                thread = threading.Thread(target=drain, daemon=True)
                thread.start()
                try:
                    code = process.wait(timeout=12)
                    status = "passed" if code == 0 else "failed"
                except subprocess.TimeoutExpired:
                    code, status = None, "timeout"
                # Docker cleanup is also required after timeout/disconnect, not only normal exit.
            finally:
                subprocess.run(
                    [self.docker, "rm", "-f", name],
                    env=environment,
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=5)
                    thread.join(timeout=5)
                    process.stdout.close()
            text = output.decode("utf-8", errors="replace")
            check_text(text)
            return {
                "status": "output_limit" if overflow.is_set() else status,
                "returncode": code,
                "output": text,
                "image_id": self.image,
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "network": "none",
                "host_writes": False,
                "limitation": "Exit status is execution evidence, not independent correctness proof",
            }
