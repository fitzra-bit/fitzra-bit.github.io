# Backlog — closing the gap between the OptiFlow design and the code

The OptiFlow deck (`dtx_facilitator/optiflow_segment/OptiFlow_DTX.pptx`) is
aspirational: it describes the system the project is aiming at, not the one
currently built. This is that gap, turned into work.

Ordered by dependency and by how much each item unlocks. Sizes are rough:
**S** ≈ a session, **M** ≈ a few, **L** ≈ a project.

---

## Already true — do not rebuild

Checked against the code, because a backlog that lists finished work is worse
than no backlog:

| Deck claim | Where it lives |
|---|---|
| Action masking, invalid actions excluded before argmax | `factory_sim/rl/environment.py:106` `action_mask()`, `simulation/line.py:76` `all_valid_actions` |
| In-flight investments (already committed, affect the baseline) | `factory_chat/plant/loader.py:95` `apply_in_flight()`, `in_flight_investments` in the plant YAML |
| Scenario library — save, load, list, compare, delete | `factory_chat/tools/scenario_manager.py` |
| Three competing optimisers | `factory_sim/rl/agents/` |
| Plant model as source of truth, separate from scenarios | `factory_chat/plant/` + scenario layer |
| LLM orchestrates tools, engine computes | `factory_chat/tools/definitions.py` — 10 tools |

---

## Tier 0 — align the deck (before DTX)

**0.1 Relabel slide 1 as an architecture proposal. (S)**
One line: *"architecture proposal; the working prototype implements the
deterministic core."* Cheapest possible fix and it makes the rest of this
backlog a feature rather than a discrepancy. Slides 5, 6, 11, 15 and 18 carry
the forward-looking claims.

---

## Tier 1 — the substantive gaps

### 1.1 OEE decomposition (M)

**Now:** each step has `capacity` and `yield_rate`. Throughput is
`min(capacity)`, effective yield is the product of step yields.

**Target:** Availability × Performance × Quality, per the deck's central framing.
Rated capacity × availability × performance gives effective throughput; quality
is the yield term.

**Why first:** it is the vocabulary plant people actually use, it is the deck's
organising idea, and it changes the plant schema — so everything downstream
should be built on the new shape rather than migrated to it later.

**Breaks:** the plant YAML schema, agent observation vectors, saved scenarios.
Version the YAML (`schema: 2`) and write a migration, or accept a clean break
and regenerate the demo scenarios.

**Done when:** a step declares availability, performance and quality; the line
reports OEE per step and overall; the existing widget scenario reproduces its
current economics under the new model (or the difference is explained).

### 1.2 Stochastic demand and trial-based evaluation (M)

**Now:** one deterministic evaluation per configuration. `--trials` exists on
the random agent only, and means "random restarts", not "sampled demand".

**Target:** demand as a distribution; evaluate a configuration over N trials;
report mean and a confidence interval rather than a point.

**Why it matters beyond the deck:** it fixes something real. The DQN's
run-to-run spread is currently invisible — three repeats at the $180K budget
gave $1.74M, $1.70M, $1.74M, and a single-shot evaluation cannot tell you that.
Any comparison between agents is currently one sample deep.

**Done when:** `--trials N` applies to all agents; output is mean ± CI; a
convergence table (N = 100/500/1000) is reproducible and shows where variance
falls below a stated threshold.

### 1.3 Supplier lead times (S–M)

**Now:** an upgrade's benefit applies the moment it is bought. No time.

**Target:** `lead_time_weeks` per upgrade; benefit begins on arrival; the
objective becomes value over a horizon rather than at a snapshot.

**Why this is the most interesting item in the backlog:** it is the first change
that makes sequencing genuinely hard. Right now greedy ROI ties the DQN at full
budget because there is no reason to defer anything. Add lead times and "buy the
16-week machine first, the 6-week one second" becomes a real decision that a
myopic agent gets wrong. **This is the item most likely to make the RL layer
earn its place** — and if it does not, that is worth knowing too.

**Done when:** upgrades declare a lead time; profit is integrated over a
horizon; a scenario exists where greedy provably underperforms a planner.

---

## Tier 2 — structural

### 2.1 Parallel lines and cascading bottlenecks (L)

**Now:** one serial line. `bottleneck = min(capacity)` over its steps.

**Target:** multiple lines feeding shared downstream steps, as on deck slide 6.
Relieving one line's bottleneck can starve or flood a shared step — the
"obvious fix exposes what was hidden" story.

**Depends on:** 1.1, so shared steps carry OEE.

**Done when:** two lines feed a shared finishing step; bottleneck analysis
identifies the cascade; the demo scenario from the deck is reproducible.

### 2.2 Discrete event simulation — decide before building (L)

The deck says SimPy. **Challenge this one before committing to it.**

DES earns its place when you need queues, buffers, blocking and starvation,
variable processing times, and shift patterns. If the model does not represent
those, SimPy adds machinery and runtime without adding insight — the closed-form
calculation is exact for a bottleneck-and-yield model and runs in microseconds.

**Recommendation:** build 1.1–1.3 and 2.1 first, then ask what question you
cannot currently answer. If the answer involves buffers or queue dynamics, do it.
If it is still "what is the throughput of this configuration", do not.

**If you do it:** keep the closed-form path as the fast screen and use DES for
final evaluation — the same train-fast / verify-slow structure as `dino_rl`.

---

## Tier 3 — interface and trust

### 3.1 `build_plant_model` tool (M)

**Now:** ten tools, none of which construct a plant. `plant/default_plant.yaml`
is hand-authored. The deck's Appendix C schema does not exist.

**Target:** describe a line in conversation, get validated YAML back, with
clarifying questions when underspecified. This is what makes slide 8's "no setup
required" true.

**Depends on:** 1.1 — do not build a generator against a schema you are about
to change.

**Done when:** a plausible spoken description produces a plant that loads and
runs; missing fields are asked about, not invented.

### 3.2 Validation harness (M)

**Now:** nothing automated. The deck (slide 11, Appendix A) claims synthetic
benchmarks with known optima, convergence testing and bottleneck identification
tests.

**Target:** exactly that, runnable.

**Why it belongs here rather than earlier:** it is what makes every claim above
checkable, and it is the direct analogue of `dino_rl`'s gate battery — the
instrument that stops you fooling yourself.

**Done when:** a suite of plants whose optimal investment sequence is derivable
by hand; agents scored against ground truth; a regression run that fails loudly
when the engine changes behaviour.

---

## Suggested order

```
0.1 relabel deck            ──► before DTX
1.1 OEE  ──►  1.2 trials  ──►  1.3 lead times  ──►  2.1 parallel lines
                   │                  │
                   └──────────────────┴──►  3.2 validation harness
1.1 ──► 3.1 build_plant_model
2.2 DES — revisit after 2.1, do not start blind
```

If only one thing gets done: **1.3, supplier lead times.** It is the smallest
change that turns this from a problem three different methods solve identically
into one where sequencing actually matters — which is the premise the whole
optimisation layer rests on.
