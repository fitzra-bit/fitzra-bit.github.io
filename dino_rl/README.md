# Chrome Dino RL

Reinforcement learning agents that teach themselves to play the Chrome offline dinosaur game.

**Architecture:** training runs in a Python simulation (`game/dino_env.py`,
~35,000 steps/sec) that mirrors the browser game constant-for-constant; the
browser game (`game/dino.html`) is the eval/demo surface. Double/Dueling DQN
with n-step returns, sparse stationary rewards, and an environment-shaped
curriculum that advances, recovers from stalls, and checkpoints automatically.

> Full design rationale and operating procedure: **[OVERHAUL.md](OVERHAUL.md)**

## Quick start — the only two commands you need

```bash
cd dino_rl
python main.py --agent dqn --episodes 100000   # start curriculum training
```

No Chrome needed for training. After **any** stop — crash, Ctrl+C, reboot:

```bash
python main.py --agent dqn --auto   # resumes mid-phase, nothing lost
```

Watch progress at **http://localhost:8765**. **Eval Avg** (greedy eval on fixed
seeds) drives phase gates and stall detection; **Deploy GATE %** — P(reach the
windup gate, score ≥2,500) — drives `best_model` selection (gate-lex). Median
alone was retired: it saturates at the frame cap and froze selection.

## Current champion & deployment timing (2026-07-07)

The metric that matters is **SCORE in the real-time, visible browser** — the
game as actually played. A long investigation (`EXPERIMENTS.md`,
`PROGRESS_REVIEW.md`) traced a persistent windup-band failure to the display's
refresh rate, not the agent: at 145 Hz the game sub-frame-integrates the jump
to a shorter arc than the sim used in training. The fix keeps the authentic
game and matches the sim to it — `DinoEnv` now models the true physics quantum
(`fe`), the measured decision clock (`cadence_samples`), and act latency.

```bash
# Watch the champion (26-feature [26,256,128], trained on the true timing model)
python main.py --demo --load models/validated_capacity_20260707/best_model.pt
```

| Champion | visible gate | full-run median | endurance (200k-frame farm) |
|---|---|---|---|
| `validated_capacity_20260707` (E8) | 95% | 22,220 | 29/30 survive (no death) |
| `validated_timing_20260705` (E5, prior) | 95% | 22,070 | — |
| v2b (pre-timing-fix) | ~70% | 21,704 | 21/30 die |

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

Validated checkpoints live in `models/` (newest first):

- `models/validated_capacity_20260707/` — **current champion** (E8, 26-feat `[26,256,128]`, true timing model; needs `--layers 26,256,128` in diagnostics)
- `models/validated_timing_20260705/` — E5 champion (26-feat, first trained on the true timing model)
- `models/validated_20260612/` — sim-era DQN (eval 11,087; browser transfer only under lockstep — see OVERHAUL.md correction)
- `models/genetic_validated_20260612_fixed/` — GA champion (eval 11,087, adaptive cap)
- `models/genetic_validated_20260612/` — first GA run (eval 3,413, **superseded** — fixed-cap artifact)

```bash
# Watch either champion play the real browser game
python main.py --demo --load models/validated_20260612/best_model.pt
python main.py --demo --load models/genetic_validated_20260612_fixed/best_genome.npz
```

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
python main.py --demo --load runs/dqn_X/best_model.pt   # watch it play
python main.py --agent genetic --generations 200 --population 30
python main.py --agent genetic --workers 4        # parallel Chrome windows
python main.py --headless                         # no visible browser
python main.py --cleanup                          # kill orphaned Chrome
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

## State features (26)

> Lineage: **15** (overhaul) → **20** (v2: dissolved-time + cadence features)
> → **26** (explicit bird-class one-hots: low/mid/high). The 15-feature core
> below is unchanged; v2 adds indices 15–19 (ttc2, traverse1/2, time-gap,
> cadence) and 20–25 (obs1/obs2 bird-class one-hots). Load older checkpoints
> with their matching `--layers` (e.g. `20,128,64` for v2b).

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
