import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from agent.cli import resolve_mode_home
from agent.core.loop import ResidentLoop
from agent.core.protocol import parse_decision
from agent.memory.mneme_client import MnemeClient, sync_outbox
from agent.models.nebius import DemoModel, NebiusClient
from agent.runtime.dashboard import render
from agent.runtime.state import BudgetExceeded, State, single_runner
from agent.tools.artifacts import ArtifactTools
from agent.tools.filesystem import FilesystemTools
from agent.tools.registry import build_default_registry
from agent.tools.shell import ShellTools
from agent.tools.web import WebTools


def test_restart_feedback_and_artifact_provenance(tmp_path):
    state = State(tmp_path / "state")
    soul = tmp_path / "SOUL.md"
    soul.write_text("Explore independently and record observed results.")
    workspace = tmp_path / "workspace"
    tools = build_default_registry(workspace, state)
    for expected in (1, 2):
        model = DemoModel()
        loop = ResidentLoop(model, state, tools, soul, workspace, cycle_interval=0)
        asyncio.run(loop.run(1))
        assert state.recent(1)[0]["id"] == expected
        assert state.recent(1)[0]["status"] == "completed"
        assert model.calls == 2  # Second decision observes the actual write result.
    artifacts = list((workspace / "artifacts").iterdir())
    assert len(artifacts) == 2
    second = next(path for path in artifacts if path.name.endswith("continuity-2.md"))
    assert "Previous cycles observed: 1" in second.read_text()
    assert len(list((state.root / "journal").iterdir())) == 2
    assert len(state.recall()) == 2
    assert state.budget()["calls"] == 0
    assert state.runtime()["active"] is False
    assert all(r["mode"] == "demo" for r in state.recent())


def test_crash_claim_not_replayed_and_lock(tmp_path):
    state = State(tmp_path)
    cycle = state.begin("demo")
    with single_runner(tmp_path):
        with pytest.raises((RuntimeError, OSError)):
            with single_runner(tmp_path):
                pass
    state.recover()
    assert state.recent()[0]["status"] == "interrupted"
    assert state.begin("demo") > cycle


@pytest.mark.parametrize(
    "path", ["../workspace-evil/a", "/tmp/a", "C:/outside", "a/../../escape", ".env", "a/.git/config", "a\\b"]
)
def test_file_paths_reject_escapes(tmp_path, path):
    fs = FilesystemTools(tmp_path / "workspace")
    with pytest.raises(ValueError):
        fs.write_file(path, "x")


def test_artifact_escape_and_overwrite_and_secret(tmp_path):
    fs = FilesystemTools(tmp_path)
    fs.write_file("file.py", "print('hello')")
    with pytest.raises(ValueError):
        fs.write_file("file.py", "changed")
    with pytest.raises(ValueError):
        fs.write_file("file.py", "password='abcdefghijk'", overwrite=True)
    with pytest.raises(ValueError):
        ArtifactTools(tmp_path).create_artifact("a", "b", subdirectory="../../outside")
    assert fs.read_file("file.py")["content"] == "print('hello')"
    assert "error" in ShellTools(tmp_path).run("python -c 'print(1)'")


def test_update_and_delete_files_are_bounded(tmp_path):
    fs = FilesystemTools(tmp_path / "workspace")
    fs.write_file("notes.txt", "before")

    result = fs.update_file("notes.txt", "after")
    assert result["status"] == "updated"
    assert fs.read_file("notes.txt")["content"] == "after"

    result = fs.delete_file("notes.txt")
    assert result["status"] == "deleted"
    assert not fs.exists("notes.txt")["exists"]

    with pytest.raises(ValueError):
        fs.update_file("missing.txt", "new")
    with pytest.raises(ValueError):
        fs.delete_file("../outside.txt")
    with pytest.raises(ValueError):
        fs.delete_file("directory")


def test_hardlink_refused(tmp_path):
    fs = FilesystemTools(tmp_path / "workspace")
    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    os.link(outside, fs.workspace / "link.txt")
    with pytest.raises(ValueError):
        fs.read_file("link.txt")


def test_no_ambient_network():
    with pytest.raises(ValueError):
        WebTools().fetch("http://127.0.0.1:8010/health")
    with pytest.raises(ValueError):
        WebTools(["https://example.com/page"]).fetch("https://example.com/page?data=secret")


def test_atomic_budget_zero_and_ambiguous(tmp_path):
    state = State(tmp_path / "zero", 0)
    with pytest.raises(BudgetExceeded):
        state.reserve(1, 1)
    state = State(tmp_path / "shared", 100)

    def reserve(_):
        try:
            return state.reserve(1, 60)
        except BudgetExceeded:
            return None

    with ThreadPoolExecutor(2) as pool:
        claims = list(pool.map(reserve, range(2)))
    assert sum(c is not None for c in claims) == 1
    assert State(tmp_path / "shared", 1000).budget()["cap_usd"] == 1.0
    assert state.budget()["unresolved"] == 1
    state.settle(next(c for c in claims if c), 110, "provider")
    assert state.budget()["halted"]


def test_explicit_budget_cap_can_raise_stale_cap(tmp_path):
    State(tmp_path / "stale", 500_000)
    state = State(tmp_path / "stale", 15_000_000)
    assert state.budget()["cap_usd"] == 15.0
    with pytest.raises(ValueError):
        State(tmp_path / "stale", 10_000_000)


