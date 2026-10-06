# Nebius × NVIDIA Global AI Hackathon

**Track:** Personal AI

## Alignment with the Personal AI Track

The track calls for always-on private AI with:

- persistent memory
- reusable skills
- chosen tool / information access
- ability to carry out tasks across workflows

The Autonomous Digital Resident goes further: it does not wait for a human task queue. It wakes with identity + memory + tools + knowledge and **chooses** what is worth doing next. This matches the organizers’ stated preference for systems that “remember context across sessions and take real action” rather than a chatbot with a system prompt.

## Hard technical requirements (satisfied by design)

1. **Runs on Nebius Token Factory or Nebius AI Cloud**  
   The application makes runtime calls to the Nebius Token Factory OpenAI-compatible inference API.

2. **Uses at least one NVIDIA open-source model**  
   At least one Nemotron family model participates meaningfully in the decision / reasoning / generation loop (primary or fallback).

### Current model candidates (Token Factory)

| Model ID | Notes |
|----------|-------|
| `nvidia/Nemotron-3_5-Lightning` | Fast, low-cost MoE — excellent for always-on agent loops |
| `nvidia/nemotron-3-super-120b-a12b` | Strong multi-agent / complex reasoning |
| `nvidia/Nemotron-3-Ultra-550b-a55b` | Flagship when deep reasoning is required |
| `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Compact alternative |

Default primary: `nvidia/Nemotron-3_5-Lightning` (cost/latency friendly for continuous cycles).

### API usage pattern

```python
from openai import OpenAI
client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",  # or regional
    api_key=os.environ["NEBIUS_API_KEY"],
)
response = client.chat.completions.create(
    model="nvidia/Nemotron-3_5-Lightning",
    messages=[...],
)
```

Nebius / NVIDIA usage is therefore **evident from the running architecture**, not bolted on at submission time.

## Submission checklist (preserved while building)

- [ ] Working demo / test build
- [ ] Public GitHub repository (this one)
- [ ] Source + instructions to run
- [ ] Open-source license (Apache-2.0)
- [ ] README with setup & run instructions
- [ ] Clear explanation of how Nebius and the NVIDIA model are used (this document + README)
- [ ] Public demonstration video < 3 minutes
- [ ] Identification of chosen track: **Personal AI**
- [ ] Feedback about the Nebius / NVIDIA technologies used

## Judging dimensions

Projects are scored equally on:

1. Technological Implementation
2. Design
3. Potential Impact
4. Quality of the Idea

The strongest Personal AI entries go beyond chatbots toward systems that remember across sessions and take real action. That is the explicit design goal of this experiment.
