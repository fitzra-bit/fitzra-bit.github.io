# Trackmania RL — Training Guide

Everything you need to run, monitor, and understand the sim-phase training.

---

## Quick start

```bash
cd trackmania_rl
pip install torch numpy          # only deps

python main.py --episodes 20000  # start curriculum from scratch
python main.py --auto            # resume the most recent run
python main.py --demo --load runs/sac_TIMESTAMP/best_actor.pt   # watch the agent drive
```

---

## What the training does

The agent is a **Soft Actor-Critic (SAC)** controller trained on a pure Python
kinematic car simulation — no game required at this stage. It drives through a
four-phase curriculum before being exported to the real Trackmania game.

### Four curriculum phases (all in sim)

| Phase | Track | Max speed | Gate (avg_laps to pass) | What the agent learns |
|-------|-------|-----------|-------------------------|------------------------|
| 0-straight | 250 m straight (open) | 22 m/s | 0.85 (= 85% completion) | Throttle, brake, stay on track |
| 1-oval | 500 m oval (closed) | 38 m/s | 3.0 laps | Proportional cornering |
| 2-slalom | 10-gate slalom (open) | 48 m/s | 0.85 (= 85% completion) | Anticipatory steering |
| 3-domain-rand | Slalom + randomised physics (open) | 55 m/s | 0.80 (= 80% completion) | Generalization / sim-to-real |

Note: for open tracks (straight, slalom), the gate metric is `progress` not `laps`. The evaluation converts open-track progress to an effective-laps value using `eff_laps = laps + progress`.

The gate is checked every 50 training episodes using **fixed-seed deterministic
eval** (5 episodes, seeds 10000–10004). The agent advances only when eval, not
training, passes the gate. This is intentional — same philosophy as the Dino RL
project: eval-gated curriculum prevents fluke advances on lucky training episodes.

---

## Reading the output

```
ep    150 | reward   -0.983 | laps  0 | prog 0.02 | α 0.130 | steps  172,000 | phase 0-straight
*** EVAL  avg_laps=0.85 | avg_progress=0.932 | avg_speed=18.3 m/s ***
```

| Field | Meaning | Good sign |
|-------|---------|-----------|
| `reward` | Total episode reward. Range is roughly −1 to +2 | Growing toward positive |
| `laps` | Laps completed in this episode | Starts 0, becomes 1+ in later phases |
| `prog` | Fraction of the track covered before episode ended | Climbing toward 1.0 in Phase 0 |
| `α` | SAC entropy temperature. Controls exploration vs. exploitation | Stays 0.1–0.5 during early learning; slowly falls as policy sharpens |
| `steps` | Total environment steps taken across all episodes | Growing ~1,200/episode in Phase 0 |
| `phase` | Current curriculum phase | Advances when eval gate is hit |
| `eval_avg_laps` | **The key number** — deterministic eval laps | Gate value triggers phase advance |
| `eval_avg_progress` | How far the agent gets on average | 1.0 = full track every time |
| `eval_avg_speed` | Average speed during eval | ~16–22 m/s is good for Phase 0 |

### What each α value means

| α value | What's happening |
|---------|-----------------|
| ~1.0 | Warm-up / full random exploration |
| 0.3–0.6 | Learning — policy is exploring meaningfully |
| 0.1–0.3 | Converging — policy is becoming confident |
| < 0.1 | Risk of over-exploitation (α has a floor at 0.1 via log_alpha clamp) |

---

## Expected timeline

These are rough estimates on a modern laptop CPU:

| Phase | Typical episodes to pass | Wall-clock time (est.) |
|-------|--------------------------|------------------------|
| 0-straight | 200–600 episodes | 10–30 minutes |
| 1-oval | 500–1500 episodes | 45 min – 2 hours |
| 2-slalom | 1000–2500 episodes | 1.5 – 4 hours |
| 3-domain-rand | 1500–4000 episodes | 2 – 6 hours |

Total: **4–12 hours** for the full curriculum depending on hardware.

The sim runs at ~700 steps/sec after the numpy inference cache and single-thread
PyTorch fix. Each Phase 0 episode averages ~200–1200 env steps (car completes the
straight or goes off-track). Phase 2-3 episodes run up to 3000 steps.

---

## What good learning looks like, phase by phase

### Phase 0 (straight track)

- Episodes 1–50: Random exploration, reward bounces between −1 and +0.1. `α` near 1.0.
- Episodes 50–200: `prog` begins creeping up (0.1 → 0.5). Some episodes reach `prog > 0.8`.
- Episodes 200–400: EVAL `avg_progress` rises. Agent starts completing the straight reliably.
- Pass condition: EVAL `avg_laps ≥ 0.85` (completing 85% of the straight consistently).

**Red flag**: If `α < 0.05` and `avg_speed ≈ 0` — the agent learned to stand still to avoid
crashing. This was fixed by the speed bonus reward (`+0.001 * speed_norm` per step) which
makes moving strictly better than braking to a halt.

### Phase 1 (oval)

- Agent sees corners for the first time. Expect initial regression in progress.
- `avg_laps` should reach 1.0 within a few hundred episodes, then climb to 3+.
- Watch `α`: should stay above 0.15 while the agent figures out cornering.

### Phase 2 (slalom)

