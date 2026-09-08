# The game, and what you can see

This is a faithful rebuild of the Chrome offline dinosaur game — same physics
constants, same pacing, same obstacle generation. It is not a simplified
imitation.

Everything here is checkable. `game/dino.html` is readable and reasonably
commented, and asking Claude Code to read it with you is a good use of ten
minutes.

---

## The world

A 600 × 150 space, seen from the side. The ground is at **y = 140**.

**The y axis points down.** Smaller y is higher up. This trips up nearly
everyone at least once.

```
  y=0    ┌──────────────────────────────────────────┐
         │                                          │
         │          🦖                    ▓         │  ← obstacles arrive
         │                                ▓         │    from the right
  y=140  └──────────────────────────────────────────┘
         x=0        x=50                          x=600
                     ↑
              the dino is always here
```

The dinosaur never moves horizontally. It sits at **x = 50** and the world
scrolls past it. When you read an obstacle's `x`, the gap between you and it is
roughly `x - 50`.

---

## What you get to see

`game.get_state()` returns a dictionary. This is the complete set of what your
agent can know:

| field | meaning |
|---|---|
| `crashed` | the episode is over |
| `score` | the game's own score. This is what you are judged on |
| `speed` | current game speed |
| `dino_y` | vertical position. **93 is standing on the ground.** Smaller is higher |
| `dino_vy` | vertical velocity. Negative is rising |
| `ground_y` | 93, so you can compare against it without hard-coding |
| `jumping` | in the air right now |
| `ducking` | crouched right now |
| `obstacles` | up to **two** ahead, nearest first. Often **empty** |

Each obstacle has `x`, `y`, `width`, `height`, `kind`.

Nothing is normalised, scaled or interpreted. These are the game's own numbers.
Turning them into something a network can use is your job, and it matters more
than most people expect.

> **The empty list.** `state["obstacles"]` is `[]` whenever nothing is in view,
> which includes the first three seconds of every episode. Reaching straight for
> `state["obstacles"][0]` is the most common way to crash your own program.

---

## What you can do

Three actions, from `game/driver.py`:

| | | |
|---|---|---|
| `NOTHING` | 0 | keep running |
| `JUMP` | 1 | start a jump |
| `DUCK` | 2 | crouch |

`DUCK` is **held** until you send something else — it behaves like holding the
down arrow, not tapping it.

---

## Physics worth knowing

You could discover all of this by experiment. Some of it is expensive to
discover by experiment.

**You cannot jump while airborne.** A `JUMP` sent mid-air is silently ignored.
The commitment happens at takeoff and the arc plays out.

**The jump is not a fixed height.** Take-off velocity is `-10 - speed/10`, so
you jump slightly higher the faster the game is going. Gravity is 0.6 per
frame. A full jump takes roughly 35–40 frames.

**Ducking in mid-air makes you fall faster** — 3× the descent rate. It is a
fast-fall, not a crouch. Whether that is useful is for you to decide.

**The game speeds up, forever.** It starts at 6 and accelerates by 0.001 every
frame up to 13. A policy tuned at the starting speed will quietly stop working
about a minute in. This catches almost everyone: your agent gets better, so it
survives longer, so it reaches speeds it has never seen, and dies there.

**The first obstacle does not appear for 3 seconds.**

---

## What is out there

| kind | size | sits at | notes |
|---|---|---|---|
| `CACTUS_SMALL` | 17 × 35 | y = 105 | appears in groups of 1–3 |
| `CACTUS_LARGE` | 25 × 50 | y = 90 | groups of 1–3 |
| `PTERODACTYL` | 46 × 40 | y = 100, 75 or 50 | only above speed 8.5 |

Cactus groups are reported as **one wider obstacle**, so `width` tells you how
big the thing you are clearing actually is.

The dinosaur's own collision box is **44 × 47** standing, and **59 × 25**
ducking — wider and much shorter. Note that ducking does not only lower you, it
also makes you longer. The three bird heights and the two dino body shapes are
the whole puzzle; work out which combinations survive.

**Birds do not travel at the game speed.** Each one is independently a little
faster or a little slower than the world around it. You cannot tell which from
a single glance at the state — the information simply is not in one snapshot.
If that bothers you, good. It should. It is a genuine partial-observability
problem and it is the same reason self-driving cars track objects across frames
instead of classifying single images.

---

## The thing that will actually shape your day

The game runs on a wall clock. It does not wait for you.

Between reading the state and your action arriving, the world has moved on. At
speed 10, a 30 ms round trip is about 5 pixels of drift. Your information is
always slightly stale, and it gets staler the faster the game goes.

You cannot switch this off. There is no step-one-frame-at-a-time mode in this
build — it was deliberately removed, because working within real time is the
problem you were given.

Run `python setup_check.py` and it will tell you your actual decision rate. Then
consider: how many attempts does the approach you have in mind need, and how
long is that in wall-clock minutes?

---

Next: [your challenge →](03-your-challenge.md)
