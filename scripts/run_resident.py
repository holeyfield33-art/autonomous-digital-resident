#!/usr/bin/env python3
"""Entry point: start the Autonomous Digital Resident."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure project root is on path when run as script
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.core.loop import ResidentLoop
from agent.memory.mneme_client import MnemeClient
from agent.models.nebius import NebiusClient


def main() -> None:
    load_dotenv()

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("resident")

    workspace = Path(os.environ.get("RESIDENT_WORKSPACE", "./workspace"))
    workspace.mkdir(parents=True, exist_ok=True)

    nebius = NebiusClient()
    mneme = MnemeClient()

    loop = ResidentLoop(
        nebius=nebius,
        mneme=mneme,
        workspace=workspace,
        soul_path=str(ROOT / "SOUL.md"),
        cycle_interval=float(os.environ.get("CYCLE_INTERVAL_SECONDS", "300")),
    )

    max_cycles = int(os.environ.get("MAX_CYCLES", "0"))
    log.info("Starting Autonomous Digital Resident")
    log.info("Nebius models: %s", nebius.model_info())
    log.info("Mneme endpoint: %s", mneme.base_url)

    try:
        asyncio.run(loop.run(max_cycles=max_cycles))
    except KeyboardInterrupt:
        log.info("Resident shutting down by request.")
    finally:
        asyncio.run(mneme.close())


if __name__ == "__main__":
    main()
