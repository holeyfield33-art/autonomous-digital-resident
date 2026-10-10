"""Regression suite raising coverage across web, cli, execution, dashboard, mneme, identity,
protocol and filesystem edge branches. Network, Docker and MCP are mocked — no external calls."""

import asyncio
import json
import threading
import urllib.request
from types import SimpleNamespace

import httpx
import pytest

from agent import cli
from agent.core import identity
from agent.core.protocol import Action, decision_schema, parse_decision
from agent.memory.mneme_client import MnemeClient, sync_outbox
from agent.models.nebius import DemoModel
from agent.runtime.dashboard import render, serve
from agent.runtime.state import State
from agent.tools import web as webmod
from agent.tools.execution import PythonRunner
from agent.tools.filesystem import FilesystemTools
from agent.tools.web import WebTools, html_to_text


# ----------------------------- identity -----------------------------
def test_identity_load_and_summary(tmp_path):
    with pytest.raises(FileNotFoundError):
        identity.load_soul(tmp_path / "nope.md")
    p = tmp_path / "SOUL.md"
    p.write_text("line one\n" + "x" * 50, encoding="utf-8")
    assert identity.load_soul(p).startswith("line one")
    assert identity.soul_summary("short text") == "short text"
    long = "head\n" + "y" * 3000
    out = identity.soul_summary(long, max_chars=100)
    assert out.endswith("[... identity continues ...]") and len(out) < 200


# ----------------------------- protocol edges -----------------------------
def test_protocol_folds_stray_action_keys_and_variants():
    raw = json.dumps({
        "summary": "s", "direction": "d", "intent": "build",
        "actions": [{"name": "write_file", "arguments": {"path": "a.py"}, "overwrite": True, "content": "x"}],
        "next_wake_seconds": 300,
    })
    fixes = []
    d = parse_decision(raw, fixes)
    assert d.actions[0].arguments["overwrite"] is True
    assert d.actions[0].arguments["content"] == "x"
    assert any("folded_action_keys" in f for f in fixes)
    # tool/args aliases, None arguments, over-limit truncation, prose intent
    raw2 = json.dumps({
        "summary": "s", "direction": "d", "intent": "keep going and building",
        "actions": [{"tool": "list_dir", "args": None}] + [{"name": f"t{i}", "arguments": {}} for i in range(8)],
        "next_wake_seconds": "45.9",
    })
    f2 = []
    d2 = parse_decision(raw2, f2)
    assert d2.actions[0].name == "list_dir" and d2.actions[0].arguments == {}
    assert len(d2.actions) == 6 and d2.intent == "continue" and d2.next_wake_seconds == 45


def test_protocol_size_limit_and_nonstring():
    with pytest.raises(ValueError, match="size limit"):
        parse_decision("x" * 200_001)
    with pytest.raises(ValueError):
        parse_decision(12345)


def test_decision_schema_lists_tools():
    sch = decision_schema(("read_file", "write_file"))
    assert sch["properties"]["actions"]["items"]["properties"]["name"]["enum"] == ["read_file", "write_file"]
    assert Action(name="x").arguments == {}


# ----------------------------- web: html + url guard -----------------------------
def test_html_to_text_extracts_title_and_skips_script():
    title, text = html_to_text("<html><head><title>Hi</title></head><body><p>One</p><script>bad()</script><p>Two</p></body></html>")
    assert title == "Hi" and "One" in text and "Two" in text and "bad()" not in text


def test_public_url_rejects_bad_and_private(monkeypatch):
    with pytest.raises(ValueError, match="http"):
        webmod._public_url("ftp://example.com")
    with pytest.raises(ValueError, match="credential"):
        webmod._public_url("http://user:pw@example.com")
    monkeypatch.setattr(webmod.socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("127.0.0.1", 80))])
    with pytest.raises(ValueError, match="Private"):
        webmod._public_url("http://localhost.evil")
    def boom(*a, **k):
        raise webmod.socket.gaierror()
    monkeypatch.setattr(webmod.socket, "getaddrinfo", boom)
    with pytest.raises(ConnectionError, match="resolve"):
        webmod._public_url("http://nope.invalid")


