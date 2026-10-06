# Autonomous Digital Resident

**NEBIUS × NVIDIA Global AI Hackathon — Personal AI Track**

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](pyproject.toml)
[![Nebius Token Factory](https://img.shields.io/badge/Nebius-Token%20Factory-purple.svg)](https://tokenfactory.nebius.com)
[![NVIDIA Nemotron](https://img.shields.io/badge/NVIDIA-Nemotron-76B900.svg)](https://nebius.com/services/token-factory/nemotron)

> An always-on autonomous AI entity with persistent identity, long-term memory, tools, and the freedom to choose its own work.

This is **not** a chatbot waiting for prompts.  
It is an experiment in continuity and agency:

**What does an AI decide to do when nobody assigns it a task — but it has identity, memory, knowledge, tools, a real workspace, and the ability to create durable artifacts?**

---

## Table of contents

1. [Idea](#idea)
2. [How it works](#how-it-works)
3. [Stack](#stack)
4. [Project layout](#project-layout)
5. [Prerequisites](#prerequisites)
6. [Setup](#setup)
7. [Running the Resident](#running-the-resident)
8. [Tools available to the Resident](#tools-available-to-the-resident)
9. [Memory (Aletheia Mneme)](#memory-aletheia-mneme)
10. [Nebius × NVIDIA usage](#nebius--nvidia-usage)
11. [Configuration](#configuration)
12. [Observing the Resident](#observing-the-resident)
13. [Hackathon notes](#hackathon-notes)
14. [Documentation map](#documentation-map)
15. [License](#license)
16. [Status](#status)

---

## Idea

Most agents are task queues with a system prompt. The Resident is designed the other way around:

| Conventional agent | Autonomous Digital Resident |
|--------------------|-----------------------------|
| Waits for a human prompt or job | Wakes and decides what is worth doing |
| Context dies with the window | Identity + memory survive restarts |
| Output is often chat | Prefers real artifacts in a workspace |
| Tools are optional helpers | Tools are how it acts on the world |

On every cycle the Resident:

1. **Wakes** — loads `SOUL.md` and recent memory  
2. **Observes** — workspace, Mneme history, available tools  
3. **Decides** — NVIDIA Nemotron (via Nebius Token Factory) chooses the next action  
4. **Acts** — executes structured tool calls (files, shell, web, artifacts)  
5. **Remembers** — writes the cycle to Mneme and a local journal  

No external task list is required.

---

## How it works

```text
┌─────────────────────────────────────────────────────────────┐
│                 Autonomous Digital Resident                 │
│                                                             │
│   SOUL.md ──► Identity                                      │
│   Mneme   ──► Long-term memory (semantic + integrity)       │
│   Nebius  ──► Nemotron models (decide / reason / write)     │
│   Tools   ──► filesystem · shell · web · artifacts          │
│   Workspace ► projects / experiments / journal / artifacts  │
│                                                             │
│              wake → observe → decide → act → remember       │
└─────────────────────────────────────────────────────────────┘
```

**Decision → action protocol.** The model is instructed to emit tool calls in a strict text format:

```text
TOOL_CALL
{"name": "create_artifact", "arguments": {"name": "notes", "content": "..."}}
END_TOOL_CALL
```

The loop parses every block, runs it through the tool registry, and records results. If no tool blocks appear, the cycle still stores the intention (so continuity is never lost).

---

## Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Inference | **Nebius Token Factory** (OpenAI-compatible API) |
| Models | **NVIDIA Nemotron** family (e.g. `nvidia/Nemotron-3_5-Lightning`) |
| Long-term memory | **[Aletheia Mneme](https://github.com/holeyfield33-art/Mneme-)** (FastMCP, PostgreSQL, pgvector, Helios) |
| Local continuity | `workspace/journal/` cycle logs |
| Packaging | `pyproject.toml` (hatchling) |
| License | Apache-2.0 |

---

## Project layout

```text
autonomous-digital-resident/
├── SOUL.md                      # Living identity of the Resident
├── README.md                    # This file
├── LICENSE                      # Apache-2.0
├── pyproject.toml
├── .env.example                 # Required secrets & defaults
├── configs/default.yaml         # Runtime defaults
├── docker-compose.yml           # Optional local notes
│
├── docs/
│   ├── architecture.md          # Design & loop details
│   ├── hackathon.md             # Track alignment, Nebius/NVIDIA mapping
│   └── mneme.md                 # Aletheia Mneme integration guide
│
├── agent/
│   ├── core/
│   │   ├── loop.py              # Autonomous cycle (observe → decide → act → remember)
│   │   └── identity.py          # SOUL.md loader
│   ├── memory/
│   │   └── mneme_client.py      # HTTP/MCP client for Aletheia Mneme
│   ├── models/
│   │   └── nebius.py            # Nebius Token Factory + Nemotron client
│   ├── tools/
│   │   ├── registry.py          # Tool registration + schemas for the model
│   │   ├── filesystem.py        # Safe workspace read/write
│   │   ├── shell.py             # Allowlisted shell in workspace cwd
│   │   ├── web.py               # HTTP(S) fetch
│   │   └── artifacts.py         # Projects, experiments, dated artifacts
│   ├── knowledge/packs/         # Optional knowledge packs
│   └── runtime/                 # Session / scheduling hooks (extensible)
│
├── workspace/                   # The Resident's own filesystem
│   ├── projects/
│   ├── experiments/
│   ├── journal/                 # Human-readable cycle logs
│   └── artifacts/
│
└── scripts/
    ├── bootstrap.py             # Seed identity into Mneme
    └── run_resident.py          # Start the autonomous loop
```

---

## Prerequisites

1. **Python 3.11+**
2. **Nebius Token Factory API key** — [tokenfactory.nebius.com](https://tokenfactory.nebius.com)
3. **Running Aletheia Mneme instance** — [github.com/holeyfield33-art/Mneme-](https://github.com/holeyfield33-art/Mneme-)  
   (local uvicorn, Docker, or Render). You need the MCP URL and an API key (`PERSONAL_MODE` or a created key).

---

## Setup

```bash
git clone https://github.com/holeyfield33-art/autonomous-digital-resident.git
cd autonomous-digital-resident

# Environment
cp .env.example .env
# Edit .env:
#   NEBIUS_API_KEY=...
#   MNEME_MCP_URL=http://localhost:8000/mcp   # or your hosted URL
#   MNEME_API_KEY=mneme_p_...                 # or created key

# Install
pip install -e .
# optional: pip install -e ".[dev]"
```

Confirm Mneme is healthy (example):

```bash
curl -s "$MNEME_MCP_URL/../health"   # or GET https://your-host/health
```

---

## Running the Resident

### 1. Bootstrap (once)

Seeds `identity/soul` and a first experience marker into Mneme:

```bash
python scripts/bootstrap.py
```

### 2. Start the loop

```bash
python scripts/run_resident.py
```

Useful environment overrides:

| Variable | Meaning | Default |
|----------|---------|---------|
| `CYCLE_INTERVAL_SECONDS` | Pause between cycles | `300` |
| `MAX_CYCLES` | Stop after N cycles (`0` = unlimited) | `0` |
| `PRIMARY_MODEL` | Nemotron model id | `nvidia/Nemotron-3_5-Lightning` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `RESIDENT_WORKSPACE` | Workspace root | `./workspace` |

Example — one short cycle for a smoke test:

```bash
MAX_CYCLES=1 CYCLE_INTERVAL_SECONDS=1 python scripts/run_resident.py
```

---

## Tools available to the Resident

All tools are scoped to the workspace (or network fetch). The model sees schemas during **observe** and must emit `TOOL_CALL` blocks to use them.

| Tool | Purpose |
|------|---------|
| `list_dir` | List directory under workspace |
| `read_file` | Read a text file |
| `write_file` | Create/overwrite a file |
| `append_file` | Append to a file |
| `mkdir` | Create directories |
| `exists` | Check path existence |
| `shell` | Allowlisted commands (`ls`, `python`, `git status`, …) in workspace cwd |
| `web_fetch` | Fetch public `http`/`https` pages |
| `create_artifact` | Dated durable note under `workspace/artifacts/` |
| `create_project` | New project stub under `workspace/projects/` |
| `create_experiment` | Experiment log under `workspace/experiments/` |

Shell commands are deliberately restricted (allowlist + no dangerous chaining). Expand the allowlist only when you intend to.

---

## Memory (Aletheia Mneme)

Long-term memory is **[Aletheia Mneme](https://github.com/holeyfield33-art/Mneme-)**:

- FastAPI + FastMCP gateway  
- PostgreSQL + pgvector (HNSW semantic search)  
- Helios SHA-256 content hashing for integrity  
- 16 tools (store, search, relate, history, verify, export, …)  
- `PERSONAL_MODE` for sovereign single-operator deployments  

Each cycle stores an `experience` memory and a local markdown journal entry under `workspace/journal/`. See **[docs/mneme.md](docs/mneme.md)** for categories, tools, and connection details.

---

## Nebius × NVIDIA usage

Compliance is architectural, not cosmetic:

1. **Runtime calls** go to Nebius Token Factory (`NEBIUS_BASE_URL`, default `https://api.tokenfactory.nebius.com/v1/`).
2. **Primary reasoning model** is an NVIDIA open model from the Nemotron family.

Default routing (overridable via env):

| Role | Model ID |
|------|----------|
| Primary | `nvidia/Nemotron-3_5-Lightning` |
| Fallback | `nvidia/nemotron-3-super-120b-a12b` |

Implementation: `agent/models/nebius.py` → used on every **decide** step of the loop.  
Full mapping to hackathon rules: **[docs/hackathon.md](docs/hackathon.md)**.

---

## Configuration

- **Secrets & endpoints:** `.env` (from `.env.example`)
- **Structured defaults:** `configs/default.yaml`
- **Identity:** edit `SOUL.md` (the Resident loads it every cycle)

Do not commit real API keys.

---

## Observing the Resident

| Channel | Location |
|---------|----------|
| Console logs | stdout (`LOG_LEVEL`) |
| Local journal | `workspace/journal/cycle_XXXXX.md` |
| Artifacts / projects | `workspace/artifacts/`, `workspace/projects/`, `workspace/experiments/` |
| Long-term memory | Mneme (`list_memories`, `semantic_search`, `export_memories`) |

You can inspect journal files while the process is running; each cycle is self-contained.

---

## Hackathon notes

- **Track:** Personal AI  
- **Repo:** public GitHub (this repository)  
- **License:** Apache-2.0  
- **Demo path:** run with `MAX_CYCLES=1` (or a short continuous run), show journal + Mneme memories + any artifacts created  
- **Video / feedback:** see submission checklist in [docs/hackathon.md](docs/hackathon.md)

---

## Documentation map

| Document | Contents |
|----------|----------|
| [docs/architecture.md](docs/architecture.md) | Loop design, components, open research questions |
| [docs/hackathon.md](docs/hackathon.md) | Track alignment, technical requirements, judging |
| [docs/mneme.md](docs/mneme.md) | Aletheia Mneme connection, tools, categories |
| [SOUL.md](SOUL.md) | Identity the Resident loads every cycle |

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).

---

## Status

Working autonomous loop with:

- Nebius Token Factory + NVIDIA Nemotron decision path  
- Aletheia Mneme long-term memory client  
- Filesystem, shell, web, and artifact tools  
- Structured tool-call execution and local journaling  

Actively developed for the Nebius × NVIDIA Global AI Hackathon (Personal AI Track).
