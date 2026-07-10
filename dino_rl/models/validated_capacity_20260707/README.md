# validated_capacity_20260707 — capacity champion (E8)

**E8** (`runs/dqn_20260706_190238`), 26-feature DQN **[26, 256, 128]** (~4×
the control's parameters), trained on the E5 recipe (true timing model:
fe 0.4138, empirical cadence clock, per-episode act-latency randomization,
gate-lex selection), control budget 2,500 episodes, seed 1.

**Correction (2026-07-07, post-certification review):** this README originally
claimed "capacity was the last binding constraint." That was an n=1 inference,
and the Phase 5 certification data does not support it at recipe level: 3
fresh big-net seeds landed gates 84–91% with endurance cap-outs 7–37% —
distributions overlapping the small-net `[26,128,64]` seeds. **E8's numbers
are artifact-level facts (earned on the visible deployment instruments and
they stand), but E8 is a top-tail draw within its recipe, not proof that
capacity shifted the distribution.** Whether capacity raises the ceiling of
good draws is an open, testable hypothesis. The demonstrated binding
constraint after the timing fix is HARVEST VARIANCE (post-curriculum
oscillation makes banked-peak quality a lottery). See EXPERIMENTS.md Phase 5.

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