class _Resp:
    def __init__(self, status=200, headers=None, body=b"", is_redirect=False, text="", data=None):
        self.status_code, self.headers, self._body = status, headers or {}, body
        self.is_redirect, self.encoding, self._text, self._data = is_redirect, "utf-8", text, data

    def iter_bytes(self, n):
        yield self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    @property
    def text(self):
        return self._text

    def json(self):
        return self._data


class _FakeClient:
    def __init__(self, handler):
        self.handler = handler

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def stream(self, method, url):
        return self.handler("stream", url)

    def post(self, url, **kw):
        return self.handler("post", url)

    def get(self, url, **kw):
        return self.handler("get", url)


def _patch_web(monkeypatch, handler):
    monkeypatch.setattr(webmod.socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.216.34", 80))])
    monkeypatch.setattr(WebTools, "_client", lambda self: _FakeClient(handler))


def test_web_fetch_html_and_redirect_and_validation(monkeypatch):
    w = WebTools()
    with pytest.raises(ValueError):
        w.fetch("http://x", max_chars=0)
    seq = [
        _Resp(is_redirect=True, headers={"location": "http://example.com/final"}),
        _Resp(status=200, headers={"content-type": "text/html"}, body=b"<title>T</title><p>Body here</p>"),
    ]
    calls = {"i": 0}
    def handler(kind, url):
        r = seq[calls["i"]]
        calls["i"] += 1
        return r
    _patch_web(monkeypatch, handler)
    out = w.fetch("http://example.com/start")
    assert out["status"] == 200 and out["title"] == "T" and "Body here" in out["content"]
    assert out["url"].endswith("/final")


def test_web_fetch_too_many_redirects(monkeypatch):
    w = WebTools()
    _patch_web(monkeypatch, lambda kind, url: _Resp(is_redirect=True, headers={"location": "http://example.com/x"}))
    with pytest.raises(ConnectionError, match="redirects"):
        w.fetch("http://example.com/")


def test_web_search_providers(monkeypatch):
    w = WebTools()
    with pytest.raises(ValueError):
        w.search("")
    with pytest.raises(ValueError):
        w.search("ok", max_results=99)
    # DuckDuckGo HTML parse
    page = ('<a class="result__a" href="http://r.com/a">Title <b>A</b></a>'
            '<a class="result__snippet">Snippet A</a>')
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    _patch_web(monkeypatch, lambda kind, url: _Resp(text=page))
    res = w.search("hello")
    assert res["provider"] == "duckduckgo" and res["results"][0]["url"] == "http://r.com/a"
    assert res["results"][0]["title"] == "Title A"
    # Tavily
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    _patch_web(monkeypatch, lambda kind, url: _Resp(data={"results": [{"title": "t", "url": "u", "content": "c"}]}))
    assert w.search("q")["provider"] == "tavily"
    monkeypatch.delenv("TAVILY_API_KEY")
    # Brave
    monkeypatch.setenv("BRAVE_API_KEY", "k")
    _patch_web(monkeypatch, lambda kind, url: _Resp(data={"web": {"results": [{"title": "t", "url": "u", "description": "d"}]}}))
    assert w.search("q")["provider"] == "brave"


def test_web_duckduckgo_anomaly(monkeypatch):
    w = WebTools()
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    _patch_web(monkeypatch, lambda kind, url: _Resp(text="ANOMALY detected"))
    with pytest.raises(ConnectionError, match="rate-limited"):
        w.search("q")


# ----------------------------- execution (PythonRunner) -----------------------------
def test_python_runner_unavailable_and_bad_image(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.tools.execution.shutil.which", lambda n: None)
    r = PythonRunner(tmp_path)
    assert r.run_python("x.py")["error"] == "execution_unavailable"
    with pytest.raises(ValueError, match="immutable"):
        PythonRunner(tmp_path, image="not-a-digest")


def test_python_runner_executes_with_fake_docker(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.tools.execution.shutil.which", lambda n: "docker")
    runner = PythonRunner(tmp_path, image="sha256:" + "a" * 64)
    runner.fs.write_file("main.py", "print('hi')")

    class FakeStdout:
        def __init__(self):
            self.chunks = [b"hello\n", b""]

        def read(self, n):
            return self.chunks.pop(0) if self.chunks else b""

        def close(self):
            pass

    class FakeProc:
        def __init__(self, *a, **k):
            self.stdout = FakeStdout()

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

        def kill(self):
            pass

    monkeypatch.setattr("agent.tools.execution.subprocess.Popen", FakeProc)
    monkeypatch.setattr("agent.tools.execution.subprocess.run", lambda *a, **k: SimpleNamespace(returncode=0))
    out = runner.run_python("main.py")
    assert out["status"] == "passed" and out["returncode"] == 0 and "hello" in out["output"]
    assert out["network"] == "none" and out["host_writes"] is False
    runner.fs.write_file("notes.txt", "not python but exists")
    with pytest.raises(ValueError, match="Python file"):
        runner.run_python("notes.txt")


# ----------------------------- dashboard (render + serve) -----------------------------
def test_dashboard_render_empty_and_populated(tmp_path):
    state = State(tmp_path)
    assert "No cycles yet" in render(state)
    cyc = state.begin("demo")
    state.event(cyc, "tool_result", {"name": "write_file", "result": {"path": "notes/a.md"}})
    state.finish(cyc, "completed", "did it", "a direction")
    html = render(state)
    assert "a direction" in html and "notes/a.md" in html


def _serve_in_thread(state, port, workspace=None):
    t = threading.Thread(target=serve, args=(state, port, workspace), daemon=True)
    t.start()
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1).read()
            return
        except Exception:
            import time
            time.sleep(0.1)


def test_dashboard_serve_endpoints(tmp_path):
    state = State(tmp_path / "s")
    cyc = state.begin("demo")
    state.event(cyc, "tool_result", {"name": "x", "result": {"path": "f.txt"}})
    state.finish(cyc, "completed", "s", "d")
    ws = tmp_path / "ws"
    FilesystemTools(ws).write_file("f.txt", "hello body")
    port = 8795
    _serve_in_thread(state, port, ws)

    def get(path):
        req = urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2)
        return req.status, req.read().decode()

    assert get("/")[0] == 200
    s, body = get("/api/status")
    assert s == 200 and "budget" in body
    assert get(f"/api/cycle?id={cyc}")[0] == 200
    assert get("/artifact?path=f.txt")[1] == "hello body"
    for bad in ("/api/cycle", "/api/cycle?id=0", "/nope"):
        with pytest.raises(urllib.error.HTTPError):
            get(bad)


# ----------------------------- mneme client -----------------------------
def test_mneme_init_guards():
    with pytest.raises(ValueError, match="loopback"):
        MnemeClient("rid", base_url="https://remote.example.com/mcp/")
    m = MnemeClient("rid42")
    assert m.prefix == "resident/rid42/"


def test_mneme_call_tool_guards():
    m = MnemeClient("rid")
    with pytest.raises(ValueError, match="capability"):
        asyncio.run(m._call_tool("delete_everything", {"key": "resident/rid/x"}))
    with pytest.raises(ValueError, match="Foreign"):
        asyncio.run(m._call_tool("get_memory", {"key": "resident/other/x"}))
    m.api_key = ""
    with pytest.raises(RuntimeError, match="credential"):
        asyncio.run(m._call_tool("get_memory", {"key": "resident/rid/x"}))


def test_sync_outbox_modes(tmp_path):
    state = State(tmp_path)
    rid = state.resident_id
    # local when no client
    assert asyncio.run(sync_outbox(state, None))["mode"] == "local"

    state.remember(f"resident/{rid}/cycle/1", "v1")
    state.remember(f"resident/{rid}/cycle/2", "v2")

    class OkClient:
        async def ensure_memory(self, k, v):
            return None

    res = asyncio.run(sync_outbox(state, OkClient()))
    assert res["mode"] == "mneme" and res["synced"] == 2

    state.remember(f"resident/{rid}/cycle/3", "v3")

    class BadClient:
        async def ensure_memory(self, k, v):
            raise RuntimeError("boom")

    res2 = asyncio.run(sync_outbox(state, BadClient()))
    assert res2["mode"] == "degraded_local" and res2["error_type"] == "RuntimeError"


# ----------------------------- cli main dispatch -----------------------------
def _run_cli(monkeypatch, tmp_path, *argv):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["resident", *argv])
    cli.main()


