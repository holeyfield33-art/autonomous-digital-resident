"""Main autonomous cycle for the Digital Resident.

Wake → Observe → Decide → Act → Remember

This is intentionally a clear, evolvable skeleton. The policy for
*what* the Resident chooses to do is left open — that is the experiment.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.core.identity import load_soul, soul_summary
from agent.memory.mneme_client import MnemeClient
from agent.models.nebius import NebiusClient

log = logging.getLogger("resident.loop")


class ResidentLoop:
    def __init__(
        self,
        nebius: NebiusClient,
        mneme: MnemeClient,
        workspace: Path,
        soul_path: str = "SOUL.md",
        cycle_interval: float = 300.0,
    ) -> None:
        self.nebius = nebius
        self.mneme = mneme
        self.workspace = Path(workspace)
        self.soul_path = soul_path
        self.cycle_interval = cycle_interval
        self.cycle_count = 0

    async def run(self, max_cycles: int = 0) -> None:
        """Run the autonomous loop. max_cycles=0 means unlimited."""
        log.info("Resident waking. Model: %s", self.nebius.model_info())
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

        # 1. Observe
        observation = await self._observe()

        # 2. Decide (Nemotron via Nebius)
        decision = await self._decide(identity, observation)

        # 3. Act (currently logs intent; tools will be wired next)
        outcome = await self._act(decision)

        # 4. Remember
        await self._remember(decision, outcome)

    async def _observe(self) -> dict[str, Any]:
        """Inspect current state: workspace, recent memories, stats."""
        workspace_listing = []
        for sub in ("projects", "experiments", "journal", "artifacts"):
            d = self.workspace / sub
            if d.exists():
                workspace_listing.append(
                    {"dir": sub, "items": [p.name for p in d.iterdir() if not p.name.startswith(".")]}
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
        }

    async def _decide(self, identity: str, observation: dict[str, Any]) -> str:
        """Ask the Nemotron model what is worth doing next."""
        system = (
            "You are the Autonomous Digital Resident. "
            "You have a persistent identity, long-term memory, tools, and a workspace. "
            "No human has assigned you a task. Decide what is most worth doing next. "
            "Prefer producing real artifacts over pure internal monologue. "
            "Respond with a clear, concrete next action or short plan."
        )
        user = (
            f"## Your Identity\n{identity}\n\n"
            f"## Current Observation\n{observation}\n\n"
            "What will you do next, and why?"
        )
        decision = self.nebius.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        log.info("Decision:\n%s", decision[:500])
        return decision

    async def _act(self, decision: str) -> dict[str, Any]:
        """Execute the decision. Tool calling will be expanded here."""
        # Placeholder: for now we record the intention.
        # Next iterations will parse tool calls / structured actions.
        return {
            "status": "intention_recorded",
            "decision_excerpt": decision[:300],
            "note": "Full tool execution to be wired in subsequent development.",
        }

    async def _remember(self, decision: str, outcome: dict[str, Any]) -> None:
        """Persist the cycle into Mneme."""
        key = f"cycle/{self.cycle_count:05d}/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        value = (
            f"DECISION:\n{decision}\n\n"
            f"OUTCOME:\n{outcome}\n"
        )
        try:
            await self.mneme.store_memory(key=key, value=value, category="experience")
            log.info("Remembered cycle as %s", key)
        except Exception as e:
            log.warning("Failed to store memory: %s", e)
