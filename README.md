# Autonomous Digital Resident

A persistent AI that chooses its own next direction, uses bounded tools, and leaves inspectable artifacts. Built for the Nebius × NVIDIA hackathon's Personal AI track.

The running system combines an operator-authored identity, its own durable memories, selected knowledge packs, NVIDIA Nemotron through Nebius Token Factory, and a dedicated workspace. No human task queue is required. The model may explore, build, continue, abandon a direction or rest. Its public summaries describe chosen actions; they are not evidence of consciousness.

Version 0.2 replaces the scaffold's host shell and placeholder MCP transport with durable state, real initialized MCP sessions, tool-result feedback and optional isolated execution. [Build review and remaining gaps](docs/BUILD_REPORT.md).

## Install and try it

Python 3.11+; Docker is needed only for execution. Mneme is optional for the offline demo.

```powershell
git clone https://github.com/holeyfield33-art/autonomous-digital-resident.git
cd autonomous-digital-resident
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-lock.txt
.\.venv\Scripts\python -m pip install --no-deps -e .
.\.venv\Scripts\resident doctor
.\.venv\Scripts\resident demo --interval 0
.\.venv\Scripts\resident demo --interval 0
.\.venv\Scripts\resident observe
```

Open **http://127.0.0.1:8766**. Both demo cycles create canned continuity artifacts, preserve increasing cycle IDs, and feed real write results back to the next canned decision. Demo is explicitly labeled and makes zero provider calls. On Linux use `.venv/bin/python` and `.venv/bin/resident`.

## Live, self-directed operation

Create a private `.env` using [.env.example](.env.example). Only live mode needs `NEBIUS_API_KEY`. Optional Mneme uses authenticated loopback MCP; this workspace's service is at `http://127.0.0.1:8010/mcp/`.

```powershell
# If an operator STOP/PAUSE marker exists:
.\.venv\Scripts\resident resume --live
# One cycle first; --cycles 0 means persistent polling under the same spend cap.
.\.venv\Scripts\resident run --live --mneme --cycles 1
.\.venv\Scripts\resident run --live --mneme --cycles 0 --interval 300
```

Each cycle has at most two model calls by default and each decision permits at most four actions. The **durable default live cap is $0.50**. Reservations precede requests; unresolved requests retain their full reservation. No SDK retries or automatic model fallback. A restart cannot raise the stored cap. Accounting is conservative and is not a billing receipt. [Cost details](docs/RUN_MANUAL.md#spending).

Do not create alternate state directories to bypass this cap. Stop/pause checks prevent new actions and model calls between steps; an in-flight request may finish within its timeout.

## Watch what it does

```powershell
# Separate terminal, correct live state:
.\.venv\Scripts\resident observe --live
.\.venv\Scripts\resident status --live
# Operator controls:
.\.venv\Scripts\resident pause --live
.\.venv\Scripts\resident resume --live
.\.venv\Scripts\resident stop --live
```

The dashboard refreshes every 15 seconds, shows heartbeat, chosen directions, actual tool results, errors and spend, and links to text-only artifact previews. It is read-only and bound to loopback.

- Live artifacts: `workspace/live/` (projects and artifacts are chosen by the model).
- Full cycle records: `.resident/live/journal/cycle-XXXXXX.json`.
- Durable identity, events, spend and local memory: `.resident/live/resident.sqlite`.
- Demo state and workspace: `.resident/demo/` and `workspace/demo/`, separately.
- Windows background operation: `.\scripts\local.ps1 start`; logs are named in `.resident/live/service.json`. See [the full manual](docs/RUN_MANUAL.md).

`--home .resident/live` now means that exact live state. The earlier scaffold incorrectly selected a nested demo directory; old nested records are preserved but are not the live Resident.

## Tools and boundaries

| Capability | Scope |
|---|---|
| list/read/write/append/mkdir/exists | Dedicated workspace; bounded UTF-8, path/link/secret checks and quotas |
| create_artifact/project/experiment | Actual files with recorded paths and content hashes |
| recall | Only this Resident's committed cycle memories |
| list/read_knowledge | Operator-selected packs; read-only and untrusted |
| run_python | Opt-in immutable Docker image; one source file, no network/credentials, read-only input, bounded CPU/memory/time/output |
| web_fetch | Opt-in exact operator-selected HTTPS URLs, no redirects or arbitrary model-generated URLs |

The model cannot execute a host shell, access sibling memory, edit controller state or identity policy, install packages, commit/push code, or grant itself additional tools. It may write code as an artifact and execute a single standard-library Python file when the operator enables Docker execution. Exit status is execution evidence, not correctness proof.

The controller runs on the host and the local operator is trusted. This is not a security claim against hostile host processes or kernel exploits. [Architecture and limitations](docs/architecture.md).

## Memory and identity

The full bounded `SOUL.md` is loaded every cycle. Recent local memories and past directions survive restarts. Mneme synchronizes this Resident's exact keys with store/read/integrity checks. An outage leaves a durable outbox; retries synchronize memory, not model requests or tools. Unrelated personal archives are never listed or forwarded to Nebius.

This local Mneme profile uses keyword fallback while offline. Do not describe it as live semantic embeddings. [Mneme guide](docs/mneme.md).

## Evidence, docs and submission

- [Run manual](docs/RUN_MANUAL.md): installation, start/stop, observation, recovery, cost, Docker and Mneme.
- [Architecture](docs/architecture.md): continuity, authority and decision contract.
- [Build report](docs/BUILD_REPORT.md): scaffold findings, repairs and observed checks.
- [Hackathon and project choice](docs/hackathon.md): deliverables and comparison with Repo Steward.
- [Provenance](docs/PROVENANCE.md): source identities, official request pattern and licenses.

Tests: `python -m pytest -q -ra`; Docker tests explicitly skip unless `RESIDENT_TEST_IMAGE` names a trusted local image ID. A separate CI job exercises real Docker isolation without paid calls. This is a working bounded prototype; independent security review, a longer continuity trial, blind artifact-quality evaluation, judge-facing demo URL and public video remain open.

Local verification passed: 21 tests including real Docker probes, plus 19 Linux
installed-package protocol tests. GitHub's jobs are currently blocked from
starting by an account billing lock; hosted CI is not green. Details and the
live restart checkpoint are in [the build report](docs/BUILD_REPORT.md).

Apache-2.0: [LICENSE](LICENSE).
