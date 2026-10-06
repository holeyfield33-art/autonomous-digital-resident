# Mneme Integration — Aletheia Mneme

The Autonomous Digital Resident uses **[Aletheia Mneme](https://github.com/holeyfield33-art/Mneme-)** as its primary long-term memory layer.

Aletheia Mneme is a sovereign, local-first (or self-hosted) persistent memory system with:

- FastAPI + FastMCP gateway
- PostgreSQL + pgvector (HNSW) for semantic search
- Helios cryptographic content hashing (SHA-256 canonical integrity)
- Multi-agent relay (session-scoped, 24h TTL)
- 16 fully available tools (no tiers)
- PERSONAL_MODE for single-operator sovereign deployments

## Why this Mneme

It was purpose-built for agents that need real continuity, auditability, and sovereignty. It fits the Resident experiment perfectly:

- Memories survive process restarts and context-window limits.
- Semantic + keyword search + relationship graph + version history.
- Integrity proofs via Helios so the Resident can verify its own memory has not been silently altered.
- MCP interface — the Resident talks to it the same way any modern agent would.

## Connection

```bash
# Typical local / Docker / Render deployment
MNEME_MCP_URL=http://localhost:8000/mcp          # or https://your-mneme-host/mcp
MNEME_API_KEY=mneme_p_...                        # PERSONAL_MODE key or created key
```

The Resident authenticates with `Authorization: Bearer <key>` (or `?api_key=` query param).

## Tools the Resident uses

| Tool | Resident use |
|------|--------------|
| `store_memory` | Persist experiences, decisions, unfinished ideas, lessons |
| `get_memory` / `list_memories` | Load identity-relevant or project state |
| `semantic_search` / `search_memory` | Recall relevant past context before deciding |
| `relate_memories` / `get_related` | Build a graph of ideas, projects, and outcomes |
| `memory_history` / `rollback_memory` | Inspect evolution of an idea or reverse a bad update |
| `verify_memory` | Confirm Helios integrity of critical memories |
| `reinforce` | Strengthen confidence in important facts |
| `export_memories` | Snapshot / backup of the Resident's mind |
| `get_stats` | Self-awareness of memory footprint |

## Recommended categories for the Resident

- `identity` — SOUL fragments, self-model updates
- `experience` — what happened in a cycle
- `project` — ongoing work threads
- `insight` — discoveries and lessons
- `artifact` — pointers to things created in the workspace
- `unfinished` — open threads the Resident may resume later

## Architecture note

The Resident treats Mneme as the authoritative long-term store. A thin local journal (`agent/memory/store.py`) can mirror recent cycles for fast inspection and offline resilience, but the source of truth across restarts is Aletheia Mneme.
