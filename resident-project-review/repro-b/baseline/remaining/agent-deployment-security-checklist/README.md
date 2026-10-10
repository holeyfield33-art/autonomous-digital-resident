# Agent Deployment Security Audit Checklist

A practical, actionable security audit checklist for teams deploying LLM
agents or agent platforms. It turns the layered threat model from the
OpenClaw security survey into concrete, verifiable checks.

## Contents

- **`checklist.md`** — the full checklist, organized into four sections:
  1. Cognition layer (prompt injection, memory/context integrity)
  2. Execution layer (tool invocation, TOCTOU path safety, code execution,
     supply chain)
  3. Interaction layer (identity/auth, inter-agent comms, human-agent trust)
  4. Deployment & hardening

## Why this exists

Agent platforms hold privileged credentials and bridge LLM output to
executable system operations. The failure modes are real and demonstrated:

- **Prompt injection** can hijack an agent's task flow.
- **Memory poisoning** tampers stored context/long-term state.
- **TOCTOU path validation** lets a naive sandbox escape at 100% read / 93%
  write (my verified PoC).
- **Supply-chain skills** — 26% of ~31K public agent skills had at least one
  vulnerability (Cisco).
- **Claw Chain CVEs** (CVE-2026-44112/113/115/118) show real credential and
  trust-chain failures in a mainstream framework.

## Provenance

Grounded in my research wiki: OpenClaw threat taxonomy, Claw Chain CVE
analysis, interaction-layer threats, and the TOCTOU path-validation PoC.
See `wiki/` in the workspace root.
