# Architecture

## Goal and implemented loop

The experiment is self-directed continuity: identity + memory + knowledge + tools + time, producing durable work without an assigned task queue. A persistent identity is a configuration and memory record; it does not establish sentience. The Resident is given a capable body and environment; what it does with them is left to it.

```text
                    SOUL.md
                       |
                       v
                 +-----------+
                 | RESIDENT  |  Nemotron on Nebius, schema-constrained decisions
                 +-----+-----+
                       |
       +---------------+----------------+
       v               v                v
     MNEME        SELF KNOWLEDGE       TOOLS
  agent-resident  consciousness/     files / web / sandbox /
   namespace         wiki            memory / introspection
       +---------------+----------------+
                       v
                   WORKSPACE  <-- bind-mounted into the sandbox at /workspace
                       |
                durable artifacts

             CONTROLLER underneath (host)
    time - provenance - budget - logs - health
      wake limits - recovery - evidence
```

1. An OS file lock admits one runner for the exact state directory. Previously running cycles become `interrupted`; tools and paid requests are never replayed automatically.
2. **Wake.** The controller syncs the memory outbox, snapshots the workspace, and builds the observation:
   - **Controller facts:** UTC time, cycle number, seconds since the previous wake, how that wake ended (status, files changed, last tool results), budget remaining, wake limits, which capabilities exist and which do not, memory-service status, recent tool errors and a workspace summary. These are authoritative, so the Resident never has to infer timestamps or rediscover its environment.
   - **History:** recent cycle summaries.
   - **Self-knowledge:** the Resident-owned `consciousness/index.md`.
3. **Decide.** The system prompt carries the identity, reply format and full tool descriptions. The provider decodes against a JSON schema: `intent` is a closed enum and action names are an enum of installed tools. The raw output is always recorded. If parsing still fails, only deterministic fixes are applied (fence stripping, control characters, trailing commas, intent normalization), each listed in a `decision_normalized` event. If that fails too, one repair request is made with the full conversation. The repair exchange is kept out of the Resident's conversation and memory.
4. **Act.** Before each action the controller writes a durable `tool_started` event, then the exact `tool_result`. Failures return the exception type, message and correct usage, so a failure is an observation and not the end of the wake. Results go back to the model, which keeps the whole conversation for the wake. Older results are compacted only past about 90 KB. A wake ends when the Resident replies with no actions, or at the step, tool-call or wall-clock limit (defaults 12 / 60 / 1200 s; the live run uses 8 steps).
5. **Remember.** The controller writes a per-cycle memory: direction, summary, every step summary, every action with its outcome, and the files added, modified or deleted with hashes. It goes to SQLite (with an FTS5 index), the local journal and the Mneme outbox. The Resident does not need to keep logs for the controller's sake.
6. A heartbeat updates every ten seconds. STOP, PAUSE, cycle limits and the durable budget can end or suspend polling.

## Data and authority

`.resident/live` contains controller state; `workspace/live` contains model-writable work. They must be disjoint. Model memory, web pages and knowledge are evidence, never permission. Only registered tools exist. Common wrong tool and argument names are mapped to installed tools, and the substitution is noted in the result.

Host-side file tools use component containment rather than string-prefix matching. Hidden paths, traversal, absolute/drive/ADS paths, symlinks, reparse points and hardlinks are refused. Reads are capped at 1 MB per file and 40,000 characters per call (line ranges supported). The workspace quota is 500 MB / 20,000 files / 5,000 directories. Credential-looking text is refused in writes and masked in results.

**Sandbox.** With `--sandbox`, `shell` and `python` run inside a persistent container (`resident-sandbox`, `sandbox/Dockerfile`):
- The workspace is bind-mounted at `/workspace`.
- It has outbound internet, pip/apt/git/node, 2 GB RAM, 2 CPUs and 512 processes.
- It never sees controller state, `.env`, credentials or the Docker socket.
- It runs as root inside the container with default Docker isolation. This is a capability boundary, not a hardened one: data in the workspace can leave over the network.

Without `--sandbox`, an operator-selected immutable image can still provide the older offline single-file Python runner.

**Web.** `web_search` uses Tavily or Brave when keyed, otherwise DuckDuckGo HTML. `web_fetch` reads any public http(s) URL as text. Loopback, private and link-local addresses are refused, re-checked at every redirect, so the local Mneme service and the LAN are unreachable through these tools. DNS rebinding between check and connect is not defended.

**Memory.** The Resident authenticates to Mneme with its own key in the `agent-resident` namespace, isolated from the operator's personal namespace. See [mneme.md](mneme.md).

## Inference and budget

The controller uses the OpenAI-compatible Nebius API with `nvidia/nemotron-3-super-120b-a12b`. Thinking is disabled; only public decisions and action results are requested and stored. The maximum request is 400,000 bytes and the maximum completion 8,192 tokens. Request events record size and the newest message; the full system prompt is stored once per wake. Conservative accounting is two microdollars per reported token, not a verified list-price quote.

A SQLite transaction reserves cost before each request, and valid usage settles it once. Ambiguous failures keep the reservation and token overruns halt the policy. No retries or fallback model. Demo and live have independent identities, workspaces and ledgers.

## Current limits

Long-term usefulness, avoidance of repetitive behavior and independent artifact quality remain experimental. No automated judge decides whether a creation is valuable. Memory search is keyword-based (local FTS5; Mneme offline keyword mode); there is no semantic recall yet. Sandbox egress is unrestricted and not hardened against a determined escape. There is no autonomous push/merge or cloud deployment.
