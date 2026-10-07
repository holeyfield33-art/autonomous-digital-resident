# Hackathon readiness and project choice

Candidate: Autonomous Digital Resident, Personal AI track. Other candidate: Repo Steward / Descend, Coding and Agentic Engineering track. Final submission choice is not yet made.

Official rules: https://nebiusglobalaihackathon.devpost.com/rules. Deadline verified October 30, 2026, 10:00 a.m. PDT. Runtime Token Factory inference qualifies; hosting every component on Nebius is unnecessary. Registration/eligibility/form submission remain human/account steps and are not inferred from code.

## Actual technology use

Live Resident decisions use NVIDIA `nvidia/nemotron-3-super-120b-a12b` on Nebius Token Factory. Those decisions choose directions and structured actions; controller tools produce the artifacts. The offline demo uses a canned model and cannot establish required-technology use by itself. Real user-started live cycles are recorded locally.

Mneme stores own identity/cycle records on local PostgreSQL. The verified local profile uses keyword fallback, not external semantic embeddings. Docker executes optional generated Python with no host writes/network. No automatic model fallback or made-up scaffold model ID remains.

## How to choose between projects

| Criterion | Digital Resident | Repo Steward |
|---|---|---|
| Central story | Continuity and self-chosen work without an assigned task queue | Review a repository change and turn suspected defects into evidence/patches |
| Current evidence | Durable demo/restart tests, real Mneme integration, real Docker probes and early live cycles | Frozen 105-call Super/Nano evaluation, original corpus, attack evidence and offline verified patches |
| Main unresolved quality question | Does continued autonomous activity produce useful work rather than repetitive notes? | Do reviews generalize, abstain reliably and produce a verified live patch? |
| Main engineering risk | Operational autonomy, memory freshness and bounded execution need an independent review | Narrow act scope and incomplete live review-to-act product integration |
| Recommended track | Personal AI | Coding and Agentic Engineering |

Recommendation: complete a small observed Resident run and score actual artifacts before selecting. Prefer the Resident if it demonstrates useful self-chosen work continued across a process restart, with real actions and a clear interface. Prefer Steward if Resident activity stays repetitive and Steward's live verification/user workflow is stronger. Novelty alone is insufficient; measured product behavior should decide.

Keep both evidence histories separate. No parameter-size explanation, consciousness claim or broad autonomous-capability claim follows from these runs.

## Selection trial

Use the existing durable $0.50 Resident cap, not a new uncapped session. Record the identity, model/protocol version, available knowledge/tools and starting accounting. No human artifact assignment.

Observe several cycles, stop at a cycle boundary, restart the same identity, and observe continuation. Retain every failed cycle, unresolved request, direction change, tool result and artifact hash. Independently inspect artifacts for usefulness and correctness. Report supported scope, elapsed time, duplicate/repetitive work and spend. This is a pilot, not a controlled general capability benchmark. Longer operation or a new paid workload needs a concrete estimate under the chosen budget.

## Deliverables still open

- Judge-accessible working demo/test-build URL, checked from a fresh environment.
- Public YouTube video under three minutes showing actual decisions, tool outcomes, artifacts and restart continuity.
- Independent security review of controller, filesystem, Docker, MCP and observation surfaces.
- A longer observed continuity trial and independently reviewed artifact quality.
- Final track, description, registration/eligibility checks and submitted form/receipt.
- Feedback grounded in actual Nebius/NVIDIA behavior and a dated prior-work disclosure.

The public repo, Apache-2.0 license, pinned installation, run manual and CI definitions are present. CI results must be observed after push, not assumed from the workflow file.

Current CI blocker: GitHub reports that its jobs cannot start because the account
is locked due to a billing issue. Local checks pass; hosted CI is not green.
See the exact run and local verification evidence in [BUILD_REPORT.md](BUILD_REPORT.md).

## Three-minute demo outline

1. Explain the experiment and show identity/tool scope (20 seconds).
2. Show a real live model choosing a direction without an assigned artifact task (40 seconds).
3. Show actual tool results, created file and optional Docker output (60 seconds).
4. Restart the same state and show remembered work/continuation (35 seconds).
5. Show budget/error visibility and honest limits (20 seconds).

## Platform feedback notes

The official chat-completion pattern is simple to integrate. Strict JSON still needs controller validation; truncation/usage and ambiguous requests require explicit handling. Disable SDK retries and automatic fallback when accounting must be traceable. Separate model-produced pseudo-error text from transport failures. The initial scaffold used an unverified model identifier and MCP approximation; the working implementation uses an official documented model and initialized transport.

Record further feedback from the Resident's actual run rather than transferring Steward's model scores to this project.
