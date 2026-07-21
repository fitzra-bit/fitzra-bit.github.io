# Champion — E12 poll-rate recipe (promoted 2026-07-19, matched head-to-head)

`best_model.pt` = E12 pilot / arm seed 0 (`runs/dqn_20260710_212411`),
dueling DQN `[28, 256, 128]` (26 features + E11 closing-velocity residuals),
trained on the **20ms decision clock**
(`measurements/cadence_poll20_20260710.npy`, realized ~1.87 f/dec) with the
true timing model (fe 0.4138, act latency U(0,0.5) train / 0.25 eval,
randstart, gate-lex selection).

## Status: CHAMPION — promoted on the matched head-to-head

History matters here: a 2026-07-18 promotion was retracted (Ryan's catch —
it compared censored medians taken at two different step caps; the "+23%"
was the cap difference, not performance). The proper test followed on
2026-07-19: **day-matched, ceiling-matched (~35k) head-to-head vs E8** —
P(ceiling) 8/10 vs 5/10, median 33,890 vs 26,794, **mean/game 30,239 vs
23,453 (+29%)**, MSBD 151k vs 47k (3.2×). **CONFIRMED** by a day-matched interleaved
A/B rerun (amendment 8, `ab_realtime.py`): E12 mean/game 33,846 vs 27,026
(+25%) and 0 vs 2 early deaths — E12 won both axes. The earlier "E8 has the
early-game edge" read was noise; pooled across all visible episodes the
sub-2,500 early-death rates are a wash (~10–12% both), dominated by windup
cactus. That shared cactus cell is the registered next repair target.

## ⚠ Deploy at 20ms poll or don't deploy

This policy reads the decision cadence as a feature. At the default 50ms
poll its cadence input goes far out of distribution and it collapses
(measured: sim median ~1,000 vs 64k-cap; the E8 champion collapses the same
way in reverse at 20ms). Every visible use needs `--poll 0.02`:

```
python main.py --demo --load models/validated_pollrate_20260710/best_model.pt --poll 0.02
python gate_battery.py --load models/validated_pollrate_20260710/best_model.pt --layers 28,256,128 --poll 0.02 --max-steps 15000
```

## Measured (visible, physical 145Hz display, 2026-07-17/18)

- Gate (20 eps): 16/20 = 80% (CI 58–92). 4 deaths: cactus_small 7.6/12.2,
  cactus_large 10.8, bird_mid 13.0.
- clean_realtime (10 eps): **≥27,263 (8/10 censored alive at the ~27.3k
  step cap)**; 2 deaths (bird_low, cactus_large @ 11–13).
- Sim (own clock): gate 100% (n=200), brittleness 99/100, endurance 26/30
  cap-outs @200k frames, bird audit 3 deaths/440 encounters.

## Provenance

E10 (bird POMDP hole) → E11 (closing-velocity feature, 26→28) → E12 (20ms
clock; recipe endurance cap-out median 23→57% across 3 seeds, sim). Full
rules, arm distributions, the two censoring incidents and the retraction:
`EXPERIMENTS.md`.
