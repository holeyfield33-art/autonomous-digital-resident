# Resident engineering run manual

## Supported setup

Python 3.11+ on Windows or Linux. Use the repository's dedicated virtual environment. Install `requirements-lock.txt`, then `pip install --no-deps -e .`. The installed entry point is `agent.cli:main`; packaged identity and knowledge are available even outside the source checkout. MCP is pinned to 1.30.0, matching the local verified transport API.

`.env` uses literal allowlisted assignments, without variable interpolation. Existing process variables take precedence. Required for live: `NEBIUS_API_KEY`. Optional memory: `MNEME_MCP_URL`, `MNEME_API_KEY` or `MNEME_LOCAL_API_KEY`, or `MNEME_LOCAL_CONFIG`. Optional execution: `RESIDENT_EXECUTION_IMAGE`. Unknown/incomplete assignments fail startup; no secret values are printed.

Run `resident doctor` for a no-cost runtime check. Use `resident demo` twice to verify increasing cycle IDs and durable artifacts. Canned choices are demo plumbing, never autonomy evidence.

## Live start and controls

From the repository:

```powershell
.\.venv\Scripts\resident status --live
.\.venv\Scripts\resident plan --live --cycles 3 --steps 2
.\.venv\Scripts\resident resume --live
.\.venv\Scripts\resident run --live --mneme --cycles 0 --interval 300
```

`--cycles 0` means persistent polling, bounded by the ledger. The model may request a longer sleep; the operator interval is a floor. A cap exhaustion cycle stops the runner.

Windows background launch uses `scripts/local.ps1`:

```powershell
.\scripts\local.ps1 start -MnemeConfig ..\Mneme-\.local\settings.json
.\scripts\local.ps1 status
.\scripts\local.ps1 pause
.\scripts\local.ps1 resume
.\scripts\local.ps1 stop
```

A stopped process needs `start` again; `resume` only clears markers. The background script records PID and start time, avoiding an unrelated reused PID. It does not forcibly terminate in-flight calls. Console foreground use ends with Ctrl+C.

## Watch actions and creations

In another terminal run:

```powershell
.\.venv\Scripts\resident observe --live --port 8766
```

Open http://127.0.0.1:8766. The page refreshes every 15 seconds. Each card distinguishes mode, direction, status, public summary and tool results; expand evidence and click artifact links. Previews are UTF-8 text, never executable HTML. A healthy heartbeat means the loop is active, not that it is producing useful work.

`GET /api/status` returns local cycles, budget and heartbeat. `GET /api/cycle?id=N` shows full recorded events for one cycle. These read-only endpoints are loopback-only and reveal local model data; do not expose the server publicly.

Live workspace: `workspace/live/`. Local journals: `.resident/live/journal/`. Background logs: the paths in `.resident/live/service.json`. Follow the named stderr log:

```powershell
$service = Get-Content .resident/live/service.json -Raw | ConvertFrom-Json
Get-Content -LiteralPath $service.stderr -Wait
```

State parent `--home .resident` plus `--live` and exact `--home .resident/live` select the same resident. Before the repair, exact mode directories incorrectly appended another mode; old nested STOP markers did not control the real live loop. Those obsolete nested files are retained, not used. Verify the actual state path before assuming a process was stopped.

## Spending

Default durable cap: $0.50. Maximum reservation per request: $0.068480. Three cycles × two steps permit at most six requests, conservatively $0.410880 if every request hits its bound, subject to existing usage/holds. Actual requests generally reserve less because input bodies are smaller. There are zero automatic provider retries and zero fallback requests.

Usage settlement is conservative accounting at $0.000002 per token, not a provider invoice. Missing/ambiguous usage retains a hold. Do not release an unresolved hold without independent provider evidence. Changing a CLI cap cannot raise the stored cap; creating a new state to evade it is not a supported budget-management procedure. This ledger is separate from Descend's previous experiments.

## Enable isolated Python creation

```powershell
docker pull python:3.11-slim
$image = (docker image inspect python:3.11-slim --format '{{.Id}}').Trim()
# Pass the inspected immutable ID explicitly:
.\.venv\Scripts\resident run --live --mneme --cycles 1 --execution-image $image
```

The model sees run_python only when an image is supplied. One source file, UTF-8, standard library, up to 16,000 characters; no writable host mounts or network. Files created inside the worker disappear. The model can save stdout to its workspace in a later action. Docker Desktop must be using Linux containers. The image is never pulled by the model.

Test the actual boundary:

```powershell
$env:RESIDENT_TEST_IMAGE = $image
.\.venv\Scripts\python -m pytest -q -ra
.\.venv\Scripts\ruff check agent scripts tests
```

Without the explicit test image, the two physical Docker tests report skips; protocol tests still run. CI runs a separate physical job, with no API keys/calls.

## Recovery and troubleshooting

- No new cycles: check STOP, PAUSE, heartbeat, runner logs and available budget.
- Duplicate-run refusal: inspect the existing process/state; do not delete its lock or start alternate state to duplicate spending.
- Mneme outage/authentication failure: cycle memory remains local and outbox error records only an exception type; correct configuration, then sync. No other user's records are retrieved.
- Provider failure: retain raw public response/error and reservation. Later cycles are new attempts, never automatic SDK retries. Inspect unresolved holds before increasing workloads.
- Malformed decision or incomplete output: failed cycle stays visible; no silent JSON/Python repair.
- Tool error: inspect tool result and policy/schema. Host shell is unavailable. Changing controller permissions based on a model request is not an implemented operation.
- Crash: OS lock releases; prior running cycles become interrupted. Tool-start events with no result indicate uncertainty, not permission to replay.
- Backup: stop cleanly, copy the complete private state directory and workspace; keep matching resident ID and memory keys. Do not publish SQLite, journals, logs, .env or generated work without privacy/provenance review.

## Release procedure

Run protocol and physical tests, lint, dependency check and installed-wheel smoke. Review staged files for sensitive content and generated state; update build evidence and open gaps. Commit/push only source/docs/tests/locks and explicitly reviewed public evidence. Live activity does not edit source or Git history.
