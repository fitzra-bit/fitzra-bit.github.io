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
spawning, collision boxes). Verified parity: random-policy score ≈45 in both;
a scripted TTC-timed jumper scores ~6,700 in the sim and behaves identically
in the browser. Training now happens at ~35k env-steps/sec with zero jitter;
the browser is for watching (`--demo`) and for final reality checks.

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

## Invalidation note

Checkpoints from before this overhaul are incompatible (15-feature input,
dueling architecture, new game physics). Genetic mode remains browser-based
as a legacy demo; its `network_layers` updated to 15 inputs.
