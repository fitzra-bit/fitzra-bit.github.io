# Training System Overhaul — Design Notes & Operating Procedure

*2026-06-12. This documents the full overhaul: what changed, why each change
was made, and how to operate the new system.*

---

## TL;DR — what changed

| Area | Before | After |
|---|---|---|
| Training environment | Live browser via Selenium, ~35 steps/sec, ±10–20ms action jitter | Python sim (`game/dino_env.py`), ~35,000 steps/sec, deterministic |
| Rewards | Phase-varying shaped rewards (approach bonus, idle penalty, …) | Sparse + stationary: **+1 clear, −1 death**, tiny survival tie-breaker |
| Curriculum knob | Reward-function changes per phase | **Environment changes** per phase (speed caps, birds on/off) |
| Phase gates / best checkpoint / stall detection | ε-contaminated training scores | **Greedy eval** (ε=0, fixed seeds) every 50 episodes |
| Q-network | Plain MLP | **Dueling** (V/A heads) |
| TD targets | 1-step, MSE | **n-step (n=3)**, Huber loss |
| Target network | Hard copy every 4000 steps | **Soft update** (τ=0.005) every step |
| Exploration | ε-greedy uniform random, per-episode decay | **Noop-biased** random (70/15/15), per-step linear decay |
| Action cadence | Per poll tick (~40 Hz wall clock) | **Action repeat ×2** (one decision per 2 frames, deterministic) |
| State | 13 features | **15 features** (+obs2 width, +obs1→obs2 gap; renormalised speed) |
| Browser game's role | Training environment | **Eval/demo surface only** (feature-parity verified) |

---

## Why each change

### 1. Sim training (the big one)

The Selenium loop had two unfixable problems as a *training* environment:

- **Sample starvation.** ~35 steps/sec means the replay buffer holds ~10
  minutes of experience and a week of wall-clock produces what the sim
  produces in minutes. Every reward-shaping crutch in the old configs
  (approach bonus, idle penalty, …) existed to squeeze learning out of too
  few samples.
- **Action-timing jitter.** Each `execute_script` round trip varies ±10–20ms.
  At speed 13 the correct-jump window is ~60–80ms, so identical states with
  identical actions produced different outcomes — irreducible label noise
  that caps how good the policy can get and explains plateau-then-regress
  behaviour at speed peaks.

`game/dino_env.py` mirrors `dino.html` constant-for-constant (same physics,
spawning, collision boxes). Verified **feature/physics** parity: random-policy
score ≈45 in both. Training now happens at ~35k env-steps/sec with zero jitter;
the browser is for watching (`--demo`) and for final reality checks.

> **Correction (2026-06-20): parity of features is not parity of timing.**
> An earlier version of this doc claimed a sim-trained policy "behaves
> identically in the browser." That holds only when the browser is driven in
> **lockstep** (`--demo --lockstep`: one decision = `action_repeat` frames,
> deterministic — gets the full 11,087). In the *real-time* `--demo` loop the
> browser advances ~3.8 frames/decision (range 1–5; `measure_timing.py`) while
> the sim trains at a fixed 2, so a frame-perfect sim policy drops to ~273.
> Real-time transfer requires timing domain randomization — see the new
> "Timing domain randomization" section below and `models/validated_jitter_20260620/`.

### 2. Sparse, stationary rewards + environment-shaped curriculum

The old curriculum changed the *reward function* between phases. Two problems:

- **Replay-buffer poisoning.** Transitions recorded under phase-1 rewards
  stay in the buffer into phase 2 with different semantics — the Q-function
  is fit to a mixture of two incompatible MDPs.
- **Every reward change moves the optimal policy**, so each phase transition
  destabilises what was already learned (the 1A/1B churn was this).

Now rewards never change: +1 per cleared obstacle, −1 on death, +0.001/frame
tie-breaker. Difficulty ramps through `DinoEnv` constructor params — speed
caps compress the timing window (the real skill axis), and birds add the
duck/jump/run discrimination problem. The buffer stays valid across phases.

### 3. Greedy-eval gating (the measurement fix)

Training scores are produced by the ε-greedy *behaviour* policy, not the
learned *target* policy. Three concrete failure modes this caused:

- **Systematic understatement + variance.** At ε=0.05 with ~30 decisions/sec,
  a random action fires every ~0.7s; one mistimed random jump kills. Training
  scores measure "policy + noise", and the noise dominates near obstacles.
