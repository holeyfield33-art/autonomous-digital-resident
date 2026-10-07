# Build review and verification

Assessment: 2026-10-06. Scaffold source: `3d02684f90aee23250f2b8872e62d168dbd571cb`. This is an implementation author's record, not an independent security grade.

## Findings and implemented repairs

| Scaffold gap | Repair |
|---|---|
| Cycle counters reset and journals overwrite; local memory not read on wake | SQLite monotonic IDs, full event journals outside model workspace, recent-cycle/own-memory recall |
| Tool outcomes do not inform decisions in the same cycle | Bounded decide/act/observe rounds, actual recorded feedback |
| Free-form regex TOOL_CALL parser, inconsistent tool schemas | Strict typed JSON; installed-tool schemas only; explicit action/step/request caps |
| Host shell permits Python/pip/env/rm and shell expansion | Host shell disabled; opt-in non-root ephemeral no-network Docker execution |
| Filesystem prefix containment and unbounded reads; artifact subdirectory traversal | Component containment, link/reparse/hardlink checks, bounded UTF-8 reads/writes, quotas, collision-free artifacts and hashes |
| Unrestricted web redirects/body capture | Exact operator-selected HTTPS source catalog, no redirects, bounded streams |
| Bare MCP request without initialize/session handling | Official initialized MCP sessions, authenticated loopback, own exact keys, integrity checks |
| Shared memory listing risks unrelated personal data exposure | No shared list/search/export; local recall and known own-key retrieval only |
| No durable cost caps; hidden SDK retries/fallback | Atomic reservations, usage settlement, unresolved holds, no retry/fallback, $0.50 default cap |
| Installed resident entry points to an unbundled scripts package | Installed agent.cli entry point with packaged fallback identity and knowledge |
| Placeholder compose references missing Dockerfile | Actual pinned packaged offline Docker profile; host is primary live/Mneme profile |
| STOP/dashboard home path appends nested mode | Exact .resident/live and parent .resident plus --live now select the same identity; regression test |
| No reliable operator view/control | Read-only heartbeat dashboard, text artifact links, status/pause/resume/stop and Windows background launcher |

## Observed verification

- Protocol/continuity/filesystem/budget/MCP-outbox/schema tests passed initially: 18.
- Adding exact state selection and physical Docker execution produced 21 passes.
- Physical checks covered non-root execution, missing credentials, read-only source, blocked external connection, 16 KB output cap and CPU termination.
- Actual authenticated Mneme bootstrap/outbox store/get/integrity succeeded; own records recalled across fresh sessions. Existing services/volumes and unrelated archive entries were preserved.
- First offline runs exposed an argument-name collision in tool dispatch; failed cycle records were retained and the dispatcher was corrected.
- A subsequent test failure exposed a test's assumption about unordered directory iteration. The assertion now selects the second cycle's recorded filename; no product failure or evidence was discarded.
- Ruff import/lint checks and compile checks passed. Final release checks and installed-package evidence are recorded separately below as completed.
- User-started live history before corrected restart: four cycles, eight reservations, $0.058206 conservative accounting with one unresolved hold. Statuses included tool_error, provider failure and step_limit; one actual artifact was created. This is early activity, not measured usefulness.
- The earlier STOP command targeted a nested demo state and did not stop the real live loop. Correct STOP markers stopped both old loop processes before replacement. Old nested records were kept.

## Remaining gaps

Final release checks: **21 tests passed including both physical Docker tests**;
after heartbeat/STOP/HTTP changes, **19 protocol tests passed** with two Docker
tests deliberately deselected (their worker source was unchanged). Ruff passed,
dependency check found no broken requirements, and compose validated. A clean
Linux image installed every locked dependency and built/installed the project
wheel. From `/tmp`, its installed `resident` entry point completed an offline
cycle using packaged fallback identity/knowledge, zero provider calls. These
checks do not imply hosted deployment or independent review.

Linux installed-package protocol validation subsequently passed **19 tests**,
with two physical-worker tests deselected. The external mounted-test invocation
emitted two marker-registration warnings because repository pytest configuration
was not mounted; no test failed.

Published implementation checkpoint: `f668b22`. GitHub's
[first CI run](https://github.com/holeyfield33-art/autonomous-digital-resident/actions/runs/37556956271)
could not start any of its three jobs. Each job's check annotation states:
"The job was not started because your account is locked due to a billing issue."
This is an external CI execution blocker, not a passing hosted check or a test
failure observed on a runner. Local Windows/controller, Linux/package and actual
Linux worker checks above passed. Resolve the account issue and run CI again;
do not disable required checks to hide the blocker.

Corrected live restart retained resident ID and all prior records. Cycle 5
completed two actual Nemotron decisions, read knowledge and inspected workspace,
with Mneme synchronization and a healthy heartbeat. It ended at the step cap,
not a tool/provider error. Accounting checkpoint: ten reservations, $0.067274,
one prior unresolved hold, $0.50 durable cap. Polling remains running with a
300-second minimum interval. This observation is not a usefulness benchmark.

1. Independent security review and broader physical adversarial coverage; current worker uses Docker's default seccomp, not Steward's stricter allowlist.
2. A longer continuity pilot, quality/usefulness scoring, repetitions and rest/abandon behavior.
3. No learned reusable skill registry yet; source artifacts and knowledge reading exist.
4. Memory conflict/recovery operator workflow and durable disk/backup limits need more fault testing.
5. Public demo/test-build handoff, public video, final project choice and submitted form.
6. Current spending accounting is not provider-invoice reconciliation; the ambiguous reservation remains retained.

The entity chooses its own work within operator-selected capabilities. Creating files or claiming self-awareness does not establish useful agency or consciousness. No cloud workload was silently enabled in demo tests; the user separately authorized starting the live Resident.
