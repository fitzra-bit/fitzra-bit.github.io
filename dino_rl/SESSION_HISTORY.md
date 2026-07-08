# Dino RL — Session History

**Date:** 2026-07-04
**Project:** `C:\Users\Ryan\fitzra-bit.github.io\dino_rl` (Chrome Dino DQN agent)
**Core goal:** A robust dino agent that performs well in the **real-time (visible) browser**, learned reliably and repeatably — not a "lucky draw." **The metric that matters is SCORE.**

---

## 1. How the session started

Ryan returned from vacation where he'd been working on his Reinforcement Learning project inside a remote container, and wanted to re-situate on his local Windows machine.

- First blocker: PowerShell couldn't start the server — "Python was not found." Resolved by using the full Anaconda path.
- He pasted demo runs of the Chrome Dino agent to review current performance.

The conversation evolved into deep RL research on the Dino agent: a DQN (dueling, n-step, Huber loss, soft target updates) trained in a Python sim (`game/dino_env.py`) and deployed to the real Chrome Dino (`game/dino.html`) via Selenium (`game/chrome_driver.py`).

---

## 2. The central problem

The v2b model was strong once past the ~700 windup but underwhelming overall — the model performed exceptionally well **once it broke through to near-full speed**, but struggled in the **windup to full speed** and, separately, on **consistent high-speed jumps**.

Ryan's framing of the problem, in his words:
- "the hardest part is not where the most data resides… little data for that speed varying time period."
- "good training signal there is sparse."
- "the training to beat the 1-2000 range has degraded the +2000 performance."

Key sub-goals that emerged:
1. Beat the "lucky find" (v2b) in a **repeatable** way.
2. Push for high-scoring runs.
3. Teach the agent that **high-speed jumps are bad behavior** through legitimate learning (not hand-coded rules/shields) — "this is sort of like hurdles… you want to be in the air as little as possible."
4. Explore **test benches / "doping" the dataset** to force specific criteria (fast-pace jumps, ducking HIGH and MID birds).
5. Be clear on **goals and root causes** before building — "I'm concerned that you are getting too myopic in your analysis."

---

## 3. Technical concepts explored

- **Sim-to-real timing gap:** sim = fixed frames/decision; real browser ≈ 3.8–4 frames/decision (measured headless), with an additional headless-vs-visible discrepancy.
- **Lockstep** (deterministic browser stepping) vs **wall-clock** (real-time) modes. Lockstep gave perfect real-game play (score 11,087).
- **Timing domain randomization** (`--jitter`, `action_repeat_min/max`) and **random start speed** (`--randstart`).
- **Feature representations:** 15 base → 20 (v2: dissolved time features + cadence) → **26** (added obstacle-class one-hots: bird_low/mid/high). Browser `to_array()` mirrors the 26-feature vector exactly (parity verified, max diff 0.0).
- **Eval hardening:** 16 fixed seeds, jittered eval, **median gating** (not mean), deployment eval decoupled from phase gating for `best_model` selection.
- **Fidelity audit:** jumping a bird = 41% (high) / 51% (mid) / 71% (low) timing window; duck/run-under = 100%. Physics confirmed faithful.
- **Fast-fall insight (validated):** ducking while airborne triggers speedDrop fast-fall; minimizing air time maximizes control. Hurdler model cleared 26/30 top-speed cacti vs a "lazy" model's 0/30.
- **Fast-pacing** (global `gap_scale` < 1) to force minimal-air-time jumps + ducking.

---

## 4. Errors caught & corrected (mostly Ryan catching me)

