# Teach a dinosaur to run

You are going to build something that learns to play a game — one you have
almost certainly played yourself, on a train, when the wifi died.

You do not need a machine learning background. You do not need to be a strong
programmer. You have Claude Code, and the point of this session is partly to
show you how far that gets you on a real problem, not a toy one.

The problem is real. Everything in this folder was pulled from a working
project, and it has the rough edges a working project has.

---

## Start here

```bash
cd dtx_dino_challenge
pip install -r requirements.txt
python setup_check.py        # confirms your machine can run everything
python play.py               # watch the starter agent be extremely bad
```

If `setup_check.py` is unhappy, it will tell you what to fix. Windows users:
see [docs/05-setup.md](docs/05-setup.md) first, there is a known trap.

---

## What is here

| | |
|---|---|
| **`agent.py`** | **The file you change.** Everything else is scaffolding. |
| `play.py` | Watch your agent, in a visible browser. For understanding behaviour. |
| `bench.py` | The official scored run. For numbers. |
| `setup_check.py` | Confirms your environment works. |
| `game/dino.html` | The actual game. You may read it. |
| `game/driver.py` | Talks to the browser. You should not need to touch it. |

And five short documents, in the order they will be useful:

1. **[What reinforcement learning actually is](docs/01-reinforcement-learning.md)** — no maths, no prerequisites
2. **[The game and what you can see](docs/02-the-game-and-state.md)** — the state you get, and the physics that will surprise you
3. **[Your challenge](docs/03-your-challenge.md)** — what to build, and how to think about it
4. **[The competition](docs/04-competition.md)** — two rounds, how scoring works, what is allowed
5. **[Setup and troubleshooting](docs/05-setup.md)** — when something will not run

---

## The one thing to understand before you start

The game runs in **real time**. It does not pause and wait for your agent to
think. Run `setup_check.py` and it will tell you how many decisions per second
your machine actually manages — probably somewhere around 30.

Sit with that number for a moment. Systems like this are normally trained on
millions of attempts. At 30 decisions a second, an hour of solid running gets
you around a hundred thousand — and that is if nothing goes wrong.

That constraint is not an accident or an oversight. It is the interesting part,
and how you respond to it is most of what you will actually learn today.

---

## Using Claude Code well

Use it constantly. That is the point. But a few things make the difference
between it being a search engine and it being a collaborator:

- **Ask it to explain the game to you.** `game/dino.html` is right there. "Read
  game/dino.html and tell me how the jump physics work" is a fair question and
  a genuinely useful answer.
- **Make it justify things.** If it hands you an algorithm, ask why that one,
  what it assumes, and how many attempts it needs before it works. Sometimes
  the honest answer is "more than you have," which is worth knowing before you
  spend forty minutes on it.
- **Describe the behaviour you are seeing, not just the error.** "It clears
  cacti but always dies on the first bird" gets you much further than "it does
  not work."
- **Let it be wrong.** It will confidently suggest things that do not fit the
  time budget or the constraints. Noticing that is a skill worth practising,
  and it is far easier to practise here than on something that matters.
