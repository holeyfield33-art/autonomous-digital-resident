# Mneme integration

This Resident uses the existing Aletheia Mneme service as optional persistent memory, with an initialized official MCP SDK session. It does not run an unauthenticated bare tools/call HTTP request.

## Local connection

The verified private local service in this workspace is `http://127.0.0.1:8010/mcp/`, health at `http://127.0.0.1:8010/health`. Database port 5434 belongs to this profile; an older unrelated instance on 5433 is preserved. Authentication remains required.

Use `MNEME_API_KEY` or `MNEME_LOCAL_API_KEY` in private environment configuration. Alternatively pass the existing ignored settings path explicitly:

```powershell
.\.venv\Scripts\resident bootstrap --live --mneme --mneme-config ..\Mneme-\.local\settings.json
.\.venv\Scripts\resident sync --live --mneme --mneme-config ..\Mneme-\.local\settings.json
```

The config is read only to obtain the endpoint and credential. Credentials are never copied into a pack, prompt, journal or committed file. This client profile deliberately permits only authenticated loopback memory endpoints.

## Ownership and retry behavior

Own keys are `resident/<durable-resident-id>/identity/<hash>` and `resident/<id>/cycle/<number>`. The client permits only store/get/verify on that prefix. It never lists, searches or exports a shared personal memory archive. The `recall` model tool searches only its local own-cycle records.

Every cycle writes locally first. The outbox processes at most five pending records per pass. It reads an exact remote key before storing and refuses conflicting values. After storing, it verifies integrity. Retrying a sync does not create another paid inference or replay an action. Local and remote content are compared when recalling known synchronized records.

Mneme offline mode uses keyword search fallback, not downloaded embeddings or external providers. Own authored action summaries may reach Nebius as continuity context; unrelated private memory does not. Local SQLite and PostgreSQL data are not encrypted by this application: keep OS permissions and backups appropriate for your data.

A healthy unauthenticated health response alone is insufficient. Verify authenticated store, get, integrity and read after restarting the Resident; the running integration performs these checks for its own keys.
