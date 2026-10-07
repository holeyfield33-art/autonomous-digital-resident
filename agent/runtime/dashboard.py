"""Loopback, read-only observation UI; untrusted output is always escaped."""

import json
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

from agent.tools.filesystem import FilesystemTools


def render(state):
    budget = state.budget()
    runtime = state.runtime()
    cards = []
    for cycle in state.recent(30):
        events = state.events(cycle["id"])
        tools = [e["payload"] for e in events if e["kind"] == "tool_result"]
        links = []
        for tool in tools:
            path = tool.get("result", {}).get("path")
            if isinstance(path, str):
                links.append(f"<a href='/artifact?path={quote(path, safe='')}'>{escape(path)}</a>")
        details = json.dumps(tools, ensure_ascii=False, indent=2)
        cards.append(
            f"<article><div class='tag'>{escape(cycle['mode'].upper())} / CYCLE {cycle['id']} / "
            f"{escape(cycle['status'])}</div><h2>{escape(cycle['direction'] or 'Waking up')}</h2>"
            f"<p>{escape(cycle['summary'])}</p><small>{escape(cycle['started'])}</small>"
            f"<details><summary>{len(tools)} tool results · inspect evidence</summary><pre>"
            f"{escape(details[:16000])}</pre></details><p>{'<br>'.join(links)}</p></article>"
        )
    paused = (state.root / "PAUSE").exists()
    stopped = (state.root / "STOP").exists()
    return (
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        "<meta http-equiv='refresh' content='15'>"
        "<title>Resident · Field notes</title><style>"
        "body{margin:0;background:#111916;color:#e7ebe1;font:16px/1.6 system-ui}"
        "main{max-width:1000px;margin:auto;padding:48px 24px}h1{font-size:48px;line-height:1.1;margin:10px 0}"
        "h2{font-size:23px;font-weight:500}.tag{font-size:12px;letter-spacing:2px;color:#b2d98b}"
        "header{border-bottom:1px solid #354139;padding-bottom:30px;margin-bottom:28px}"
        "article{border:1px solid #354139;border-radius:12px;padding:24px;margin:18px 0;background:#1b2520}"
        "small{color:#a9b8ae}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 monospace}"
        "summary{cursor:pointer;color:#b2d98b}.metrics{display:flex;gap:24px;flex-wrap:wrap}"
        "a{color:#b2d98b}</style><main><header><div class='tag'>AUTONOMOUS DIGITAL RESIDENT</div>"
        "<h1>A place to think.<br>A record of doing.</h1>"
        "<p>Observe chosen directions, durable artifacts and the evidence of each action.</p>"
        f"<div class='metrics'><span>{budget['calls']} provider calls</span>"
        f"<span>${budget['accounted_usd']:.6f} accounted / ${budget['cap_usd']:.2f} cap</span>"
        f"<span>{budget['unresolved']} unresolved reservations</span>"
        f"<span>{'STOP requested' if stopped else 'PAUSED' if paused else 'Running' if runtime['healthy'] else 'Stopped / no fresh heartbeat'}</span></div>"
        "<small>Refresh to update. Demo cycles are canned. Execution status does not prove correctness. "
        "Controls are in the local CLI; this page cannot start actions.</small></header>"
        + (
            "".join(cards)
            or "<article>No cycles yet. Run resident demo to inspect the offline workflow.</article>"
        )
        + "</main></html>"
    )


def serve(state, port=8766, workspace=None):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("Host") not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
                self.send_error(403)
                return
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}:
                self.send_error(403)
                return
            parsed = urlsplit(self.path)
            if parsed.path == "/":
                content, mime = render(state), "text/html"
            elif parsed.path == "/api/status":
                content, mime = (
                    json.dumps(
                        {"cycles": state.recent(30), "budget": state.budget(), "runtime": state.runtime()}
                    ),
                    "application/json",
                )
            elif parsed.path == "/api/cycle":
                try:
                    cycle = int(parse_qs(parsed.query)["id"][0])
                    if cycle <= 0:
                        raise ValueError()
                    content, mime = json.dumps(state.events(cycle)), "application/json"
                except (KeyError, ValueError, IndexError):
                    self.send_error(400)
                    return
            elif parsed.path == "/artifact" and workspace is not None:
                try:
                    path = parse_qs(parsed.query)["path"][0]
                    result = FilesystemTools(workspace).read_file(path, max_chars=16000)
                    content, mime = result["content"], "text/plain"
                except (KeyError, IndexError, ValueError, OSError, UnicodeError):
                    self.send_error(404)
                    return
            else:
                self.send_error(404)
                return
            raw = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
            )
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"Resident observation: http://127.0.0.1:{port}", flush=True)
        server.serve_forever()
