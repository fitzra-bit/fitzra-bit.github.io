# DTX session — full project

Everything needed to run the session inside GE. This is the **facilitator**
copy: it contains material participants must not see before the right moment.

---

## What to hand out, and when

| When | Give them | Not this |
|---|---|---|
| A week or more ahead | `DTX-Setup.zip` — the pre-install pack | anything else |
| Start of the build session | `DTX-Challenge.zip` — the participant folder | — |
| After they hit the sample-budget wall | `DTX-Round2-Simulator.zip` | — |
| Never | | **`dtx_facilitator/`** |

The three participant zips are built from this tree — `dtx_preflight/`,
`dtx_dino_challenge/` and `dtx_facilitator/round2_simulator/` respectively.
They are not committed to the repository; in the packaged distribution they
sit alongside this file.

> **`dtx_facilitator/` is yours only.** It holds the run of show, the reveal,
> what was deliberately withheld and why, both follow-on segments, and the
> Round 2 payload. Handing it over spoils the session.

---

## The folders

| | |
|---|---|
| `dtx_facilitator/` | **Start here.** `FACILITATOR.md` is the run of show. |
| `dtx_preflight/` | Pre-install pack. Spoiler-free — safe to send in advance. |
| `dtx_dino_challenge/` | The participant artifact. Complete on its own. |
| `dino_rl/` | The full research project. Debrief material — the experiment log, the sim-vs-browser investigation, the honest progress review. |
| `factory_sim/` | Production-line simulator with three competing optimisers. |
| `factory_chat/` | OptiFlow — the conversational layer over `factory_sim`. |
| `trackmania_rl/` | A second RL project. Not used in the session. |
| `BACKLOG.md` | Sequenced work to bring the code up to the OptiFlow deck. |

---

## Before the day

**1. Send `DTX-Setup.zip` out early.** Managed laptops need lead time, and the
most common blocker — a corporate proxy blocking the ChromeDriver download —
is far easier to solve a week ahead. `preflight.py` produces a report
participants can send back, so you know who is ready.

Fill in the two `[SESSION LEAD — ...]` placeholders in
`dtx_preflight/README.md` first: how GE staff obtain Claude Code access, and
where to send the report.

**2. Run `preflight.py` yourself on a representative GE laptop.** This is the
one thing that could not be verified when the pack was built. If the proxy
blocks the driver download across the board, that is a bulk problem worth
solving centrally rather than 25 times in the room.

**3. Install `torch` ahead of the factory segment.** It is the slow one.

**4. Sort out `ANTHROPIC_API_KEY` for OptiFlow**, and confirm it works *from
the GE network*. Screenshot the first few demo steps as a fallback — it is the
only part of the session that needs a live external service.

**5. Rehearse the OptiFlow demo once.** The model picks its own tool calls, so
the suggested prompts in `dtx_facilitator/optiflow_segment/README.md` are a
starting point, not a script.

**6. Read the note on the deck.** `OptiFlow_DTX.pptx` is aspirational in
places — it describes the target system, not the built one. The segment README
lists the gap line by line and recommends relabelling slide 1 as an
architecture proposal. One sentence, said out loud, and the gap becomes a
useful point rather than a discrepancy someone spots.

---

## Quick commands

```bash
# Dino — sim training, dashboard on :8765
cd dino_rl && python main.py --agent dqn --episodes 100000

# Dino — real-time validation (needs the game served, from dino_rl/)
python -m http.server 8766
python gate_battery.py --load models/validated_pollrate_20260710/best_model.pt --episodes 20 --poll 0.02

# Factory — three optimisers, ~25 seconds
cd factory_sim && python main.py
python main.py --scenario ../dtx_facilitator/factory_segment/scenarios/widget_factory_constrained.yaml

# OptiFlow — conversational layer
cd factory_chat
export ANTHROPIC_API_KEY=...
export OPTIFLOW_PLANT=../dtx_facilitator/optiflow_segment/plant/dtx_plant.yaml
python app.py
```

Only the E12 champion (`models/validated_pollrate_20260710`) loads against the
current environment, and it requires `--poll 0.02`. See "Saved checkpoints" in
`dino_rl/README.md` for why, and for how to still measure the older ones.