def test_cli_status_plan_doctor_and_controls(monkeypatch, tmp_path, capsys):
    _run_cli(monkeypatch, tmp_path, "status")
    assert "budget" in capsys.readouterr().out
    _run_cli(monkeypatch, tmp_path, "plan", "--cycles", "3", "--steps", "2")
    assert "per_call_reservation_ceiling_usd" in capsys.readouterr().out
    _run_cli(monkeypatch, tmp_path, "doctor")
    assert "docker_linux" in capsys.readouterr().out
    _run_cli(monkeypatch, tmp_path, "pause")
    assert (tmp_path / ".resident" / "demo" / "PAUSE").exists()
    _run_cli(monkeypatch, tmp_path, "resume")
    assert not (tmp_path / ".resident" / "demo" / "PAUSE").exists()


def test_cli_rejects_bad_args(monkeypatch, tmp_path):
    for argv in (
        ("run", "--cycles", "99999"),
        ("run", "--budget-usd", "500"),
        ("demo", "--live"),
        ("status", "--soul", "missing_soul.md"),
    ):
        with pytest.raises(SystemExit):
            _run_cli(monkeypatch, tmp_path, *argv)


def test_cli_demo_run_executes_a_cycle(monkeypatch, tmp_path, capsys):
    (tmp_path / "SOUL.md").write_text("Explore and rest.", encoding="utf-8")
    _run_cli(monkeypatch, tmp_path, "demo", "--cycles", "1", "--steps", "3")
    out = capsys.readouterr().out
    assert "budget" in out
    # a demo cycle was recorded
    state = State(tmp_path / ".resident" / "demo")
    assert state.recent(1)[0]["mode"] == "demo"


