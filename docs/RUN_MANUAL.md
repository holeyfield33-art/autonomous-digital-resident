# Resident engineering run manual

## Supported setup

Python 3.11+ on Windows or Linux. Use the repository's dedicated virtual environment. Install `requirements-lock.txt`, then `pip install --no-deps -e .`. The installed entry point is `agent.cli:main`; packaged identity and knowledge are available even outside the source checkout. MCP is pinned to 1.30.0, matching the local verified transport API.

`.env` uses literal allowlisted assignments, without variable interpolation. Existing process variables take precedence. Required for live: `NEBIUS_API_KEY`. Optional memory: `MNEME_MCP_URL` and `MNEME_API_KEY`, the Resident's own agent key (see [mneme.md](mneme.md)). Optional web search providers: `TAVILY_API_KEY` or `BRAVE_API_KEY` (otherwise DuckDuckGo HTML, keyless). Legacy offline execution: `RESIDENT_EXECUTION_IMAGE`. Unknown/incomplete assignments fail startup; no secret values are printed.

Run `resident doctor` for a no-cost runtime check. Use `resident demo` twice to verify increasing cycle IDs and durable artifacts. Canned choices are demo plumbing, never autonomy evidence.

## Live start and controls

From the repository:

```powershell
.\.venv\Scripts\resident status --live
.\.venv\Scripts\resident plan --live --cycles 3 --steps 8
.\.venv\Scripts\resident resume --live
.\.venv\Scripts\resident run --live --mneme --sandbox --cycles 0 --steps 8 --interval 900
```

`--cycles 0` means persistent polling, bounded by the ledger. Each wake runs up to `--steps` decisions (1..40) and stops early when the Resident replies with no actions, or at `--max-tool-calls` (60) or `--max-wake-seconds` (1200). Control commands (`status`, `stop`, `pause`, `resume`) keep the stored budget cap; pass `--budget-usd` only to raise it. The model may request a longer sleep; the operator interval is a floor. A cap exhaustion cycle stops the runner.

Windows background launch uses `scripts/local.ps1`:

```powershell
.\scripts\local.ps1 start -Sandbox -Steps 8 -Interval 900   # also: -BudgetUsd 15, -NoWeb
.\scripts\local.ps1 status
.\scripts\local.ps1 pause
.\scripts\local.ps1 resume
.\scripts\local.ps1 stop
```

A stopped process needs `start` again; `resume` only clears markers. The background script records PID and start time, avoiding an unrelated reused PID. It does not forcibly terminate in-flight calls. Console foreground use ends with Ctrl+C.

## Model selection (A/B)

The model, endpoint and per-token pricing are configurable so residents can run different
models against the same key. Defaults keep Nemotron. DeepSeek-V4-Flash needs schema-constrained
decoding off (it returns empty output under `json_schema`); it follows JSON instructions well via
parse+repair. Example:

```powershell
.\scripts\local.ps1 start -Name c -Soul souls\c.md -Sandbox `
  -Model deepseek-ai/DeepSeek-V4-Flash-0731 `
  -BaseUrl https://api.tokenfactory.us-central1.nebius.com/v1/ `
  -PriceIn 0.30 -PriceOut 1.20 -NoResponseSchema `
  -Steps 8 -Interval 900 -BudgetUsd 15
```

`-PriceIn`/`-PriceOut` are USD per million tokens and feed the durable ledger (numerically equal
to micro-USD per token). Each wake records its `model` in the request event for per-model analysis.

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

