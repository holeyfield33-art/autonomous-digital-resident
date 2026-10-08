import subprocess
import sys
from types import SimpleNamespace

import pytest

from agent import cli
from agent.tools.registry import build_default_registry
from agent.tools.sandbox import Sandbox


def test_python_writes_report_syntax(tmp_path):
    tools = build_default_registry(tmp_path)
    good = tools.call("write_file", path="ok.py", content="def f():\n    return 1\n")
    assert good["syntax"] == "ok"
    bad = tools.call("write_file", path="bad.py", content='"""doc"""\nx = 1\n"""\n')
    assert bad["syntax"] == "error" and bad["syntax_error"]["line"] == 3
    assert (tmp_path / "bad.py").exists()  # reported, not blocked
    broken = tools.call("edit_file", path="ok.py", old_text="return 1", new_text="return (1")
    assert broken["status"] == "edited" and broken["syntax"] == "error"
    assert "syntax" not in tools.call("write_file", path="notes.md", content="# not python (\n")


def test_edit_miss_returns_closest_match(tmp_path):
    tools = build_default_registry(tmp_path)
    tools.call("write_file", path="a.py", content="import os\n\ndef main():\n    print('hello world')\n    return 0\n")
    miss = tools.call("edit_file", path="a.py", old_text="def main():\n  print('hello world')\n", new_text="x")
    assert miss["error"] == "ValueError" and "closest_match" in miss["message"]
    assert miss["closest_match"] == "def main():\n    print('hello world')\n"
    assert miss["closest_lines"] == [3, 4] and miss["similarity"] >= 0.5
    retry = tools.call("edit_file", path="a.py", old_text=miss["closest_match"], new_text="def main():\n")
    assert retry["status"] == "edited"
    unrelated = tools.call("edit_file", path="a.py", old_text="zzzzzzzzzzzzzzzzzzzz", new_text="x")
    assert "closest_match" not in unrelated and "read_file" in unrelated["message"]


class FakeSandbox(Sandbox):
    def __init__(self, workspace, replies, name="resident-sandbox"):
        super().__init__(workspace, name=name)
        self.docker, self.calls, self.argv, self.replies = "docker", [], [], replies

    def _docker(self, *args, timeout=60, stdin=None):
        self.calls.append(args[0] if args[0] != "exec" else ("exec", args[-1]))
        self.argv.append(args)
        reply = self.replies(args)
        if isinstance(reply, Exception):
            raise reply
        return reply


def _ok(stdout=b"", stderr=b"", code=0):
    return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def _up(workspace):
    return _ok(f"true|{workspace}\n".encode())


def test_sandbox_inspects_once_and_recovers(tmp_path):
    state = {"gone": False}

    def replies(args):
        if args[0] == "inspect":
            return _up(tmp_path)
        if args[0] == "exec" and state["gone"]:
            state["gone"] = False
            return _ok(stderr=b"Error response from daemon: container abc is not running", code=1)
        return _ok(b"hi\n")

    box = FakeSandbox(tmp_path, replies)
    assert box.shell("echo hi")["status"] == "ok"
    assert box.python("print('hi')")["status"] == "ok"
    assert box.calls.count("inspect") == 1  # cached between calls
    state["gone"] = True
    assert box.shell("echo hi")["status"] == "ok"  # retried after re-verifying
    assert box.calls.count("inspect") == 2


def test_sandbox_slow_docker_is_reported_as_data(tmp_path):
    def slow_inspect(args):
        return subprocess.TimeoutExpired(args, 60) if args[0] == "inspect" else _ok()

    tools = build_default_registry(tmp_path, sandbox=FakeSandbox(tmp_path, slow_inspect))
    result = tools.call("shell", command="ls")
    assert result["error"] == "RuntimeError" and "Retry" in result["message"]

    def hung_exec(args):
        if args[0] == "inspect":
            return _up(tmp_path)
        return subprocess.TimeoutExpired(args, 30)  # both the command and the pkill hang

    box = FakeSandbox(tmp_path, hung_exec)
    assert box.python("while True: pass", timeout=5)["status"] == "timeout"


def test_sandbox_never_uses_or_removes_another_residents_container(tmp_path):
    other = tmp_path / "other-workspace"
    mine = tmp_path / "workspace-b"
    for running in (b"true", b"false"):
        box = FakeSandbox(mine, lambda args, r=running: _ok(r + f"|{other}\n".encode()) if args[0] == "inspect" else _ok())
        tools = build_default_registry(mine, sandbox=box)
        result = tools.call("shell", command="ls")
        assert result["error"] == "RuntimeError" and "different workspace" in result["message"]
        assert box.calls == ["inspect"]  # no exec, no rm, no run


def test_new_sandbox_gets_persistent_deps(tmp_path):
    created = {"done": False}

    def replies(args):
        if args[0] == "inspect":
            return _up(tmp_path) if created["done"] else _ok(code=1)
        if args[0] == "run":
            created["done"] = True
        return _ok()

    box = FakeSandbox(tmp_path, replies, name="resident-sandbox-b")
    box.ensure()
    run = next(a for a in box.argv if a[0] == "run")
    assert "rm" not in box.calls  # nothing existed to remove
    assert "type=volume,source=resident-sandbox-b-deps,target=/opt/deps" in run
    assert "PIP_USER=1" in run and "NPM_CONFIG_PREFIX=/opt/deps/npm" in run
    assert any("profile.d" in str(a) for a in box.argv if a[0] == "exec")
    with pytest.raises(ValueError):
        Sandbox(tmp_path, name="bad name; rm -rf /")


def test_explicit_missing_soul_is_refused(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["resident", "status", "--soul", "souls/typo.md"])
    with pytest.raises(SystemExit, match="Soul file not found"):
        cli.main()