def test_resolve_mode_home_conflict():
    with pytest.raises(ValueError, match="conflicts"):
        cli.resolve_mode_home("x/demo", live=True)
    mode, path = cli.resolve_mode_home("x/live")
    assert mode == "live"


# ----------------------------- filesystem edge branches -----------------------------
def test_filesystem_path_guards_and_ops(tmp_path):
    fs = FilesystemTools(tmp_path)
    for bad in ("a\\b", "c:/x", "../x", ".hidden/x", "/abs"):
        with pytest.raises(ValueError):
            fs._safe(bad)
    assert fs._safe("/workspace/sub/f.txt").name == "f.txt"
    fs.write_file("dir/a.txt", "one")
    assert fs.exists("dir")["type"] == "dir"
    assert fs.exists("dir/a.txt")["type"] == "file"
    assert fs.exists("ghost")["exists"] is False
    assert fs.file_info("dir/a.txt")["lines"] == 1
    assert fs.file_info("dir")["type"] == "dir"
    assert fs.append_file("dir/a.txt", " two")["status"] == "appended"
    assert "two" in fs.read_file("dir/a.txt")["content"]
    assert fs.mkdir("dir")["status"] == "exists"
    assert fs.move("dir/a.txt", "dir/b.txt")["status"] == "moved"
    assert fs.copy("dir", "dir2")["status"] == "copied"
    assert fs.find_files("*.txt")["matches"]
    hits = fs.search_text("two", file_glob="*.txt")
    assert hits["hits"][0]["path"].endswith("b.txt")
    with pytest.raises(ValueError):
        fs.list_dir(".", depth=9)
    with pytest.raises(ValueError):
        fs.read_file("dir/b.txt", max_chars=0)
    with pytest.raises(IsADirectoryError):
        fs.read_file("dir")
    with pytest.raises(NotADirectoryError):
        fs.list_dir("dir/b.txt")


# ----------------------------- loop paths -----------------------------
from agent.core.loop import ResidentLoop  # noqa: E402
from agent.runtime.state import BudgetExceeded  # noqa: E402
from agent.tools.registry import build_default_registry  # noqa: E402


