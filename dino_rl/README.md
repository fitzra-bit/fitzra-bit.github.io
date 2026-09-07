# Chrome Dino RL

Reinforcement learning agents that teach themselves to play the Chrome offline dinosaur game.

**Architecture:** training runs in a Python simulation (`game/dino_env.py`,
~35,000 steps/sec) that mirrors the browser game constant-for-constant; the
browser game (`game/dino.html`) is the eval/demo surface. Double/Dueling DQN
with n-step returns, sparse stationary rewards, and an environment-shaped
curriculum that advances, recovers from stalls, and checkpoints automatically.

> Full design rationale and operating procedure: **[OVERHAUL.md](OVERHAUL.md)**

## Quick start

Training and validation are two halves of one loop. **The sim buys throughput;
the real-time visible browser is the metric of record.** A checkpoint is not
worth anything until it survives the browser — that is why the promoted
directories are named `validated_*`.

### 1. Train — in the sim

```bash
cd dino_rl
python main.py --agent dqn --episodes 100000   # start curriculum training
python main.py --agent dqn --auto              # resume after ANY stop, nothing lost
```

No Chrome and no game server needed for this half. Watch progress at
**http://localhost:8765**. **Eval Avg** (greedy eval on fixed seeds) drives
phase gates and stall detection; **Deploy GATE %** — P(reach the windup gate,
score ≥2,500) — drives `best_model` selection (gate-lex). Median alone was
retired: it saturates at the frame cap and froze selection.

### 2. Validate — in the real-time visible browser

Everything in this half loads `http://localhost:8766/game/dino.html`
(`config.py: game_url`), so it needs the game served. Run this from `dino_rl/`
in its own shell and leave it up:

```bash
python -m http.server 8766
```

Then, cheap primary metric first — P(pass the windup gate) from the canonical
speed-6 start, ~30–40 min for 20 visible episodes:

```bash
python gate_battery.py --load runs/<run>/best_model.pt --episodes 20
```

Then the champion-crowning instrument — the deployment loop with no per-step
instrumentation, because that observer effect corrupted the earlier
measurements:

```bash
python clean_realtime.py --load runs/<run>/best_model.pt --episodes 10
```

`gate_battery.py` runs the *same protocol* in the sim (`--sim`) or the browser
(default) precisely so the fidelity gap can be measured rather than assumed —
only trust its sim mode for ranking once sim-vs-visible fidelity is validated at
the gate.

> **Running the commands.** These assume `python` resolves to the interpreter
> that has this project's dependencies. If you installed into a venv, invoke it
> explicitly — on Windows PowerShell a bare `python` may hit the Microsoft Store
> alias stub instead:
> ```
> .\.venv\Scripts\python.exe -m http.server 8766
> .\.venv\Scripts\python.exe main.py --agent dqn --auto
> ```
> All commands and all `--load` paths are relative to `dino_rl/`, not the repo root.

## Current champion & deployment timing (2026-07-18)

The metric that matters is **SCORE in the real-time, visible browser** — the
game as actually played. A long investigation (`EXPERIMENTS.md`,
`PROGRESS_REVIEW.md`) traced a persistent windup-band failure to the display's
refresh rate, not the agent: at 145 Hz the game sub-frame-integrates the jump
to a shorter arc than the sim used in training. The fix keeps the authentic
game and matches the sim to it — `DinoEnv` now models the true physics quantum
(`fe`), the measured decision clock (`cadence_samples`), and act latency.

