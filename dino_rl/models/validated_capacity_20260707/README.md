# validated_capacity_20260707 — capacity champion (E8)

**E8** (`runs/dqn_20260706_190238`), 26-feature DQN **[26, 256, 128]** (~4×
the control's parameters), trained on the E5 recipe (true timing model:
fe 0.4138, empirical cadence clock, per-episode act-latency randomization,
gate-lex selection), control budget 2,500 episodes, seed 1.

Capacity was the last binding constraint (Ryan's model-level instinct,
raised in the June conversations, confirmed by this arm): the corrected
world's continuous cadence input and context-conditional strategies
outgrew `[26,128,64]`.

**Results (visible browser = deployment truth, 2026-07-07):**
- Gate battery (n=20): **19/20 = 95%**
- Full-distance (10 eps, 20k-step ceiling): **median 22,220, 9/10 at ceiling**
- Calibrated screen: 96% (CI 92–98); brittleness spread 6
- **Sim endurance: SATURATED the farm — 29/30 episodes ran the full 200k
  frames (~55 game-min each) without dying** (prior champion: 21/30 deaths,
  median 44,903). True ceiling unknown; instruments must grow (failure-budget
  testing) to find it.
- Known residual: rare early-game deaths (~6% of visible episodes, first
  obstacles at speed 6.3–7.2) — the region scorecard's start-band watch item.

Unprecedented curriculum: exited phase 4-birds AT the eval cap (11,088).

Demo:  `python main.py --demo --load models/validated_capacity_20260707/best_model.pt`
       (diagnostics need `--layers 26,256,128`)
Lineage: dethrones validated_timing_20260705 (E5 seed 1). Full record: `../EXPERIMENTS.md`.