| Issue | Correction |
|---|---|
| `bird_strategy.py` isolated direct-query gave wrong verdict | Isolated OOD states don't reflect in-game behavior; fixed with `bird_behavior_ingame` airborne-during-overlap metric |
| Action-window in-game metric also wrong | Missed early jumps (dino jumps before the window); fixed with airborne-during-overlap |
| "CPU contention" excuse | **Wrong** — Ryan corrected twice: machine cooking under 50% all day, single-threaded-bound |
| Observer effect in `measure_realtime.py` | Extra clock-reads per step slowed the loop and corrupted the death profile; fixed by reading deathCause once after crash |
| **Headless ≠ visible** (the big one) | `clean_realtime.py --headless` reported 87% cap-reach; the visible demo showed mostly deaths. Headless metric itself untrustworthy — must run **visible** |
| Low metric cap (4000 steps) masked degradation | Cappers cleared ~263, exactly where the model was dying; overstated the model |
| Deploy cap change 36k→80k | Same seed went 87%→8% (best_model selection picked a worse checkpoint) — sim-based selection unreliable for real-time |
| Myopia / defeatism | "why can't you run visible runs as part of the working loop… this is so defeatist" — the fix was already a CLI flag |
| **Measuring the wrong metric** | I framed everything around step-count / cap-reach. Ryan: **"the score is what matters, this has been pretty clear from every raw report i've provided."** |

---

## 5. Root causes identified

- **RC-A — training conditions ≠ deployment:** over-cranked jitter (2-8, 2-12 mis-calibrated timing; reverted to 2-6); jitter was calibrated to *headless* cadence (~3.8), not the *visible* cadence that is the real deployment target.
- **RC-B — measuring the wrong proxy:** headless instead of visible; **step-count / cap-reach instead of SCORE.**

---

## 6. What's working vs. not

**Solved:**
- Lockstep = perfect real-game play (11,087).
- Jitter + randstart = first real-time-viable models.
- Fidelity audit confirmed physics faithful.
- Fast-fall validated (hurdler 26/30 vs lazy 0/30 at top speed).
- Real cadence ~4 frames/decision, latency negligible — **staleness ruled out** as the failure cause.

**Unsolved:**
- **Repeatability.** The "bench" model (26-feat, gap 0.85, jitter 2-6, `runs/dqn_20260627_230813`) showed 87% headless but wildly variable visible. Repro seeds measured 8%/33% headless (headless unreliable). v2b (`runs/dqn_20260621_191112`, 20-feat) remains the best model by the visible standard.

**By SCORE (the correct metric):**
```
bench model, visible:  scores ≈ 200, 1.3k, 4.5k, 22k, 22k   → bimodal, median ~4.5k, best 22k
v2b (overnight):       mostly ~22k, best 22,330             → consistently high
```
→ **v2b is far better** — consistently ~22k vs the bench's coin-flip 200-to-22k spread. The bench isn't good; it's high-variance.

---

## 7. Key files

- **`game/dino_env.py`** — sim environment. `N_FEATURES = 26`. Params: `action_repeat_min/max`, `start_speed_min/max`, `use_dissolved`, `use_cadence`, `bird_weight`, `bird_gap_scale(_low)`, `gap_scale` (global fast-pacing). `_observe()` ends with obstacle-class one-hots.
- **`game/game_state.py`** — browser `to_array()` mirrors the 26-feature vector; has `cadence_frames`.
- **`game/chrome_driver.py`** — `DinoDriver(headless, lockstep)`; computes cadence from `runningTime` deltas; `step(action, n_frames)` for lockstep.
- **`game/dino.html`** — `enableLockstep()`, `stepFrames(n)`, exposes `runningTime`.
- **`config.py`** — `DQN_CONFIG`: `network_layers=[26,128,64]`, `action_repeat_min=2 / max=6` (matched to real ~4), `train_gap_scale=0.85`, `deploy_eval_max_frames=80000`, `deploy_eval_params={"birds":True,"max_speed":13.0,"bird_weight":0.5}`, `eval_episodes=16`, `eval_jitter=True`, `eval_metric="median"`.
- **`curriculum.py`** — reverted to simple 4-phase (1-slow, 2-mid, 3-full-speed, 4-birds).
- **`agents/dqn/trainer.py`** — `deployment_evaluate()`, `_make_deploy_env()`, `evaluate()`, median-based `last_eval`, `best_eval` from deploy eval.
- **`clean_realtime.py`** (RC-B metric) — real-time wall-clock eval, no per-step instrumentation. **Now reports SCORE (median/mean/best/worst)** + death profile. Headless with `--headless`, visible without.
- Diagnostic scripts: `measure_realtime.py`, `fidelity_audit.py`, `reproducibility_test.py`, `ablation_study.py`, `bird_strategy.py`, `failure_modes.py`, `cruise_robustness.py`.

