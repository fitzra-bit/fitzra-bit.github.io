# Facilitator notes — Dino RL build session

**Keep this folder. Do not hand it out.** `dtx_dino_challenge/` is the
participant artifact and is complete on its own.

---

## The arc

The session is built around one reveal.

Participants spend Round 1 fighting a game that runs in real time at about
thirty decisions a second. Whatever they try, the binding constraint is that
they cannot get enough attempts. Some will feel it as frustration; the ones who
name it — *"the problem isn't my algorithm, it's that I can't run enough
episodes"* — have arrived at the actual lesson.

Then you hand them a simulator that is two thousand times faster, and it drops
into their existing agent with a one-line import change.

The point is not that simulation is a clever trick. It is that **where your
attempts come from is a first-class engineering decision**, usually a bigger
lever than the choice of algorithm. That transfers to anything they will work
on.

The second beat, which lands during Round 2: they are still scored in the
browser. Training fast and being judged slow is the permanent condition of
applied RL, and the gap between the two is where the real work lives.

---

## Run of show

| | |
|---|---|
| **Intro — 20 min** | RL concepts. `docs/01` is the participant-facing version; teach from it or over it. |
| **Setup — 15 min** | `pip install -r requirements.txt`, then `setup_check.py`. Do this before the concepts if the room is on unfamiliar machines — it is where time disappears. |
| **Round 1 — 30 min** | Build. Then `python bench.py`. |
| **Reveal + Round 2 — 60 min** | Hand out `round2_simulator/`. Then `python bench.py --round 2`. |
| **Debrief — 20 min** | Your experiment history. Prize. |

Budget 15 minutes for setup even though it looks like five. Chrome and
ChromeDriver version mismatches are the usual culprit; `setup_check.py`
diagnoses them, and `docs/05-setup.md` has the fixes.

**Windows warning worth saying out loud before anyone starts:** a bare `python`
may hit the Microsoft Store alias stub and print a nonsense message even when
Python is installed. Tell them to use `.\.venv\Scripts\python.exe` and you will
save several people fifteen minutes each.

---

## Round 1 — what you will see

Most teams land on some version of "jump when the nearest obstacle is closer
than X." That is the right instinct and it works — scores in the hundreds.

Then it stops working, and the reason is worth surfacing to the room: **the game
accelerates.** A threshold tuned at speed 6 is wrong at speed 10. Teams that
notice this and make the threshold depend on speed pull clearly ahead. It is a
nice, concrete illustration of a policy that does not generalise across the
state distribution it will actually meet.

Three failure modes to watch for, all cheap to unstick:

- **`IndexError` on `obstacles[0]`.** The list is empty for the first three
  seconds of every episode. Extremely common.
- **Someone starts a DQN.** Do not stop them — let them discover the sample
  budget, that is the lesson. Do check in around the 20 minute mark so they
  still get a number on the board.
- **Silence and no score.** Usually an exception swallowed inside `act()`, or
  never actually acting. `play.py` prints the action mix; all-zeros is the tell.

Things worth calling out publicly when they happen: anyone who tests against a
hand-written baseline before building something clever; anyone who watches
`play.py` to diagnose rather than guessing from the score; anyone who asks
Claude Code how many episodes an approach needs *before* building it.

---

## The reveal

Do it as a moment. Ask first — *"what's actually stopping you?"* — and let the
room answer. Somebody will say sample efficiency in their own words. Hand out
`round2_simulator/` on the back of that.

Two things to say while they integrate:

1. **It is a one-line change.** Their agent is unmodified. This is deliberate:
   the interface was designed so the swap costs nothing, which is itself a
   lesson about how to structure a system you intend to train.
2. **The scoreboard has not moved.** Round 2 is still `bench.py`, still the
   browser. Say this clearly and early, because some teams will otherwise
   optimise against the simulator right up until the final run.

---

## Round 2 — what to watch for

