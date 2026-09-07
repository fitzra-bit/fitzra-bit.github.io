# What reinforcement learning actually is

No maths in this document. Fifteen minutes, and you will have enough to start.

---

## The shape of the problem

Most software you have written is told what to do. You write the rules, the
computer follows them.

Most machine learning you have heard of is *shown* what to do. Here are a
million photos labelled "cat" or "not cat"; learn the pattern. Someone had to
produce the right answer for every example first.

Reinforcement learning is neither. Nobody tells the system what to do, and
nobody knows the right answer to show it. Instead it acts, sees what happens,
and gets a number back saying how well things are going. That is the entire
signal. It has to work out the rest.

The loop is small enough to write out:

```
        ┌──────────────────────────────────┐
        │                                  │
   [ look at the world ]                   │
        │                                  │
   [ choose an action ]                    │
        │                                  │
   [ world changes, you get a reward ]     │
        │                                  │
        └──────────────────────────────────┘
```

For our dinosaur:

| | |
|---|---|
| **World** | position and speed of the dino, what obstacles are ahead |
| **Action** | do nothing, jump, or duck |
| **Reward** | still alive, and how far you have run |

That is it. That is the whole framework. Everything else is detail about how
to do it well.

---

## Why this is harder than it sounds

Three problems show up immediately, and they are the same three problems in
every RL system anyone has ever built.

### 1. Which action was the mistake?

Your dinosaur runs for eight seconds and hits a cactus. Which of the roughly
240 decisions it made was the bad one?

Almost certainly not the last one. By the time you are close enough to the
cactus to see the crash coming, it is too late — the mistake was jumping half
a second too early, or not jumping at all a moment before that. The failure
shows up somewhere quite far from its cause.

This is **credit assignment**, and it is the central difficulty of the field.
A reward arrives, and you have to work out which of your past choices earned
it. Everything clever in RL is, in some form, an attempt at this.

### 2. You cannot learn about what you never try

If your agent never jumps, it never discovers that jumping clears cacti. If it
only ever does the thing that has worked so far, it will never find the thing
that works better.

But if it keeps trying random things to find out, it plays badly while doing
so. Every RL system has to trade off **exploring** against **exploiting**, and
there is no universally right answer. Watch for it in your own agent: you will
recognise it when you see it stuck in a mediocre habit.

### 3. Learning takes an enormous number of attempts

This is the one that will actually shape your afternoon.

The dinosaur has to try, fail, and adjust — over and over. Published results on
games like this typically involve hundreds of thousands to millions of
attempts. You have a real browser running in real time, at roughly thirty
decisions a second.

Do the arithmetic before you commit to an approach. It changes what is sensible
to build.

---

## The vocabulary

Enough to follow along, and to talk to Claude Code without being bluffed:

**State** — what your agent can see right now. Note *can see*: real agents
rarely see everything. Ours cannot see how fast a bird is flying from a single
glance, only where it currently is.

**Action** — what it can do. Ours has three options.

**Reward** — the number that says how well it is doing. Choosing this well is
subtle. Reward "distance travelled" and you may get an agent that sprints into
the first cactus. Reward "staying alive" and you may get one that never takes a
risk. What you reward is what you get, including when that is not what you
meant.

**Policy** — the thing that turns a state into an action. Your agent *is* a
policy. It can be a neural network, or a handful of if-statements. Both are
policies. Only one of them fits in a lunch break.

**Episode** — one attempt, start to crash.

**Sample efficiency** — how much a system learns per attempt. Rarely the
headline in a paper. Frequently the thing that decides whether you get a result
today.

---

## What actually gets used

Roughly in order of how much data they need:

**Hand-tuned rules.** "Jump when the obstacle is closer than X." Not learning at
all, but it is a real baseline, and an honest one to measure against. Do not
skip it out of embarrassment — if your neural network cannot beat five lines of
if-statements, that is important information about your neural network.

**Search over a few parameters.** Write a policy with a small number of knobs,
try many settings, keep what scores best. Needs tens to hundreds of attempts.
This is a genuine and respectable family of methods — evolutionary strategies
live here.

**Learning a value function.** The Q-learning and DQN family. Learn to predict
how good each action is in each situation, from experience. Powerful, general,
and hungry: thousands of episodes minimum.

**Learning a policy directly.** Policy gradients, PPO, and friends. What most
modern systems use. Hungrier still.

The instinct is to reach for the most sophisticated option. The engineering
judgement is to reach for the one that fits your budget. Today, your budget is
measured in decisions per second, and it is small.

---

## Where this shows up outside games

The dinosaur is a toy. The pattern is not:

- **Control** — data centre cooling, robot arms, chemical plants
- **Scheduling** — traffic signals, factory lines, delivery routing
- **Recommendation** — treating what to show as a sequence of decisions, not a single prediction
- **Language models** — RLHF, which is how the assistant you are about to use was tuned

Every one has the same shape as the dinosaur: repeated decisions, delayed
consequences, and no labelled right answer. And every one has the same
awkward question underneath — *where do the attempts come from?* That question
is coming for you in about an hour.

---

Next: [the game and what you can see →](02-the-game-and-state.md)
