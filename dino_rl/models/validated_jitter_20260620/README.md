# Validated jitter-robust run — 2026-06-20

> ### ⚠ Not runnable against the current env
>
> This checkpoint takes **15 inputs**; `game/dino_env.py` now emits
> `N_FEATURES = 28`, so `main.py --demo` cannot load it — that path does not
> truncate. Era: pre-v2 (v2 widened the observation 15 → 26).
>
> **It is still measurable.** `gate_battery.py` and `clean_realtime.py` truncate
> the observation to the net's width, so the numbers below remain reproducible:
>
> ```
> python gate_battery.py --load models/validated_jitter_20260620/best_model.pt \
>     --layers 15,128,64 --episodes 20
> ```
>
> Truncation is sound only because every widening appended features; it hands
> this net the first 15 of 28. Scores here were measured against the env of
> their own era and are not directly comparable to numbers produced today.
> See the compatibility table in `../../README.md`.

The first model trained to play the **real-time browser game** (not just the
sim). Trained with `--jitter --randstart`: timing domain-randomization plus
random start speed. Completes the full 4-phase curriculum and, crucially,
survives the un-throttled wall-clock loop where the sim-only model collapsed.

## Why this exists

The earlier `validated_20260612` model scores 11,087 in the sim but only
~273 in the real wall-clock browser (`--demo`). That gap is **not** a model
flaw — it's a sim-to-real *timing* gap:

- The sim trains at a fixed **2 frames/decision**; the real browser loop
  advances **~3.8 frames/decision** (range 1–5, see `measure_timing.py`).
- A frame-perfect policy can't survive that jittery cadence. In the sim,
  the frame-perfect model degrades from 11,087 (at 2 frames) to ~273 (at 4).

This run closes that gap with two changes (both training-only; eval and the
real game are unchanged):

1. **Timing jitter** (`--jitter`): each training step advances a random
   number of frames in `[action_repeat_min, action_repeat_max]` = 2–6,
   bracketing the measured real distribution. Eval is fixed at
   `eval_action_repeat` = 4 (the real-loop median) for a clean, deployment-
   representative gating signal.
2. **Random start speed** (`--randstart`): each training episode starts at a
   uniform speed in 6–12 (clamped to the phase max). This gives full-length
   practice in the data-light, high-difficulty bird band (≥8.5) instead of a
   brief fly-through after the easy early game — manufacturing the "good
   signal" that was otherwise sparse in the hardest region.

## Results

| Metric | Value |
|---|---|
| Curriculum | completed all 4 phases (~ep 600) |
| Greedy eval @ 4 frames/decision (deployment cadence) | **11,087** (timeout ceiling) |
| **Real wall-clock browser** (`--demo`, the actual target) | **~3,300+ mean, 5 of 6 runs cruising** (vs ~273 for `validated_20260612`) |
| Baseline without randstart | walled at phase-4 eval **565** for 500+ episodes |

The jitter-only baseline got timing-robust on cacti but stalled hard on
birds-under-jitter (eval 565). Adding random start speed cracked the bird
phase in ~50 episodes and rode to the ceiling — confirming the bottleneck was
*good signal in the hard region*, not training volume.

## Watch it play the real game

```bash
cd dino_rl
python -m http.server 8766 &
# real-time, un-throttled — this is the meaningful test:
# NOT RUNNABLE (see banner above)
# python main.py --demo --load models/validated_jitter_20260620/best_model.pt
# deterministic/lockstep (also perfect, but the agent controls the clock):
# NOT RUNNABLE (see banner above)
# python main.py --demo --lockstep --load models/validated_jitter_20260620/best_model.pt
```

Reproduce the training:

```bash
python main.py --agent dqn --jitter --randstart --episodes 8000
```

## Files

- `best_model.pt` — weights at greedy-eval 11,087; the real-time-validated model
- `phase_*_complete.pt` — weights at each curriculum phase completion
- `config.json` — exact hyperparameters (incl. jitter/randstart settings)
- `log.csv`, `state.json` — full training log and final state

Architecture unchanged from `validated_20260612`: dueling Q-network, trunk
`[15, 128, 64]`, 15-feature state. Checkpoints remain interoperable.
