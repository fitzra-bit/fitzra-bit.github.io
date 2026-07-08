# validated_timing_20260705 — champion trained on the TRUE deployment timing

**E5 seed 1** (`runs/dqn_20260705_134404`), 26-feature DQN `[26,128,64]`.
The first model trained on the deployment physics that actually exist on the
target machine (145Hz display → fe≈0.414 sub-frame integration), with the
measured decision clock and per-episode action-latency randomization.
Selected by gate-lex (gate-pass primary), not the old saturated median.

**Visible (real-time browser, 145Hz display) results, 2026-07-05/06:**
- Gate battery (n=20, score ≥ 2,500 from canonical start): **19/20 = 95%**
- Full-distance (10 eps, 20k-step ceiling): **median 22,070**, 9/10 at ceiling,
  worst 10,592 (vs prior champion v2b: 21,704, 7/10, worst 180)
- Endurance (4 eps, uncapped): 515 · 1,646 · 34,842 · **157,682** (all-time record)
- Brittleness (calibrated-screen spread across latency 0→0.414fr): 5 pts

Recipe reproduced across 3 seeds (calibrated-screen gate 83–94%). Windup-gate
deaths (large cacti @ speed 7.1–7.7 — the June/July failure mode) absent from
all three. Emergent conditional bird strategy: jumps at comfortable spacing,
fast-fall jump-aborts under high birds, full-ducks mid birds when tight.

Demo:   `python main.py --demo --load models/validated_timing_20260705/best_model.pt`
Judge:  `python gate_battery.py --load ... --episodes 20` (visible) or
        `--sim --fe 0.4138 --cadence-file measurements/cadence_visible_20260705.npy
        --act-latency 0.25` (calibrated screen). Full history: `../EXPERIMENTS.md`.