- Narrow gates, anticipatory steering required. Progress will drop initially.
- Curvature lookahead features (5/12/25 waypoints ahead) are critical here.
- If agent stalls: check that `avg_speed` is reasonable (not braking to zero).

### Phase 3 (domain randomisation)

- Physics parameters vary ±15–40% per episode. Initial drop in performance is expected.
- Policy should recover and exceed Phase 2 gate within 2000 episodes.
- Generalization here is the bridge to the real game.

---

## Running a demo (watch the agent drive)

```bash
python main.py --demo --load runs/sac_TIMESTAMP/best_actor.pt --phase 0-straight
```

This renders a matplotlib animation of one greedy episode:
- **Blue line**: agent's path
- **Green dot**: start
- **Orange dot**: end  
- **Grey dashed**: centreline
- **Grey solid**: track boundaries

Replace `--phase 0-straight` with `1-oval`, `2-slalom`, or `3-domain-rand` to
test a checkpoint on a different track.

---

## Files saved during training

```
runs/
  sac_YYYYMMDD_HHMMSS/
    log.csv          ← one row per episode (all stats)
    config.json      ← hyperparameters used for this run
    state.json       ← episode number + curriculum state (for --auto resume)
    best_actor.pt    ← actor weights at best eval avg_laps (update any time)
    best_critic.pt   ← critic weights at the same checkpoint
    phase_0-straight_actor.pt   ← actor saved when phase gate is passed
    phase_0-straight_critic.pt
    ...              ← one pair per completed phase
    checkpoint.pt    ← full training state (used by --auto for hot-resume)
```

The most useful file for the real-game transfer is `best_actor.pt` or the
latest `phase_3-domain-rand_actor.pt`.

---

## Resuming after a stop

```bash
python main.py --auto
```

`--auto` finds the most recent `runs/` directory, loads `state.json` to recover
the episode counter and curriculum phase, and loads `checkpoint.pt` for the full
network + optimizer state. Training continues exactly where it left off.

Alternatively, load just the actor weights:

```bash
python main.py --episodes 20000 --load runs/sac_TIMESTAMP/best_actor.pt
```

This starts fresh episode counting but with the actor pre-initialized — useful
when you want to restart curriculum after a partial convergence.

---

## Tuning knobs (config.py)

| Parameter | Default | Effect |
|-----------|---------|--------|
| `hidden` | [128, 128] | Network size. [256, 256] is more powerful but 4× slower |
| `lr` | 3e-4 | Learning rate. Drop to 1e-4 if training is unstable |
| `target_entropy` | -1.0 | SAC entropy target. Higher = more exploration retained |
| `min_buffer` | 2000 | Steps of random data before learning starts |
| `eval_every` | 50 | Episodes between greedy evals. Lower = more frequent but slower |
| `explore_std_start` | 0.5 | Exploration temperature multiplier at step 0 (std × 1.5) |
| `explore_std_end` | 0.05 | Temperature multiplier floor (std × 1.05 at convergence) |
| `explore_decay_steps` | 500000 | Steps to decay temperature multiplier to floor |

**α floor**: The `log_alpha` is clamped at −2.3 in `trainer.py`, keeping α ≥ 0.1
regardless of the `target_entropy` setting. This prevents the "stand-still" local
optimum where the agent learns certainty before competence.

---

## After curriculum: bridge to the real game

Once Phase 3 is complete (or `best_actor.pt` shows good slalom performance):

1. **Export the actor weights**: `runs/.../best_actor.pt` — these are plain PyTorch weights.

2. **TMInterface wrapper** (future phase): Load the actor into a Python script that:
   - Reads car telemetry from TMInterface (speed, position, heading)
   - Constructs the same 10-feature observation vector
   - Feeds it through the actor network  
   - Maps the [-1, 1] actions to TMInterface steering/gas/brake inputs

3. **Physics calibration**: Domain randomization in Phase 3 was tuned to bracket
   the real game's physics range. Expect moderate transfer — the agent will need
   ~50–200 real-game episodes to re-calibrate.

The sim doesn't need to be perfect; it needs to be diverse enough that the real
game falls within the distribution. That's the job of `domain_rand=True` in Phase 3.

---

## Common issues

**Training is very slow (< 100 steps/sec)**  
`torch.set_num_threads(1)` is set in `main.py`. If something overrides this,
PyTorch's OpenMP thread synchronization dominates tiny matrix ops and slows updates
from 6ms to 1000ms+. Verify with: `python -c "import torch; print(torch.get_num_threads())"`.

**α collapsed to near zero, agent is stuck**  
Kill the run. The `log_alpha` floor at −2.3 (α ≥ 0.1) prevents this in fresh runs.
If resuming an old checkpoint with collapsed α, manually set `log_alpha` by editing
`checkpoint.pt`: load with `torch.load`, set `state['log_alpha'] = torch.tensor([-1.0])`,
re-save.

**"No resumable run found" with --auto**  
The `runs/` directory must be in the working directory (`trackmania_rl/`). Check
`ls runs/` — if empty or missing, start fresh without `--auto`.

**Phase never advances (stalled message)**  
Phase 3 has a stall detector (35 evals without progress). If stalled:
- Check `eval_avg_speed` — if near 0, the speed bonus may need scaling up
- Check that `α` isn't collapsing (should stay ≥ 0.1)
- Consider increasing `explore_std_start` in `config.py` and restarting from the Phase 2 checkpoint