The current champion adds two more measured levers: closing-velocity features
(E11 — the birds' hidden speed offset, unobservable in one snapshot) and a
**20ms decision clock** (E12 — the 50ms poll left only ~46px between decisions
at top speed; 20ms is both faster AND cleaner, and it roughly doubled the
recipe's endurance). Poll rate is part of the agent, not the game.

```bash
# Serve the game first, from dino_rl/, in a second shell:
#   python -m http.server 8766

# Watch the champion (28-feat, 20ms clock — --poll 0.02 REQUIRED: it reads its
# decision cadence and collapses on the 50ms default)
python main.py --demo --load models/validated_pollrate_20260710/best_model.pt --poll 0.02
```

The E8 reference artifact (`validated_capacity_20260707`, 26-feat) can no longer
be demoed — E11 widened the observation to 28 and it will not load. See
[Saved checkpoints](#saved-checkpoints--what-still-runs).

Score comparisons are only valid at a MATCHED step cap and, ideally,
interleaved in one session (EXPERIMENTS.md amendments 7–8; a cap-mismatched
comparison briefly mis-promoted E12 before the real, matched test did it
properly):

The 2026-07-19 day-matched, ceiling-matched (~35k) head-to-head settled it:

| Model | P(reach 35k) | median | mean/game | MSBD | notes |
|---|---|---|---|---|---|
| `validated_pollrate_20260710` (E12) — **champion** | 8/10 | 33,890 (censored) | **30,239** | 151k | requires `--poll 0.02`, `--layers 28,256,128` |
| `validated_capacity_20260707` (E8) | 5/10 | 26,794 | 23,453 | 47k | 50ms clock; confirmed 2026-07-20 interleaved rerun (E8 mean 27,026 vs E12 33,846) |
| `validated_timing_20260705` (E5, prior) | — | ≥22,070 @ old cap | — | — | 50ms clock |
| v2b (pre-timing-fix) | — | 21,704 | — | — | |

Judge a checkpoint: `python gate_battery.py --load <m> --episodes 20` (visible)
or add `--sim --fe 0.4138 --cadence-file measurements/cadence_visible_20260705.npy
--act-latency 0.25` for the calibrated fast screen. Endurance past the score
cap: `--until-deaths K` (mean-score-between-deaths, for near-perfect models).

## The game

`game/dino.html` is a faithful clone of the Chromium offline game, with the
original's physics constants and pacing:

| Aspect | Value (original) |
|---|---|
| Coordinate space | 600×150, ground at 140, dino ground-y 93 |
| Speed | 6 → 13, acceleration 0.001/frame |
| Jump | v₀ = −10 − speed/10, gravity 0.6/frame, ascent capped at max height |
| Fast-fall | duck mid-air = 3× descent (original speed-drop) |
| Obstacle gaps | `width·speed + minGap·0.6` … ×1.5, per original formula |
| Cactus groups | up to 3, gated by speed (small >4, large >7) |
| Birds | speed ≥ 8.5, three heights: low=jump, mid=duck, high=run under |
| Physics | dt-based, variable timestep — **NOT frame-rate independent**: on a 145 Hz display it sub-frame-integrates (`fe≈0.414`) to a shorter jump arc than the sim's `fe=1`. This was the "windup gate" root cause (see OVERHAUL.md); the sim now matches it via `DinoEnv(fe=…)`. |

**Curriculum control is via URL params, not file edits:**

```
dino.html?birds=0                 # Phase 1-3: cacti only
dino.html?birds=1                 # Phase 4: full game
dino.html?birds=1&birdmin=0      # birds immediately (testing)
dino.html?maxspeed=9&accel=0.0005 # gentler pacing (custom phases)
```

Playable by hand too: space/↑ = jump, ↓ = duck.

### Rendering (visual only — physics untouched)

The renderer had drifted from the simulation it draws. The T-Rex's three leg
sprites were allocated 14 rows and drawn in only 5–7 of them, so the dino ran
7–9 px **above** the ground line every cactus sits flush on; the ducking sprite
stopped 10 px short of its own hitbox; and the two pterodactyl frames shared no
pixels, so the bird strobed vertically instead of flapping. A visual pass fixed
those and tidied the draw layer:

- every sprite now bottoms out on y139, one pixel above the ground bar
- `bmp()` takes a declared `(w, h)` and warns on mismatch — it never throws,
  because it runs upstream of `window.Runner` and a throw would silently
  zero every episode
- ground is one 2400 px pre-built strip (2 `drawImage`) instead of 33 `fillRect`
  per frame, and its scroll phase is a pure function of `rawDistance`, never an
  accumulator — `draw()` runs once per `stepFrames(n)` batch, so an accumulator
  would drift with the agent's `action_repeat`
- the HUD is a 10×13 bitmap font, removing the last `ctx.fillText` (and the last
  canvas text state) from the draw path
- a landing dust puff and a jump shadow, both draw-owned state only

**Nothing about gameplay changed.** The agents read numeric state through
`Runner.instance_`, never pixels, and the physics constants, `update()`,
`checkCollision()`, the spawner, the `tRex`/`runner` interfaces, `stepFrames()`
and the lockstep loop are all byte-identical. This was verified two ways: a
region-by-region diff of every simulation function, and a 636-scenario lockstep
replay (5 speeds × 2 obstacle types × 3 group sizes × 21 jump-takeoff frames,
plus duck sweeps — 481 crashes and 155 clears) whose full state traces match the
pre-change build exactly. The PRNG stream is also untouched: the cloud recycler
draws from the *same* global `Math.random()` stream as the obstacle spawner, so
adding or removing even one cloud would reshuffle every future obstacle
sequence — the decorative ground strip therefore uses its own seeded xorshift.

## The curriculum (`curriculum.py`)

Rewards never change (+1 clear, −1 death). Difficulty ramps through the
**environment** — speed caps compress the jump-timing window, then birds add
the duck/jump/run discrimination problem:

| Phase | Environment | Gate (greedy eval avg) |
|---|---|---|
| 1-slow | cacti only, speed ≤ 8 | 600 |
| 2-mid | cacti only, speed ≤ 10 | 800 |
| 3-full-speed | cacti only, speed ≤ 13 | 1000 |
| 4-birds | full game | 1500 |

Reference points: random policy ≈ 45; perfectly-timed scripted jumper ≈ 6,700.

The trainer is self-driving:

- **Auto-advance** — eval gate met → checkpoint → next phase's env built
  in-process. No restart, no edits.
- **Stall recovery** — no eval improvement for `stall_evals` rounds →
  (1) ε-floor boost, then (2) revert to phase-best weights + boost, then
  (3) STALLED flag in logs/dashboard (the only point a human is needed —
  and it means the phase design needs a change, not a restart).
- **Resume** — `state.json` written every episode; full checkpoints include
  optimizer state. `--auto` continues exactly where the run died.

## Two learners, same exam

The genetic algorithm runs the **same sim, same env-shaped curriculum, and
same fixed-seed greedy eval** as the DQN (`agents/genetic/sim_trainer.py`), so
their `eval_avg` numbers are directly comparable. Both complete all four phases
autonomously, with zero human intervention, and reach the same near-perfect
ceiling.

| | DQN | Genetic |
|---|---|---|
| Through curriculum | ~45 min | **~8 min** |
| Units of learning (curriculum) | ~675 episodes | **~79 generations** (50 genomes × 3 eps) |
| To eval ceiling | (through curriculum) | ~200 more generations |
| Final champion eval | 11,087 (10-min timeout) | **11,087 (same)** |
| Parameters | ~12,000 (dueling [15,128,64]) | **419** ([15,16,8,3]) |

Both reach the **same ceiling**; the DQN gets there in fewer "lives" (per-step
credit assignment vs one fitness scalar per genome per life), the GA gets
through the curriculum far faster in wall-clock and in a tiny genome.

> ⚠ **Measurement lesson.** An earlier GA run looked stuck at eval 3,413. That
> was a *selection-saturation artifact*, not a capacity limit: a fixed
> fitness-episode frame cap meant that once several genomes survived the whole
> window they scored identically, so selection couldn't rank them and evolution
> random-walked. The fix is an **adaptive fitness cap** that doubles whenever
> the champion maxes out the window. See
> `models/genetic_validated_20260612_fixed/README.md` for the full before/after.

## Saved checkpoints — what still runs

`game/dino_env.py` sets `N_FEATURES = 28`. v2 took the observation 15 → 26; E11
took it 26 → 28 (closing-velocity residuals). Because the vector is **append-only**,
an older net can still be fed a valid observation by truncating to its width —
but only the tools that actually do so:

| Tool | Truncates? | Older checkpoints |
|---|---|---|
| `gate_battery.py`, `clean_realtime.py`, `bird_velocity_audit.py`, `bird_strategy.py` | yes — `obs[:n_in]` via `--layers` | **runnable** |
| `main.py --demo` | **no** | fail to load |
| genetic (`agents/neural_net.py`) | **no** | fail at the first matmul |

| Checkpoint | Inputs | `--demo` | `gate_battery` / `clean_realtime` |
|---|---|---|---|
| `validated_pollrate_20260710` — **champion** (E12) | 28 | yes, `--poll 0.02` | yes |
| `validated_capacity_20260707` (E8) | 26 | no | yes, `--layers 26,256,128` |
| `validated_timing_20260705` (E5) | 26 | no | yes, `--layers 26,128,64` |
| `validated_20260612` (sim-era DQN) | 15 | no | yes, `--layers 15,128,64` |
| `validated_jitter_20260620` | 15 | no | yes, `--layers 15,128,64` |
| `genetic_validated_20260612_fixed` (GA champion) | 15 | no | no — genetic `.npz` is not a `QNetwork` |
| `genetic_validated_20260612` (superseded) | 15 | no | no — same |

So: the E12 champion is the only checkpoint you can **demo**, but every older
*DQN* checkpoint is still **measurable** on the real-time instruments with an
explicit `--layers`. That is what keeps `EXPERIMENTS.md`'s baselines reproducible.
The two genetic genomes are the genuine dead ends — nothing truncates for them.

> **Caveat on truncation.** It hands an old net the first *n* features, which is
> only sound because every widening appended. If a base feature's *meaning* ever
> changes, truncation will silently feed wrong values rather than erroring.
> Historic eval scores (11,087 for the sim-era DQN and the GA champion) were
> measured against the env of their own era and are not directly comparable to
> numbers produced today.

```bash
# Serve the game first, from dino_rl/, in another shell:
#   python -m http.server 8766

# Demo (champion only)
python main.py --demo --load models/validated_pollrate_20260710/best_model.pt --poll 0.02

# Measure an older baseline — works, with an explicit --layers
python gate_battery.py --load models/validated_capacity_20260707/best_model.pt \
    --layers 26,256,128 --episodes 20
```

`--poll 0.02` is not optional for the champion — it reads its own decision
cadence as a feature, and at the 50ms default that input goes out of
distribution and it collapses.

### Known break: `--agent genetic`

`GENETIC_CONFIG["network_layers"]` is still `[15, 16, 8, 3]` while `DinoEnv`
emits 28 features, and `run_sim_episode()` passes the observation through
untruncated. **`python main.py --agent genetic ...` crashes on the first
forward pass.** The GA results recorded here were produced before v2; the
agent has not been re-fitted to the current observation. Fixing it means
choosing deliberately between widening the genome to 28 inputs (retrains from
scratch) or truncating in `run_sim_episode` (keeps the old feature set).

## Run artifacts

```
runs/dqn_<timestamp>/
├── config.json               # config snapshot
├── log.csv                   # per-episode log (append-safe across resumes)
├── state.json                # resume state — updated every episode
├── checkpoint.pt             # full training state (model+target+optimizer)
├── best_model.pt             # weights at all-time best (for --demo)
├── phase_best.pt             # weights at current phase's best rolling avg
└── phase_<name>_complete.pt  # weights at each phase completion
```

## Other modes

```bash
python main.py --agent dqn --no-curriculum        # flat training, full game
python main.py --demo --load runs/dqn_X/best_model.pt   # watch a fresh run play
python main.py --headless                         # no visible browser
python main.py --cleanup                          # kill orphaned Chrome

# BROKEN — see "Known break: --agent genetic" above. Left documented rather than
# deleted because the GA results in this README were produced with them.
# python main.py --agent genetic --generations 200 --population 30
# python main.py --agent genetic --workers 4      # parallel Chrome windows
```

## Architecture

```
dino_rl/
├── main.py                     # CLI: train / resume / demo / cleanup
├── config.py                   # base hyperparameters (= curriculum phase 1)
├── curriculum.py               # phase definitions + auto-advance/stall logic
├── logger.py                   # run dirs, CSV, checkpoints, resume state
├── cleanup.py                  # orphaned-process recovery
├── game/
│   ├── dino.html               # faithful game clone (URL-param configurable)
│   ├── dino_env.py             # Python sim mirror (~35k steps/sec) — train here
│   ├── chrome_driver.py        # Selenium/Playwright wrapper + JS injection
│   └── game_state.py           # 15-feature normalized state vector
├── agents/
│   ├── neural_net.py           # numpy net (genetic)
│   ├── genetic/                # population, selection, crossover, mutation
│   │                           #   + sim_trainer.py (sim-based GA, shared curriculum)
│   └── dqn/                    # Dueling DQN: network, n-step replay, trainer
└── visualization/
    ├── dashboard.py            # Rich terminal dashboard
    └── web_dashboard.py        # http://localhost:8765 — charts + phase status
```

## State features (28)

> Lineage: **15** (overhaul) → **20** (v2: dissolved-time + cadence features)
> → **26** (explicit bird-class one-hots: low/mid/high) → **28** (E11:
> closing-velocity residuals). The 15-feature core below is unchanged; v2 adds
> indices 15–19 (ttc2, traverse1/2, time-gap, cadence), 20–25 are the
> obs1/obs2 bird-class one-hots, and 26–27 are per-obstacle closing-velocity
> residuals `(measured Δx/frame − speed)/2` — the only observable trace of the
> birds' hidden ±0.8 speed offset (E10 POMDP audit). Measured the same way in
> sim and browser (consecutive-read deltas, first sighting = 0) so the feature
> distribution matches at deploy time. Load older checkpoints with their
> matching `--layers` (e.g. `26,256,128` for the 2026-07-07 champion,
> `20,128,64` for v2b).

Identical layout in sim (`dino_env._observe`) and browser
(`game_state.to_array`) — that parity is what lets a sim-trained network
play the real game:

```
0  obs1 dist               8  gap obs1→obs2
1  obs1 top-edge y         9  speed (speed−6)/7
2  obs1 width             10  dino y-offset
3  obs1 is-bird           11  dino y-velocity
4  obs2 dist              12  jumping flag
5  obs2 top-edge y        13  ducking flag
6  obs2 width             14  time-to-collision (frames/120)
7  obs2 is-bird
```

Bird heights in the y feature: low 0.67 (jump it), mid 0.50 (duck it),
high 0.33 (run under) — the network must learn all three responses.
