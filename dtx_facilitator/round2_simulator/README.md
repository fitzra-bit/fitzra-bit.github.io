# Round 2 — the same game, two thousand times faster

Copy `dino_env.py` and `fast_game.py` into your `dtx_dino_challenge` folder,
next to `agent.py`.

Then change one import in your training code:

```python
# from game.driver import DinoGame
from fast_game import FastDinoGame as DinoGame
```

That is the whole integration. Same three methods, same raw state dictionary,
same physics constants, same obstacle generation. Your agent does not know the
difference.

Check what you just gained:

```bash
python fast_game.py
```

You were getting about 30 decisions per second. You will now get somewhere
around 60,000.

---

## What this changes

Everything you ruled out an hour ago on the grounds of "that needs thousands of
episodes" is now back on the table. A few hundred episodes was a long
afternoon. It is now under a second.

If you wanted to train a network and could not, you can now. If you wanted to
search a parameter space properly instead of guessing, you can now. If you
wanted to run the same idea across five random seeds to find out whether it was
real or luck, that is now cheap enough to be routine — and it is a habit worth
forming.

---

## What this does not change

**You are still scored in the browser.** `bench.py` has not moved and does not
use this.

This matters more than it sounds. The simulation is faithful — same constants,
same generation — but faithful is not identical. The browser runs on a wall
clock with real jitter; the simulation advances only when you tell it to. A
policy that is precisely tuned in here can meet slightly different timing out
there, and precision that depended on exact frame counts is the first thing to
break.

So: **train fast, then verify slow.** A number from the simulator is a
hypothesis. `bench.py` is the experiment. When the two disagree, the browser is
right, because the browser is what you are being judged on — and in a real
deployment, the browser is the part that is actually the world.

If you find a gap between your simulator score and your browser score, you have
found the single most important phenomenon in applied reinforcement learning.
It has a name — the sim-to-real gap — and teams spend careers on it.

---

## A few things worth knowing

**`action_repeat`** controls how many game frames pass per decision. Default 2.
The browser gives you roughly two or three frames' worth per decision,
depending on your machine. Setting this too low trains an agent that expects to
act more often than it will be able to.

**Nothing happens until you call `act()`.** In the browser the world moves on
while you think. Here it waits. A loop that reads state without acting will
spin forever on an unchanging world.

**Seeds.** `reset(seed=N)` gives a repeatable episode. Fixing a seed is how you
tell "my change helped" apart from "I got a different set of obstacles." Vary
seeds when measuring how good something is; fix them when debugging why
something broke.

**Speed makes sloppiness cheap and mistakes invisible.** At 60,000 decisions
per second you can run a broken experiment to completion in the time it takes
to notice it was broken. Check that your scores are moving for the reason you
think.
