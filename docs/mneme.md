# Mneme integration

The Resident uses the private local Aletheia Mneme service as optional persistent memory, over an initialized official MCP SDK session.

## Its own namespace

The Resident authenticates with its **own agent key**, which maps to the Mneme namespace `agent-resident`. It never uses the operator's personal key, so it cannot read, list or search the personal archive, and the personal key never has to be placed in this repository.

The key is created and rotated from the Mneme repository. The raw key is written to Mneme's ignored `.local/agents/resident.key` and straight into this repository's `.env` as `MNEME_API_KEY`. It is never printed.

```powershell
cd ..\Mneme-
# First time:
.\.venv-local\Scripts\python.exe scripts\agent_key.py create resident --env-file ..\autonomous-digital-resident\.env
# Rotate (old key revoked immediately):
.\.venv-local\Scripts\python.exe scripts\agent_key.py rotate resident --env-file ..\autonomous-digital-resident\.env
# See namespaces, active keys and memory counts (no secrets shown):
.\.venv-local\Scripts\python.exe scripts\agent_key.py list
```

After creating or rotating the key, restart the Resident so it reads the new `.env`, then drain the outbox:

```powershell
cd ..\autonomous-digital-resident
.\.venv\Scripts\resident stop --live
.\.venv\Scripts\resident sync --live --mneme
.\scripts\local.ps1 start -Sandbox -Steps 8 -Interval 900
```

Do not set `MNEME_LOCAL_CONFIG` or `--mneme-config` for the Resident: those read the personal key from Mneme's `settings.json` and take precedence over `MNEME_API_KEY`.

## Local connection

Endpoint `http://127.0.0.1:8010/mcp/`, health `http://127.0.0.1:8010/health`. The client accepts only authenticated loopback endpoints. A healthy `/health` response does not prove authentication; the first wake's `memory_sync` event does. `mode: "mneme"` means records were stored and verified. `mode: "degraded_local"` with `error_type: "ExceptionGroup"` almost always means the key was rejected.

## Ownership and sync behavior

The Resident's keys are `resident/<durable-resident-id>/identity/<hash>` and `resident/<id>/cycle/<number>`. The client permits only `store_memory`, `get_memory` and `verify_memory` on that prefix.

Every wake writes locally first, into SQLite with a full-text index. The outbox syncs up to 25 pending records per pass, and `resident sync` drains the whole backlog. Each record is read before storing, so conflicting remote values are refused rather than overwritten, and integrity is verified after the write. Retrying a sync never repeats inference or tool actions.

The model's memory tools (`search_memory`, `cycle_history`, `get_cycle`) read the local records, which are the same records that sync to Mneme.

## Search mode

The local Mneme profile runs with `MNEME_OFFLINE=true`: no embedding provider and no model downloads, so `semantic_search` falls back to PostgreSQL keyword search. Semantic recall for the Resident would need local embeddings enabled in Mneme plus a scoped search tool in this client. Its own namespace is what makes that safe to add later.

## History

Before 2026-10-07 the Resident wrote 69 records into the personal namespace with an older personal key. Those copies were left in place; its current memory lives in `agent-resident`. Local SQLite and PostgreSQL data are not encrypted by either application, so keep OS permissions and backups appropriate.
