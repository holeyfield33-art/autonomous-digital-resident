# Architecture

## Design stance

The architecture is part of the experiment. The goal is not a feature checklist — it is a **persistent AI entity** that can remember its own existence, use tools, and choose work without a human task queue.

Central question:

> What does an AI decide to do when it has identity, memory, knowledge, tools, time, and freedom?

---

## Component map

```text
┌──────────────────────────────────────────────────────────────────┐
│                   Autonomous Digital Resident                    │
│                                                                  │
│  Identity          Memory              Models           Tools    │
│  ────────          ──────              ──────           ─────    │
│  SOUL.md           Aletheia Mneme      Nebius TF        FS       │
│  identity.py       mneme_client.py     Nemotron         Shell    │
│                    local journal       nebius.py        Web      │
│                                                         Artifacts│
│                                                                  │
│                    ┌─────────────────────────────┐               │
│                    │  ResidentLoop (loop.py)     │               │
│                    │  wake → observe → decide    │               │
│                    │       → act → remember      │               │
│                    └──────────────┬──────────────┘               │
│                                   │                              │
│                                   ▼                              │
│                    workspace/{projects,experiments,              │
│                               journal,artifacts}                 │
└──────────────────────────────────────────────────────────────────┘
```

| Component | Path | Role |
|-----------|------|------|
| Identity | `SOUL.md`, `agent/core/identity.py` | Loaded every cycle; defines drives and stance |
| Loop | `agent/core/loop.py` | Orchestrates one full cycle |
| Models | `agent/models/nebius.py` | Nebius Token Factory client; Nemotron primary/fallback |
| Memory | `agent/memory/mneme_client.py` | Aletheia Mneme (store, list, search, stats, …) |
| Tools | `agent/tools/*` | Discoverable actions; registry + schemas for the model |
| Workspace | `workspace/` | Real filesystem the Resident owns |
| Entry | `scripts/run_resident.py`, `scripts/bootstrap.py` | Start loop / seed identity |

---

## Core loop (implemented)

### 1. Wake

- Load `SOUL.md` via `load_soul` / `soul_summary`
- Instantiate (or reuse) Nebius client, Mneme client, tool registry bound to workspace

### 2. Observe

Collect a structured snapshot:

- Contents of `workspace/{projects,experiments,journal,artifacts}`
- Recent Mneme memories (`list_memories`)
- Mneme stats (`get_stats`)
- **Tool schemas** so the model knows what it can call

### 3. Decide

Nemotron (via Nebius) receives:

- Identity excerpt  
- Observation JSON  
- Instructions to prefer real artifacts and to emit tool calls in a fixed format:

```text
TOOL_CALL
{"name": "tool_name", "arguments": { ... }}
END_TOOL_CALL
```

Multiple blocks are allowed. Reasoning may appear outside the blocks.

### 4. Act

`ResidentLoop._parse_tool_calls` extracts JSON blocks; `ToolRegistry.call` executes each tool. Results are collected (success or structured error). If no blocks are present, the cycle records an *intention-only* outcome — continuity is preserved either way.

### 5. Remember

- **Mneme:** one `experience` memory per cycle (bounded payload: decision excerpt + tool names/status)
- **Local journal:** `workspace/journal/cycle_XXXXX.md` with full decision text and outcome JSON for human inspection

### 6. Sleep

`asyncio.sleep(cycle_interval)` then next cycle (or stop if `MAX_CYCLES` reached).

---

## Tool system

Tools are registered in `build_default_registry(workspace)`:

| Tool | Module | Notes |
|------|--------|-------|
| `list_dir`, `read_file`, `write_file`, `append_file`, `mkdir`, `exists` | `filesystem.py` | Paths resolved under workspace; escape rejected |
| `shell` | `shell.py` | Allowlist only; cwd = workspace |
| `web_fetch` | `web.py` | http/https only |
| `create_artifact`, `create_project`, `create_experiment` | `artifacts.py` | Structured durable outputs |

Schemas in `TOOL_SCHEMAS` are injected into the observation so the model does not need a separate API catalog.

---

## Memory strategy

| Store | Authority | Use |
|-------|-----------|-----|
| Aletheia Mneme | **Source of truth** across restarts | Identity seed, cycle experiences, future semantic recall |
| `workspace/journal/` | Human-facing / offline | Full cycle transcripts |

Recommended Mneme categories: `identity`, `experience`, `project`, `insight`, `artifact`, `unfinished`. See [mneme.md](mneme.md).

---

## Model strategy

- Every meaningful **decide** step calls Nebius Token Factory.
- Default primary: `nvidia/Nemotron-3_5-Lightning` (always-on friendly).
- Fallback: `nvidia/nemotron-3-super-120b-a12b` on primary failure.
- Optional local models are out of scope for compliance but can be added later for cheap auxiliary tasks without replacing Nemotron on the main path.

---

## Safety boundaries (current)

- Filesystem tools cannot leave the workspace root.
- Shell is allowlisted; shell metacharacters for chaining are rejected.
- Web tool only accepts `http`/`https`.
- No automatic modification of `SOUL.md` in the loop yet (open research question).

---

## Open research questions

These are intentionally unresolved — the experiment is meant to surface answers:

1. How should the decision policy evolve from cycle to cycle?
2. Under what constraints may the Resident edit its own `SOUL.md`?
3. How aggressive should self-scheduling be (interval vs continuous work)?
4. What counts as a “real artifact” worth keeping vs scaffolding?
5. How to surface ongoing work to a human without collapsing back into a chatbot UI?
6. When should the Resident use `semantic_search` / `relate_memories` vs only recent lists?

---

## Extensibility hooks

- **New tools:** implement a function, `register` in `build_default_registry`, add a schema entry.
- **Richer act policy:** replace text `TOOL_CALL` parsing with native tool-calling APIs when Nemotron endpoints expose them stably.
- **Scheduler / multi-process:** `agent/runtime/` is reserved for session and cadence logic beyond a single process loop.
