# Experiment Ledger — Dino RL windup-gate program

*One row per arm. One variable per arm. Every number states its instrument.
Protocol defined 2026-07-04 (see PROGRESS_REVIEW.md for rationale).*

## Instruments

| Instrument | What it measures | Cost | Status |
|---|---|---|---|
| `measure_cadence.py` | Visible frames/decision distribution by speed band, tail percentiles. Zero extra browser reads (no observer effect). | ~5 min | built 2026-07-04 |
| `gate_battery.py` | P(score ≥ 2,500 from canonical start). Browser (deployment truth) or `--sim` (fast screen; trust pending E1). Wilson 95% CI + death profile. | ~35 min / 20 eps visible; seconds in sim | built 2026-07-04 |
| `clean_realtime.py` | Full-distance visible score distribution (champion crowning only). | ~2.5 h / 10 eps | reframed to SCORE 2026-07-04 |
| Trainer `deploy eval` (E0c) | Uncensored per-eval report: gate_pass + p10 + deaths, printed and logged (`deploy_gate` in log.csv). Reporting only — gating/selection still median. | free | added 2026-07-04 |
| Empirical cadence clock (E1b) | `DinoEnv(cadence_samples=...)`: eval decision timing resampled from the MEASURED real loop (fractional frames; `measurements/cadence_visible_20260705.npy`, n=2000, mean 3.56 std 0.36) instead of uniform 2–6 jitter. `gate_battery --cadence-file`, `measure_cadence --dump`. Rationale: sim errors were structured (−19/−10 on honest checkpoints, +47/+48 on argmax picks) — the eval clock over-randomized vs reality. | free after one 3-min collection | added 2026-07-05. **Calibration result (n=200 each): honest checkpoints tightened — bench 31→38 (visible ~50, err −19→−12), v2b 60→65 (visible ~70, err −10→−5) — but the argmax candidates are UNTOUCHED: candA 98 (visible 50), candB 92 (visible 45).** The uniform clock's phantom 5–6-frame draws explained roughly half the pessimistic bias on honest policies; the candidates' +47 inflation lives elsewhere. **RESOLVED 2026-07-05 with act-latency modeling** (`DinoEnv(act_latency_frames=0.25)`, `gate_battery --act-latency`; action lands after floor+Bernoulli substeps under the previous action, mean-exact dose). Calibration (n=200): bench 51 (visible ~50, **err +1**), v2b 65 (visible ~70, **err −5**). **CALIBRATED SCREEN = `--fe 0.4138 --cadence-file measurements/cadence_visible_20260705.npy --act-latency 0.25`.** The E2 candidates fit NO dose (98→11 across 0.4 frames of latency; Bernoulli-0.25 gives 16/25 vs visible 50/45): their performance is not a stable property but a micro-timing die roll — matches their streaky visible batteries. **New selection criterion: BRITTLENESS = spread between latency-0 and latency-0.414 screens.** v2b spread 1pt (robust); bench 20; candA 87, candB 78 (pathological — auto-reject before visible testing). v2b's real virtue quantified at last: timing robustness. |

| Failure-budget endurance (E9 / Phase 5) | `gate_battery --sim --until-deaths K`: plays UNCAPPED episodes until K deaths, reports **mean score between deaths (MSBD)** as a Poisson rate with log-normal CI. Cap-outs are right-censored (score = exposure, not a death). Replaces fixed-n pass-rate / capped-median farms, which E8 SATURATED (29/30 cap-outs, all percentiles = the cap). Discriminates arbitrarily far into near-perfection. | scales with model quality (bad models die fast, good models run long) | added 2026-07-07. Validated on champion: instrument counts deaths vs cap-outs, computes MSBD+CI, surfaces death causes (caught the early-game watch item: cactus_small @ 7.2). |

**Standing rules:** visible browser is deployment truth · SCORE / gate-pass /
**MSBD** are the metrics · no cross-instrument comparisons · every training arm
= 3 seeds · champion promotion only via full protocol (20-ep gate battery +
10-ep clean_realtime, visible) · **near-perfection (>90% gate): pass-rate
saturates — use MSBD + failure-budget; pre-register bars and stop batteries
early once the outcome is locked (sequential stopping)**.

