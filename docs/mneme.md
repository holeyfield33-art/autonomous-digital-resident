# Mneme Integration — Aletheia Mneme

The Resident’s long-term memory is **[Aletheia Mneme](https://github.com/holeyfield33-art/Mneme-)**, a sovereign persistent memory system built for agents that need continuity, auditability, and control over their own state.

Repository: https://github.com/holeyfield33-art/Mneme-

---

## What Aletheia Mneme provides

| Capability | Detail |
|------------|--------|
| Gateway | FastAPI + FastMCP (streamable HTTP MCP) |
| State store | PostgreSQL (e.g. Neon) — namespaces, keys, memories, history |
| Semantic search | pgvector + HNSW; embeddings with graceful fallback |
| Integrity | **Helios** — SHA-256 over canonical memory snapshots |
| Multi-agent | Relay store (session-scoped, 24h TTL, isolated namespaces) |
| Access | 16 tools, no tiers; `PERSONAL_MODE` for single-operator deployments |
| Auth | Bearer API key (`mneme_p_…` / `mneme_f_…`); Argon2id verification |

This is not a generic vector DB wrapper. It is a memory layer designed so agents do not have to ship secrets and session history through untrusted middleware.

---

## Why the Resident uses it

- Experiences and identity **survive** process restarts and context-window limits  
- Semantic + keyword search + relationship graph support future “what was I working on?” recall  
- Helios lets critical memories be **verified**, not only retrieved  
- MCP interface matches how modern agents already talk to tools  
- Same stack the author controls end-to-end (sovereign-first)

---

## Connection

Environment variables (see `.env.example`):

```bash
MNEME_MCP_URL=http://localhost:8000/mcp    # or https://your-host/mcp
MNEME_API_KEY=mneme_p_...                  # PERSONAL_MODE or created key
```

Client implementation: `agent/memory/mneme_client.py`

- Sends JSON-RPC-style `tools/call` requests to the MCP HTTP endpoint  
- Authenticates with `Authorization: Bearer <MNEME_API_KEY>`  
- Exposes async helpers matching Mneme tool names  

Health check (on the Mneme service, not the MCP path):

```bash
curl -s http://localhost:8000/health
```

Expected shape includes `"product": "Aletheia Mneme"` and database status.

---

## Tools used by the Resident

| Mneme tool | How the Resident uses it |
|------------|---------------------------|
| `store_memory` | Bootstrap identity; every cycle’s experience record |
| `list_memories` | Observe phase — recent context |
| `get_stats` | Observe phase — memory footprint awareness |
| `get_memory` | Targeted load (e.g. identity key) |
| `search_memory` / `semantic_search` | Future richer recall before deciding |
| `relate_memories` / `get_related` | Link projects, insights, unfinished threads |
| `memory_history` / `rollback_memory` | Inspect or repair evolution of an idea |
| `verify_memory` | Helios integrity check on critical keys |
| `reinforce` | Strengthen high-value facts |
| `export_memories` | Snapshot / backup |
| `forget_memory` / `update_memory` | Maintenance |

The current loop always **stores** and **lists**; other tools are available on the client for policy upgrades without new plumbing.

---

## Categories (convention)

| Category | Intent |
|----------|--------|
| `identity` | SOUL fragments, self-model |
| `experience` | Per-cycle decisions and outcomes |
| `project` | Ongoing work threads |
| `insight` | Lessons and discoveries |
| `artifact` | Pointers to workspace outputs |
| `unfinished` | Threads the Resident may resume |

Bootstrap writes:

- `identity/soul` — full `SOUL.md` text  
- `experience/bootstrap` — first marker that the Resident has been seeded  

Cycles write keys like:

```text
cycle/00001/20261006T174500Z
```

under category `experience`.

---

## Dual write: Mneme + local journal

| Destination | Why |
|-------------|-----|
| Mneme | Authoritative long-term store; searchable; survives machines |
| `workspace/journal/cycle_XXXXX.md` | Full decision text + outcome JSON for humans and offline debug |

If Mneme is temporarily unreachable, the loop logs a warning and still writes the local journal when possible so the cycle is not invisible.

---

## Running Mneme for development

Follow the Mneme repo (`aletheia-mneme/`):

```bash
cd path/to/Mneme-/aletheia-mneme
pip install -r requirements.txt
# Set DATABASE_URL, PERSONAL_MODE=true, PERSONAL_API_KEY=..., etc.
uvicorn main:app --host 0.0.0.0 --port 8000
```

Or use a deployed instance (e.g. Render) and point `MNEME_MCP_URL` / `MNEME_API_KEY` at it.

---

## Security notes

- Prefer `PERSONAL_MODE` for a single Resident operator  
- Never commit real `MNEME_API_KEY` values  
- Relay endpoint uses a separate `RELAY_SECRET` (multi-agent); the Resident’s default path uses the main MCP tools, not relay  
- Helios hashes cover immutable content fields — use `verify_memory` when integrity matters  

---

## Next memory upgrades (optional)

1. Call `semantic_search` in **observe** with a short query derived from open workspace threads  
2. `relate_memories` between `experience/*` and `project/*` keys when tools create projects  
3. Periodic `export_memories` artifact under `workspace/artifacts/`  
4. On identity changes, `update_memory` + `verify_memory` for `identity/soul`  
