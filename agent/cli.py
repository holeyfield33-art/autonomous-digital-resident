"""Installed CLI. Offline by default; live runs require an explicit mode and budget."""

import argparse
import asyncio
import json
import logging
import os
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

from dotenv import dotenv_values

from agent.core.loop import ResidentLoop
from agent.memory.mneme_client import MnemeClient, sync_outbox
from agent.models.nebius import (
    MAX_OUTPUT_TOKENS,
    MAX_REQUEST_BYTES,
    MICRO_USD_PER_TOKEN,
    DemoModel,
    NebiusClient,
)
from agent.runtime.state import State
from agent.tools.registry import build_default_registry
from agent.tools.sandbox import Sandbox
from agent.tools.web import WebTools


def load_environment(path):
    if not path or not Path(path).exists():
        return
    allowed = {
        "NEBIUS_API_KEY",
        "MNEME_API_KEY",
        "MNEME_LOCAL_API_KEY",
        "MNEME_MCP_URL",
        "MNEME_LOCAL_CONFIG",
        "RESIDENT_EXECUTION_IMAGE",
        "RESIDENT_MODEL",
        "RESIDENT_BASE_URL",
        "RESIDENT_PRICE_IN",
        "RESIDENT_PRICE_OUT",
        "TAVILY_API_KEY",
        "BRAVE_API_KEY",
    }
    values = dotenv_values(path, interpolate=False, encoding="utf-8-sig")
    if any(k not in allowed or not isinstance(v, str) for k, v in values.items()):
        raise ValueError("Environment file contains an unsupported or incomplete assignment")
    for key, value in values.items():
        os.environ.setdefault(key, value)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "command",
        choices=[
            "run",
            "demo",
            "status",
            "observe",
            "doctor",
            "sync",
            "bootstrap",
            "pause",
            "resume",
            "stop",
            "plan",
            "sandbox",
            "inbox",
            "reply",
            "tell",
        ],
    )
    p.add_argument("--live", action="store_true", help="Enable real Nebius inference; demo is default")
    p.add_argument(
        "--home",
        type=Path,
        default=Path(".resident"),
        help="State parent, or exact mode directory such as .resident/live",
    )
    p.add_argument("--workspace", type=Path, help="Dedicated resident-owned directory")
    p.add_argument("--soul", type=Path, help="Identity file (default SOUL.md, else the packaged soul)")
    p.add_argument("--knowledge", type=Path, default=Path(__file__).parent / "knowledge" / "packs")
    p.add_argument("--cycles", type=int, default=1, help="0 polls until stopped or spending is exhausted")
    p.add_argument("--steps", type=int, default=12, choices=range(1, 41), metavar="1..40")
    p.add_argument("--max-tool-calls", type=int, default=60, help="Per-wake tool call limit")
    p.add_argument("--max-wake-seconds", type=int, default=1200, help="Per-wake wall-clock limit")
    p.add_argument("--sandbox", action="store_true", help="Give the Resident its persistent Docker sandbox")
    p.add_argument("--sandbox-offline", action="store_true", help="Run the sandbox with --network none")
    p.add_argument(
        "--sandbox-name", default="resident-sandbox", help="Container name; each resident needs its own"
    )
    p.add_argument("--no-web", action="store_true", help="Disable web_search/web_fetch")
    p.add_argument("--interval", type=int, default=300)
    p.add_argument(
        "--budget-usd", default=None, help="Raise the durable cap (default: keep it; $0.50 for new state)"
    )
    p.add_argument("--env-file", type=Path, default=Path(".env"))
    p.add_argument("--mneme", action="store_true")
    p.add_argument("--mneme-config", type=Path, help="Existing ignored Mneme local settings; never copied")
    p.add_argument("--execution-image", help="Immutable local Docker sha256 image ID")
    p.add_argument("--source-url", action="append", default=[], help="A suggested source shown in facts")
    p.add_argument("--model", help="Hosted model id (default: Nemotron)")
    p.add_argument("--base-url", help="Inference endpoint base URL")
    p.add_argument("--price-in", type=float, help="Input price USD per million tokens (for the ledger)")
    p.add_argument("--price-out", type=float, help="Output price USD per million tokens (for the ledger)")
    p.add_argument(
        "--no-response-schema",
        action="store_true",
        help="Disable json_schema constrained decoding (required for DeepSeek-V4-Flash)",
    )
    p.add_argument("--human-channel", action="store_true", help="Give the resident a contact_operator tool")
    p.add_argument("--msg-id", type=int, help="Agent message id to reply to (reply command)")
    p.add_argument("--text", default="", help="Message body (reply/tell commands)")
    p.add_argument("--port", type=int, default=8766)
    return p


