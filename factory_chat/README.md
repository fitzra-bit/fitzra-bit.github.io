# OptiFlow — Manufacturing Process Optimization Chat

A conversational interface over the [`factory_sim`](../factory_sim) engine. You
talk to it like a plant analyst — "where's my bottleneck?", "what if we add a
second CNC machine?", "compare that to the yield-first plan" — and it runs the
simulator, builds scenarios, and renders the economics inline.

```bash
cd factory_chat
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # required
python app.py                        # opens http://localhost:8000
```

Model is configurable via `OPTIFLOW_MODEL` (default `claude-sonnet-4-6`).
The plant model is configurable via `OPTIFLOW_PLANT`, so you can point at a
different facility without editing the shipped file:

```bash
OPTIFLOW_PLANT=/path/to/my_plant.yaml python app.py
```

## The core idea: separate "what is" from "what if"

OptiFlow keeps two things deliberately apart:

- **The plant model** (`plant/default_plant.yaml`) is the *source of truth* for
  physical reality: each step's capacity, yield, and OPEX, plus an upgrade
  catalog with real vendor quotes and dates. It reflects what exists. Edit it to
  match your actual facility.
- **Scenarios** capture *hypotheticals*: market assumptions (unit value, budget)
  and a set of candidate investment decisions, optionally with some marked
  **in-flight** (already committed). You never edit reality to explore a
  what-if — you branch a named scenario.

This split is what makes the conversation auditable: every number traces back to
either the plant model or an explicit scenario assumption.

## What the assistant can do (tools)

| Tool | Purpose |
|---|---|
| `load_plant` | Load the plant model — capacities, yields, OPEX, upgrade catalog |
| `run_baseline` | Compute current throughput, bottleneck, yield, economics |
| `run_optimizer` | Run an agent (greedy / random / DQN) to find an investment plan |
| `compare_agents` | Run all agents head-to-head on the same plant/budget |
| `build_custom_scenario` | Construct a scenario from a specified set of upgrades |
| `create_scenario` | Start a named scenario from the plant model |
| `save_current_as_scenario` | Persist the working scenario with a name + rationale |
| `list_scenarios` / `load_saved_scenario` | Browse and reopen saved scenarios |
| `compare_scenarios` | Side-by-side economics of two or more saved scenarios |

Scenarios persist to `saved_scenarios/*.json` (gitignored) and are also exposed
over REST: `GET /scenarios`, `GET /scenarios/{id}`, `DELETE /scenarios/{id}`.

## Architecture

```
factory_chat/
├── app.py                     # FastAPI app: chat stream, sessions, scenario REST
├── requirements.txt
├── plant/
│   ├── default_plant.yaml     # SOURCE OF TRUTH: steps, yields, OPEX, upgrade quotes
│   └── loader.py              # YAML → plant model
├── prompts/
│   └── system.py              # system prompt: plant awareness, scenario triggers
├── tools/
│   ├── definitions.py         # Anthropic tool schemas
│   ├── executor.py            # tool handlers + inline HTML renderers
│   └── scenario_manager.py    # scenario persistence + comparison
├── static/
│   ├── index.html             # chat UI + Scenarios tab
│   ├── app.js                 # chat stream, scenario cards, compare bar
│   ├── configurator.js        # plant/scenario configurator
│   └── style.css
└── saved_scenarios/           # persisted scenarios (gitignored)
```

The simulator math (bottleneck, yield chain, ROI, the three optimization
agents) lives in [`factory_sim`](../factory_sim); OptiFlow imports it and adds
the plant-model/scenario layer plus the chat and rendering.

## Example conversation

> **You:** What's my current bottleneck?
> **OptiFlow:** *(runs baseline)* CNC Machining at 120 units/hr — it caps the
> whole line. Effective yield is 87% after the scrap chain…
>
> **You:** If I had $350k, what's the best plan?
> **OptiFlow:** *(runs optimizer + compares agents)* The greedy plan adds a
> second CNC machine first; the DQN fixes CNC yield first (tooling + SPC), then
> adds capacity — same CAPEX, but it doesn't run a high-scrap process faster.
> Want me to save the yield-first plan as a scenario?