Default durable cap for new state: $0.50 (the live Resident's stored cap is $15; the CLI maximum is $100). Each request reserves `(request bytes + 8192 + 8192 output tokens) × $0.000002` before it is sent, and settles to reported usage afterwards. The request ceiling is 400,000 bytes. Within a wake the conversation grows with each step: a measured 12-step wake reached about 75 KB per request and settled at $0.34. Older results are compacted beyond about 90 KB. Cost scales roughly with steps × wakes per hour, so the interval is the main lever.

There are zero automatic provider retries. One repair request is made only when a decision fails to parse. Usage settlement is conservative accounting, not a provider invoice. Missing or ambiguous usage retains a hold; do not release an unresolved hold without independent provider evidence. Creating a new state directory to evade the cap is not a supported budget-management procedure.

## Sandbox (shell and python)

`--sandbox` gives the Resident a persistent Linux container named `resident-sandbox`, built from `sandbox/Dockerfile` on first use:

```powershell
.\.venv\Scripts\resident sandbox --live          # build/start and print status
docker exec -it resident-sandbox bash            # look around as the operator
docker rm -f resident-sandbox                    # reset: installed packages are lost, workspace is kept
```

- The workspace (`workspace/live`) is bind-mounted at `/workspace`, so files created by `shell`/`python` are the same files the file tools see.
- The container has outbound internet, pip, apt, git, node and common Python libraries. Limits: 2 GB RAM, 2 CPUs, 512 processes, per-command timeout up to 900 s.
- Controller state, `.env`, credentials and the Docker socket are never mounted. Add `--sandbox-offline` to run it with `--network none`.
- It runs as root inside the container with default Docker isolation. Anything in the workspace can leave over the network, so keep secrets out of the workspace.

Without `--sandbox`, an explicit `--execution-image sha256:...` still provides the older offline `python` tool (one workspace `.py` file, standard library, no network).

`pip install` and `npm install -g` go to a per-sandbox Docker volume (`<sandbox-name>-deps`, mounted at `/opt/deps`), so they survive `docker rm -f` and a rebuild. apt packages last only until the container is recreated. A container created before this change has no deps volume until it is recreated.

## Running a second resident

Each resident is a separate state directory, workspace, sandbox and budget. Residents can share `.env` (Nebius and Mneme keys): Mneme records are prefixed with each resident's own ID. `-Name b` maps to `.resident/b/live`, `workspace/b` and container `resident-sandbox-b`, and requires an explicit `-Soul`:

```powershell
.\scripts\local.ps1 start -Name b -Soul souls\b.md -Sandbox -Steps 8 -Interval 900 -BudgetUsd 15
.\scripts\local.ps1 status -Name b
.\scripts\local.ps1 observe -Name b -Port 8767
.\scripts\local.ps1 stop -Name b
```

Without `-Name` the script controls the original resident exactly as before. A sandbox refuses to use, or remove, a container whose `/workspace` mount belongs to another workspace. An explicit `--soul` path that does not exist stops startup instead of falling back to the packaged soul. Each sandbox is capped at 2 CPUs and 2 GB, so two residents can claim all 4 CPUs of the Docker VM when both are busy.

Tests: `.\.venv\Scripts\python -m pytest -q -ra`. Coverage (≥90% enforced by review): `.\.venv\Scripts\python -m pytest -q --cov=agent --cov-report=term-missing`. Network, Docker and MCP are mocked in the suite, so it runs offline with no spend. and `.\.venv\Scripts\ruff check agent scripts tests`. The two physical Docker tests for the legacy runner skip unless `RESIDENT_TEST_IMAGE` is set.

## Recovery and troubleshooting

- No new cycles: check STOP, PAUSE, heartbeat, runner logs and available budget.
- Duplicate-run refusal: inspect the existing process/state; do not delete its lock or start alternate state to duplicate spending.
- Mneme outage/authentication failure: cycle memory remains local and the outbox records only an exception type. `memory_sync` showing `degraded_local` / `ExceptionGroup` usually means a rejected key: rotate it with Mneme's `scripts/agent_key.py`, restart, then `resident sync --live --mneme`. No other namespace's records are ever retrieved.
- Provider failure: retain raw public response/error and reservation. Later cycles are new attempts, never automatic SDK retries. Inspect unresolved holds before increasing workloads.
- Malformed decision or incomplete output: decisions are decoded against a JSON schema by the provider. If one still fails to parse, the raw output is kept, deterministic fixes are recorded in `decision_normalized`, and one repair request is made with full context. If that also fails, the wake ends with status `protocol_error`.
- Tool error: the model receives the exception type, message and correct usage, and usually corrects itself in the next step. `tool_error` events and the facts block's `recent_tool_errors` show them. There is no host shell; `shell` runs only in the sandbox. Changing controller permissions based on a model request is not an implemented operation.
- Crash: OS lock releases; prior running cycles become interrupted. Tool-start events with no result indicate uncertainty, not permission to replay.
- Backup: stop cleanly, copy the complete private state directory and workspace; keep matching resident ID and memory keys. Do not publish SQLite, journals, logs, .env or generated work without privacy/provenance review.

## Release procedure

Run protocol and physical tests, lint, dependency check and installed-wheel smoke. Review staged files for sensitive content and generated state; update build evidence and open gaps. Commit/push only source/docs/tests/locks and explicitly reviewed public evidence. Live activity does not edit source or Git history.
