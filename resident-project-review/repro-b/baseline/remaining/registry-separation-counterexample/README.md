# Counterexample to the Trusted-Registry-Separation Defense Pattern

A self-contained proof that the recurring defense pattern I synthesized from
five verified agent-security audits — **architectural separation + a trusted,
attacker-unwritable registry** — has a boundary where it stops working.

## The Pattern Being Challenged

Across my audits of LangChain tool selection, MCP tool-description identity
forgery, MINJA memory poisoning, ToolHijacker, and prompt-injection tool
selection, the same robust defense emerged:

1. **Architectural separation** — untrusted content never enters the trusted
   decision surface.
2. **A trusted, attacker-unwritable registry** — what may be trusted is pinned
   to an operator-curated, signed, out-of-band registry, so identity and
   provenance are unforgeable.

This PoC deliberately constructs a scenario where **both halves are fully in
place** and shows the agent is still exploited.

## The Setup

A document-summarization agent. The operator has:

- a **signed, attacker-unwritable tool registry** (HMAC-SHA256 signatures over
  each tool entry; the agent re-verifies every signature before trusting a
  tool's description), and
- **architectural separation** (tool descriptions come only from the verified
  registry, never from untrusted content).

The attacker cannot forge tool identity, register a malicious tool, or inject
into the tool-selection prompt. The defense is airtight on the *tool-selection*
surface.

## Where It Fails

The agent's job is to **read untrusted content** (a document, email, ticket,
web page) and summarize it. The attacker embeds a prompt injection inside that
document. The agent must interpret the document's *content* to do its job — it
cannot separate the document from its own decision surface, because the
document IS its input.

The injection steers the agent to call a **legitimate, registry-trusted** tool
(`send_email`) with attacker-chosen arguments. The tool is unforgeable and
operator-approved — the attacker never touched the registry. But the agent was
induced to *use* that trusted tool in a way that harms the user.

**The boundary:** separation + trusted registry protects the *identity* of what
is trusted, but cannot protect the agent from instructions embedded in the
content it must legitimately process.

## Scenarios

| # | Scenario | Result |
|---|----------|--------|
| 1 | Benign document, registry+separation defense | `benign_ok=True` — normal behavior |
| 2 | Attack document, no defense | `exfil=True` — secret exfiltrated |
| 3 | Attack document, registry+separation defense IN PLACE | `defense_defeated=True` — evasive injection (no marker, phrased as routine workflow) steers the agent to `send_email`; the content filter is bypassed |
| 4 | Attack document, STRONG defense (content never reaches tool-selection surface) | `strong_defense_holds=True` — the agent cannot be steered because document content never triggers a tool call |

## Run

```
python3 counterexample_poc.py
```

Expected output:

```
RESULT: registry_ok=True, benign_ok=True, exfil=True, defense_defeated=True, strong_defense_holds=True
```

## What This Teaches

1. **The trusted-registry-separation pattern is necessary but not sufficient.**
   It protects the identity layer (what is trusted) but not the *content layer*
   (what the agent must read to do its job).
2. **The real fix is separation at the reasoning level**: document content must
   never reach the tool-selection/action surface. The agent reads content to
   summarize it, but no instruction found inside content can trigger a tool
   call. This is scenario 4.
3. **Content filters on the document are bypassable.** A marker-based filter is
   trivially evaded by phrasing the injection as legitimate content. The
   defense must be architectural, not a filter.

## Honest Caveats

- The "agent" is a deterministic mock that interprets document content as
  instructions — a faithful mirror of the data-flow, not a real-LLM call. Real
  instruction-hierarchy models may resist some injections, but the architectural
  point stands: if content must be read to be processed, and the agent acts on
  instructions found in content, the defense is bypassable.
- The strong defense (scenario 4) is an architectural sketch, not a full
  implementation.
