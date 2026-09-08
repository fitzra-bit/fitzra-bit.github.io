# Your challenge

Build something in `agent.py` that keeps the dinosaur alive.

That is the whole brief. What follows is not a specification — it is the set of
questions worth thinking about, roughly in the order they will hit you.

---

## The only rule that matters

`Agent.act(state)` returns `0`, `1` or `2`.

Everything else — whether you use a neural network, how you learn, what you
remember between steps, whether you learn at all — is yours.

---

## Get a number on the board first

Before anything sophisticated:

```bash
python play.py      # watch the starter agent
python bench.py     # get its score
```

The starter agent jumps on a timer, blind. Whatever it scores is your floor,
and you now have a number to beat and a loop you know works. Improving
something is a much better position than starting from nothing.

---

## Four questions, in the order they will bite

### 1. What does your agent look at?

The state is raw. `x = 483.2`, `speed = 7.4`, `dino_y = 93.0`.

Feeding those numbers straight into a neural network works badly, and the
reason is worth understanding rather than taking on trust. Ask Claude Code why
inputs on wildly different scales cause problems. It is a five-minute
explanation that will serve you for years.

Things worth considering:

- Is *absolute* obstacle position what matters, or the **gap** between you and it?
- Is a gap in pixels meaningful on its own, when the game gets faster? At speed
  6 a 200-pixel gap is a long way off. At speed 13 it is nearly upon you.
- What do you do when `obstacles` is empty? "No obstacle" needs to be
  representable, not crash.
- Is a bird's `y` more usefully a number, or three separate yes/no facts?

This is called feature engineering. It is unglamorous and it is very often
where the actual improvement comes from.

### 2. Where does the reward come from?

Nobody hands you one. `score` is available, and whether that is the right thing
to learn from is a real question.

Consider: if you reward distance travelled, what does an agent that maximises
it do at the first cactus? If you reward survival only, what does a maximally
cautious agent look like? What you reward is what you get.

### 3. How does it improve?

Honestly answer this before you write the code: **how many attempts does my
approach need, and how many can I actually run?**

`setup_check.py` gave you decisions per second. An episode is tens of seconds.
Multiply it out. Then decide.

Some shapes that fit a short session:

- **Tune by hand.** Write the policy, watch it fail, change a number. You are
  the learning algorithm. Startlingly effective, and you will understand every
  decision it makes.
- **Search a few parameters.** Small number of knobs, try many combinations,
  keep the best. Tens of attempts, not thousands.
- **Learn online from what just happened.** Adjust after every episode based on
  how it went. Fits real time, if your update is cheap and your policy is small.

And one that probably does not:

- **Train a deep network from scratch.** Claude Code will write you a beautiful
  DQN. It will also need far more experience than this afternoon contains. This
  is not a warning against ambition — it is the actual engineering constraint,
  and noticing it yourself is worth more than being told.

### 4. What is actually killing you?

Score alone will not tell you. `play.py` will. Watch it.

"Dies at the first cactus every time" and "clears twenty cacti then dies to the
first bird" are completely different problems with completely different fixes,
and they can produce the same number.

---

## Working with Claude Code

You have an assistant that can read this entire codebase in seconds and write
whatever you describe. Some ways to get more out of it:

**Point it at the game.** "Read game/dino.html and explain how the jump arc
works" — it will, accurately, and you will design better for knowing.

**Ask for the cost, not just the code.** "Roughly how many episodes before this
starts working?" is the question that separates an approach that will produce a
result today from one that will produce a beautiful, untrained network at 4pm.

**Describe symptoms.** "It jumps too early on large cacti but is fine on small
ones" is a far more useful prompt than "make it better."

**Push back.** If the first suggestion does not fit your constraints, say so.
"That needs thousands of episodes and I have about two hundred — what changes?"
is a completely reasonable thing to say, and the answer is usually good.

**Have it explain its own code.** If you cannot say what a line does, you cannot
debug it at 3pm when it stops working. Ask.

---

## What good looks like

Not the biggest number. By the end you should be able to say:

- what your agent looks at, and why those things
- why you chose your approach over the alternatives
- what is currently killing it, and what you would try next

An agent scoring 400 whose author can answer those three questions has learned
more than one scoring 900 that was pasted in whole.

---

Next: [the competition →](04-competition.md)