The interesting thing is the **sim-to-real gap**. Teams will get large
simulator scores and then watch them fall over in the browser. That is not a
bug in the exercise, it is the exercise.

Common causes, all genuine:

- Policies tuned to exact frame counts, which the wall clock does not honour
- Training with an `action_repeat` that does not match the browser's real cadence
- Overfitting to a fixed seed instead of sampling episodes

Push them toward *measuring* the gap rather than being annoyed by it: score in
the simulator, score in the browser, compare, form a hypothesis about the
difference. That loop is the actual skill.

---

## Your material for the debrief

Everything you need is in the main project repository (`dino_rl/`) — keep it
out of participant hands until this point:

- `EXPERIMENTS.md` — the full experiment log. The value is that it records
  things that did **not** work and why, which is what nobody publishes.
- `OVERHAUL.md` — the sim-vs-browser fidelity investigation.
- `PROGRESS_REVIEW.md` — honest assessment, including retracted conclusions.

Three stories that land well after they have felt the problem themselves:

**The windup gate.** A persistent failure was chased for a long time as an
agent problem. It turned out to be the display's refresh rate: at 145 Hz the
browser integrates the jump arc in smaller sub-steps than the simulator did, so
the trained jump was subtly wrong. The lesson is not "check your refresh rate."
It is that when a model fails in deployment, the environment is a suspect, and
the fix was to make the simulator match reality rather than to keep tuning the
agent.

**The measurement that measured itself.** Per-step instrumentation was slowing
the loop enough to change the results being measured. `clean_realtime.py` exists
because the observer effect was real. Anyone who has ever added logging to
debug a performance problem will recognise it.

**The genetic algorithm that looked worse than it was.** A GA appeared to plateau
far below the DQN. The cause was a fitness cap: once several candidates survived
the whole evaluation window they scored identically, so selection had nothing to
rank and evolution random-walked. With an adaptive cap it reached the same
ceiling. The conclusion had been about the learner; the problem was in the
measurement. Worth pairing with the leaderboard — ask what their median is
failing to distinguish.

---

## What was deliberately withheld, and why

If a participant goes looking, be ready for these.

**The lockstep hooks are gone from the game.** The research build can advance
the game one frame at a time, which makes the timing problem disappear. Those
hooks were removed from `dtx_dino_challenge/game/dino.html` — not hidden,
removed — so that real-time is structurally the only option in Round 1. The
game's header comment says so plainly.

**No engineered features.** The main project has a 28-feature observation vector
built over several iterations. Participants get the raw state dictionary
instead. Feature design is one of the most transferable things in the session
and handing it over would have made "build a neural network" into filling in a
template.

**`CLAUDE.md` asks Claude Code not to lead with "build a simulator."** It is told
to engage fully if a participant gets there independently. If a team does, that
is a win — celebrate it and give them the payload early.

---

## Follow-on segment — making it industrial

`factory_segment/` is a separate ~30 minute block for after the dino session,
answering "that was a game, what does it have to do with my job?"

It runs the same three-agent comparison against a five-step production line with
a capital budget. The finding is more useful than a win for the neural network:
at full budget all three agents tie, and greedy ROI — which you can explain to a
plant manager in one sentence — captures essentially all the value. Tighten the
budget until the constraint binds and greedy falls $50K/period behind, but the
thing that beats it is *search*, not *learning*, and the DQN never beats random
search at any budget while carrying run-to-run variance the others do not.

That is a better lesson for a GE audience than "use RL", and it closes the loop
on the morning: it is still a simulator, and they have already felt what that
costs.

## Prize

Highest median on the Round 2 benchmark. Say the median rule out loud early —
someone will otherwise report their best run.

Consider a second, non-numeric award. The most interesting entry is often not
the highest scoring: a simple policy that beat a network, a well-diagnosed
failure, a feature nobody else thought of. Rewarding that shapes how the room
talks about the results, and it is closer to how this work actually gets judged.