- **Winner's-curse checkpoints.** `best_model.pt` was saved at the max of
  noisy episode scores — which selects for *lucky exploration draws*, not
  good policies. The saved "best" was often not the best network.
- **Self-defeating recovery.** Stall interventions raise ε to 0.30, which
  craters training scores, which the stall detector reads as "still no
  improvement", which escalates again. The recovery mechanism and the
  measurement fought each other. Same for phase gates: right after an
  intervention, completion became nearly impossible until ε decayed.

Now every 50 episodes the trainer runs 5 episodes at ε=0 on **fixed seeds**
(the same exam every time, so deltas measure the policy, not the obstacle
draw). Phase completion, `best_model.pt`, `phase_best.pt`, and stall
detection all key exclusively off this `eval_avg`. Training scores are
display-only.

### 4. Algorithm upgrades

- **n-step returns (n=3):** with sparse rewards, 1-step TD propagates the
  death signal one decision per update; n-step carries it 3× further per
  update. Each stored transition carries its own γᵏ so episode-end partial
  windows are exact.
- **Dueling heads:** most dino states are "nothing nearby — action is
  irrelevant" (state-value dominates); a few are "obstacle here — action is
  everything" (advantage dominates). The architectural split matches the
  problem.
- **Huber loss + soft target updates (τ=0.005):** outlier-robust targets and
  smooth target drift, replacing the hard 4000-step copies that previously
  correlated with crashes at score peaks.
- **Noop-biased exploration (70/15/15):** uniform random jumps ⅓ of the time
  keeps the explorer permanently airborne; it never observes what *waiting*
  does. Mostly-noop exploration probes the decision that matters — when to
  break the noop.
- **Step-based linear ε decay:** episode-based decay made exploration depend
  on episode length (fast deaths → fast decay). Now it's a function of
  experience volume.

### 5. State additions

- **obs2 width + obs1→obs2 gap:** chained obstacles at high speed require
  jumping *early or late* so you land with room before the next one — the
  old state couldn't represent "how much room".
- **Speed renormalised** to `(speed−6)/7` so the feature spans [0,1] instead
  of the compressed [0.30, 0.65].
- **Authoritative counters in the game** (`obstaclesCleared`, `deathCause`):
  the old threshold-crossing clear detection silently missed clears in dense
  obstacle groups. Death causes (`cactus_large`, `bird_mid`, …) are logged
  per eval — when phase 4 struggles, the logs say *what kills it*, not just
  that it died.

---

## What was deliberately removed

- `jump_approach_bonus`, `idle_action_penalty`, `airborne_jump_penalty`,
  TTC shaping windows — sample-starvation crutches; the sim makes them
  unnecessary and they all risk distorting the optimal policy.
- Per-phase reward overrides in the curriculum — see §2.
- Training-score-based control decisions — see §3.
- Chrome from the training loop entirely.

The **insight that survives** from the 1A/1B experiments: *penalties during
early exploration poison Q-values*. The overhaul honours it by having no
shaping penalties at all.

---

## New operating procedure

### Start training
```bash
cd dino_rl
python main.py --agent dqn --episodes 100000
```
No Chrome, no game server needed. Watch http://localhost:8765 — Phase,
Eval Avg (the number that matters), Best, ε, loss, action mix.

### Restart after anything (crash, Ctrl+C, reboot)
```bash
python main.py --agent dqn --auto
```
Resumes the newest run mid-phase: weights, optimizer, ε, phase, episode
counter, eval bests. CSV history continues in the same file.

### Watch it play (real browser game)
```bash
python -m http.server 8766 &        # serve the game (only needed for demo)
python main.py --demo --load runs/dqn_<ts>/best_model.pt
```

### Check progress without the dashboard
```bash
tail -5 runs/dqn_<ts>/log.csv       # eval_avg column is the truth
cat runs/dqn_<ts>/state.json        # phase, episode, ε right now
```

### When is intervention actually needed?
Only when the dashboard/logs show **STALLED** (red phase chip). That means
both automatic interventions (ε boost; revert-to-phase-best + boost) failed
— i.e., the phase needs a *design* change (gate too high, env step too
large), not a restart. Edit the phase in `curriculum.py`, then
`python main.py --agent dqn --auto`.

