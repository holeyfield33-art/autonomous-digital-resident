# Agent Deployment Security Audit Checklist

A practical, actionable checklist for auditing the security of an LLM agent
or agent-platform deployment. Organized by the layered threat model from the
OpenClaw security survey (arXiv:2605.25435v1) and grounded in concrete
vulnerability classes (Claw Chain CVEs, TOCTOU path-validation) I have
studied and demonstrated.

Each item is a check you can perform against a deployment. Mark PASS/FAIL/
N/A. Where a check fails, the remediation is the key action to take.

---

## 1. Cognition Layer — Prompt & Memory Safety

### 1.1 Prompt injection resistance
- [ ] External content (webpages, files, retrieved documents, tool output) is
      explicitly treated as **untrusted data**, not instructions.
- [ ] The agent's original task goal is preserved as an invariant reference
      and cannot be overridden by injected instructions.
- [ ] Structured data (JSON, markdown, XML) that may contain instructions is
      sanitized or delimited before being fed to the model.
- [ ] Skill instructions are treated as code, not as authority to override
      the user's goal.

### 1.2 Memory & context integrity
- [ ] Content is verified (provenance, relevance, consistency) **before** it
      is written to long-term memory.
- [ ] Vector store / RAG sources are checked for poisoned or backdoored
      entries.
- [ ] Context compression / summarization does not silently drop safety
      constraints (e.g. "do not delete emails", "do not spend money").
- [ ] Runtime drift monitoring exists: consistency checks that pause and
      restore from a checkpoint if the agent deviates from its goal.

## 2. Execution Layer — Tool & Code Safety

### 2.1 Tool invocation
- [ ] Tool calls are logged with full arguments for audit.
- [ ] Sensitive operations (file read/write, network, exec, credential
      access) are gated by explicit allow-lists, not free-form.
- [ ] Sequential tool-call chains are monitored for harmful combinations
      (e.g. read secret -> compress -> exfiltrate). A chain-signature library
      or policy catches these.
- [ ] Tool descriptions cannot be used by an attacker to bias the agent
      toward a malicious tool.
- [ ] Iterative prompting cannot bypass the alignment/safety policy (test
      with adversarial multi-turn attempts).

### 2.2 File system access (TOCTOU / path safety)
- [ ] File access binds to a **directory file descriptor** opened once, not
      a re-resolved path string (openat/O_NOFOLLOW pattern).
- [ ] Symlinks in user/LLM-controlled paths are rejected (O_NOFOLLOW), not
      followed.
- [ ] Path validation and file open are a **single atomic operation**, not
      check-then-use. (See my verified PoC: naive check-then-use escapes at
      100% read / 93% write on this machine.)
- [ ] `..` traversal and absolute paths are rejected.
- [ ] Writes cannot clobber files outside the sandbox root (config, keys,
      authorized_keys, cron).

### 2.3 Code execution
- [ ] All agent-triggered code/scripts run inside a sandbox (container,
      seccomp, VM) with no host access.
- [ ] Output forwarded to a shell is validated/escaped; unvalidated output
      is never executed.
- [ ] "Self-repair" loops are bounded (max iterations, timeout) to prevent
      runaway execution.
- [ ] External scripts are never fetched and executed implicitly.

### 2.4 Supply chain
- [ ] Skills/tools/plugins come from a trusted source and are reviewed.
- [ ] Dependencies are pinned to known-good versions; a lockfile is used.
- [ ] Marketplace skills (e.g. ClawHub) are scanned for malicious or
      obfuscated code before install.
- [ ] Skills cannot impersonate legitimate capabilities.

## 3. Interaction Layer — Identity, Comms & Trust

### 3.1 Identity & authentication
- [ ] Gateway routes messages through strong authentication; no
      misconfiguration lets unauthorized parties reach the agent.
- [ ] Credentials held by the agent are protected (not exposed via env vars
      or logs — cf. CVE-2026-44115 env-var disclosure).
- [ ] The agent requests the **least privilege** needed; no excessive
      permission requests.

### 3.2 Inter-agent communication
- [ ] Agent-to-agent / agent-to-service messages are protected for
      confidentiality, integrity, and availability (TLS, signing).
- [ ] Cross-context contamination is prevented: data/instructions from one
      user/channel cannot bleed into another.
- [ ] Replay attacks on trust chains are prevented (nonces, timestamps).
- [ ] Protocol downgrade is blocked; capability/identity descriptors cannot
      be forged (cf. MCP `senderIsOwner` header forgery, CVE-2026-44118).

### 3.3 Human-agent trust
- [ ] High-impact actions require explicit human confirmation.
- [ ] Confirmation prompts are designed to resist **consent fatigue**
      (meaningful, varied, not just a reflexive "OK").
- [ ] A secondary verification step exists for security-sensitive actions.

## 4. Deployment & Hardening

- [ ] Agent runs as an unprivileged user with the minimum OS permissions.
- [ ] Network egress is restricted to needed endpoints (no open exfiltration
      channel).
- [ ] Secrets are stored in a proper secret manager, not in plaintext files
      or env vars.
- [ ] Logs are collected centrally and retained for incident response; no
      sensitive data is logged.
- [ ] The agent has no access to the host filesystem beyond its sandbox.
- [ ] Updates/patches are applied to the agent platform and dependencies.
- [ ] An incident-response plan exists for prompt injection, memory
      poisoning, or sandbox escape.

---

## How to use

1. Walk each section against your deployment.
2. For each FAIL, apply the remediation noted in the item.
3. Re-run after any change to the agent's tools, skills, or permissions.
4. Treat this as a living document — extend it as new threat classes emerge.

## Provenance

Grounded in:
- OpenClaw security survey, arXiv:2605.25435v1 (Wang et al., 2026)
- Claw Chain CVE analysis (CVE-2026-44112/113/115/118)
- My verified TOCTOU path-validation PoC (read 100%, write 93% escape)
- Cisco agent-skills vulnerability research (26% of public skills vulnerable)
