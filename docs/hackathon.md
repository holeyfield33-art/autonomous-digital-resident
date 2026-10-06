# Nebius × NVIDIA Global AI Hackathon

**Chosen track:** Personal AI  
**Repository:** [holeyfield33-art/autonomous-digital-resident](https://github.com/holeyfield33-art/autonomous-digital-resident)  
**License:** Apache-2.0

---

## Why this fits the Personal AI Track

The track asks for always-on private AI with:

- persistent memory  
- reusable skills / tools  
- chosen tool and information access  
- work that continues across workflows and sessions  

Organizers emphasize systems that **remember across sessions and take real action**, not chatbots with a system prompt.

The Autonomous Digital Resident is built exactly on that axis:

| Track expectation | How this project meets it |
|-------------------|---------------------------|
| Always-on / continuous | Cyclic loop with configurable interval; no human prompt required per cycle |
| Persistent memory | Aletheia Mneme (semantic + integrity) + local journal |
| Tools & information access | Filesystem, shell, web, artifacts — chosen by the model each cycle |
| Cross-session continuity | Identity (`SOUL.md`) + Mneme survive process restarts |
| Real action | Structured tool execution that writes durable workspace artifacts |

It deliberately goes **beyond** “assistant with memory”: there is no external task queue. The entity wakes, observes, and decides.

---

## Hard technical requirements

### 1. Runs on Nebius Token Factory or Nebius AI Cloud

**Satisfied:** every decision step issues a runtime inference call to the Nebius Token Factory OpenAI-compatible API.

```python
# agent/models/nebius.py (simplified)
client = OpenAI(
    base_url=os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"),
    api_key=os.environ["NEBIUS_API_KEY"],
)
response = client.chat.completions.create(
    model="nvidia/Nemotron-3_5-Lightning",  # or configured primary
    messages=[...],
)
```

The entire app does not need to be hosted on Nebius compute as long as Token Factory is part of the running system — which it is on the critical path.

### 2. Uses at least one NVIDIA open-source model

**Satisfied:** primary and fallback models are NVIDIA Nemotron family IDs served by Token Factory.

| Role | Default model ID |
|------|------------------|
| Primary | `nvidia/Nemotron-3_5-Lightning` |
| Fallback | `nvidia/nemotron-3-super-120b-a12b` |

Other available Nemotron endpoints (e.g. Ultra, Nano) can be selected via `PRIMARY_MODEL` / `FALLBACK_MODEL` without code changes.

Nebius / NVIDIA usage is therefore **visible in the running architecture** (`agent/models/nebius.py` + every cycle log), not added as branding at submission time.

---

## Technologies mentioned by organizers (context)

Examples such as NVIDIA NemoClaw, OpenShell, Hermes Agent, and Nebius Serverless are **options**, not mandatory combinations. This project prioritizes:

- Token Factory inference (required path)  
- Nemotron open models (required path)  
- A real memory layer (Aletheia Mneme)  
- A minimal, inspectable autonomous loop  

Additional Nebius AI Cloud deployment (Serverless Jobs / Endpoints / DevPods) can be layered later if a hosted demo is needed; it is not required for eligibility given Token Factory runtime use.

---

## Submission checklist

| Requirement | Status |
|-------------|--------|
| Working demo / test build | Runnable via `scripts/run_resident.py` (needs keys + Mneme) |
| Public GitHub / GitLab / Bitbucket repo | This repository |
| Source, assets, run instructions | README + docs |
| Open-source license | Apache-2.0 |
| README with setup and run instructions | Yes |
| Clear explanation of Nebius + NVIDIA use | This doc + README |
| Public demo video < 3 minutes | TODO before submission |
| Identify track | **Personal AI** |
| Feedback on Nebius/NVIDIA technologies | TODO at submission |

---

## Judging dimensions (equal weight)

1. **Technological Implementation** — Token Factory + Nemotron on the decision path; Mneme memory; tool execution; durable workspace  
2. **Design** — Identity-first loop; observe → decide → act → remember; constrained tools; inspectable journals  
3. **Potential Impact** — Template for always-on personal agents that own continuity instead of waiting for prompts  
4. **Quality of the Idea** — Agency without a task queue; “what does it choose to build?” as the research question  

---

## Suggested demo narrative (< 3 min)

1. Show `SOUL.md` and empty-ish workspace  
2. Start Mneme + set env keys  
3. `python scripts/bootstrap.py` then `MAX_CYCLES=1 python scripts/run_resident.py`  
4. Show console decision, `workspace/journal/cycle_00001.md`, any new artifact/project  
5. Query Mneme for the stored experience / identity  
6. Point at `agent/models/nebius.py` model IDs and Token Factory base URL  

---

## Feedback placeholders (fill at submission)

- Token Factory latency / reliability for continuous agent loops: _TBD_  
- Nemotron-3.5-Lightning suitability for tool-oriented autonomous cycles: _TBD_  
- Gaps or wishes for agent-oriented APIs (native tool calling, longer sessions): _TBD_  
