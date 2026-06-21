# Validated run — 2026-06-12 (first full-curriculum completion)

The first run of the overhauled training system (sim training, sparse
stationary rewards, env-shaped curriculum, greedy-eval gating). The full
4-phase curriculum completed **autonomously in ~45 minutes wall-clock
(~675 episodes) on CPU, with zero human interventions and zero stalls**.

## Results

| Stage | Result |
|---|---|
| Phase 1 (cacti, speed ≤ 8) | perfect play (eval 7,150 = episode timeout) at ep ~100 / 2 min |
| Phase 2 (cacti, speed ≤ 10) | gated out, evals 1,340 / 949 vs gate 800 |
| Phase 3 (cacti, speed 13) | gated out at eval 1,988 vs gate 1,000 |
| Phase 4 (full game, birds) | eval 520 → 942 → **11,087** (timeout, full game) |
| Browser transfer (lockstep) | 11,087 — perfect when the agent drives the clock |
| Browser transfer (real-time `--demo`) | **~273 — collapses under wall-clock timing jitter** |

> **Correction (2026-06-20):** an earlier version listed a "127 obstacles, 0
> deaths" real-time transfer test. That is not reproducible — in the
> un-throttled `--demo` loop this model averages ~273 and dies at speed 7–9,
> because it trained at a fixed 2 frames/decision but the real browser runs at
> ~3.8 (see `../../OVERHAUL.md` and `../../measure_timing.py`). It transfers
> perfectly only in **lockstep** (`--demo --lockstep`). For a model that plays
> the *real-time* game, see `../validated_jitter_20260620/`.

The phase-4 progression shows bird discrimination being learned: at eval
942 it died to all three bird heights; one eval round later it stopped
dying entirely (high=run under, mid=duck, low=jump).

## Files

- `best_model.pt` — weights at eval 11,087; the transfer-validated model
- `phase_*_complete.pt` — weights at each curriculum phase completion
- `log.csv` — full per-episode log incl. eval_avg and death_cause columns
- `config.json` — exact hyperparameters of the run
- `state.json` — final curriculum/trainer state

## Watch it play

```bash
cd dino_rl
python -m http.server 8766 &
python main.py --demo --load models/validated_20260612/best_model.pt
```

Architecture: dueling Q-network, trunk [15, 128, 64] (see
`agents/dqn/network.py`); 15-feature state (see `game/game_state.py`).