---

## 8. The `clean_realtime.py` reframe (final work in session)

Changed the eval to report the goal metric — **SCORE** — instead of cap-reach / cleared-count:

```python
scores.append(last.score)          # SCORE is the metric
...
print(f"  ep {ep:2d}: SCORE {last.score:8.0f}  "
      f"({'survived cap' if not crashed else 'died spd %.1f' % last.speed})")
...
s = np.array(scores)
print(f"\n== SCORE — median {np.median(s):.0f}  mean {s.mean():.0f}  "
      f"best {s.max():.0f}  worst {s.min():.0f}")
print(f"== all scores: {sorted([int(x) for x in scores], reverse=True)}")
```

---

## 9. Ryan's messages (chronological)

1. "so while on vacation i was working on my Reinforcement learning. I'd like to check back in on this project that was working in the remote container but get re-situated here on my this machine"
2. "so i opened powershell and was unable to start the server… Python was not found"
3. "so take a look at the current run" (v2b demo, underwhelming)
4. "why is that one input not necessarily as robust as creating a tree… Is there more of a consideration we can make at the model level?"
5. "its not the windup bucket is empty… the function is more complex… good training signal there is sparse"
6. "the model before the jitter… once you got past 700 - it was flawless. Clearly the training to beat the 1-2000 range has degraded the +2000 performance"
7. "the hardest part is not where the most data resides… little data for that speed varying time period. But am I misunderstanding the model here?"
8. "do the 3 and i'll consider next steps" (save model, correct docs, commit)
9. "how do i start the latest model for demo"
10. "something going on… in the windup to essentially full speed but once you break through its working exceptionally well"
11. "can we just seperate all the obstacle types… rather than needing to learn obstacle (bird) and position"
12. "Ok lets try it" (categorical features)
13. "are we using a rolling median?"
14. "lets recenter our goal. we had a robust process… it wasn't as robust at the top end speed… trying to have it learn some of both through a broader curriculum but we're degrading"
15. "Root cause analysis. We had a path that led us to build v2b. But then we were looking at what v2b was bad at and it was the top speed jumps no?"
16. "I want a really deep think around this with a well constructed plan… a real analysis of whats ACTUALLY FUCKING WORKING."
17. "MAYBE the model should learn that this is a BAD behavior… making test benches/sims that force certain criteria aka dope the data set. Should we be trying other models or designs?"
18. "This is sort of like hurdles. Ultimately you want to be in the air as little as possible… learning to duck both HIGH AND MID birds - which clearly we have never achieved."
19. "before we do any future builds I want us to be clear on our goals, our root causes. I'm concerned that you are getting too myopic in your analysis."
20. "Ok proceed"
21. "are we still training?"
22. "i think we need to maybe be able to provide more headroom since we're trying to push for 20000 runs"
23. "the first 2 runs failed before 300. However… the second one had a keyboard interrupt from an installer"
24. "no you misunderstood what I meant by 300" (demo: Score 247, 225)
25. "the 3rd run is still going at the score 12k and running."
26. "none have 'gone the distance'… Like this is all terrible"
27. "so why can't you run visible runs as part of the working loop. I feel like this is so defeatist"
28. "hold on 20k steps is not the CAP WTF MATE"
29. **"the score is what matters, this has been pretty clear from every raw report i've provided"**
30. "generate a md file of the chat history of this session"

---

## 10. Where things stand / next steps

- **Metric locked:** SCORE (median / mean / best over N visible episodes). Cap-reach and cleared-count are retired.
- **Working loop must run VISIBLE**, not headless.
- **v2b is the current champion by score** (consistent ~22k). The 26-feat "bench" model is high-variance and not an improvement despite its flattering headless number.
- Open decision: whether to commit the uncommitted changes (bench config, `gap_scale`, categorical 26-feature, deploy cap) or revert toward the v2b setup.
- Likely next experiment: measure the true **visible** cadence and recalibrate jitter to it (RC-A), while judging every candidate by visible **score** distribution (RC-B).

---

*Full raw transcript: `C:\Users\Ryan\.claude\projects\C--Users-Ryan-home-monitor\0dfe4333-072b-4c0c-8300-444772b8d5d0.jsonl`*
