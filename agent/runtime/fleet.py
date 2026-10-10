"""Loopback command center: one page aggregating every live resident, host health, and the
operator<->agent message channel. Read-only; replies are sent with the CLI commands shown inline."""

import json
import shutil
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agent.runtime.state import State


def discover(resident_root):
    """Live resident homes under .resident, newest-named last. Skips round1/demo archives."""
    root = Path(resident_root)
    homes = []
    for sqlite in sorted(root.rglob("resident.sqlite")):
        parts = sqlite.parts
        if "round1" in parts or "demo" in parts:
            continue
        home = sqlite.parent
        name = home.parent.name if home.name == "live" else home.name
        if name in (root.name, ""):  # the original .resident/live (round-0, parked)
            name = "live(r0)"
        homes.append((name, home))
    return homes


def _age(iso):
    try:
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(iso)
        s = int(delta.total_seconds())
        return f"{s}s" if s < 90 else f"{s // 60}m" if s < 5400 else f"{s // 3600}h"
    except Exception:
        return "?"


def snapshot(resident_root):
    data = {"residents": [], "host": {}, "messages": []}
    for name, home in discover(resident_root):
        try:
            st = State(home, None)  # None = keep the durable cap; a number would try to lower it and raise
            b = st.budget()
            rt = st.runtime()
            cycles = st.recent(6)
            inbox = st.inbox(limit=12)
        except Exception as exc:
            data["residents"].append({"name": name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        last = cycles[0] if cycles else None
        data["residents"].append({
            "name": name,
            "healthy": rt.get("healthy", False),
            "heartbeat_age": _age(rt.get("at")) if rt.get("at") else "—",
            "spent": round(b["accounted_usd"], 2),
            "cap": b["cap_usd"],
            "calls": b["calls"],
            "cycle": last["id"] if last else 0,
            "status": last["status"] if last else "—",
            "direction": (last["direction"] or last["summary"] or "") if last else "",
        })
        for cyc in cycles:
            data.setdefault("_feed", []).append({
                "name": name, "cycle": cyc["id"], "status": cyc["status"],
                "when": cyc["started"], "text": (cyc["direction"] or cyc["summary"] or "")[:160],
            })
        for m in inbox:
            if m["role"] == "agent" and m["status"] == "open":
                data["messages"].append({"name": name, **m})
    data["_feed"] = sorted(data.get("_feed", []), key=lambda e: e["when"], reverse=True)[:25]
    # host
    def _free(drive):
        try:
            u = shutil.disk_usage(drive)
            return round(u.free / 1e9, 1), round(u.total / 1e9, 1)
        except Exception:
            return None, None
    cfree, ctot = _free("C:\\")
    dfree, dtot = _free("D:\\")
    wlog = Path(resident_root) / "watchdog.log"
    wline = ""
    try:
        wline = wlog.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1]
    except Exception:
        pass
    data["host"] = {"c_free": cfree, "c_total": ctot, "d_free": dfree, "d_total": dtot, "watchdog": wline}
    return data


def render(resident_root):
    d = snapshot(resident_root)
    h = d["host"]
    cards = []
    for r in d["residents"]:
        if "error" in r:
            cards.append(f"<article><h3>{escape(r['name'])}</h3><p class='err'>{escape(r['error'])}</p></article>")
            continue
        pct = min(100, round(100 * r["spent"] / r["cap"])) if r["cap"] else 0
        dot = "ok" if r["healthy"] else "off"
        cards.append(
            f"<article><div class='row'><span class='dot {dot}'></span><h3>{escape(r['name'])}</h3>"
            f"<span class='badge'>cyc {r['cycle']} · {escape(r['status'])}</span></div>"
            f"<p class='dir'>{escape(r['direction'][:180])}</p>"
            f"<div class='bar'><span style='width:{pct}%'></span></div>"
            f"<small>${r['spent']:.2f} / ${r['cap']:.0f} · {r['calls']} calls · ♥ {escape(r['heartbeat_age'])}</small></article>"
        )
    feed = "".join(
        f"<li><b>{escape(e['name'])}</b> <span class='badge'>cyc {e['cycle']} {escape(e['status'])}</span> "
        f"{escape(e['text'])}</li>" for e in d["_feed"]
    )
    msgs = []
    for m in d["messages"]:
        cmd = f".\\scripts\\local.ps1 reply -Name {m['name']} -MsgId {m['id']} -Text \"...\""
        msgs.append(
            f"<li><b>{escape(m['name'])}</b> #<b>{m['id']}</b> · {escape(m['summary'])}"
            f"<div class='body'>{escape(m['body'][:400])}</div>"
            f"<code>{escape(cmd)}</code></li>"
        )
    msg_html = "<ul class='msgs'>" + ("".join(msgs) or "<li class='muted'>No open requests from any resident.</li>") + "</ul>"

    def disk(free, tot):
        return f"{free}/{tot} GB free" if free is not None else "—"
    low = "warn" if (h.get("c_free") or 99) < 8 else ""
    return (
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        "<meta http-equiv='refresh' content='15'><title>Resident Command Center</title><style>"
        "body{margin:0;background:#0d1117;color:#e6edf3;font:15px/1.55 system-ui}"
        "main{max-width:1200px;margin:auto;padding:28px 20px}h1{font-size:26px;margin:0 0 4px}"
        ".host{display:flex;gap:20px;flex-wrap:wrap;font-size:13px;color:#9fb0c3;border-bottom:1px solid #243041;padding-bottom:14px;margin-bottom:18px}"
        ".host .warn{color:#ff7b72;font-weight:600}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}"
        "article{border:1px solid #243041;border-radius:10px;padding:14px 16px;background:#161b22}"
        ".row{display:flex;align-items:center;gap:8px}h3{margin:0;font-size:16px;flex:1}"
        ".badge{font-size:11px;color:#9fb0c3;border:1px solid #30363d;border-radius:20px;padding:1px 8px}"
        ".dir{color:#c9d4e0;font-size:13px;min-height:34px;margin:8px 0}"
        ".bar{height:6px;background:#21262d;border-radius:3px;overflow:hidden}.bar span{display:block;height:100%;background:#2f81f7}"
        "small{color:#8b98a9}.dot{width:9px;height:9px;border-radius:50%}.dot.ok{background:#3fb950}.dot.off{background:#6e7681}"
        "section{margin-top:26px}h2{font-size:15px;color:#9fb0c3;text-transform:uppercase;letter-spacing:1px}"
        "ul{list-style:none;padding:0}.feed li{padding:6px 0;border-bottom:1px solid #1b2230;font-size:13px}"
        ".msgs li{border:1px solid #30363d;border-radius:8px;padding:10px 12px;margin:8px 0;background:#161b22}"
        ".msgs .body{color:#c9d4e0;margin:6px 0;font-size:13px}.msgs code{display:block;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:6px 8px;color:#7ee787;font:12px monospace;overflow-x:auto}"
        ".muted{color:#6e7681}.err{color:#ff7b72}</style>"
        "<main><h1>Resident Command Center</h1>"
        f"<div class='host'><span class='{low}'>C: {disk(h.get('c_free'), h.get('c_total'))}</span>"
        f"<span>D: {disk(h.get('d_free'), h.get('d_total'))}</span>"
        f"<span>watchdog: {escape((h.get('watchdog') or 'not running')[:80])}</span>"
        "<span>auto-refresh 15s · read-only</span></div>"
        f"<div class='grid'>{''.join(cards) or '<p>No live residents.</p>'}</div>"
        f"<section><h2>Open requests to you</h2>{msg_html}</section>"
        f"<section><h2>Activity</h2><ul class='feed'>{feed}</ul></section>"
        "</main></html>"
    )


def serve(resident_root, port=8800):
    root = str(resident_root)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("Host") not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
                self.send_error(403)
                return
            if self.path == "/api":
                body, mime = json.dumps(snapshot(root)), "application/json"
            elif self.path == "/":
                body, mime = render(root), "text/html"
            else:
                self.send_error(404)
                return
            raw = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *a):
            pass

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"Resident command center: http://127.0.0.1:{port}", flush=True)
        server.serve_forever()
