"""Main autonomous cycle for the Digital Resident.

Wake → Observe → Decide → Act → Remember

The model is asked to emit structured TOOL_CALL blocks when it wants
to use tools. The act phase parses and executes them via the registry.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.core.identity import load_soul, soul_summary
from agent.memory.mneme_client import MnemeClient
from agent.models.nebius import NebiusClient
from agent.tools.registry import ToolRegistry, build_default_registry

log = logging.getLogger("resident.loop")

# Match blocks like:
# TOOL_CALL
# {"name": "write_file", "arguments": {"relative": "...", "content": "..."}}
# END_TOOL_CALL
TOOL_CALL_RE = re.compile(
    r"TOOL_CALL\s*\n\s*(\{.*?\})\s*\n\s*END_TOOL_CALL",
    re.DOTALL | re.IGNORECASE,
)


class ResidentLoop:
    def __init__(
        self,
        nebius: NebiusClient,
        mneme: MnemeClient,
        workspace: Path,
        soul_path: str = "SOUL.md",
        cycle_interval: float = 300.0,
        tools: ToolRegistry | None = None,
    ) -> None:
        self.nebius = nebius
        self.mneme = mneme
        self.workspace = Path(workspace)
        self.soul_path = soul_path
        self.cycle_interval = cycle_interval
        self.cycle_count = 0
        self.tools = tools or build_default_registry(self.workspace)

    async def run(self, max_cycles: int = 0) -> None:
        """Run the autonomous loop. max_cycles=0 means unlimited."""
        log.info("Resident waking. Model: %s", self.nebius.model_info())
        log.info("Tools available: %s", self.tools.list_tools())
        while True:
            self.cycle_count += 1
            log.info("── Cycle %d starting ──", self.cycle_count)
            try:
                await self.one_cycle()
            except Exception:
                log.exception("Cycle %d failed", self.cycle_count)
            if max_cycles and self.cycle_count >= max_cycles:
                log.info("Reached max_cycles=%d — stopping.", max_cycles)
                break
            await asyncio.sleep(self.cycle_interval)

    async def one_cycle(self) -> None:
        soul = load_soul(self.soul_path)
        identity = soul_summary(soul)

        observation = await self._observe()
        decision = await self._decide(identity, observation)
        outcome = await self._act(decision)
        await self._remember(decision, outcome)

    async def _observe(self) -> dict[str, Any]:
        workspace_listing = []
        for sub in ("projects", "experiments", "journal", "artifacts"):
            d = self.workspace / sub
            if d.exists():
                workspace_listing.append(
                    {
                        "dir": sub,
                        "items": [p.name for p in d.iterdir() if not p.name.startswith(".")],
                    }
                )

        recent: list = []
        stats: dict = {}
        try:
            recent = await self.mneme.list_memories(limit=15)
            stats = await self.mneme.get_stats()
        except Exception as e:
            log.warning("Mneme observe partial failure: %s", e)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "workspace": workspace_listing,
            "recent_memories": recent,
            "mneme_stats": stats,
            "cycle": self.cycle_count,
            "available_tools": self.tools.schemas(),
        }

    async def _decide(self, identity: str, observation: dict[str, Any]) -> str:
        system = (
            "You are the Autonomous Digital Resident.\n"
            "You have a persistent identity, long-term memory (Mneme), tools, and a workspace.\n"
            "No human has assigned you a task. Decide what is most worth doing next.\n"
            "Prefer producing real artifacts over pure internal monologue.\n\n"
            "When you want to use a tool, emit one or more blocks exactly in this form:\n\n"
            "TOOL_CALL\n"
            '{"name": "tool_name", "arguments": {"param": "value"}}\n'
            "END_TOOL_CALL\n\n"
            "You may include reasoning outside those blocks. "
            "You may emit multiple TOOL_CALL blocks. "
            "Available tools and parameters are listed in the observation."
        )
        user = (
            f"## Your Identity\n{identity}\n\n"
            f"## Current Observation\n{json.dumps(observation, default=str, indent=2)[:12_000]}\n\n"
            "What will you do next? Use TOOL_CALL blocks for any concrete actions."
        )
        decision = self.nebius.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        log.info("Decision (excerpt):\n%s", decision[:800])
        return decision

    def _parse_tool_calls(self, decision: str) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        for match in TOOL_CALL_RE.finditer(decision):
            raw = match.group(1)
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict) and "name" in obj:
                    calls.append({
                        "name": obj["name"],
                        "arguments": obj.get("arguments") or obj.get("args") or {},
                    })
            except json.JSONDecodeError as e:
                log.warning("Failed to parse TOOL_CALL JSON: %s — %s", e, raw[:200])
        return calls

    async def _act(self, decision: str) -> dict[str, Any]:
        calls = self._parse_tool_calls(decision)
        results: list[dict[str, Any]] = []

        if not calls:
            log.info("No TOOL_CALL blocks found — recording intention only.")
            return {
                "status": "intention_only",
                "decision_excerpt": decision[:500],
                "tool_results": [],
            }

        for call in calls:
            name = call["name"]
            args = call.get("arguments") or {}
            if not isinstance(args, dict):
                args = {}
            log.info("Executing tool: %s(%s)", name, list(args.keys()))
            result = self.tools.call(name, **args)
            results.append({"tool": name, "arguments": args, "result": result})
            log.info("Tool %s result keys: %s", name, list(result.keys()) if isinstance(result, dict) else type(result))

        return {
            "status": "tools_executed",
            "tool_count": len(results),
            "tool_results": results,
            "decision_excerpt": decision[:400],
        }

    async def _remember(self, decision: str, outcome: dict[str, Any]) -> None:
        key = f"cycle/{self.cycle_count:05d}/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        # Keep memory payload bounded
        outcome_summary = {
            "status": outcome.get("status"),
            "tool_count": outcome.get("tool_count", 0),
            "tool_names": [r.get("tool") for r in outcome.get("tool_results", [])],
            "decision_excerpt": outcome.get("decision_excerpt", "")[:400],
        }
        value = f"DECISION:\n{decision[:3000]}\n\nOUTCOME:\n{json.dumps(outcome_summary, indent=2)}\n"
        try:
            await self.mneme.store_memory(key=key, value=value, category="experience")
            log.info("Remembered cycle as %s", key)
        except Exception as e:
            log.warning("Failed to store memory: %s", e)

        # Also write a local journal entry for human inspectability
        try:
            journal_dir = self.workspace / "journal"
            journal_dir.mkdir(parents=True, exist_ok=True)
            journal_path = journal_dir / f"cycle_{self.cycle_count:05d}.md"
            journal_path.write_text(
                f"# Cycle {self.cycle_count}\n\n"
                f"## Decision\n\n{decision}\n\n"
                f"## Outcome\n\n```json\n{json.dumps(outcome, default=str, indent=2)[:8000]}\n```\n",
                encoding="utf-8",
            )
        except Exception as e:
            log.warning("Local journal write failed: %s", e)
