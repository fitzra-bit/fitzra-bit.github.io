# Trackmania RL — Sim-First Curriculum

A SAC agent that learns to drive before it ever sees the real game. The
curriculum runs entirely in a fast Python simulation; the result is a policy
that already knows how to steer and manage speed, so the real TMInterface
phase is calibration rather than ground-zero learning.

## Why sim-first

The same insight from the dino project applies but harder: the real Trackmania
game runs at real-time (no 1000× speedup), and TMInterface episodes are long.
Training basic car control in-game would take hours to get past "car
immediately drives off-track." The Python sim teaches the *shape* of the
skill (proportional steering, speed management, smooth inputs) in seconds;
the real game teaches the exact calibration.

The sim-to-real gap is honest: unlike the dino project (where the sim was a
perfect physics mirror), the kinematic bicycle model is an approximation. Domain
randomisation in Phase 3 compensates — by training on varied physics the policy
becomes robust to the specific values in the real game.

## Quick start

```bash
cd trackmania_rl
pip install -r requirements.txt

python main.py --episodes 20000           # full sim curriculum
python main.py --auto                      # resume after any stop
python main.py --demo --load runs/sac_X/best_actor.pt   # visualise
```

## Curriculum phases (all Python sim)

| Phase | Track | Physics | Gate |
|---|---|---|---|
| **0-straight** | Straight, 250m | Fixed, slow (≤22 m/s) | avg_laps ≥ 0.85 |
| **1-oval** | Oval circuit | Fixed, medium (≤38 m/s) | avg_laps ≥ 3.0 |
| **2-slalom** | S-curve | Fixed, fast (≤48 m/s) | avg_laps ≥ 2.0 |
| **3-domain-rand** | S-curve | **Randomised** (friction, wheelbase, max_speed) | avg_laps ≥ 2.0 |

Gates are checked by a **greedy (deterministic) eval on fixed seeds** — the
same measurement discipline as the dino project. Training episode scores
are display-only; every control decision keys off `eval_avg_laps`.

After Phase 3: export `best_actor.pt` and load into a TMInterface wrapper
for real-game calibration (Phase 4+, not yet implemented here).

## Algorithm: SAC (Soft Actor-Critic)

DQN doesn't apply to continuous steering/throttle. SAC is the right choice:
off-policy (sample-efficient, reuses the same replay buffer design), entropy-
maximising (naturally explores without a separate ε schedule), and stable on
continuous control tasks.

```
Actor       — Gaussian policy with tanh squashing → actions in [−1, 1]²
Twin critics — Q1, Q2 → use min(Q1, Q2) to reduce overestimation
α (entropy temperature) — automatically tuned each step to target H* = −2
Soft target update τ = 0.005 — same as dino DQN, smooth target drift
```

## Observation (10 features)

```
0  speed_norm        speed / max_speed                 [0, 1]
1  lat_norm          lateral offset / track_width      [−1, 1]
2  heading_err_norm  heading vs track tangent / π      [−1, 1]
3  curv_near         signed curvature 5 wp ahead
4  curv_mid          signed curvature 12 wp ahead
5  curv_far          signed curvature 25 wp ahead
6  progress          fraction of track completed       [0, 1]
7  steer_prev        previous steer action             [−1, 1]
8  accel_prev        previous accel action             [−1, 1]
9  wall_dist_norm    nearest wall / track_width        [0, 1]
```

Three lookahead curvature features (near/mid/far) are key: they let the agent
*anticipate* corners rather than react to them. This is the car-control
equivalent of the dino agent's time-to-collision feature.

## Action (2 continuous)

```
0  steer    −1 = full left,  +1 = full right
1  accel    −1 = full brake, +1 = full throttle
```

## Reward

```
+Δprogress   distance advanced along centreline as fraction of track (per step)
−1.0         on going off-track (terminal)
```

Same philosophy as dino: sparse, stationary, never changes across phases.
Difficulty comes from the environment (track shape, speed cap), not reward shaping.

## Architecture

```
trackmania_rl/
├── main.py                 # CLI: train / resume / demo
├── config.py               # SAC hyperparameters
├── curriculum.py           # Phase definitions + auto-advance/stall logic
├── logger.py               # Run dirs, CSV, checkpoints, state.json
├── requirements.txt
├── game/
│   ├── track.py            # Track geometry (straight, oval, slalom)
│   └── car_env.py          # Kinematic bicycle model sim (gym-style)
└── agents/
    └── sac/
        ├── network.py      # Actor (Gaussian + tanh) + Twin Critic
        ├── replay_buffer.py# Preallocated numpy buffer
        └── trainer.py      # SAC loop + eval-gated curriculum
```

## Run artifacts

```
runs/sac_<timestamp>/
├── config.json             # hyperparameter snapshot
├── log.csv                 # per-episode log
├── state.json              # resume state
├── checkpoint.pt           # full state (actor+critic+optimisers+episode)
├── best_actor.pt           # weights at best eval_avg_laps
├── best_critic.pt
└── phase_<name>_actor.pt   # weights at each phase completion
```

## What's next (real-game phase)

1. Install `tminterface` and the TM game (Nations Forever is free)
2. Implement `game/tm_env.py` — wraps TMInterface, maps game state to the
   same 10-feature obs vector, injects the same 2-action commands
3. Add Phase 4+ to `curriculum.py` with `env_params={"interface": "tm", ...}`
4. Load `best_actor.pt` from Phase 3 as the starting weights
5. Expect a short regression then rapid calibration to real physics
