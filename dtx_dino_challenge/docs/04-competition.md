# The competition

Two rounds. There is a prize.

---

## Round 1 — real time

**Roughly 30 minutes. Everything you need is already in this folder.**

Build the best agent you can under the constraint you have been given: a game
that runs on a wall clock at about thirty decisions a second.

```bash
python bench.py
```

5 episodes, 60 second cap each, so about five minutes. Your ranked number is
the **median**.

Nobody is expected to produce a trained neural network in this round. Some of
the strongest entries will be a handful of well-chosen if-statements, and that
is a legitimate result, not a consolation prize. The purpose of Round 1 is to
put you hard against the real constraint so that what comes next means
something.

---

## Round 2 — after the reveal

**Roughly 60 minutes. You will be given something at the start of this round.**

Same agent, same interface, considerably more room.

```bash
python bench.py --round 2
```

10 episodes, 90 second cap, so up to fifteen minutes — leave time for it.

**Round 2 is still scored in the real-time browser.** Whatever you gain in the
second round, the thing being measured does not change. That is deliberate, and
by the end of the session you will have opinions about why.

---

## Scoring

Your ranked number is the **median** score across the round's episodes.

Median, not best, because obstacles are randomly generated and any single run is
part skill and part luck. An agent that scores 200, 220, 240, 260, 4000 got one
good roll. An agent that scores 900 every time is better, and median says so.

`bench.py` also prints mean, best and worst. The spread is diagnostic: a wide
gap usually means one specific situation is killing you.

---

## Rules

**Yes:**

- Any approach at all. Hand-written rules, search, neural networks, anything.
- Any help from Claude Code. Use it as hard as you like — that is the point.
- Saving and loading your own weights or parameters from a file.
- Continuing to learn during the benchmark run, if your agent works that way.
- Reading anything in this folder, including the game itself.

**No:**

- Editing `bench.py`, `game/driver.py` or `game/dino.html`. Everyone is
  measured on the same game.
- Anything that reaches into the page to change the game's behaviour.
- Requirements beyond `requirements.txt` that a fresh machine could not install.

The honest version of the rule: your agent should decide what to do by looking
at the state it is given, and should not make the game easier.

---

## Submitting

Run the benchmark and show the output. It includes an `agent.py` fingerprint —
a short hash tying the score to the exact code that produced it. Keep the code
that produced your number.

Be ready to say, in about a minute:

- what your agent looks at
- how it decides
- what is still killing it

That last one is genuinely the most interesting part, and it is where the
discussion afterwards will spend most of its time.

---

## A note on the leaderboard

The number is a device for making you try things. It is not the point of the
afternoon.

The most interesting entry will not necessarily be the highest. Someone will
find a feature nobody else thought of. Someone will discover that a simple
policy beats their neural network and be able to explain exactly why. Someone
will fail informatively — attempt something too ambitious for the time, hit the
wall, and be able to describe precisely which wall it was.

All of that beats a big number, and all of it is what the debrief is for.
