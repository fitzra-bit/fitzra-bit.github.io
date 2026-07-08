# Dino RL — Progress Review & Critical Assessment

*2026-07-04. A critical audit of what we set out to do, what we actually did,
and how far apart those are. Companion docs: `OVERHAUL.md` (the documented
plan), `SESSION_HISTORY.md` (narrative), `SESSION_TRANSCRIPT.md` (raw record).*

---

## 1. The goal, stated plainly

A dino agent that **scores high in the real-time, visible browser** — the
game as Ryan actually runs it — produced by a **repeatable process**, not a
lucky draw. The metric is **SCORE**. Everything else (cap-reach, cleared
counts, headless numbers, sim evals) is a proxy, and every proxy we leaned on
this session eventually lied to us.

Sub-goals on record:
1. Beat v2b **repeatably** (not find another lottery ticket).
2. Learn that high-speed jumps are bad behavior ("hurdles: minimize air time")
   through training, not hand-coded shields.
3. Duck HIGH and MID birds — never yet achieved by any model.
4. Be clear on goals and root causes before building.

## 2. Scoreboard: goals vs. reality

| Goal | Status | Evidence |
|---|---|---|
| High score, real-time visible browser | **Achieved once, by accident** | v2b (`runs/dqn_20260621_191112`, 20-feat), measured 2026-07-04: median 21,704, 7/10 cruise — but 3/10 deaths, so "consistently 22k" was a favorable manual sample |
| Repeatable process that produces such models | **Not achieved** | Bench (`runs/dqn_20260627_230813`, 26-feat): median 10,997, 5/10 cruise — a coin flip. Seed repro of its config: 8% / 33% cap-reach (headless — itself untrustworthy) |
| Beat v2b | **Not achieved** | Head-to-head under the honest instrument (§5): v2b median 21,704 vs bench 10,997. Net model progress since v2b: **zero, possibly negative** |
| Duck HIGH/MID birds | **Not achieved** | No model has demonstrated it; fidelity audit says duck = 100% viable, so it's learnable in principle |
| Minimal-air-time jumping | **Validated in probes only** | Hurdler probe 26/30 top-speed cacti vs lazy 0/30; not confirmed as behavior of any deployed champion |
| Sim-to-real transfer | **Half solved** | Lockstep = perfect (11,087). Real-time = partially closed by jitter+randstart, but jitter was calibrated to the **headless** cadence (~3.8 f/dec); the **visible** cadence — the actual deployment condition — has never been measured |
| Trustworthy measurement | **Achieved only at session end** | `clean_realtime.py`, visible, score-based — first honest instrument, running now |

## 3. The critical part: where the effort actually went

**Most of this session was spent discovering that our own measurements were
wrong.** Five distinct measurement failures, each found only after decisions
had been made on top of it:

1. **Observer effect** — `measure_realtime.py` per-step instrumentation
   slowed the loop it measured; the death profile was an artifact.
2. **Headless ≠ visible** — 87% cap-reach headless vs mostly-dead visible.
   The entire working loop judged models in a universe the user doesn't play in.
3. **4,000-step cap** — cut measurement off exactly where the model was
   dying; flattered every candidate.
