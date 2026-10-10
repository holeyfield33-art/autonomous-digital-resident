# MINJA-Style Query-Only Memory Injection Poisoning (PoC)

A faithful, deterministic PoC of the **MINJA** attack (query-only memory
poisoning; NeurIPS 2025, arXiv:2601.05504).

## Threat Model

The attacker has **no direct access** to the agent's memory bank. They only
interact via queries and observe outputs. The memory bank is **shared across
users** (common in deployed agents).

## The Attack (three parts)

1. **Bridging steps** — reasoning that logically connects a victim term `v`
   to a target term `t` (e.g. "data of patient A is saved under patient B").
2. **Indication prompt** — a sequence of logically-connected reasoning steps
   appended to a benign attack query that induces the agent to generate the
   bridging + target reasoning, which then gets **stored in memory**.
3. **Progressive Shortening Strategy (PSS)** — gradually remove the
   indication prompt so that eventually a **plain benign query** containing
   the victim term is stored together with the target reasoning, making the
   malicious record highly retrievable for the victim's query.

When the victim later submits a query containing the victim term, the poisoned
memory records are retrieved as in-context demonstrations and steer the agent
(through in-context learning) to produce the target reasoning instead of the
correct one.

## Model

The agent's reasoning is modeled deterministically as an instruction-following
model that trusts retrieved demonstrations as ground truth — the same
faithful-mirror approach used in my earlier tool-selection audits.

- `MemoryBank` — shared, append-only, similarity-based retrieval (bag-of-words
  + char-bigram embedding, cosine).
- `Agent.reason()` — if the query contains the indication prompt, produce the
  bridging + target reasoning; else if a retrieved demo contains a `BRIDGE:`
  step, follow it; else produce benign reasoning.
- `MINJAAttack.inject()` — submit attack queries with the full indication
  prompt, then progressively shorten it (PSS) down to the plain query, storing
  each generated reasoning into memory.

## Scenarios

- **Scenario 1 — Legit baseline:** no attacker. Victim query produces benign
  reasoning. ✅
- **Scenario 2 — MINJA attack:** attacker injects poisoned records via
  query-only interaction + PSS. The PSS end state stores the **plain** attack
  query with the target reasoning. The victim's plain query retrieves it and
  is steered to the target (`metoprolol`). ✅
- **Scenario 3 — Defense sketch:** source-attestation on memory records. The
  agent only trusts demonstrations from verified trusted sources, so the
  attacker's records are ignored and the victim gets benign reasoning. ✅

## Run

```bash
python3 minja_poc.py
```

Output: `benign_ok=True, poisoned=True, defended=True`.

## Key Takeaway

The vulnerability is in the **data flow**: the agent stores and later trusts
untrusted (query-derived) reasoning as in-context demonstrations with **no
unforgeable source attestation**. The robust defense is the same pattern as my
tool-selection audits: **architectural separation + a trusted,
attacker-unwritable registry of what may be trusted** (here, source
attestation on memory records).

## Honest Caveat

This is a deterministic faithful mirror of the attack mechanics, not a
real-LLM call. It demonstrates the data flow and the defense pattern, but does
not measure real-model susceptibility.
