# Segment — making the model usable by the person who knows the plant

**Facilitator material. Runs after the factory segment, ~20 minutes.**

The factory segment ends on an uncomfortable note. Three agents produced a list
of ten purchases worth $1.8M a period. Now imagine handing that list to a plant
manager.

*Why the CMM before the second furnace? What happens if the tooling quote comes
in 20% higher? We already committed to the night shift — does that change
anything?*

You cannot answer any of those from a ranked list, and "the neural network said
so" is not an answer anyone should accept about capital. **A model nobody can
interrogate does not get used.** That is the gap this segment closes, and it is
usually the real reason good analytics dies on the shelf.

---

## What OptiFlow is

The same `factory_sim` engine, behind a conversation. You talk to it like an
analyst — *"where's my bottleneck?"*, *"what if we add a second CNC machine?"*,
*"compare that against the yield-first plan"* — and it runs the simulator and
shows the economics.

```bash
cd factory_chat
export ANTHROPIC_API_KEY=...
export OPTIFLOW_PLANT=../dtx_facilitator/optiflow_segment/plant/dtx_plant.yaml
python app.py                        # opens http://localhost:8000
```

---

## The two ideas worth teaching

Both of these transfer far beyond this app, and both are the kind of thing a
room of new hires will meet within a year.

### 1. The model orchestrates. The simulator computes.

This is the most important slide of the whole session for a GE audience.

The language model does not calculate throughput, yield or payback. It cannot —
and if it tried, it would produce confident numbers that were quietly wrong.
What it does is decide *which tool to call*: `run_baseline`, `run_optimizer`,
`build_custom_scenario`, `compare_agents`. Every number on screen came out of
the same deterministic engine the RL agents used.

That division is what makes the output defensible. When someone asks "where did
$2.8M come from?", the answer is a simulator run with a named scenario, not a
model's recollection. **The natural language is the interface, not the
arithmetic.**

If you take one thing from this segment into your own work: when you put an LLM
near an engineering decision, give it tools and let the tools do the maths.

### 2. Separate "what is" from "what if"

`plant/dtx_plant.yaml` is the **source of truth** — the capacity, yield and cost
of each step as they actually are, plus the upgrade catalogue. It describes
reality.

**Scenarios** are hypotheticals: a budget, market assumptions, a set of proposed
decisions, some possibly marked as already committed. You never edit reality to
explore a what-if. You branch a named scenario.

This sounds like housekeeping and is actually the thing that makes the
conversation auditable. Every number traces to a named scenario over a versioned
plant model. Anyone who has watched a spreadsheet get "just tweaked" during a
review until nobody knows what it represents will recognise the failure this
prevents.

---

## Demo script

Roughly ten minutes, live. Rehearse it once with a real key — the model chooses
its own tool calls, so the phrasing below is a starting point rather than a
script that will reproduce word for word.

1. **"What does this line look like right now? Where's my bottleneck?"**
   Grounds everyone in the same picture the factory segment opened with: CNC
   machining, 80 u/h, 91% yield.

2. **"What if we bought a second CNC machine?"**
   It builds the scenario and runs it. Point out that the answer is a simulator
   result, not a guess.

3. **"Compare that against spending the same money on machining yield instead."**
   This is the question the whole morning was building toward, now asked in a
   sentence rather than written as code.

4. **"Save that as 'yield-first' and compare it to the capacity plan."**
   Shows the what-is / what-if split doing real work.

5. **"Run all three optimizers on this and tell me where they disagree."**
   Ties directly back to the previous segment, and lands better having already
   seen that they mostly agree.

**Have a fallback.** It is a live model against a live API. If the room is
large or the network is unreliable, screenshot steps 1–3 beforehand. Nothing
undermines "the model orchestrates, the tools compute" quite like a timeout.

---

## Where this goes next — worth saying out loud

The honest limitation: everything here still rests on a *model of* a plant. The
capacities are estimates and the upgrade quotes are assumptions.

But notice what changed. In the factory segment, the output was a list of
purchases — brittle, because it inherits every modelling error. Here, the output
is a conversation that a person who knows the line can push back on. They can
say *"that yield delta is optimistic, the vendor always overstates"*, change it,
and see what survives.

**That is what makes a model usable in an operating business: not that it is
right, but that the person who knows where it is wrong can interrogate it.**

Which is also the thread running through the whole day. The dinosaur taught them
that a model trained in simulation behaves differently in reality. The factory
taught them that the simple baseline is often enough and sophistication has to
earn its place. This one says: whatever you build, the person who has to live
with the decision needs to be able to argue with it.

