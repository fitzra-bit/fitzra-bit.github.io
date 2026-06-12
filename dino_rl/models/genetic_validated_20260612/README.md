# Genetic champion — 2026-06-12 (first full-curriculum completion by evolution)

The sim-based genetic algorithm (`agents/genetic/sim_trainer.py`) completed
the same 4-phase curriculum as the DQN — same sim, same fixed-seed eval
exam, same gates — **autonomously in ~79 generations / ~8 minutes wall-clock
on CPU**, zero interventions.

## Head-to-head vs DQN (identical curriculum + eval protocol)

| | DQN (`models/validated_20260612`) | Genetic (this) |
|---|---|---|
| Wall-clock to curriculum complete | ~45 min | **~8 min** |
| Units of learning | ~675 episodes | ~79 generations (50 genomes × 3 eps) |
| Final champion eval | **11,087** (episode timeout — near-perfect) | 3,413 (strong, still dies eventually) |
| Parameters | ~12,000 (dueling [15,128,64]) | **419** ([15,16,8,3]) |
| Phase 4 (birds) | eval 520 → 942 → 11,087 | eval 696 → 529 → 3,413 |

Takeaway: evolution distills a tiny reactive policy through the gates far
faster in wall-clock; gradient learning reaches a much higher ceiling on
the same exam. Both got through bird discrimination (jump low / duck mid /
ignore high) without human help.

## Files

- `best_genome.npz` — champion at eval 3,413 (419-parameter NumpyNet)
- `phase_*_complete.npz` — champion at each curriculum phase completion
- `state.json` — final curriculum/trainer state

## Watch it play

```bash
cd dino_rl
python -m http.server 8766 &
python main.py --demo --load models/genetic_validated_20260612/best_genome.npz
```
