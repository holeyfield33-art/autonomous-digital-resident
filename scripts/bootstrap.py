#!/usr/bin/env python3
"""Bootstrap the Resident: seed initial identity memory into Mneme."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.core.identity import load_soul
from agent.memory.mneme_client import MnemeClient

log = logging.getLogger("bootstrap")


async def bootstrap() -> None:
    load_dotenv()
    logging.basicConfig(level="INFO", format="%(levelname)s: %(message)s")

    soul = load_soul(ROOT / "SOUL.md")
    mneme = MnemeClient()

    try:
        # Store the living identity
        await mneme.store_memory(
            key="identity/soul",
            value=soul,
            category="identity",
        )
        log.info("Stored identity/soul")

        # Seed a first experience marker
        await mneme.store_memory(
            key="experience/bootstrap",
            value=(
                "The Autonomous Digital Resident was bootstrapped. "
                "Identity loaded from SOUL.md. Ready to begin self-directed cycles."
            ),
            category="experience",
        )
        log.info("Stored experience/bootstrap")

        stats = await mneme.get_stats()
        log.info("Mneme stats after bootstrap: %s", stats)
    except Exception as e:
        log.error("Bootstrap failed (is Mneme running and MNEME_API_KEY set?): %s", e)
        raise
    finally:
        await mneme.close()


if __name__ == "__main__":
    asyncio.run(bootstrap())