---

## The deck — `OptiFlow_DTX.pptx`

De-branded copy of the original 18-slide deck. Changes were confined to slides
1, 6, 10 and 12:

| Was | Now |
|---|---|
| "P&G AI Technical Interview" byline | "GE Digital Technology Experience" |
| Line A — Liquid Detergent · Supplier: Rosler | Line A — Component Machining · Machine tool vendor |
| Line B — Personal Care · Supplier: Haas / ATC | Line B — Subassembly · Automation vendor |
| "Haas Q1 Discount", "Haas offering 18% discount" | "Supplier Q1 Discount", "Machine tool vendor offering…" |
| Memphis Line 2 | Plant 2, Line 2 |

Verified afterwards that none of P&G, Procter, Interview, Detergent, Personal
Care, Rosler, Haas, ATC or Memphis appears in any slide text. Document metadata
was already clean (authored by PptxGenJS) and no speaker notes carried branding.
The file opens cleanly and all 18 slides are intact.

### Read this before you present it

**The deck describes a more capable system than the repository contains.** That
was fine for an interview, where a deck can carry a design proposal. It is a
problem here, because DTX participants will have the code in front of them.

It is also accurate about more than I first credited. Action masking, in-flight
investments, the scenario library, the three competing optimisers and the
LLM-orchestrates-tools split are all really there. The forward-looking claims are
narrower than "the deck oversells":

| The deck says | The code does |
|---|---|
| "Built on SimPy — Python discrete event simulation" | No SimPy anywhere. Plain arithmetic. |
| OEE: Availability × Performance × Quality | No OEE. `capacity` and `yield_rate` only. |
| "Stochastic demand with configurable…" | Nothing stochastic. One deterministic evaluation. |
| "N=500 trials, variance below 0.5%" | There are no trials to run. |
| "Cascading bottlenecks across parallel lines" | A single serial line; `bottleneck = min(capacity)`. |
| Supplier lead times driving sequencing | No lead-time field in the model. |
| "N=500 trials: ~1.2s on M2 Pro" | Not applicable. |

I checked by searching for each term across `factory_sim/` and `factory_chat/`:
zero hits for simpy, OEE, availability, demand, stochastic and lead_time.

This matters more than usual for this session specifically, because the whole
dino arc is about measurement discipline and not fooling yourself with a metric.
Presenting capability claims the visible code does not support undercuts the
thing you spent the morning teaching, and a sharp new hire may well notice.

Three honest ways to handle it, in order of effort:

1. **Relabel the deck as a design proposal.** Add a line to slide 1 —
   "architecture proposal; the working prototype implements the deterministic
   core" — and say it once out loud. Cheapest, and it turns the gap into a
   useful point about the distance between a design and a shipped increment.
2. **Cut or annotate the over-claiming slides.** Slides 5, 6, 11, 15 and 18
   carry most of it. A shorter deck that matches the code needs no caveats.
3. **Build the missing pieces.** Real work, and not before this session — see
   `BACKLOG.md` at the repo root, which sequences it.

My recommendation is (1) — the gap between "what we designed" and "what we
built so far" is itself a good thing for new hires to see named openly, and it
costs you one sentence.

---

## Practical notes

**API key.** `ANTHROPIC_API_KEY` must be set, or the app exits with a clear
message. Sort out which account and key you are using before the day — this is
the one part of the session that needs live network access to an external
service, and it is worth confirming it works from the GE network specifically.

**Model.** `OPTIFLOW_MODEL` overrides the default.

**The plant model here is a training copy.** The shipped
`factory_chat/plant/default_plant.yaml` names real suppliers — Haas,
Kennametal, Hexagon, Ipsen, Wexxar — against invented price quotes and quote
dates. That is fine as a personal project and not something to project in a GE
training room, so `plant/dtx_plant.yaml` replaces them with equipment classes
("Machine tool supplier", "Metrology supplier"). **Every number is identical** —
verified by loading both and comparing throughput, effective yield, revenue,
OPEX, gross profit, the bottleneck, and all eleven upgrades' capex, capacity
delta, yield delta, opex delta and max applications. Only labels differ, so the
economics and the lesson are unchanged.

Use it via `OPTIFLOW_PLANT` rather than overwriting the original.

**What I could not verify.** The app starts, serves the UI, and loads this plant
correctly — checked. An actual conversation needs a real API key, so the demo
script above is unrehearsed. Run through it once yourself before presenting.