def resolve_mode_home(home, live=False):
    """A mode directory is an exact path, never a parent to append demo to."""
    home = Path(home)
    if home.name in {"live", "demo"}:
        if live and home.name == "demo":
            raise ValueError("--live conflicts with an explicit demo directory")
        return home.name, home.resolve()
    mode = "live" if live else "demo"
    return mode, (home / mode).resolve()


async def operate(args, state, workspace):
    load_environment(args.env_file)
    config = args.mneme_config or os.environ.get("MNEME_LOCAL_CONFIG")
    memory = MnemeClient(state.resident_id, config_path=config) if args.mneme else None
    if args.command in {"bootstrap", "sync"}:
        if args.command == "bootstrap":
            soul = args.soul.read_text(encoding="utf-8")
            from agent.tools.filesystem import check_text

            check_text(soul)
            import hashlib

            state.remember(
                f"resident/{state.resident_id}/identity/{hashlib.sha256(soul.encode()).hexdigest()}", soul
            )
        result = await sync_outbox(state, memory)
        while args.command == "sync" and result.get("mode") == "mneme" and result.get("synced"):
            result = await sync_outbox(state, memory)  # drain the whole backlog
        print(json.dumps(result))
        return
    model = (
        NebiusClient(
            state,
            model=args.model,
            base_url=args.base_url,
            price_in=args.price_in,
            price_out=args.price_out,
            use_schema=not args.no_response_schema,
        )
        if args.live
        else DemoModel()
    )
    image = args.execution_image or os.environ.get("RESIDENT_EXECUTION_IMAGE")
    sandbox = None
    if args.sandbox:
        sandbox = Sandbox(workspace, name=args.sandbox_name, network=not args.sandbox_offline)
        await asyncio.to_thread(sandbox.ensure)
    web = None if args.no_web else WebTools(args.source_url)
    tools = build_default_registry(
        workspace, state, args.knowledge, image, web=web, sandbox=sandbox, human_channel=args.human_channel
    )
    soul_path = args.soul
    loop = ResidentLoop(
        model,
        state,
        tools,
        soul_path,
        workspace,
        memory,
        cycle_interval=args.interval,
        max_steps=args.steps,
        max_tool_calls=args.max_tool_calls,
        max_wake_seconds=args.max_wake_seconds,
        sandbox=sandbox,
        source_urls=args.source_url,
        human_channel=args.human_channel,
    )
    tools.register("system_status", loop.system_status)
    try:
        await loop.run(args.cycles)
    finally:
        model.close()
        if memory:
            await memory.close()
    print(json.dumps({"latest": state.recent(1), "budget": state.budget()}))


