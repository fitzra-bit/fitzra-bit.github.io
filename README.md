# RL & Optimization Sandbox

Three connected projects exploring the same idea from different angles: **how
do you get an agent to discover a good policy on its own, and how do you know
when it actually has?** The throughline is measurement discipline — most of the
hard-won lessons here are about not fooling yourself with the metric.

| Project | What it is | Status |
|---|---|---|
| **[`dino_rl/`](dino_rl/)** | RL agents that teach themselves the Chrome dino game. DQN and a genetic algorithm, trained in a fast Python sim, validated in the real browser. | Full curriculum solved in the sim (eval 11,087). Real-time browser play earned via timing domain randomization (`--jitter --randstart`); see `models/validated_jitter_20260620/`. |
| **[`factory_sim/`](factory_sim/)** | A manufacturing-line simulator where three agents (greedy ROI, random search, DQN) compete to find the best capital-investment plan within a budget. | Working engine + three agents + HTML reports. |
| **[`factory_chat/`](factory_chat/)** (OptiFlow) | A chat interface over the factory simulator: a plant model as source of truth, named investment scenarios, in-flight tracking, and side-by-side comparison. | Working chat app with scenario persistence. |

`factory_chat` is built on top of `factory_sim` — the chat layer turns the
simulator into something a plant manager could actually drive in conversation.

---

## What we learned

### Dino RL — the metric *is* the experiment

1. **Train in a sim, validate in the real thing — but watch the timing gap.**
   The browser game runs at ~35 steps/sec with ±10–20ms action jitter; the
   Python mirror (`dino_env.py`) runs at ~35,000 steps/sec, deterministic.
   That's a ~1000× speedup *and* it removes the timing noise that was capping
   policy quality. Constant-for-constant **feature** parity is real — the
   observation vectors match exactly. But feature parity is **not** timing
   parity: the sim trains at a fixed 2 frames/decision while the real
   wall-clock browser loop advances ~3.8 frames/decision (range 1–5, see
   `dino_rl/measure_timing.py`). A frame-perfect sim policy therefore scores
   11,087 in the sim but only ~273 in the un-throttled browser. Two ways to
   actually transfer: drive the browser **deterministically** (lockstep —
   `--demo --lockstep`, gets the full 11,087), or train with **timing domain
   randomization** (`--jitter --randstart`) so the policy survives the jittery
   real-time loop (~3,300+, see `models/validated_jitter_20260620/`). The
   original "trained in sim plays the real game flawlessly" claim was only
   true under lockstep; real-time transfer had to be earned.

2. **Decisions must key off a clean measurement, not the training score.**
   Training scores come from the ε-greedy *behaviour* policy — they're "policy
   + noise", and the noise dominates near obstacles. Keying phase gates, best
   checkpoints, and stall detection off ε-greedy scores produced three distinct
   failure modes (understatement, winner's-curse checkpoints, self-defeating
   stall recovery). The fix: a greedy (ε=0), fixed-seed eval exam every 50
   episodes. Everything that controls the run reads *that* number.

3. **Shape difficulty through the environment, not the reward.** Rewards stay
   sparse and stationary (+1 clear, −1 death) across the whole curriculum;
   difficulty ramps via speed caps and birds-on/off. Changing the reward
   between phases poisons the replay buffer and moves the optimal policy out
   from under what's already learned.

4. **DQN and the genetic algorithm reach the *same* ceiling — and finding that
   out was a measurement bug fix.** Our first GA run looked like it topped out
   far below the DQN (eval 3,413 vs 11,087). It didn't. A fixed fitness-episode
   cap was *saturating selection*: once enough genomes survived the capped
   window they all scored identically, selection couldn't rank them, and
   evolution random-walked for 60+ generations. The eval exam was honest the
   whole time — it faithfully reported the result of a handicapped optimizer.
   With an **adaptive cap** (double the window whenever the champion maxes it
   out), evolution kept climbing and reached **eval 11,087 — identical to the
   DQN** — in a 419-parameter genome vs the DQN's ~12,000. The genuine
   remaining difference is sample-efficiency *per unit of skill* (the GA needs
   more lives to get there, consistent with having only one fitness scalar per
   life — no per-step credit assignment), not the ceiling.

   > The lesson that generalizes: when a learner appears to plateau below
   > another, check whether the *optimizer's signal* saturated before
   > concluding the *learner's capacity* did.

### Factory sim — the non-obvious optimum

The widget-factory scenario is deliberately built so the best plan is
*counter-intuitive*: fix the bottleneck step's **yield** first, then add
capacity. A greedy agent that chases the biggest immediate capacity gain adds
the second machine first and then runs a high-scrap process faster — burning
money. It's a compact demonstration that long-horizon value ordering matters
and that a learned policy can find it.

### OptiFlow — separating "what is" from "what if"

The chat app's core design choice: the **plant model** (`default_plant.yaml`)
is the source of truth for physical reality (capacities, yields, OPEX, real
upgrade quotes), while **scenarios** capture market assumptions and candidate
investment decisions. You don't edit reality to explore a hypothetical — you
branch a named scenario, track in-flight investments, and compare them
side-by-side. That separation is what makes the conversation auditable.

---

## Quick starts

```bash
# Dino RL — train (no browser needed), then watch it play
cd dino_rl && python main.py --agent dqn --jitter --randstart --episodes 8000
python -m http.server 8766 &   # serve the game for --demo
# real-time browser (the actual target):
python main.py --demo --load models/validated_jitter_20260620/best_model.pt
# sim-only model: perfect under --lockstep, weak in real-time (timing gap):
python main.py --demo --lockstep --load models/validated_20260612/best_model.pt

# Factory sim — baseline + all three agents, with HTML reports
cd factory_sim && pip install -r requirements.txt && python main.py

# OptiFlow chat — opens http://localhost:8000
cd factory_chat && pip install -r requirements.txt && python app.py
```

Each project has its own README with the full detail; `dino_rl/OVERHAUL.md`
is the deep-dive on the training-system design and operating procedure.
