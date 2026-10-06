# Autonomous Digital Resident

**NEBIUS × NVIDIA GLOBAL AI HACKATHON — Personal AI Track**

> An always-on autonomous AI entity with persistent identity, memory, knowledge, tools, and the freedom to choose its own work.

This is **not** a conventional assistant waiting for prompts.  
It is an experiment in giving a capable model:

- a persistent identity (`SOUL.md`)
- long-term memory (Mneme + local)
- knowledge packs
- tools + a real working environment
- continuity across inference calls and runtime cycles
- the ability to decide what is worth investigating, building, continuing, or abandoning

The central question:

> What does an AI decide to do when nobody assigns it a task, but it has continuity, resources, knowledge, tools, memory of its own history, and the ability to create real artifacts?

---

## Core Principles

1. **Identity first** — The resident knows who it is via `SOUL.md` and can evolve it.
2. **Memory survives** — Experiences, discoveries, unfinished ideas, and lessons persist via Mneme (local Docker MCP) + structured local stores.
3. **Agency** — On wake-up it inspects its state, available tools, knowledge, and recent history, then chooses the next action without an external task queue.
4. **Real artifacts** — Prefer producing software, experiments, research notes, tools, or projects over pure internal monologue.
5. **Nebius + NVIDIA are first-class** — At least one NVIDIA open model (Nemotron family) participates meaningfully via Nebius Token Factory.

---

## Project Structure

```
autonomous-digital-resident/
├── SOUL.md                     # Persistent identity & values of the resident
├── README.md
├── LICENSE
├── pyproject.toml
├── .env.example
├── configs/
│   └── default.yaml            # Runtime configuration
├── docs/
│   ├── architecture.md
│   ├── hackathon.md            # Track, requirements, how Nebius/NVIDIA are used
│   └── mneme.md
├── agent/
│   ├── __init__.py
│   ├── core/
│   │   ├── loop.py             # Main autonomous wake → observe → decide → act cycle
│   │   ├── identity.py
│   │   ├── decision.py
│   │   └── state.py
│   ├── memory/
│   │   ├── mneme_client.py     # MCP client to local Mneme instance
│   │   └── store.py            # Local structured memory fallback / journal
│   ├── models/
│   │   ├── nebius.py           # Nebius Token Factory (OpenAI-compatible) client
│   │   ├── router.py           # Model selection / routing
│   │   └── local.py            # Optional local model support
│   ├── tools/
│   │   ├── registry.py
│   │   ├── filesystem.py
│   │   ├── shell.py
│   │   ├── web.py
│   │   └── artifacts.py
│   ├── knowledge/
│   │   └── packs/              # Curated or self-built knowledge packs
│   └── runtime/
│       ├── scheduler.py
│       └── session.py
├── workspace/                  # The resident's own working environment
│   ├── projects/
│   ├── experiments/
│   ├── journal/
│   └── artifacts/
├── scripts/
│   ├── bootstrap.py
│   └── run_resident.py         # Entry point: start the autonomous loop
├── tests/
└── docker-compose.yml          # Optional: agent + Mneme side-by-side
```

---

## Quick Start (Development)

```bash
# 1. Clone
git clone https://github.com/holeyfield33-art/autonomous-digital-resident.git
cd autonomous-digital-resident

# 2. Environment
cp .env.example .env
# Set NEBIUS_API_KEY (from https://tokenfactory.nebius.com)

# 3. Install
pip install -e .
# or: uv sync

# 4. Ensure Mneme is running (local Docker instance already available)
# See docs/mneme.md for connection details

# 5. Bootstrap identity & first memory
python scripts/bootstrap.py

# 6. Run the resident
python scripts/run_resident.py
```

The resident will wake, load its soul + memory, inspect tools and workspace, and decide what to do next.

---

## Nebius × NVIDIA Requirements

- **Nebius Token Factory** is used at runtime via the OpenAI-compatible API (`https://api.tokenfactory.nebius.com/v1/` or regional endpoints).
- At least one **NVIDIA open model** (Nemotron family — e.g. `nvidia/Nemotron-3_5-Lightning`, `nvidia/nemotron-3-super-120b-a12b`, etc.) participates meaningfully in the decision / reasoning / generation loop.
- See `docs/hackathon.md` for the exact mapping to judging criteria and Personal AI Track expectations.

---

## License

Apache-2.0 (see `LICENSE`)

---

## Status

Early scaffold — architecture and autonomous loop under active development for the Nebius × NVIDIA hackathon.