def test_outbox_retries_only_own_memory(tmp_path):
    state = State(tmp_path)
    key = f"resident/{state.resident_id}/cycle/1"
    state.remember(key, "An observed artifact was created.")

    class Memory:
        fail = True

        async def ensure_memory(self, key, value):
            if self.fail:
                raise ConnectionError()

    memory = Memory()
    assert asyncio.run(sync_outbox(state, memory))["mode"] == "degraded_local"
    assert state.pending()[0]["synced"] == 0
    memory.fail = False
    assert asyncio.run(sync_outbox(state, memory))["synced"] == 1
    assert state.pending() == []
    client = MnemeClient(state.resident_id, api_key="fixture")
    with pytest.raises(ValueError):
        asyncio.run(client.get_memory("workspace/other/private"))


def test_schema_and_html_errors_are_data(tmp_path):
    with pytest.raises(ValueError):
        parse_decision('{"summary":"ok", "actions": [], "shell": "env"}')
    # Intent must be the closed enum; prose must surface a diagnostic ValueError.
    with pytest.raises(ValueError, match="intent"):
        parse_decision(
            json.dumps(
                {
                    "summary": "ok",
                    "direction": "d",
                    "intent": "Continue maintaining system health",
                    "actions": [],
                    "next_wake_seconds": 300,
                }
            )
        )
    state = State(tmp_path)
    cycle = state.begin("demo")
    state.finish(cycle, "error", "<script>alert(1)</script>", "<b>fake</b>")
    html = render(state)
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_dashboard_tolerates_list_tool_results(tmp_path):
    state = State(tmp_path)
    cycle = state.begin("demo")
    state.event(cycle, "tool_result", {"name": "filesystem", "result": ["not", "an", "object"]})
    state.finish(cycle, "completed", "ok", "Done")
    html = render(state)
    assert "not</pre>" not in html
    assert '"not"' in html and '"an"' in html and '"object"' in html


def test_provider_usage_and_failure_hold(tmp_path):
    state = State(tmp_path)

    class Client:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kwargs):
            return SimpleNamespace(
                model_dump=lambda **kw: {
                    "id": "fixture",
                    "model": kwargs["model"],
                    "usage": {"prompt_tokens": 30, "completion_tokens": 10},
                    "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                }
            )

    model = NebiusClient(state, client=Client())
    assert asyncio.run(model.chat([{"role": "user", "content": "fixture"}], 1)) == "{}"
    assert state.budget()["accounted_usd"] == 0.00008
    assert state.budget()["unresolved"] == 0
    model.client.chat.completions.create = lambda **kw: (_ for _ in ()).throw(ConnectionError())
    with pytest.raises(RuntimeError):
        asyncio.run(model.chat([{"role": "user", "content": "fixture"}], 1))
    assert state.budget()["unresolved"] == 1
    assert state.budget()["calls"] == 2


def test_bad_decision_is_retained_and_failure_survives(tmp_path):
    class BadModel(DemoModel):
        async def chat(self, messages, cycle):
            return "not JSON"

    soul = tmp_path / "SOUL.md"
    soul.write_text("Choose your own work.")
    state = State(tmp_path / "state")
    workspace = tmp_path / "workspace"
    loop = ResidentLoop(BadModel(), state, build_default_registry(workspace), soul, workspace)
    result = asyncio.run(loop.one_cycle())
    assert result["status"] == "error"
    assert any(e["kind"] == "decision_raw" for e in state.events(1))
    assert "error" in state.recall()[0]["value"]


def test_tool_failure_is_structured_and_recoverable(tmp_path):
    class RecoveringModel(DemoModel):
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, cycle):
            self.calls += 1
            if self.calls == 1:
                return json.dumps(
                    {
                        "summary": "Try the failing tool once.",
                        "direction": "recover",
                        "intent": "continue",
                        "actions": [{"name": "read_file", "arguments": {"relative": "missing.txt"}}],
                        "next_wake_seconds": 10,
                    }
                )
            return json.dumps(
                {
                    "summary": "The failure was recorded and the cycle can continue.",
                    "direction": "continue",
                    "intent": "continue",
                    "actions": [],
                    "next_wake_seconds": 10,
                }
            )

    soul = tmp_path / "SOUL.md"
    soul.write_text("Recover safely.")
    state = State(tmp_path / "state")
    workspace = tmp_path / "workspace"
    model = RecoveringModel()
    loop = ResidentLoop(model, state, build_default_registry(workspace), soul, workspace, max_steps=2)

    result = asyncio.run(loop.one_cycle())

    assert result["status"] == "completed"
    assert model.calls == 2
    errors = [event for event in state.events(1) if event["kind"] == "tool_error"]
    assert len(errors) == 1
    assert errors[0]["payload"]["tool"] == "read_file"
    assert errors[0]["payload"]["error"] == "FileNotFoundError"
    assert errors[0]["payload"]["recovered"] is True


def test_tool_list_matches_schemas(tmp_path):
    tools = build_default_registry(tmp_path)
    assert set(tools.list_tools()) == {s["name"] for s in tools.schemas()}
    assert {"update_file", "delete_file"}.issubset(tools.list_tools())
    assert "shell" not in tools and "web_fetch" not in tools and "run_python" not in tools


def test_stop_and_dashboard_home_select_the_actual_live_state(tmp_path):
    mode, root = resolve_mode_home(tmp_path / ".resident" / "live")
    assert mode == "live" and root == (tmp_path / ".resident" / "live").resolve()
    assert resolve_mode_home(tmp_path / ".resident", live=True) == (mode, root)
    with pytest.raises(ValueError):
        resolve_mode_home(tmp_path / ".resident" / "demo", live=True)
    state = State(root)
    (root / "STOP").touch()
    model = DemoModel()
    loop = ResidentLoop(
        model,
        state,
        build_default_registry(tmp_path / "workspace"),
        tmp_path / "unused-soul.md",
        tmp_path / "workspace",
    )
    asyncio.run(loop.run())
    assert model.calls == 0 and state.recent() == []
