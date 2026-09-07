# Segment — from a dinosaur to a production line

**Facilitator material. Runs after the dino session, ~30 minutes.**

The question this answers is the one somebody in the room is already thinking:
*that was a game — what does it have to do with my job?*

The honest answer is that the machinery is identical and the hard parts are the
same, but the results are less flattering to the sophisticated method than the
morning implied. That is what makes it worth showing.

---

## The setup

`factory_sim/` models a five-step widget line. Each step has a capacity, a yield
rate and a recurring cost, and a menu of possible upgrades with capital costs.
Throughput is limited by the bottleneck step; effective yield is the product of
every step's yield. You have a capital budget and have to decide what to buy.

```bash
cd factory_sim
python main.py --inspect-only
```

Thirty seconds, and it shows the baseline: **CNC machining is the bottleneck at
80 u/h, and it also has the worst yield at 91%.** The whole line runs at 80 u/h
because of one machine. Gross profit is $1.01M a period.

That picture is worth pausing on. Everyone recognises it.

---

## The mapping — say this explicitly

| | Dinosaur | Production line |
|---|---|---|
| **State** | obstacles, speed, position | capacity, yield and cost at each step; budget left |
| **Action** | jump, duck, nothing | which upgrade to buy next |
| **Reward** | distance survived | change in profit per dollar of capital |
| **Episode** | one run until you crash | one investment programme until the budget runs out |

Same loop. Same three hard problems from this morning:

- **Credit assignment** — which purchase actually produced the gain? The one
  that lifted the bottleneck, or the one three steps earlier that made lifting
  it worthwhile?
- **Exploration** — you cannot buy the same machine twice to find out.
- **Sample budget** — you get one real factory, and one shot per year. This is
  the same constraint they hit at 30 decisions per second, now with capital
  attached.

---

## The demo

Three agents, same problem. Greedy ROI always buys the best immediate return.
Random search samples thousands of purchase sequences. The DQN learns
long-horizon values. Full run, about 25 seconds:

```bash
python main.py
```

### The result nobody expects

| Agent | Throughput | Yield | Gross profit / period | Capital spent |
|---|---|---|---|---|
| Baseline | 80 u/h | 85.6% | $1.01M | — |
| Greedy ROI | 202 u/h | 94.6% | $2.80M | $328.5K |
| Random search | 202 u/h | 94.6% | **$2.81M** | $326.5K |
| DQN | 202 u/h | 94.6% | $2.80M | $328.5K |

**They all find the same answer.** All three buy essentially the same set of
upgrades, differing only in order. Random search actually edges the DQN by
$10K a period while spending $2K less — it skipped one marginal purchase that
the other two made because they still had budget left.

Let that land before explaining it. A room that has just spent an afternoon on
reinforcement learning expects the neural network to win.

The reason it does not: **at $350K there is enough capital to buy everything
worth buying.** Greedy's myopia costs nothing when you are not forced to choose.
The problem looks hard and is not.

---

## Then make it hard

The interesting question is not *which agent wins* but *when does sophistication
start to pay*. Tighten the budget so the constraint actually binds:

```bash
python main.py --scenario ../dtx_facilitator/factory_segment/scenarios/widget_factory_constrained.yaml
```

| Budget | Greedy ROI | Random search | DQN | Greedy's shortfall |
|---|---|---|---|---|
| $350K | $2.80M | $2.81M | $2.80M | none |
| $180K | $1.69M | **$1.74M** | **$1.74M** | **−$50K / period** |
| $80K | $1.67M | **$1.68M** | **$1.68M** | −$10K / period |

At $180K, greedy is **$50K a period behind** — about 3%, and over the
scenario's 24-period horizon roughly **$1.2M** of foregone profit. It gets there
by taking the best available return each time and thereby spending money it
needed for a better combination later.

That is the entire case for planning over greed, in one number, on a problem
that looks like a plant.

---

## The part that is most useful to a GE audience

**The DQN never beats random search.** Not at any budget.

And it is less reliable. Three repeat runs at $180K:

| | run 1 | run 2 | run 3 |
|---|---|---|---|
| Greedy ROI | $1.69M | $1.69M | $1.69M |
| Random search | $1.74M | $1.74M | $1.74M |
| DQN | $1.74M | **$1.70M** | $1.74M |

Greedy and random are deterministic. The DQN carries training variance, and one
run in three landed below plain random search.

So the honest conclusion is not "use reinforcement learning." It is:

1. **Always build the dumb baseline.** Greedy ROI captured 98% of the available
   value at full budget, in milliseconds, and you can explain it to a plant
   manager in one sentence.
2. **Sophistication has to earn its place.** Here the thing that beat greedy was
   *search*, not *learning*. The action space is small enough to sample well,
   so nothing more clever was required.
3. **RL earns its place when you cannot enumerate.** Long horizons, large or
   continuous action spaces, decisions that must be made repeatedly under
   changing conditions. Scheduling a line hour by hour, not choosing ten
   upgrades once.
4. **Variance is a cost.** A method that is better on average and occasionally
   worse is a harder thing to put in front of a capital committee than a method
   that is slightly worse and always the same.

---

## Closing the loop back to this morning

One more thing to say, and it is the strongest link between the two halves.

**This is a simulator.** Every number here comes from a model of a factory, not
a factory. The upgrade specs are estimates, the yield deltas are assumptions,
the demand is fixed.

They already know what that means, because they spent the afternoon watching a
policy trained in a fast simulation behave differently in the real-time browser.
Same gap, different stakes: this time being wrong means capital is committed to
the wrong machine.

Which is why the useful output of a model like this is rarely "buy these ten
things." It is *the bottleneck is CNC machining and its yield matters more than
its capacity* — a piece of understanding that survives the model being somewhat
wrong. Point at `factory_chat/` if you want to show where that goes: the same
plant model behind a conversational interface, so the person who actually knows
the line can interrogate it.

---

## Running it live — practical notes

- Full three-agent run: **~25 seconds**. Inspect-only: instant.
- Needs `pyyaml`, `rich`, `numpy`, `torch` (`factory_sim/requirements.txt`).
  Torch is the slow install — do it well before you present.
- Every run writes an HTML report next to the scenario file
  (`widget_factory_dqn.html` and friends). Good for sharing afterwards.
- **The DQN result varies between runs.** Do not script the talk around it
  producing $1.74M. Frame the variance as the point and either outcome works
  for you — that is the safest way to demo a stochastic method live.
- The two budget variants live in `scenarios/` next to this file, so the
  comparison reproduces without editing the original scenario.