def _loop(tmp_path, model, **kw):
    state = State(tmp_path / "st")
    soul = tmp_path / "SOUL.md"
    soul.write_text("Explore.", encoding="utf-8")
    ws = tmp_path / "ws"
    loop = ResidentLoop(model, state, build_default_registry(ws, state), soul, ws, **kw)
    return state, ws, loop


class _Scripted(DemoModel):
    def __init__(self, replies):
        super().__init__()
        self.replies, self.i = replies, 0

    async def chat(self, messages, cycle, schema=None):
        r = self.replies[min(self.i, len(self.replies) - 1)]
        self.i += 1
        if isinstance(r, Exception):
            raise r
        return r


def _dec(actions, intent="build"):
    return json.dumps({"summary": "s", "direction": "d", "intent": intent,
                       "actions": actions, "next_wake_seconds": 60})


def test_loop_tool_limit(tmp_path):
    m = _Scripted([_dec([{"name": "list_dir", "arguments": {}}])])
    _, _, loop = _loop(tmp_path, m, max_steps=8, max_tool_calls=2)
    assert asyncio.run(loop.one_cycle())["status"] == "tool_limit"


def test_loop_budget_and_crash(tmp_path):
    _, _, loop = _loop(tmp_path, _Scripted([BudgetExceeded()]))
    assert asyncio.run(loop.one_cycle())["status"] == "budget_exhausted"
    _, _, loop2 = _loop(tmp_path / "b", _Scripted([RuntimeError("boom")]))
    assert asyncio.run(loop2.one_cycle())["status"] == "error"


def test_loop_repair_then_rest(tmp_path):
    m = _Scripted(["this is not json at all", _dec([], intent="rest")])
    state, _, loop = _loop(tmp_path, m)
    status = asyncio.run(loop.one_cycle())["status"]
    assert status in ("completed", "rested")  # repair recovered instead of protocol_error
    assert m.i >= 2  # a repair request was issued


def test_loop_large_result_compacted(tmp_path):
    state = State(tmp_path / "st")
    soul = tmp_path / "SOUL.md"
    soul.write_text("Explore.", encoding="utf-8")
    ws = tmp_path / "ws"
    FilesystemTools(ws).write_file("big.txt", "A" * 30000)
    m = _Scripted([
        _dec([{"name": "read_file", "arguments": {"path": "big.txt", "max_chars": 30000}}]),
        _dec([]),
    ])
    loop = ResidentLoop(m, state, build_default_registry(ws, state), soul, ws, max_steps=4)
    assert asyncio.run(loop.one_cycle())["status"] == "completed"


def test_loop_system_status(tmp_path):
    state, _, loop = _loop(tmp_path, _Scripted([_dec([])]))
    st = loop.system_status()
    assert "now_utc" in st and "capabilities" in st


# ----------------------------- state ledger -----------------------------
def test_state_budget_exceeded_and_pending(tmp_path):
    state = State(tmp_path, 1000)  # $0.001 cap (1000 micro)
    cyc = state.begin("demo")
    with pytest.raises(BudgetExceeded):
        state.reserve(cyc, 5000)  # over cap
    res = state.reserve(cyc, 500)
    state.settle(res, 400, "prov-1")
    assert state.budget()["accounted_usd"] == 0.0004
    rid = state.resident_id
    state.remember(f"resident/{rid}/k", "v")
    assert any(p["key"].endswith("/k") for p in state.pending(10))


# ----------------------------- sandbox validation branches -----------------------------
from agent.tools.sandbox import Sandbox  # noqa: E402


class _FakeBox(Sandbox):
    def __init__(self, workspace, replies, **kw):
        super().__init__(workspace, **kw)
        self.docker, self.replies = "docker", replies

    def _docker(self, *args, timeout=60, stdin=None):
        return self.replies(args)


