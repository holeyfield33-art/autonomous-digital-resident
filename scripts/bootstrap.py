"""Compatibility launcher for explicitly requested local memory bootstrap."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.cli import main

if __name__ == "__main__":
    sys.argv.insert(1, "bootstrap")
    main()
