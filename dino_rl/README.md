# Chrome Dino RL

Reinforcement learning agents that teach themselves to play the Chrome offline dinosaur game — a faithful self-hosted clone driven live via Selenium + JS injection.

Two learning modes:
- **DQN with curriculum** (the main event) — Double DQN learns through staged phases that advance, recover from stalls, and checkpoint automatically
- **Genetic** — a population of agents evolves across generations

## Quick start — the only two commands you need

```bash
cd dino_rl
python -m http.server 8766 &        # serve the game
python main.py --agent dqn --episodes 5000    # start curriculum training
```

After **any** stop — crash, Ctrl+C, reboot:

```bash
python main.py --agent dqn --auto   # resumes mid-phase, nothing lost
```

Watch progress at **http://localhost:8765** (phase, scores, Q-values, action mix, shaped-reward breakdown).

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
| Physics | dt-based (frame-rate independent — stable under parallel load) |

**Curriculum control is via URL params, not file edits:**

```
dino.html?birds=0                 # Phase 1-3: cacti only
dino.html?birds=1                 # Phase 4: full game
dino.html?birds=1&birdmin=0      # birds immediately (testing)
dino.html?maxspeed=9&accel=0.0005 # gentler pacing (custom phases)
```

Playable by hand too: space/↑ = jump, ↓ = duck.

## The curriculum (`curriculum.py`)

Declarative phases — each defines game params, reward-shaping overrides,
exploration reset, and a completion threshold:

| Phase | Game | Added shaping | Completes at avg20 |
|---|---|---|---|
| 1-jump | cacti only | outcome + jump-approach nudge | 200 |
| 2-shaping | cacti only | mild idle penalty, tighter approach window | 500 |
| 3-converge | cacti only | none — convergence run | 1000 |
| 4-birds | full game | none (birds force duck learning) | 2000 |

The trainer is self-driving:

- **Auto-advance** — phase completes → checkpoint saved → next phase's rewards
  merged, epsilon reset, game URL re-navigated. No restart, no edits.
- **Stall recovery** — no rolling-avg improvement for `stall_window` episodes →
  (1) epsilon boost, then (2) revert to phase-best weights + boost, then
  (3) STALLED flag in logs/dashboard (the only point a human is needed —
  and it means the phase design needs a change, not a restart).
- **Resume** — `state.json` written every episode (phase, window, epsilon,
  counters); full checkpoints include optimizer state. `--auto` continues
  exactly where the run died.

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
│   ├── chrome_driver.py        # Selenium wrapper + JS injection
│   └── game_state.py           # 13-feature normalized state vector
├── agents/
│   ├── neural_net.py           # numpy net (genetic)
│   ├── genetic/                # population, selection, crossover, mutation
│   └── dqn/                    # Double DQN: network, replay buffer, trainer
└── visualization/
    ├── dashboard.py            # Rich terminal dashboard
    └── web_dashboard.py        # http://localhost:8765 — charts + phase status
```

## State features (13)

```
0  dist to obstacle 1      7  speed
1  obs1 top-edge y         8  dino y-offset
2  obs1 width              9  dino y-velocity
3  obs1 is-bird           10  jumping flag
4  dist to obstacle 2     11  ducking flag
5  obs2 top-edge y        12  time-to-collision (speed-invariant)
6  obs2 is-bird
```

Bird heights in the y feature: low 0.67 (jump it), mid 0.50 (duck it),
high 0.33 (run under) — the network must learn all three responses.
