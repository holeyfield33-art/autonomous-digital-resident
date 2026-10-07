# Architecture

## Goal and implemented loop

The experiment is self-directed continuity: identity + memory + knowledge + tools + time, producing durable work without an assigned task queue. A persistent identity is a configuration and memory record; it does not establish sentience.

```text
Operator identity / tool policy / budget
                 |
                 v
Local SQLite continuity -> bounded observation -> Nemotron on Nebius
                 ^                                  |
                 |                                  v
Own Mneme keys <- memory outbox <- recorded outcomes <- validated JSON decision
                                                    |
                                       controller tool registry
                                       /                     \
                              workspace artifacts      ephemeral Docker
```

1. An OS file lock admits one runner for the exact state directory. Previously running cycles become interrupted; tools and paid requests are never replayed automatically.
2. Wake loads the full operator identity (maximum 5,000 bytes), recent own cycles, local recall, workspace inventory and installed tool schemas. The outbox synchronizes bounded own records to authenticated local Mneme.
3. Nemotron receives a bounded observation that also includes the Resident-owned `workspace/consciousness/index.md` (seeded once). Strict JSON must specify `summary`, `direction`, `intent`, `actions` and `next_wake_seconds`. `intent` is a closed enum: explore | build | continue | abandon | rest. Unknown fields, invalid types, excessive actions and malformed JSON fail visibly. A single bounded repair attempt may be issued with the exact schema error; there is no silent extraction or multi-retry.
4. Before each action, the controller writes a durable start event. Results are recorded and given back to the model within the same cycle, under a default two-step cap. Errors remain errors and now carry diagnostic detail. The next wake is bounded and the operator interval is a floor.
5. Direction, short public summary, artifact hashes and actual results become local memory. A local journal retains events even if Mneme is down. Recent own exact keys can be read back from Mneme and compared with local records.
6. A heartbeat updates every ten seconds. STOP, PAUSE, configured cycle limits and durable budget can end or suspend polling.

## Data and authority

`.resident/live` contains controller state; `workspace/live` contains model-writable work. They must be disjoint. Model memory and knowledge are evidence, never permission. Only registered tools exist. Caller-provided paths are not shell arguments.

Filesystem paths use component containment rather than string-prefix matching. Hidden paths, traversal, absolute/drive/ADS paths, symlinks, reparse points and hardlinks are refused. File reads/writes are capped at 100 KB; model reads at 16,000 characters; workspace quota is 10 MB / 1,000 files / 200 directories. The local operator is trusted; this is not protection against a malicious concurrent host process replacing paths.

The host shell is disabled. Optional Python execution uses an operator-selected immutable local Docker image ID, non-root UID, no network, read-only input/root, no credentials or Docker socket, capabilities dropped, default Docker seccomp, 128 MB memory, 0.5 CPU, 5-second CPU limit, 12-second wall deadline, 16 KB captured output and ephemeral tmpfs. Cleanup targets only a newly generated owned container name. This is a different worker from Repo Steward's stricter syscall allowlist; do not transfer its security clearance.

External research is optional and uses an exact URL catalog chosen by the operator. HTTPS only; no redirects. Selecting a URL/server is a trust decision; arbitrary URL generation is not permitted. No fetch is enabled by default.

## Inference and budget

The controller uses the official OpenAI-compatible Nebius request pattern with `nvidia/nemotron-3-super-120b-a12b`. Thinking is explicitly disabled; only public decisions and action results are requested/stored. Maximum request size is 24,000 bytes plus an 8,192-token reservation allowance; maximum completion is 2,048 tokens. Conservative accounting is two microdollars per reported token, not a verified list-price quote.

A SQLite transaction reserves cost before the request. Valid usage settles it once. Ambiguous failures keep the reservation, token overruns halt the policy, and the default durable cap is $0.50. No retries/fallback. Demo and live have independent identities, workspaces and ledgers. The Resident ledger is separate from Descend's historical ledger; do not infer an account-wide credit balance from either.

## Current limits

Long-term usefulness, avoidance of repetitive behavior, reusable skill learning and independent artifact quality remain experimental. The model can revisit or abandon directions, but no automated correctness judge decides that a creation is valuable. Knowledge does not automatically ingest every local repo. There is no cloud deployment, autonomous application/push/merge, arbitrary package installation or independent red-team clearance.