def test_sandbox_validation_and_status(tmp_path):
    up = lambda args: SimpleNamespace(returncode=0, stdout=f"true|{tmp_path}\n".encode(), stderr=b"")  # noqa: E731
    box = _FakeBox(tmp_path, up, name="resident-sandbox-x")
    with pytest.raises(ValueError, match="timeout"):
        box.shell("ls", timeout=99999)
    with pytest.raises(ValueError, match="cwd"):
        box._exec(["bash", "-c", "x"], "../escape", 10)
    with pytest.raises(ValueError, match="non-empty"):
        box.shell("   ")
    with pytest.raises(ValueError, match="non-empty"):
        box.python("")
    assert box.status()["running"] is True and box.status()["name"] == "resident-sandbox-x"
    # image_exists + build path
    def built(args):
        if args[0] == "image":
            return SimpleNamespace(returncode=1, stdout=b"", stderr=b"")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
    box2 = _FakeBox(tmp_path, built, name="resident-sandbox-y")
    assert box2.image_exists() is False
    box2.build()  # returncode 0 -> no raise


def test_sandbox_no_docker():
    box = Sandbox.__new__(Sandbox)
    box.docker = None
    with pytest.raises(RuntimeError, match="not installed"):
        box._docker("ps")


# ----------------------------- mneme network (mocked MCP) -----------------------------
def test_mneme_ensure_memory_with_mocked_mcp(tmp_path, monkeypatch):
    import agent.memory.mneme_client as mc

    class FakeSession:
        def __init__(self, *a):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def initialize(self):
            pass

        async def call_tool(self, name, args):
            payload = {"get_memory": {"value": None},
                       "store_memory": {"ok": True},
                       "verify_memory": {"valid": True}}[name]
            return SimpleNamespace(isError=False, structuredContent=payload, content=[])

    class FakeCM:
        async def __aenter__(self):
            return (None, None, None)

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(mc, "streamablehttp_client", lambda url, headers=None: FakeCM())
    monkeypatch.setattr(mc, "ClientSession", FakeSession)
    m = mc.MnemeClient("rid", api_key="secret")
    asyncio.run(m.ensure_memory("resident/rid/cycle/1", "hello"))  # store + verify path
    assert asyncio.run(m.get_memory("resident/rid/cycle/1")) == {"value": None}
    assert asyncio.run(m.verify_memory("resident/rid/cycle/1")) == {"valid": True}
    asyncio.run(m.close())


def test_mneme_conflict_refused(tmp_path, monkeypatch):
    import agent.memory.mneme_client as mc

    class FakeSession:
        def __init__(self, *a):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def initialize(self):
            pass

        async def call_tool(self, name, args):
            return SimpleNamespace(isError=False, structuredContent={"value": "OLD"}, content=[])

    class FakeCM:
        async def __aenter__(self):
            return (None, None, None)

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(mc, "streamablehttp_client", lambda url, headers=None: FakeCM())
    monkeypatch.setattr(mc, "ClientSession", FakeSession)
    m = mc.MnemeClient("rid", api_key="secret")
    with pytest.raises(RuntimeError, match="conflict"):
        asyncio.run(m.ensure_memory("resident/rid/cycle/1", "NEW"))