### Tuning knobs, in the order to try them
1. Phase gates (`complete_eval_avg` in `curriculum.py`) — calibration:
   random ≈ 45, perfect scripted jumper ≈ 6,700 (cacti @ speed 8).
2. `epsilon_decay_steps` (150k) — slower if early phases under-explore.
3. `n_step` (3 → 5) and `lr` (1e-4 → 5e-5) if loss oscillates at high scores.
4. Prioritized replay — documented future option; add only if death
   transitions are demonstrably under-sampled (they're ~1/200 of the buffer).

---

## Run artifacts

```
runs/dqn_<timestamp>/
├── config.json                # config snapshot
├── log.csv                    # per-episode; eval_avg/eval_best columns
├── state.json                 # resume state, rewritten every episode
├── checkpoint.pt              # FULL state: model+target+optimizer+counters
├── best_model.pt              # weights at best EVAL (not training) score
├── phase_best.pt              # weights at current phase's best eval
└── phase_<name>_complete.pt   # weights at each phase completion
```

## Genetic algorithm — same discipline, applied to evolution

The overhaul's measurement principles were ported to a sim-based genetic
algorithm (`agents/genetic/sim_trainer.py`), which now shares the DQN's sim,
env-shaped curriculum, and fixed-seed greedy eval. Two GA-specific points:

- **Common random numbers.** Within a generation every genome is scored on the
  *same* episode seeds, so selection compares policies, not obstacle-draw luck.
  Seeds rotate each generation to prevent overfitting one sequence.
- **Adaptive fitness cap.** Fitness episodes start with a short frame cap (fast
  early generations) and the cap **doubles whenever the generation champion
  times out** on most of its episodes. A *fixed* cap silently saturates
  selection — once several genomes survive the whole window they score
  identically and evolution random-walks. We hit exactly this (best fitness
  pinned at the cap score for 60+ generations, eval stuck at 3,413); the
  adaptive cap fixed it and the GA reached eval 11,087, matching the DQN. This
  is the genetic analogue of §3: *the control signal, not just the report, has
  to stay informative.*

## Timing domain randomization — sim→real transfer (2026-06-20)

The overhaul made the sim a perfect *trainer* but left a *deployment* gap: the
sim is deterministic at 2 frames/decision; the real-time browser is jittery at
~3.8. Closing it took two training-only changes (eval and the real game are
unchanged), both enabled together via `--jitter --randstart`:

### Timing jitter (`--jitter`)
Each **training** step advances a random number of frames in
`[action_repeat_min, action_repeat_max]` = 2–6, bracketing the measured real
distribution (mean 3.8, range 1–5; reproduce with `measure_timing.py`). This
forces the policy to learn timing *margins* instead of frame-perfect timing.
**Eval stays fixed at `eval_action_repeat` = 4** (the real-loop median) on the
usual fixed seeds — so the gating signal is deterministic *and* representative
of deployment. (`DinoEnv` uses an independent `timing_rng` so the obstacle
sequence for a seed is identical with or without jitter, keeping runs comparable.)

### Random start speed (`--randstart`)
Jitter alone got the policy robust on cacti but it **walled on phase 4 (birds)
at eval 565 for 500+ episodes**. Diagnosis: the bird band (speed ≥ 8.5) is the
hardest region *and* the most data-starved of *successful* trajectories — every
episode only flies through it briefly after surviving the easy early game, and
once the agent dies there it rarely collects a clean traverse to learn from.
Fix: start each **training** episode at a uniform speed in 6–12 (clamped to the
phase max), so the agent gets *full-length* practice in the hard band every
episode. This cracked the bird phase in ~50 episodes and rode to the 11,087
ceiling. The lesson rhymes with §3: when a learner plateaus, check whether the
*hard region is under-represented in good signal* before concluding it's at
capacity. Eval always starts at the canonical speed 6.

### Result
| Loop | sim-only model (`validated_20260612`) | jitter+randstart (`validated_jitter_20260620`) |
|---|---|---|
| sim / lockstep browser | 11,087 | 11,087 |
| **real-time `--demo` browser** | **~273** (dies speed 7–9) | **~3,300+, 5/6 cruise** |

## The true deployment timing model — the windup gate (2026-07-04/07)

The 2026-06-20 jitter work made real-time play *viable* (~3,300) but a hard
failure remained that no amount of jitter, curriculum, or data rebalancing
fixed: every model died at **large cacti in the speed 7.1–7.7 windup band**,
~50% of runs, while cruising flawlessly once past it. Two weeks of theories
(sample scarcity, cadence spikes, high-bird strategy) missed it because the
cause was not in the agent at all. Full forensic record: `EXPERIMENTS.md`.

### Root cause: sub-frame integration on a high-refresh display

`dino.html`'s real-time loop is variable-timestep: each `requestAnimationFrame`
calls `update(dt)` with `fe = dt / MS_PER_FRAME`. On a **145 Hz** display
`fe ≈ 0.414`, so the Euler-integrated jump advances in sub-frame steps and
produces a jump arc **~3 px lower and ~4 px shorter** than the sim / lockstep /
headless arc (all of which step at `fe = 1`). That deficit is negligible
everywhere except where `multipleSpeed: 7` first spawns triple-wide large cacti
(speed 7–8) at minimum jump range — precisely the death band. One mechanism
explains the whole picture: the 7.1–7.7 band, `cactus_large` exclusivity,
headless ≠ visible, lockstep passing, and sensitivity to system load
(irregular frame times worsen the integration error).

Proven causally by A/B: a fixed-timestep accumulator (`dino.html?fixedstep=1`)
run visible, real-time, speed-capped 7.5 → **8/8** vs **0/8** for the default
loop, same model. The `?fixedstep=1` param is diagnostic scaffolding only.

### Decision: match the sim to the game, not the game to the sim

The authentic variable-`dt` game on the target display *is* the deployment
target, so the fix lives in the sim. `DinoEnv` gained three measured-timing
parameters (all default to the historical `fe=1` / atomic-action behavior):

- **`fe`** — physics quantum in frames. `0.4138 = 60/145` reproduces the real
  jump arc. `step()` runs `round(n_frames / fe)` sub-steps of `fe` frames each.
- **`cadence_samples`** — per-decision frames resampled from the *measured*
  visible loop (`measurements/cadence_visible_20260705.npy`, mean 3.56,
  std 0.36), replacing uniform 2–6 jitter which over-randomized the eval clock.
- **`act_latency_frames`** — observe→act delay (~0.25 frames measured); the
  action lands after the first sub-step(s), not atomically. Randomized per
  episode in training (`act_latency_min/max`) so robustness is *learned*.

### The calibrated screen and the brittleness metric

With all three, the sim predicts visible gate-pass within ~5 pts for
timing-robust policies (bench 51 vs visible ~50; v2b 65 vs ~70). The
diagnostic byproduct: sweeping `act_latency` 0→0.414 measures **brittleness**
— robust policies barely move (v2b spread 1, champion 5), Goodhart policies
that exploit atomic-action timing collapse (spread 78–87) and are rejected
before costing a visible battery. Selection also moved from saturated-median
to **gate-lex** (gate-pass primary, median tiebreak): the median froze
`best_model` at the frame cap and discarded gate-solving checkpoints.

### Result

| Model | recipe | visible gate | full-run median | endurance |
|---|---|---|---|---|
| v2b (`validated_jitter_20260620` line) | jitter+randstart, fe=1 world | ~70% | 21,704 | 21/30 die @200k |
| `validated_timing_20260705` (E5) | + true timing model | 95% | 22,070 | (screen) |
| `validated_capacity_20260707` (E8) | + `[26,256,128]` capacity | 95% | 22,220 | **29/30 survive 200k** |

The champion trains on the physics its deployment display actually renders.
Windup-gate deaths are gone; conditional bird strategy (jump when spaced,
duck/fast-fall when tight) emerged with zero strategy engineering. Recipe
reproduced across seeds. The lesson that generalizes: **when a learned policy
contradicts obvious optimal play, suspect the environment before the learner**
— the "never-ducking dino" was a sim-fidelity bug report filed months early.

## Invalidation note

Checkpoints from before this overhaul are incompatible (15-feature input,
dueling architecture, new game physics). The genetic agent's `network_layers`
were updated to 15 inputs; a legacy browser-based GA (`--agent genetic
--browser`) is kept for demonstration, but the sim-based GA is the default.

**Feature-count lineage:** 15 (overhaul) → 20 (v2: dissolved + cadence) → 26
(explicit bird-class one-hots). The current champion is 26-feature `[26,256,128]`;
older checkpoints need their matching `--layers` (e.g. `20,128,64` for v2b).