**Amendments (2026-07-07, Phase 5 review):** (1) reproducibility bars come from
the recipe's MEASURED expected distribution (median across seeds), never from
the champion's numbers; (2) no arm decision on fewer than 3 seeds — no
exceptions, including decisive-looking arms (E7/E8 violated this; the
certification failure was the bill); (3) certification rules use median/k-of-n
forms, not all-must-pass ANDs (with per-seed pass prob p, all-3-pass = p³ — a
coin flip even at p=0.8); (4) recipe-level CAUSAL claims ("X was the
constraint") require the multi-seed distribution, not the adopted artifact;
(5) the certifiable unit at current harvest variance is the PIPELINE
(train k seeds → screen → select), not the single run.

**Known selection flaw (target of E2):** `best_model` updates only on a
strictly-greater deploy median; once the median saturates at the frame cap
(25,387.41), best_model freezes at the FIRST checkpoint to hit it.

## Reference points (visible, 2026-07-04)

| Model | Instrument | Result |
|---|---|---|
| bench `runs/dqn_20260627_230813` (26-feat) | clean_realtime, 10 eps | median 10,997 · 5/10 cruise · deaths: 5× cactus_large @ spd 7.1–7.7 |
| v2b `runs/dqn_20260621_191112` (20-feat, `--layers 20,128,64`) | clean_realtime, 10 eps | median 21,704 · 7/10 cruise · deaths: 2× cactus_large (7.1, 8.0), 1× bird_mid (11.4) |

## Phase 0 — Instruments

| ID | What | Result | Verdict |
|---|---|---|---|
| E0a | Visible cadence by speed band (windup vs cruise), tails vs trained jitter 2–6 | 2,000 decisions, bench model. ALL: mean 3.56, p99 3.8. **Windup <8 is the ONLY band with tail events: p99 5.1, max 8.7, 1.0% of decisions >6 frames, 0.6% >8.** Mid/cruise: max 4.6, zero >6. | **Cadence spikes beyond the trained 2–6 jitter exist exclusively in the windup band** — where all visible deaths occur. RC-A pinned: not the mean (3.56, well-covered), the *tail*, and only during windup. Elevates E5, reshaped as spike-injection (~1% @ 7–9 frames), NOT a wider uniform range (2–8/2–12 uniform already failed as "over-cranked"). |
| E0b | Gate battery built + smoke-tested (browser + sim) | Sim mode: bench = **86% gate-pass (CI 78–91), deaths at speed 8.1–13.0, diverse causes, ZERO below 8** — vs visible truth 50% pass, ALL deaths cactus_large @ 7.1–7.7. Browser mode smoke: 2/3 pass, fail = cactus_large @ 7.2 (~5 min total). | Instrument works end-to-end. **Phase 0 complete 2026-07-04.** **E1 preview: sim-with-uniform-2–6-jitter does NOT track visible at the gate — wrong magnitude AND wrong failure mode.** The sim never generates the >6-frame windup spikes E0a found, so it cannot reproduce the windup death. Fidelity fix candidate: spike-injected cadence in sim eval — if that reproduces the visible death profile, sim screening becomes trustworthy. |
| E0c | Trainer deploy-eval uncensored (gate_pass print + `deploy_gate` CSV column) | done — takes effect on next training run | |

## Phase 1 — Calibration (no training)

| ID | What | Decision rule | Result |
|---|---|---|---|
| E1 | Sim vs visible gate battery on same checkpoints (bench, v2b, 3 sweep seeds) | Sim ranks = visible ranks → iterate in sim, confirm visible. Else visible-only + sim fidelity becomes priority bug | **ROOT CAUSE FOUND (pending A/B confirm).** Elimination chain, bench model, capped 7.5 cacti-only: (1) sim jitter 2–6: **100/100**; spike-injected 1%/5%: 82%/78% with wrong death profile → spike hypothesis rejected. (2) Visible real-time: **0/8**, all cactus_large @ 7.3–7.5, warm browser → warmup exonerated. (3) TRUE lockstep-4 in browser: **8/8** → physics constants/geometry/spawn exonerated (note: first lockstep run 5/8 was contaminated — `load_url` reset `__lockstep`, hybrid stepping; driver fixed). (4) Act latency ~4ms flat, pre-death cadence flat (max 4.2) → loop timing exonerated. (5) rAF probe: **display = 145Hz → visible game integrates at fe≈0.414**; sim/lockstep/headless use fe=1. Sub-frame Euler → jump apex ~3px lower, range ~4px shorter — fatal exactly where `multipleSpeed: 7` first spawns triple large cacti (speed 7–8) at minimum jump range. Explains death band 7.1–7.7, headless≠visible, cactus_large exclusivity, and system-load sensitivity. **Causal A/B: `?fixedstep=1` visible real-time capped 7.5 → 8/8 vs 0/8 control. Root cause proven.** RYAN'S CALL: do NOT fix the game — the authentic variable-dt game on the 145Hz display is the deployment truth; the sim matches IT. `DinoEnv` gained `fe` param (physics quantum; 0.4138 = 60/145). **Fidelity validation, fe=0.4138 sim vs visible:** capped 7.5: 0/100 all cactus_large @ 7.1–7.5 (visible: 0/8, same profile — exact). Full game bench: 31% (CI 25–38) vs visible 50% (CI 24–76); v2b: 60% (CI 53–67) vs visible 70% (CI 40–89). Ranking correct, failure mode correct, magnitudes within CI. **VERDICT (revised after E2 confirmation): fe-matched sim is failure-mode-faithful and rank-suggestive, but per-checkpoint point estimates are UNRELIABLE near the edge** — it scored the phase_4 bench checkpoint 97% sim vs 50% visible (E2). Use the sim screen for shortlisting only; every claim requires visible n=20. (`?fixedstep=1` stays as diagnostic scaffolding only.) |
| E2 | Gate battery over ALL saved checkpoints of recent runs (selection audit) | Any checkpoint ≥80% gate (n=20 visible) + cruise confirmed → new champion, lexicographic selection validated | **JACKPOT (sim screen, fe=0.4138, n=150).** Top finds: `dqn_20260627_230813/phase_4-birds_complete.pt` (= its phase_best) **97%** (CI 92–99, 5 deaths, NOT the gate profile) and `dqn_20260628_123240/best_model.pt` **93%** (CI 88–96). The frozen `best_model` of the same bench run: 30%. v2b best_model: 57%. **The bench RUN had solved the gate; the saturated-median selection discarded the solving checkpoint.** Selected-vs-best-on-disk gaps per run: 30→97, 9→37, 43→43, 93→93 (two runs' best_model froze on bad checkpoints, two got lucky). **Visible confirmation, 97% candidate: 10/20 = 50% (CI 30–70) — NOT PROMOTED** (rule: ≥80%). Death profile ALSO diverged: 5/10 deaths in the opening seconds (score <130, speed 6.3–6.8, first obstacles) — an episode-start transient the sim doesn't reproduce; plus scattered cactus_small and one bird_mid. Two lessons: (a) selection audit stands — best-on-disk ≠ selected — but no free champion; (b) sim point estimates near the edge are off by up to ~47pts per checkpoint. **93% candidate: 9/20 = 45% (CI 26–66) — NOT PROMOTED.** Its visible fails: 4× instant first-cactus (score ≤164), 5× bird_mid (4 at full speed, scores 2,045–2,389 — dies just short repeatedly), 2× cactus_small mid-run. **E2 CLOSED: selection flaw confirmed (best-on-disk ≫ frozen best_model in sim), but neither candidate survived visible confirmation — v2b remains champion (visible gate 70%, median 21,704).** Two NEW visible-only failure modes the fe-sim misses: (1) episode-start instant deaths (both candidates, ~20% of episodes; absent in v2b/bench baselines) — suspect the cadence-feature placeholder on first post-reset decisions; offline action-flip test proposed; (2) full-speed mid-bird deaths (candidate B). Sim-real gap is multi-factor; fe fixed the dominant one (jump arc), not all. 20-feat run dqn_20260620_231150 skipped (checkpoints failed to load). Full table in task output b6kiqjwar. |

## Phase 2 — Training arms (3 seeds each; control = June-28 sweep, measured in E1)

## Roadmap (recentered 2026-07-05, after Phase 0/1 closed)

**Phase 2 — E5: train on the true timing model.** *LAUNCHED 2026-07-05 11:43
(3 seeds sequential, ~2.5-3h each: `main.py --agent dqn --episodes 2500
--randstart --seed {0,1,2}`; config carries fe 0.4138 + cadence_file +
act latency U(0,0.5) train / 0.25 eval + deploy_metric gate_lex +
deploy_eval_max_frames 36k; uniform --jitter retired, superseded by the
empirical clock; smoke-tested 55 eps first).* The centerpiece. 3 seeds:
training env = fe 0.4138 + empirical cadence clock + latency randomization
(0–0.5fr, so robustness is learned); trainer deploy-eval replaced with the
calibrated screen + gate-pass selection (kills the saturated-median /
frozen-best_model bug — the old "selection fix" folds in here); all
checkpoints kept for audit. Judge: calibrated screen → brittleness spread →
visible n=20 region scorecard (start/gate/cruise-birds). **Exit: a seed beats
v2b (visible gate >70%, median >21.7k full-run) with spread <15 — new
champion + first repeatable recipe. All seeds coin-flip → Phase 3.**

**E5 RESULTS (2026-07-05).** All 3 seeds trained clean (~1-2h each; seed 0
resumed after an infra crash — `--resume-dir` added to main.py after an
`--auto` collision nearly corrupted seed 2; contaminated dir quarantined).
Every seed banked a gate-solving checkpoint via gate-lex selection (final
policies oscillated as always — seed 1's last deploy evals were 62%/25% while
its banked best was 16/16; the selection fix is why the peak survived):

| seed | trainer best gate | calibrated screen (n=200) | brittleness spread |
|---|---|---|---|
| 1 (`dqn_20260705_134404`) | 16/16 | **94%** (CI 90–97) | 5 |
| 0 (`dqn_20260705_114306`) | 14/16 | **90%** (CI 85–93) | 4 |
| 2 (`dqn_20260705_123105`) | 15/16 | **83%** (CI 77–88) | 8 |
| v2b reference | — | 65% | 1 |

**Seed 1 VISIBLE n=20: 19/20 = 95% (CI 76–99)** — screen predicted 94%
(instrument dead-on); sole death cactus_large @ 8.6. Windup-gate deaths are
GONE from all three seeds' residual profiles (deaths scattered, mean speed
10.5–11.5). **Gate bar (>70% visible) cleared decisively; repeatability
demonstrated across 3 seeds (83–94% screen, spreads ≤8).**

**CROWN RUN (clean_realtime, 10 eps, 20k-step ceiling, visible):**
```
== SCORE — median 22,070  mean 20,937  best 22,395  worst 10,592
   9/10 reached the ceiling; 1 death: bird_high @ speed 13.0 (score 10,592)
```
**PHASE 2 EXIT MET — NEW CHAMPION: `runs/dqn_20260705_134404/best_model.pt`
(E5 seed 1, 26-feat).** vs v2b: median 22,070 > 21,704 · caps 9/10 > 7/10 ·
visible gate 95% > 70% · brittleness 5 < 15 · worst-case 10,592 vs 180.
Emergent behavior (Ryan, observed live): conditional bird strategy — jumps
birds at comfortable spacing, fast-fall-aborts jumps under high birds and
full-ducks mid birds when tight. Goal #3 (duck HIGH+MID), never previously
achieved, emerged from the corrected physics with zero strategy engineering.
**Phase 3 (data arms) NOT NEEDED — gate solved by the timing model alone.
Next: Phase 4 (residual bird deaths at speed 13, endurance past the 20k
cap) + Phase 5 (repeatability certification, commit, docs).**
Demo: `python main.py --demo --load runs/dqn_20260705_134404/best_model.pt`

**Phase 3 (conditional) — data-distribution arms on the E5 baseline.**
E3 start-speed rebalance toward 6–7.5; E4 stratified/prioritized replay for
sub-8 transitions; E6 windup drill last. One variable per arm, 3 seeds,
same judging. Only if Phase 2 leaves the gate unsolved.

**Phase 4 — the next score frontier.** After gate ≥90% visible: mid-bird
ducking at speed (the never-achieved skill; candB showed it's the frontier —
2,045–2,389 deaths) and endurance past the 20k-step measurement cap (raise
cap for champions; the game is endless). Region scorecard grows:
start / gate / cruise / birds / endurance. Bird-drill env if needed.

*Phase 4 opening measurements (2026-07-05 evening):*
- **Endurance farm** (champion, calibrated sim, 30 eps, 200k-frame cap via
  `gate_battery --sim-max-frames --threshold 999999999`): **median true death
  score 44,903** (2× the old 20k-step ceiling), p10 5,399; 9/30 outlasted even
  200k frames (score 64,388 — reported as cause `?`, actually timeouts; TODO
  separate cap-outs from deaths in summarize). True deaths (21): cactus_small
  8, cactus_large 7, bird_high 3, bird_mid 3 — **scattered, all ~speed 13, no
  dominant class**. Frontier = generic top-speed margin, not a missing skill.
- **Bird scorecard** (`bird_strategy.py --calibrated`, 20 eps): commit-window
  action mix shows heavy duck usage at all heights — but the window metric
  conflates airborne fast-fall with ducking (the documented early-jump flaw),
  so percentages are strategy flavor only. Decisive stat: **0 low-bird deaths
  in ~1.3M score-units; birds ≈29% of scattered residue.** Bird skills
  effectively complete (matches Ryan's live observation of conditional
  ducking/jump-aborts).
*Phase 4 improvement arms:*

| ID | Variable | Decision rule | Result |
|---|---|---|---|
| E7 | Training budget ×2 (5,000 eps, seed 1, same recipe — the E5 budget was inherited from the broken-world era) | adopt if sim endurance median (n=30, calibrated, 200k-frame cap) beats champion's 44,903 AND no regression on gate battery (calibrated ≥90%) / brittleness (<15) / visible P(20k) (≥9/10) | **REJECTED (2026-07-06).** Run `dqn_20260706_074338` (NB: not a replay of seed 1 — FP nondeterminism under different thread load; treat as independent draw). Banked best 16/16 on trainer eval but: calibrated gate **71%** (vs champion 94), endurance median **6,309** (vs 44,903, 7× worse), deaths bird_mid 18/30. Brittleness 12 (ok). Strike one vs undertraining theory — doubled budget produced a worse draw, not a better peak. Bonus findings: (a) n=16 deploy eval saturates at 16/16 — two "perfect" checkpoints differ 94-vs-71 at n=200 (median tiebreak did rank them correctly across runs); (b) post-curriculum peak quality is draw-dependent; budget doesn't buy peaks. |
| E8 | Network capacity ×~4 params (`[26,256,128]` vs control `[26,128,64]`), control budget 2,500 eps, seed 1 | same rule as E7; second consecutive fail → per stopping rule, Phase 4 closes and Phase 5 certifies the champion | **SCREEN: ADOPT-CLASS (2026-07-06/07).** Run `dqn_20260706_190238`. Unprecedented curriculum: exited phase 4 AT the eval cap (11,088; all prior runs ~1.7–2.4k). Calibrated gate **96%** (CI 92–98) vs champion 94; brittleness spread 6; **endurance: 29/30 episodes SATURATED the 200k-frame farm (median=p10=p90=max=64,388; 1 death in 30 × ~55 game-min)** vs champion median 44,903 with 21/30 deaths. The model outgrew the endurance instrument. ~~Capacity was the binding constraint (confirmed)~~ **[CORRECTED 2026-07-07, post-cert review: that was an n=1 causal inference and the certification data does not support it — fresh big-net seeds' gates (84–91%) and endurance (7–37% cap-outs) overlap the small-net distribution; E8 is a top-tail draw within its own recipe. Artifact-level results stand; recipe-level capacity effect UNRESOLVED. This arm also violated the 3-seed standing rule, as did E7.]** **VISIBLE CONFIRMED + ADOPTED (2026-07-07): gate 19/20 = 95%; full-distance median 22,220, 9/10 at ceiling** (vs champion 22,070, 9/10). All adopt criteria met → **NEW CHAMPION: `models/validated_capacity_20260707` ([26,256,128])**. Known residual: rare early-game instant deaths (2/31 visible episodes: 64 @6.4, 191 @7.2 — start-band watch item). **Phase 4 CLOSES via stopping rule (a): endurance lift confirmed** (sim farm saturated). → Phase 5: certify the E8 recipe (3 fresh seeds), failure-budget instruments (run-until-k-deaths + sequential stopping) replace saturated pass-rate batteries, OVERHAUL.md timing chapter, README, merge. |

- **Visible ground-truth endurance** (4 eps, 250k-step ceiling, overnight →
  2026-07-06): **515 · 1,646 · 34,842 · 157,682** (median 18,244, mean 48,671).
  Deaths: bird_high ×2, bird_mid ×1, cactus_large ×1, mean speed 11.9. The
  **157,682** run (~2¼ h of play) is the all-time record by ~7× the old cap and
  exceeds the sim farm's own frame cap 2.4× — the true ceiling is far beyond
  every instrument so far. Shape agreement with sim (heavy tail, scattered
  top-speed deaths); weak-n cautions: visible low tail sits below sim p10, and
  birds are 3/4 of visible deaths vs ~29% in sim. **Phase 4 metric decision:
  endurance medians need n too large for routine visible runs — operational
  scorecard = sim endurance median (n=30+, currently 44,903) + visible P(reach
  20k) (cheap 15-min episodes, currently 9/10); reserve big visible endurance
  for champion-level claims.**

**Phase 5 — repeatability certification + consolidation.** The original #1
goal is a PROCESS: rerun the winning config on 3 fresh seeds, all must pass.
Then: commit the branch (large uncommitted state: instruments, env timing
model, docs), write the fe/timing chapter into OVERHAUL.md, update README.

*(Retired: jitter-tail spike reshaping (disproven); fixed-step deployment
(Ryan's call: authentic game is the target). Open low-priority: episode-start
transient — largely subsumed by brittleness; revisit only if it appears in a
robust policy.)*

### Phase 5 execution (launched 2026-07-07)

**E8-recipe certification** — the E8 config (`[26,256,128]`, control budget,
true timing model, gate-lex) on 3 FRESH seeds (0, 2, 3; `--net-layers
26,256,128`). Pre-registered **certification rule: every seed banks a
checkpoint with calibrated gate ≥90%, brittleness spread <15, AND ≥80%
endurance-farm cap-outs (24/30 @200k) — same instruments E8 was adopted on.**
All 3 pass → recipe certified reproducible. Training done (banked deploy
evals: seed 0 16/16, seed 2 15/16, seed 3 16/16); screening in progress.

| seed | run dir | calibrated gate | brittleness | endurance cap-outs (200k) | rule? |
|---|---|---|---|---|---|
| 0 | `dqn_20260707_123333` | 91% | 3 | 2/30 (7%) | ✗ |
| 2 | `dqn_20260707_123423` | 85% | 10 | 11/30 (37%) | ✗ |
| 3 | `dqn_20260707_152625` | 84% | 10 | 3/30 (10%) | ✗ |
| *(E8 champion, ref)* | `validated_capacity_20260707` | 96% | 6 | 29/30 (97%) | — |

**CERTIFICATION FAILS AS PRE-REGISTERED (0/3 seeds pass all criteria).** But the
result splits cleanly and honestly:
- **Core achievement IS reproducible.** All 3 fresh seeds solve the windup gate
  (calibrated gate 84–91% vs pre-timing-fix ~50%; deaths scattered at speed 13,
  no windup cluster), with brittleness spreads all <15. The timing-model recipe
  reliably produces gate-competent, timing-robust models — goal #1 (a repeatable
  PROCESS) is met for the gate.
- **E8's endurance was a top-tail draw, NOT a recipe property.** Fresh seeds
  endure far less (median 18k–48k, 7–37% cap-outs) than E8's 29/30. The
  certification bar was mistakenly set at E8's *exceptional* numbers — the
  classic anti-pattern of certifying against the champion's lucky draw instead
  of the recipe's expected distribution. 2/3 also miss the 90% gate bar (84–85%).

**Verdict:** recipe certified for **gate competence + robustness** (reproducible);
**endurance ceiling is seed-variance** (E8 is a genuinely strong draw whose
visible numbers stand — it earned them on the deployment instrument). E8 remains
champion. Lesson logged: set reproducibility bars at the recipe's *expected*
level (median across seeds), not the champion's.

Deliverables: failure-budget instrument (`--until-deaths`, MSBD) — DONE;
OVERHAUL.md timing chapter — DONE; README — DONE; branch pushed through
`8068d15`. Remaining: certification-verdict commit; optional merge to main.

### Phase 5 review addendum (2026-07-07) — process audit + capacity backfill

Post-merge review of Phase 5's logic found four process flaws, now codified as
standing-rule amendments (see top): (1) the cert rule's all-must-pass AND form
had ~coin-flip false-failure odds even for a good recipe; (2) its thresholds
were anchored on E8's own draw — the project's 4th winner's-curse instance;
(3) the "split verdict" softened the pre-registered ≥90% gate bar post-hoc
(2/3 seeds missed it at 84–85%); (4) certification used the saturated 200k
farm instead of the MSBD instrument built expressly because it saturated.

**Capacity backfill (endurance farm on E5 small-net seeds 0/2, same settings):**

| recipe | calibrated gates | endurance cap-outs @200k farm |
|---|---|---|
| small `[26,128,64]` (3 draws) | 83, 90, 94 (median 90) | 27%, 30%, **60%** (median 30%) |
| big `[26,256,128]` (4 draws) | 84, 85, 91, 96 (median 88) | 7%, 10%, 37%, **97%** (median 23%) |

**The capacity claim is not just unproven — the data leans against it:** the
small net's median endurance is higher, and the program's 2nd-best endurance
draw (E5-seed2, 60% cap-outs, capped median 64,388) is a small net that had
screened at only 83% gate. Findings: (a) E8 is an extreme draw, from either
recipe's perspective; (b) within-recipe variance (7→97%, 27→60%) dwarfs any
between-recipe difference; (c) gate skill and endurance skill are partially
DECOUPLED — screening on gate alone under-values endurance-strong draws.
**The binding constraint after the timing fix is harvest variance**, and the
certifiable unit is the pipeline (train k seeds → screen on gate AND
endurance/MSBD → select). Claim-site corrections applied to the champion
README, E8 ledger row, and OVERHAUL.md results table.

### E10 — bird closing-velocity observability audit (2026-07-07)

Hypothesis (from external review + feature inspection): birds carry a hidden
±0.8 `speed_offset`; the TTC feature computes `x/speed` — wrong by ~12% for
birds, unknowable from one snapshot → bird deaths should skew toward FAST
(+offset) birds. Probe: `bird_velocity_audit.py` (calibrated timing,
start-speed 11–13 to farm top-speed encounters; 100 eps × 3 models).

**CONFIRMED, ~5× skew.** Pooled cert seeds 2+3: encounters +365/−332,
deaths **+17/−3** (4.7% vs 0.9% per encounter; p≈0.001). cert-seed2: 5/5
deaths on fast birds. **E8 champion: 0 bird deaths in 500 encounters** — a
good draw covers the hole by margin, but the recipe distribution bleeds
through it. First mechanistic account of a residual-death class since the
windup gate.

Fix candidates (one variable each, in cost order): (a) **closing-velocity
feature** — driver/env already hold the previous read; per-obstacle Δx/frame
is computable in the existing loop, mirroring the cadence-feature pattern
(26→28 inputs, surgical); (b) **4-frame stacking** (26→104) — reveals velocity
AND all other temporal structure, still architecture-preserving; (c) DRQN —
only if (a)/(b) underdeliver. Judged under amended rules: 3 seeds, gate AND
endurance distributions vs the now-measured baselines.

### E11 — closing-velocity feature arm (launched 2026-07-07)

Features 26–27: per-obstacle closing-velocity residual `(measured Δx/frame −
speed)/2`, clipped ±1, plausibility-gated (|v−speed|>1.5 → 0, kills id-reuse /
mismatch artifacts). Sim: id-tracked previous positions in `_observe`; browser:
driver matches consecutive reads by type + expected travel (mirrors the
cadence-feature pattern; resets on restart/navigation). Sanity-verified: fast
birds read +0.410, slow −0.411, cacti zero-mean. `N_FEATURES=28`; config
default net `[28,256,128]`; older checkpoints unaffected (obs truncated to
their input dim everywhere).

**Arm:** 3 seeds (0/1/2), `--net-layers 28,256,128`, 2,500 eps, E5/E8 recipe
otherwise. **Pre-registered rule: ADOPT if pooled bird-audit fast:slow death
ratio ≤2× (baseline 5×) AND distributions don't regress vs the big-net
baseline (gate median ≥88, endurance cap-out median ≥23%). Distribution
claims only; no single-draw conclusions.**

**Results (screened 2026-07-10, calibrated timing throughout):**

| Seed | Run | Gate n=200 | Britt. lat0/lat.414 | Bird fast:slow (deaths) | Endurance cap-outs | End. median |
|---|---|---|---|---|---|---|
| 0 | `dqn_20260709_225323` | 87% | 91% / 82% | 0.3× (2/6) | 3/30 (10%) | 11,053 |
| 1 | `dqn_20260710_015056` | 91% | 89% / 91% | 5.0× (5/1) | 15/30 (50%) | 60,700 |
| 2 | `dqn_20260709_225412` | 92% | 95% / 92% | 0.0× (0/9) | 7/30 (23%) | 21,181 |

**Verdict vs rule — ADOPT (all three prongs pass):**
- **Pooled bird ratio: 0.43×** — 7 fast vs 16 slow deaths over ~1,479
  encounters (fast 0.94%, slow 2.17% per encounter). Bar was ≤2×; baseline 5×.
  Per-seed ratios (0.3/5.0/0.0×) swing wildly on tiny death counts — the
  pooled rule exists precisely for this.
- **Gate median 91** ({87, 91, 92}) ≥ 88. No regression.
- **Endurance cap-out median 23%** ({10, 50, 23}%) ≥ 23%. No regression
  (baseline {7, 10, 37, 97}%).

**Reading beyond the rule (flagged, not concluded):** the fast-bird skew
didn't just close — it *inverted*. Pooled slow-bird death rate (2.17%) now
exceeds fast (0.94%), driven by slow LOW birds (seed 2: 8/9 bird deaths were
slow-low, 9.8% cell rate; seed 0: 5 slow-low). Plausible mechanism: the
residual is 0 on first sighting (needs two reads), so the *first* decision
against a bird is still made blind, and a slow bird shifts the jump window
later than the blind prior expects. Total bird mortality still improved
(~1.6% per encounter pooled vs baseline ~2.8%). Candidate refinement if it
matters later: none registered yet — poll-rate arm outranks it.

**Champion: UNCHANGED.** E8 artifact (`validated_capacity_20260707`, measured
97% cap-out endurance, 0/500 bird-audit deaths) still beats every E11 artifact
on its own measured numbers. E11 adoption is a RECIPE change: the 28-feature
observation closes the E10 POMDP hole at the distribution level, so future
harvests start from a floor without the hidden-velocity blind spot. Visible
confirmation of an E11 artifact deferred (game server stopped per Ryan
2026-07-09; browser-side closing_v mechanics also need a headless check before
visible numbers are trusted — driver code shipped but has only run in sim
parity tests).

### E12 — poll-rate (decision quantization) arm (launched 2026-07-10)

**Hypothesis:** the agent's 50ms poll (~3.56 frames ≈ 46px between decisions
at speed 13) caps jump-timing precision, and this — not observability (closed
by E11) — is the binding constraint on endurance. The poll interval is
AGENT-side (`GAME_CONFIG["poll_interval"]`), not a game modification.

**Probe (existing artifacts at fast cadence, sim, calibrated):** naive runs
collapsed completely (E8 median ~100, E11-s1 ~400–1,000 vs native 60,700) —
the cadence feature goes far OOD (0.30 vs trained 0.55–1.46). With a new
`--cadence-feature` clamp (feature reports native 3.565 while the world runs
÷2): **E8 fully rescued — 27/30 cap-outs (90%) ≈ its native 97%**; E11-s1 NOT
rescued (465 — deeper timing specialization). Conclusions: (a) fast cadence is
mechanically playable at champion level; (b) a 3.56-trained policy gains
nothing from doubled resolution — the payoff, if any, requires a policy
TRAINED at fast cadence. Probe cannot bound it.

**Poll sweep (visible browser, 1,200 decisions/leg, dumped to
`measurements/cadence_poll{50,20,10,00}_20260710.npy`):**

| requested | realized mean f/dec | p95 | max | px/dec @13 | act_ms |
|---|---|---|---|---|---|
| 50ms (control) | 3.72 | 4.2 | 10.0 | 48 | 5.3 |
| 20ms | 1.87 | 2.1 | 4.2 | 24 | 4.9 |
| 10ms | 1.28 | 1.7 | 2.9 | 17 | 5.3 |
| 0ms (spin) | 0.66 | 0.8 | 1.3 | 8.6 | 5.2 |

Control ≈ July-5 baseline (3.56 → 3.72, mild drift, instrument valid). Act
latency ~5ms (≈0.3 fr) is poll-invariant — latency model unchanged. The 20ms
clock has NO spike tail (max 4.2 vs 10.0) — faster polling is also cleaner.
Caveat: fast legs sampled only the windup band (measuring policy collapses
at fast cadence in the real loop — no browser-side feature clamp); control
shows windup≈mid, and this closes properly once a fast-trained policy can
re-measure all bands.

**Pilot (1 seed, resource decision only — NOT an adopt decision):** E11
recipe + `--cadence-file measurements/cadence_poll20_20260710.npy` (20ms
clock: 2× decision density, ~2× training cost; the 0.66 floor is the second
rung if this pays). **Pre-registered pilot rule: spend on the full 3-seed arm
iff the pilot's calibrated screen ON ITS OWN CLOCK shows gate ≥85% AND
endurance cap-out ≥23% (E11 median). Pre-registered ADOPT rule (full arm
only): endurance cap-out median STRICTLY > 23% (the lift is the hypothesis)
AND gate median ≥88 AND bird pooled ratio ≤2× (E11 gains retained). Champion
promotion additionally requires visible confirmation at 20ms poll.**

**Pilot results (seed 0 = `runs/dqn_20260710_212411`, screened 2026-07-11 on
its own 20ms clock):** gate **200/200 = 100%** (CI 98–100) — first perfect
gate this program has measured; brittleness 99%/100% (spread ~1); bird audit
3 deaths/440 encounters (0.68%, all fast-HIGH, 0 slow); endurance **26/30
cap-outs (87%)**, median = cap, p10 54,686 — vs E11 seeds {10, 50, 23}%. All
4 endurance deaths at speed 13.0, ALL birds (2 high, 2 mid) — the
tight-cactus death mode that dominated every 50ms policy is absent from the
profile. **Spend rule: PASS (100 ≥ 85; 87 ≥ 23). Full arm launched
2026-07-11 ~09:45: seeds 1, 2 in parallel, same recipe + clock (pilot counts
as seed 0). Adopt/promotion rules as pre-registered above — pilot numbers are
ONE DRAW; no causal claim until the arm distribution exists.**

**Full arm results (seeds 1, 2 screened 2026-07-11, own 20ms clock):**

| Seed | Run | Gate n=200 | Britt. | Bird deaths f/s (enc) | Endurance cap-outs | End. median |
|---|---|---|---|---|---|---|
| 0 (pilot) | `dqn_20260710_212411` | 100% | 99/100 | 3/0 (440) | 26/30 (87%) | 64,388 (cap) |
| 1 | `dqn_20260711_094524` | 74% | 77/72 | 2/0 (384) | 17/30 (57%) | 64,388 (cap) |
| 2 | `dqn_20260711_094626` | 96% | 96/92 | 0/0 (440) | 10/30 (33%) | 28,604 |

**Verdict vs pre-registered adopt rule:**
- **Endurance cap-out median 57%** ({87, 57, 33}) **STRICTLY > 23%** ✓ — the
  lift is real at the distribution level: every E12 seed ≥ the E11 median;
  the E12 WORST draw (33%) beats the E11 median.
- **Gate median 96** ({100, 74, 96}) ≥ 88 ✓.
- **Pooled bird ratio: INDETERMINATE BY DEGENERACY — 5 fast vs 0 slow deaths
  (~1,264 encounters).** The ratio's letter (≤2×) cannot be evaluated with a
  zero denominator, and 5 events can't pin a skew (P(5:0 | equal rates) ≈ 3%).
  The prong's INTENT (retain E11's bird gains) passes unambiguously: total
  bird mortality 0.40%/encounter vs E11's 1.6% (4× better), zero slow-side
  deaths (E11's inversion gone). Registered as-is, not softened post-hoc: the
  rule failed to anticipate zero-denominator outcomes.

**ADOPT (2 prongs pass, 3rd indeterminate with intent unambiguously met).**
Decision-rate quantization was a real, large constraint — but note causality
nuance: the 20ms clock is also CLEANER (no spike tail), so "faster" and
"cleaner" are partially confounded in this arm. Seed 1 is a weak-gate draw
(74%, windup cactus_large deaths, E2-style start transient) — harvest
variance persists. Remaining death frontier at 20ms: fast HIGH birds
(pilot 3, seed 1 2 + 8 in endurance) and seed-1's windup transient.

**Recipe going forward: E11 features + 20ms clock
(`--cadence-file measurements/cadence_poll20_20260710.npy`, agent
`poll_interval` 0.02 at deploy). Candidate artifact: seed 0/pilot (gate 100%,
endurance 87%). NOT yet champion — promotion requires the visible protocol at
20ms poll (20-ep gate + 10-ep clean_realtime) + browser closing_v mechanics
check. Cross-clock artifact comparisons (vs E8 champion @50ms) are
banned per standing rules — the clocks are different instruments.**

**Browser-side closing_v mechanics check (E11 feature in the REAL game,
headless, 20ms poll, candidate seed 0, 5 eps / 27,844 reads):** coverage
**96%** of obs1-present reads non-zero (first-sighting zeros are the 4%);
cactus residuals mean −0.000, std 0.000, |max| 0.004 (dead zero — plausibility
gate + matching clean); bird residuals split **fast +0.400 (n=3,566) / slow
−0.400 (n=3,877)**, exactly the ±0.8 speed offset after /2 norm. The
driver's consecutive-read matching reproduces the sim estimator faithfully —
the E11 feature is real at deploy, not a sim-only artifact. Only visible
protocol (physical display) now remains before promotion. Tool:
`closing_v_check.py`.

**Visible confirmation, candidate seed 0 @ poll 0.02 (20 eps, physical
145Hz display, 2026-07-12): GATE 6/20 = 30% (CI 15–52) — FAILS the ≥80%
promotion bar. NOT PROMOTED.** Sim→visible gap: calibrated-sim 100% →
visible 30%. Signature is anomalous and uniform: all 14 deaths at speed
EXACTLY 13.0 (MAX_SPEED), scores tightly 2222–2300 (just short of the 2500
gate), death cause null ("?") on every one. Null cause is mechanically odd —
dino.html sets `crashed=true` and `deathCause=cause` together (only when
`checkCollision()!==null`), so a genuine collision should always carry a
cause; 14/14 nulls suggests EITHER a real top-speed failure the sim misses
OR a 20ms-visible harness artifact (spurious crash read / two-execute_script
race at max game speed). **OPEN — not resolved.** Discriminating test (needs
display): run E8 champion (known ~22k visible median @50ms) at poll 0.02 —
same 2250/speed-13/null failure ⇒ harness artifact (30% is not a policy
verdict); plays fine ⇒ candidate-specific real gap. Until resolved, E12's
sim-level ADOPT stands but the RECIPE IS NOT VISIBLE-CONFIRMED; no champion
change. clean_realtime deferred (gate failed).

**RESOLVED (2026-07-17): the 30% visible gate was instrument censoring, not
policy failure.** Discriminator (E8 @ 20ms visible): 18/20 died EARLY with
real causes (windup cacti, median 150 — matches the sim OOD-collapse probe,
median 122, nearly number-for-number); its 2 lucky max-speed episodes "died"
at 2283/2273, speed 13.0, cause null — the exact candidate signature. Two
different policies sharing one death spot = harness. Mechanism: `cause=None`
(not '?') means the episode ended WITHOUT crashed=true — gate_battery's
--max-steps default (5,000) × ~1.77 realized f/step ≈ 8,850 frames ≈ score
~2,260: alive at the cap, just short of the 2,500 gate line. All 14
"deaths" were censored-alive episodes. Instrument fixed: capped episodes now
report CENSORED_ALIVE, excluded from the death profile.

**Visible gate RERUN (--max-steps 15000, 20 eps, 2026-07-17): 16/20 = 80%
(CI 58–92) — MEETS the ≥80% promotion bar exactly.** 4 real deaths, diverse
(cactus_small 7.6/12.2, cactus_large 10.8, bird_mid 13.0). Best visible gate
ever measured (v2b 70%, E2 candidates 45–50%). Zero margin — recorded as-is;
the bar is the bar in both directions. Proceeding to clean_realtime (10 eps,
poll 0.02, high step cap) — the crowning metric vs E8's visible median 22,220.

**Crowning run (clean_realtime, 10 eps, poll 0.02, step cap 50k ≈ score
~27.3k, 2026-07-18): median 27,263 — RIGHT-CENSORED (8/10 episodes ALIVE at
the cap; true median higher). Beats E8's visible 22,220 by ≥23%. Deaths 2/10
(bird_low, cactus_large @ spd 11–13).**

**PROMOTED 2026-07-18: `models/validated_pollrate_20260710` (E12 seed 0) is
CHAMPION.** Full protocol: visible gate 16/20 = 80% (bar met exactly) +
crowning median > predecessor (censored-low, still +23%). Deploy contract:
**--poll 0.02 required everywhere** (cadence feature OOD-collapses at 50ms —
symmetric to E8 collapsing at 20ms; poll rate is part of the artifact).
E8 (`validated_capacity_20260707`) retained as best 50ms-clock artifact.
README + model READMEs updated; main.py --demo grew --poll.

**Program state after E12:** windup gate solved at distribution level (E5/
fe+cadence), observability hole closed (E11), decision quantization halved
(E12). Remaining measured frontier: (a) visible gate 80% vs sim 100% — the
residual sim→visible gap now lives in the 4 real gate deaths (windup cactus
+ mid-band cactus + top-speed bird), (b) the 0.66 f/dec spin floor (second
rung, untested), (c) E11's first-sighting-blind residual + slow-low-bird
cell, (d) harvest variance (arm seeds 74–100% gate). No arm registered yet
for any of these.

**⚠ CORRECTION + PROMOTION RETRACTED (2026-07-19, Ryan's catch):** the
crowning comparison above is INVALID. E8's "median 22,220" was itself
right-censored — its crowning record reads "9/10 at ceiling": 22,220 IS
E8's instrument cap, not a death score. E12's 27,263 was taken at a cap I
raised to ~27.3k. Comparing two censored floors at two different ceilings
says nothing about which true median is higher — the "+23%" was the cap
difference, not measured performance. (Same flaw further back: E8-over-E5's
"22,220 vs 22,070, both 9/10 at ceiling" was cap-noise; the full-run-median
column has tracked the cap of the day across the whole champion lineage. The
gate and the sim endurance farm were doing the real discrimination.)

Like-for-like, everything measured favors E8: gate 95 vs 80; P(reach 22.2k)
90% vs 80%. E12's demonstrated edge exists only above E8's old cap — where
E8 was never tested and its sim endurance (29/30 @200k farm) predicts it may
also cruise. **`validated_capacity_20260707` (E8) REMAINS CHAMPION.** E12
seed 0 status: candidate — visible gate 80% (bar met), higher-ceiling
evidence real but not comparative.

**Standing-rule amendments (6) and (7):** (6) a censored median must be
reported as "≥cap (k/n censored)", never as a point value; (7) cross-artifact
score comparisons require the SAME score ceiling (frames-equivalent across
clocks) on both sides — a number taken at a different cap is a different
instrument (this is measurement failure #3's subtler sibling: the cap doesn't
just censor, it MANUFACTURES differences when it moves between tests).

**Fair head-to-head (registered, pending Ryan's go — needs display time):**
both artifacts, 10 eps clean_realtime each, SAME score ceiling ≈34k (100k
frames: E8 @50ms --max-steps ~27000; E12 @20ms --max-steps ~57000), each on
its own clock. Pre-registered read: champion = better on {gate (already
measured), same-ceiling median, deaths-per-exposure}; reliability AND
ceiling both count (Ryan 2026-07-19: "overall performance and
consistency/reliability BOTH matter"). If both saturate 34k, escalate the
ceiling or switch to visible MSBD (failure-budget).

**Head-to-head leg 1 — E8 @50ms, ceiling ~36k (10 eps, 2026-07-19):**
`[36470, 36283, 36019, 34317, 33713 | deaths 19874, 16874, 13059, 7748 @spd
13, 171 @7.1]` — median 26,794, mean 23,453, 5/10 cap-outs. **E8's old
"22,220, 9/10 at ceiling" was concealing a ~50% mid-cruise death band at
7.7k–19.9k.** Same-ceiling analysis (both censored at E12's 27.26k cap):
P(ceiling) E8 5/10 vs E12 8/10; censored median 23,568 vs 27,263; MSBD ~47k
vs ~111k (E12's exposure capped lower — bias against E12); gate 95 vs 80
(E8's one lead). No single comparison significant at n=10/20; nominal
pattern = Outcome B: neither dominates, every long-run axis favors E12,
early-game gate favors E8. Leg 2 (E12 @20ms, matched ~35k ceiling) running —
completes MSBD at equal exposure.

**Head-to-head leg 2 — E12 @20ms, matched ~35k ceiling (10 eps, 2026-07-19):**
`[35330, 34105, 33921, 33914, 33897, 33883, 33861, 33858 | deaths 23939
(cactus_large), 5682 (bird_high), both @spd 13]` — 8/10 cap-outs, median
33,890 (censored), mean 30,239, zero sub-2,500 deaths this run. **Matched-
instrument verdict: E12 leads P(ceiling) 8/10 vs 5/10, median +26%, mean
+29%, MSBD 151k vs 47k (3.2×). E8 retains the early-game edge: pooled
sub-2,500 rate ~6% vs ~15% across all visible episodes.** Promotion decision
= Ryan's both-matter weighing; recommendation on record: promote E12 on
per-game expected score (+29%, which already prices the early deaths in),
register the early-game cell (E12's 1-in-7 sub-2.5k starts; suspects:
unmeasured cruise-band 20ms clock is NOT this cell — windup/mid transient,
first-read cadence placeholder, E2-lineage) as the next repair arm.

**PROMOTED (Ryan's call, 2026-07-19): `validated_pollrate_20260710` (E12
seed 0) is CHAMPION** on the day-matched, ceiling-matched head-to-head (mean
+29%, median +26%, MSBD 3.2×; E8's early-game edge noted and accepted as a
repair-arm target, not a blocker). E8 (`validated_capacity_20260707`)
retained as the 50ms-clock reference artifact. Deploy contract: --poll 0.02.

**Amendment (8):** visible A/B comparisons must INTERLEAVE artifacts
episode-by-episode within one session — day-matched by construction. Basis:
E8's P(reach 22.2k) swung 9/10 → 5/10 across 12 days (sampling noise at
n=10 + measured platform drift, 50ms cadence 3.56→3.72 f/dec; cross-era
number comparisons are unreliable in both directions).

**Confirmation run (registered, launching now): interleaved A/B, 10 eps per
side, matched ~35k ceiling (E8 @50ms/30k steps, E12 @20ms/62k steps), new
instrument `ab_realtime.py`. Pre-registered read: the promotion STANDS
unless E8 wins mean-per-game in the interleaved rerun, in which case the
crown is re-examined with all three day-matched pairs on the table.**

**Confirmation — INTERLEAVED A/B, day-matched, 10 eps/side, matched ~35k
ceiling (`ab_realtime.py`, 2026-07-19/20):**
- **A = E8 @50ms:** median 33,556, mean 27,026, 8/10 cap-outs, 2 deaths
  (both cactus_small @ spd 7.3–7.4, scores 215/241), MSBD 135,132.
- **B = E12 @20ms:** median 33,849, **mean 33,846**, **10/10 cap-outs, 0
  deaths**, MSBD ∞. Astonishingly tight (33,785–33,917).
- **VERDICT: B wins mean/game 33,846 vs 27,026 (+25%) AND reliability
  (0 vs 2 early deaths).** Pre-registered stake was "promotion stands unless
  E8 wins mean-per-game" → E8 lost → **PROMOTION CONFIRMED, LOCKED.**

**Correction to the earlier "E8 has the early-game edge" claim:** that was a
noisy snapshot (E8's July-7 gate 95% vs E12's 80% on different days). Pooled
across ALL visible episodes, sub-2,500 early-death rates are a WASH — E12
~6/50 (12%), E8 ~4/40 (10%) — both dominated by windup cactus_small/large,
statistically indistinguishable at these n. In this day-matched interleaved
run E12 was actually the cleaner of the two (0 vs 2). Honest read: **E12
wins mean/MSBD robustly and repeatedly; the early-game cactus cell is a
SHARED weakness of both artifacts, not an E8 advantage — and it is the
clear next target (repair arm, benefits any champion on this recipe).**