def main():
    args = parser().parse_args()
    if args.command == "demo" and args.live:
        raise SystemExit("Demo cannot use live inference")
    if not 0 <= args.cycles <= 10000 or not 0 <= args.interval <= 3600 or not 1024 <= args.port <= 65535:
        raise SystemExit("Invalid cycle, interval or port limit")
    cap = None
    if args.budget_usd is not None:
        cap = Decimal(args.budget_usd)
        if not cap.is_finite() or not 0 <= cap <= 100:
            raise SystemExit("Budget must be finite and between $0 and $100")
    if args.soul is None:
        args.soul = Path("SOUL.md") if Path("SOUL.md").exists() else Path(__file__).parent / "default_soul.md"
    elif not args.soul.is_file():
        raise SystemExit(f"Soul file not found: {args.soul}")
    mode, root = resolve_mode_home(args.home, args.live)
    args.live = mode == "live"
    if args.command == "demo" and args.live:
        raise SystemExit("Demo cannot target live state")
    workspace = (args.workspace or Path("workspace") / mode).resolve()
    if root == workspace or root.is_relative_to(workspace) or workspace.is_relative_to(root):
        raise SystemExit("Controller state and model workspace must be disjoint")
    state = State(root, None if cap is None else int(cap * 1_000_000))
    if args.command in {"pause", "stop", "resume"}:
        if args.command == "resume":
            for name in ("STOP", "PAUSE"):
                (root / name).unlink(missing_ok=True)
        else:
            (root / args.command.upper()).touch()
        print(args.command + " recorded; in-flight calls finish within their configured timeout")
    elif args.command == "status":
        print(
            json.dumps(
                {
                    "resident_id": state.resident_id,
                    "cycles": state.recent(),
                    "budget": state.budget(),
                    "runtime": state.runtime(),
                },
                indent=2,
            )
        )
    elif args.command == "inbox":
        print(json.dumps(state.inbox(), indent=2))
    elif args.command == "reply":
        if args.msg_id is None or not args.text:
            raise SystemExit("reply requires --msg-id and --text")
        rid = state.answer_message(args.msg_id, args.text)
        print(json.dumps({"replied_to": args.msg_id, "operator_message_id": rid}))
    elif args.command == "tell":
        if not args.text:
            raise SystemExit("tell requires --text")
        mid = state.post_message("operator", args.text[:80], args.text)
        print(json.dumps({"operator_message_id": mid, "note": "Delivered to the resident on its next wake."}))
    elif args.command == "sandbox":
        sandbox = Sandbox(workspace, name=args.sandbox_name, network=not args.sandbox_offline)
        sandbox.ensure()
        print(json.dumps(sandbox.status(), indent=2))
    elif args.command == "observe":
        from agent.runtime.dashboard import serve

        serve(state, args.port, workspace)
    elif args.command == "plan":
        per_call = (MAX_REQUEST_BYTES + 8192 + MAX_OUTPUT_TOKENS) * MICRO_USD_PER_TOKEN / 1e6
        print(
            json.dumps(
                {
                    "mode": mode,
                    "max_calls": args.cycles * args.steps if args.cycles else "cap-limited",
                    "per_call_reservation_ceiling_usd": per_call,
                    "workload_reservation_ceiling_usd": args.cycles * args.steps * per_call
                    if args.cycles
                    else None,
                    "ledger": state.budget(),
                    "retries": 0,
                    "fallback_calls": 0,
                },
                indent=2,
            )
        )
    elif args.command == "doctor":
        docker = shutil.which("docker")
        ready = False
        if docker:
            try:
                ready = (
                    subprocess.run(
                        [docker, "info", "--format", "{{.OSType}}"], capture_output=True, timeout=10
                    ).stdout.strip()
                    == b"linux"
                )
            except subprocess.TimeoutExpired:
                pass
        print(
            json.dumps(
                {
                    "python_runtime": "available",
                    "docker_linux": ready,
                    "state": "available",
                    "provider_calls": 0,
                    "memory": "use bootstrap --mneme then sync to verify authenticated writes",
                    "execution": "requires --execution-image sha256:...; doctor does not execute code",
                },
                indent=2,
            )
        )
    else:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
        # SDK debug logs can include remote payloads; never enable them by default.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpx2").setLevel(logging.WARNING)
        logging.getLogger("mcp").setLevel(logging.WARNING)
        try:
            asyncio.run(operate(args, state, workspace))
        except KeyboardInterrupt:
            print("Stopped by operator; durable records retained")


if __name__ == "__main__":
    main()