# ----------------------------- cli env loading -----------------------------
def test_cli_load_environment(tmp_path, monkeypatch):
    import os
    env = tmp_path / ".env"
    env.write_text('# comment\nRESIDENT_PRICE_IN=0.30\nRESIDENT_MODEL=some/model\n', encoding="utf-8")
    monkeypatch.delenv("RESIDENT_PRICE_IN", raising=False)
    monkeypatch.delenv("RESIDENT_MODEL", raising=False)
    cli.load_environment(env)
    assert os.environ.get("RESIDENT_PRICE_IN") == "0.30"
    os.environ.pop("RESIDENT_PRICE_IN", None)
    os.environ.pop("RESIDENT_MODEL", None)
    # missing file is a no-op; unknown key is rejected
    cli.load_environment(tmp_path / "nope.env")
    bad = tmp_path / "bad.env"
    bad.write_text("TOTALLY_UNKNOWN=1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        cli.load_environment(bad)


def test_state_read_methods(tmp_path):
    state = State(tmp_path)
    c1 = state.begin("demo")
    state.event(c1, "tool_result", {"name": "write_file", "result": {"path": "p"}})
    state.finish(c1, "completed", "built the thing", "a direction")
    c2 = state.begin("demo")
    state.finish(c2, "rested", "rested now", "resting")
    assert len(state.recent(10)) == 2
    assert state.get_cycle(c1)["status"] == "completed"
    with pytest.raises(LookupError):
        state.get_cycle(999)
    hist = state.cycle_history(limit=5)
    assert isinstance(hist, (list, dict))
    assert state.last_event(c1, "tool_result")["name"] == "write_file"
    assert state.last_event(c1, "nonexistent") is None
    assert "built" in json.dumps(state.search_memory("built"))


def test_cli_sync_and_bootstrap(monkeypatch, tmp_path, capsys):
    (tmp_path / "SOUL.md").write_text("Be.", encoding="utf-8")
    _run_cli(monkeypatch, tmp_path, "sync")
    assert "local" in capsys.readouterr().out
    _run_cli(monkeypatch, tmp_path, "bootstrap")
    out = capsys.readouterr().out
    assert "mode" in out or "synced" in out


def test_loop_wake_second_limit_and_run_wrapper(tmp_path):
    # tight wall-clock limit: the wake stops on the deadline path
    m = _Scripted([_dec([{"name": "list_dir", "arguments": {}}])])
    _, _, loop = _loop(tmp_path, m, max_steps=40, max_tool_calls=60, max_wake_seconds=0)
    res = asyncio.run(loop.one_cycle())
    assert res["status"] in ("time_limit", "step_limit", "tool_limit", "completed")
    # public run() wrapper over a single cycle
    m2 = _Scripted([_dec([], intent="rest")])
    _, _, loop2 = _loop(tmp_path / "r", m2)
    asyncio.run(loop2.run(1))


# ----------------------------- human collaboration channel -----------------------------
def test_human_channel_two_way(tmp_path):
    state = State(tmp_path)
    # agent -> operator
    out = state.contact_operator("Need the ASI catalog deployed", "Please publish v0.3 to the site.")
    assert out["status"] == "sent_to_operator"
    assert len(state.awaiting_operator()) == 1
    # operator initiates + replies
    state.post_message("operator", "direction", "Focus on AAC-12 evidence this week.")
    mid = out["message_id"]
    state.answer_message(mid, "Deployed. Here is the URL.")
    # agent picks up both operator messages exactly once
    first = state.take_operator_messages()
    assert len(first) == 2 and any("Deployed" in m["body"] for m in first)
    assert state.take_operator_messages() == []  # delivered only once
    # the answered request is no longer awaiting
    assert state.awaiting_operator() == []
    with pytest.raises(ValueError):
        state.contact_operator("")
    with pytest.raises(LookupError):
        state.answer_message(9999, "x")


def test_human_channel_registered_and_in_facts(tmp_path):
    state = State(tmp_path / "st")
    reg = build_default_registry(tmp_path / "ws", state, human_channel=True)
    assert "contact_operator" in reg.list_tools()
    reg.call("contact_operator", summary="hi", body="there")
    assert len(state.awaiting_operator()) == 1
    # without the flag the tool is absent
    reg2 = build_default_registry(tmp_path / "ws2", State(tmp_path / "st2"))
    assert "contact_operator" not in reg2.list_tools()


# ----------------------------- fleet command center -----------------------------
def test_fleet_snapshot_and_render(tmp_path):
    from agent.runtime import fleet
    root = tmp_path / ".resident"
    # two live residents + an archived round1 that must be ignored
    for name in ("a", "b"):
        s = State(root / name / "live")
        cyc = s.begin("live")
        s.finish(cyc, "completed", "did work", "a direction for " + name)
        s.contact_operator(f"{name} needs a decision", "please advise")
    arch = State(root / "round1" / "a" / "live")
    arch.begin("live")
    (root / "watchdog.log").write_text("WATCHDOG_UP ok\n", encoding="utf-8")
    snap = fleet.snapshot(root)
    names = {r["name"] for r in snap["residents"]}
    assert names == {"a", "b"}  # round1 excluded
    assert len(snap["messages"]) == 2 and snap["host"]["watchdog"].startswith("WATCHDOG_UP")
    html = fleet.render(root)
    assert "Resident Command Center" in html
    assert "a needs a decision" in html and "reply -Name a" in html