4. **Cap-reach / cleared-count framing** — the raw reports Ryan pasted led
   with *Score* every time; the analysis kept translating into a step-count
   proxy anyway. Called out explicitly (transcript #29).
5. **Deploy-cap checkpoint selection** — changing `deploy_eval_max_frames`
   36k→80k flipped the same seed from 87% to 8% because `best_model.pt`
   selection is sim-based and doesn't track real-time quality.

The irony is documented in our own plan. `OVERHAUL.md` §3 exists because
ε-contaminated training scores corrupted checkpoint selection, and its GA
section states the principle outright: *"the control signal, not just the
report, has to stay informative."* We honored that principle inside the sim
and violated it wholesale on the deployment side. The June 27–28 training
runs (bench + 3-seed sweep, ~4 runs) were launched, compared, and ranked
using instruments 2–5 above. **Every conclusion drawn from those comparisons
is void.** All three sweep seeds report an identical sim `best_eval` of
25,387 — a number with no demonstrated relationship to visible score.

**Build velocity outran measurement validity.** The 26-feature one-hots,
`gap_scale` 0.85 fast-pacing, and curriculum changes are all plausible ideas —
and all currently unjudgeable, because they were evaluated with broken
instruments. This is the "myopia" Ryan flagged (#19): optimizing the loop
that was easy to measure instead of the goal that was stated.

**The champion was found, not engineered.** v2b predates almost all of this
session's work. If the process were the product, we'd have nothing to show;
what we have is one strong model and — as of today — one honest instrument.

## 4. What is genuinely solid (credit where due)

- **The sim trainer** (`OVERHAUL.md`): sparse rewards, env-shaped curriculum,
  greedy-eval gating, 35k steps/s. Sound, and not implicated in any failure above.
- **Lockstep proof**: when the agent controls the clock, the real game is
  solved (11,087, every episode). The residual problem is timing, full stop.
- **Jitter + randstart**: a real transfer breakthrough (~273 → ~3,300+ demo),
  and the diagnosis behind it (sparse *good* signal in the hard band, Ryan's
  insight) generalized correctly.
- **Fidelity audit**: physics parity confirmed; duck/run-under = 100% window.
- **Fast-fall / hurdler validation**: mechanism confirmed, awaiting integration.
- **The error-correction loop itself**: every bad instrument was caught —
  though nearly always by Ryan, not by the analysis (see `SESSION_HISTORY.md`
  §4). That asymmetry is part of the critique.

## 5. Where we stand right now (2026-07-04)

**First honest measurement is complete.** Bench model
(`runs/dqn_20260627_230813`), visible, 10 episodes, 20k-step ceiling:

```
== SCORE — median 10,997   mean 11,236   best 23,080   worst 187
   scores: 23080, 22703, 22038, 21732, 21710 | 283, 220, 220, 192, 187
== deaths 5/10: death-speed mean 7.3, causes {cactus_large: 5}
```

Two findings:

1. **Perfectly bimodal, 50/50.** Five episodes cruise to ~22k (best 23,080 —
   the highest score ever recorded for any model here); five die under 300.
   There is no middle. Median 10,997 is a mathematical artifact of the split,
   not a description of any actual run.
2. **The failure mode is a single obstacle class in a single speed band:**
   every death was a **large cactus at speed 7.1–7.7** (the windup). Not
   birds, not high speed, not variety — one gate. If it clears the windup
   cacti, it is effectively unbeatable to the 20k ceiling.

The earlier 5 informal visible episodes (200/1.3k/4.5k/22k/22k) came from the
pre-reframe script; consistent with the picture, but the 10-episode block
above is the canonical baseline.

**v2b, same instrument, same day** (visible, 10 eps, `--layers 20,128,64`):

```
== SCORE — median 21,704   mean 15,623   best 22,605   worst 180
   scores: 22605, 22542, 22521, 21742, 21704, 21703, 21699 | 1184, 345, 180
== deaths 3/10: death-speed mean 8.8, causes {cactus_large: 2, bird_mid: 1}
```

### Head-to-head (first instrument-clean comparison)

| | v2b (20-feat) | bench (26-feat) |
|---|---|---|
| median | **21,704** | 10,997 |
| cruise rate (reached 20k-step ceiling) | **7/10** | 5/10 |
| best | 22,605 | **23,080** |
| windup deaths (cactus_large, spd 7–8) | 2 | 5 |
| post-windup deaths | 1 (bird_mid @ spd 11.4) | **0** |

Verdict, with the criticism pointing both ways:

- **v2b remains champion** — median 21,704 vs 10,997, cruise 7/10 vs 5/10.
  The 26-feature bench work did not beat it. §2 stands.
- **But v2b's reputation was inflated.** "Consistently ~22k" came from manual
  demo sessions; under the honest instrument it dies 3/10, twice at the same
  windup large-cactus gate as the bench. The favorable-sample effect the
  review warns about applied to the champion's number too.
- **The windup large-cactus gate is THE shared bottleneck**: bench fails it
  50%, v2b ~20%. It is the single highest-leverage target — fixing it takes
  bench 5/10→~10/10 and v2b 7/10→~9/10.
- Once past the windup, bench was perfect (5/5 to ceiling, and the all-time
  best score, 23,080) while v2b lost one episode to a mid bird at speed 11.4.
  The 26-feature model may genuinely cruise better; it just flips a coin at
  the gate. With n=10 per model this is suggestive, not proven.

Statistical honesty: 10 episodes per model. 7/10 vs 5/10 alone is weak
evidence; the median gap and the death-cause concentration are the stronger
signals. Rerun before betting anything expensive on the difference.

## 6. The plan, tied to the root causes

RC-A: training conditions ≠ deployment (jitter calibrated to headless cadence).
RC-B: measuring the wrong proxy (headless; step-count) — **fixed** as of today.

1. ~~**Finish the bench visible run**~~ **DONE** — median 10,997, 5/10 cruise,
   all deaths cactus_large @ spd 7.1–7.7.
2. ~~**Run v2b through the identical instrument**~~ **DONE** — median 21,704,
   7/10 cruise; still champion, but not the near-perfect model its manual
   demos suggested. See §5 head-to-head.
3. **Measure the visible cadence** (`measure_timing.py`, no headless) — the
   deployment timing distribution we should have measured first.
4. **Retrain with jitter matched to visible cadence**; judge candidates only
   by visible score distribution vs. v2b.
5. **Then** decide the uncommitted work (26-feat, gap_scale, deploy-cap):
   keep what beats v2b under the honest instrument; revert what doesn't.

## 7. Rules going forward (paid for the hard way)

- **Measure in the deployment condition.** Visible browser, wall clock.
  Headless is banned as a decision input.
- **SCORE is the metric.** Median + best over ≥10 visible episodes.
- **No cross-instrument comparisons.** A number is only comparable to numbers
  produced by the same measurement setup.
- **Baseline before build.** No new feature/curriculum experiment until the
  current champion's distribution under the honest instrument is on record.
- **Champion selection must use the deployment metric** — sim `best_eval`
  chooses which checkpoint we keep, and it has been shown not to track
  visible score. This is an open design flaw (trainer's `best_model.pt`).
