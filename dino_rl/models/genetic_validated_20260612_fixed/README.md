# Genetic champion — 2026-06-12 (adaptive fitness cap, corrected run)

Same curriculum, same fixed-seed eval exam as the DQN. This run fixed the
**fitness cap measurement artifact** from the first genetic run: a hard 2-min
frame cap silently saturated selection once the champion could survive the full
window — evolution random-walked for 60+ generations while real skill
differences lived beyond the cap. The fix doubles the cap whenever the champion
times out on most of its fitness episodes, up to the 10-min eval ceiling.

Result: the GA reaches the **same 11,087 eval ceiling as the DQN** (10-min
episode timeout — near-perfect), just at generation ~200 post-curriculum vs the
DQN's ~675 episodes through curriculum.

## Head-to-head vs DQN (identical curriculum + eval protocol)

| | DQN (`models/validated_20260612`) | Genetic (this) |
|---|---|---|
| Wall-clock through curriculum | ~45 min | **~8 min** |
| Units of learning through curriculum | ~675 episodes | **~79 generations** (50 genomes × 3 eps) |
| Generations/episodes to eval ceiling | included above | ~200 more gens (~25 min) |
| Final champion eval | **11,087** (10-min timeout) | **11,087** (10-min timeout) |
| Parameters | ~12,000 (dueling [15,128,64]) | **419** ([15,16,8,3]) |
| Phase 4 (birds) completion eval | 1,500+ (gated) | 1,500+ (gated) |

**Both algorithms reach the same ceiling.** Evolution distills an equally
capable policy into a 419-parameter genome, gets through the curriculum 5×
faster in wall-clock, but needs additional post-curriculum generations to fully
converge — consistent with the credit-assignment structural disadvantage (no
gradient; one fitness scalar per life; rare events invisible to selection during
early training).

## Why the first run (eval 3,413) was wrong

`models/genetic_validated_20260612` used a fixed 2-min fitness cap
(`FITNESS_FRAME_CAP_START = 7,200` frames). Once several genomes could survive
the full window, their fitness scores were all identical (bounded by the cap
score of ~1,727). Selection could no longer distinguish them — the population
random-walked for 60+ generations. The eval exam (fixed seeds, 10-min cap) did
see the real skill, but evolution itself couldn't act on it.

Fix: `if champion times out on ≥ episodes-1: cap = min(cap × 2, EVAL_FRAME_CAP)`.

## Files

- `best_genome.npz` — champion at eval 11,087 (419-parameter NumpyNet, gen 295)
- `phase_*_complete.npz` — champion at each curriculum phase completion
- `state.json` — final curriculum/trainer state (generation 296, all phases done)

## Watch it play

```bash
cd dino_rl
python main.py --demo --load models/genetic_validated_20260612_fixed/best_genome.npz
```
