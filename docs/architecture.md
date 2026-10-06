# Architecture Overview

## Design Stance

Do not assume a particular architecture from the brief.  
The architecture is itself part of the experiment.

Goal: make the central experiment real — a persistent AI entity that can remember its own existence, access knowledge and tools, choose its own direction, and build real artifacts without waiting for a human to tell it what to build.

## High-level components

```text
┌──────────────────────────────────────────────────────────────────┐
│                     Autonomous Digital Resident                   │
│                                                                  │
│  ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌─────────┐ │
│  │  Identity  │   │   Memory   │   │   Models   │   │  Tools  │ │
│  │  SOUL.md   │◄──┤  Mneme +   │◄──┤  Nebius    │◄──┤ FS/Shell│ │
│  │  + self-   │   │  local     │   │  Nemotron  │   │ Web/Art │ │
│  │  model     │   │  journal   │   │  (+ local) │   │ ifacts  │ │
│  └─────┬──────┘   └─────┬──────┘   └─────┬──────┘   └────┬────┘ │
│        │                │                │               │      │
│        └────────────────┼────────────────┼───────────────┘      │
│                         ▼                ▼                      │
│                  ┌─────────────────────────────────┐            │
│                  │     Core Loop (wake → observe   │            │
│                  │     → decide → act → remember)  │            │
│                  └─────────────────────────────────┘            │
│                                  │                              │
│                                  ▼                              │
│                  ┌─────────────────────────────────┐            │
│                  │         Workspace               │            │
│                  │  projects / experiments /       │            │
│                  │  journal / artifacts            │            │
│                  └─────────────────────────────────┘            │
└──────────────────────────────────────────────────────────────────┘
```

## Core loop (conceptual)

1. **Wake** — Load SOUL.md, recent Mneme context, local journal, available tools & knowledge packs.
2. **Observe** — Inspect workspace state, unfinished threads, external resources, current capabilities.
3. **Decide** — Using a Nemotron model (via Nebius Token Factory), form a short coherent plan or single high-value next action. No external task queue is required.
4. **Act** — Execute via tools (filesystem, shell, web, artifact creation, Mneme writes, etc.).
5. **Remember** — Write experiences, decisions, outcomes, and open threads back to Mneme (and local journal).
6. **Sleep / schedule** — Persist state and wait for the next cycle (or continue immediately if still productive).

The loop is designed so that individual inference calls and process restarts do not erase identity or history.

## Memory strategy

- **Authoritative long-term store**: Aletheia Mneme (MCP + PostgreSQL + pgvector + Helios).
- **Local journal**: Fast, inspectable recent-cycle log for resilience and human debugging.
- Categories and relationships are first-class so the Resident can build a graph of its own ideas and projects.

## Model strategy

- Primary reasoning / decision / generation path goes through Nebius Token Factory.
- At least one NVIDIA Nemotron model is used meaningfully on every meaningful cycle.
- Optional local models can be used for cheap auxiliary tasks (classification, short summaries) if desired; they are not required for the hackathon compliance path.

## Tool system

Tools are registered and discoverable. The Resident can inspect what is available and choose which to use. The workspace is a real filesystem the Resident can read and write.

## Open research questions (intentionally left open)

- How should the decision policy evolve?
- Should the Resident be allowed to modify its own SOUL.md under constraints?
- How aggressive should self-scheduling be?
- What constitutes a “real artifact” worth keeping vs. experimental scaffolding?
- How to surface the Resident’s ongoing work to a human observer without turning it back into a chatbot?

These are to be discovered by running the experiment, not prescribed in advance.
