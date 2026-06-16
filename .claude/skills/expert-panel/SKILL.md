---
name: expert-panel
description: >-
  Dissect a complex, cross-functional, or high-stakes decision by running it
  through a panel of distinct expert personas modeled on a traditional IT
  department — CIO, business leaders, sourcing, legal, cyber, infrastructure,
  operations, and an independent (Bain-style) consultant. Use when a problem has
  competing priorities, multiple stakeholders, real trade-offs, or no obvious
  right answer, and you want structured, decision-grade analysis rather than a
  single point of view. Triggers: "run this through the panel", "what would the
  experts say", "stress-test this decision", "give me the cross-functional view",
  vendor/build-vs-buy/migration/investment/policy decisions.
---

# Expert Panel

A repeatable engine that turns any problem into decision-grade analysis by
running it through eight expert personas with genuinely competing mandates, then
synthesizing — not averaging — their views into a recommendation.

The value of this method is **structured disagreement**. A flat consensus is a
failure mode. Your job is to surface where the experts conflict, why, and what
that means for the decision.

## When to use

Use for problems with competing priorities, multiple stakeholders, real
trade-offs, or no obvious right answer — vendor selection, build-vs-buy,
migrations, security/policy calls, capital investment, org/process change.

Do **not** use for simple factual lookups, single-domain questions with a clear
answer, or tasks that are pure execution. Say so and answer directly instead.

## The panel

Eight personas. Full definitions — mandate, primary fear, biases, deal-breakers,
reflexive questions — are in `personas.md`. **Read that file before running.**

| Persona | One-line mandate |
|---|---|
| CIO | Strategic alignment & board credibility; the decision-maker who weighs the panel |
| Business leaders | Speed to a capability that moves their P&L |
| Sourcing / Procurement | Best commercial terms, vendor leverage, no lock-in |
| Legal | Limit liability, ensure compliance, protect data rights |
| Cyber / Security | Reduce attack surface, protect data, contain blast radius |
| Infrastructure | Stability, scalability, maintainability, low tech debt |
| Operations | Keep it running day-to-day; supportability and toil |
| Independent consultant (Bain-style) | Objective outside view, benchmarks, challenge the internal consensus |

The panel is the **default**, not a fixed cast. For a given problem you may
down-weight personas to near-zero, or add one (common additions: CFO/Finance,
Data/Privacy officer, Enterprise Architecture, End-users/Change management). If
you add or drop personas, say so and why in the framing step.

## Method

Run these phases in order. Do not skip the independence step — it is what keeps
the analysis from collapsing into agreement.

### 1. Frame the decision
State, crisply:
- **The decision to be made** (the actual fork, not the topic). If the problem
  is vague, name the decision you're assuming and proceed.
- **Success criteria** — what "good" looks like, ideally 3–6 measurable or
  rankable dimensions (cost, time-to-value, risk, fit, supportability, etc.).
  These become the scoring axes for options later.
- **Constraints** — budget, deadlines, regulatory, technical, political.
- **Key assumptions and unknowns** — what you're taking as given, and what you
  don't know that matters.

### 2. Weight the panel
Score each persona's relevance to *this* problem (0 = ignore, 1 = minor, 2 =
material, 3 = central). Spend analytical effort in proportion to weight. State
the weighting in one line each so the reader sees where the stakes are.

### 3. Independent positions
For each persona with weight ≥ 1, write an independent brief **without
referencing the others yet**. Each brief contains:
- **Position** — what this persona wants to happen.
- **Why** — reasoning from their mandate and what they optimize for.
- **Steelman + attack** — the strongest case *for* the proposal from their seat,
  then the strongest case *against*. Both are mandatory; this defeats groupthink.
- **Red lines** — their non-negotiables / deal-breakers.
- **What they need answered** — the open questions that would change their view.

Keep each persona in character. A persona that agrees with everyone is being
written wrong — find the friction their mandate creates.

### 4. Map the tensions
This is the core deliverable. Identify the 3–6 sharpest **conflicts between
personas** (e.g., Cyber "no" vs. Business "now"; Sourcing cheapest vs. Infra
best-fit; Legal liability vs. everyone's momentum). For each: who's on each side,
what the trade-off actually is, and what would resolve it. Note any *false*
conflicts that dissolve under a clarifying fact.

### 5. Outside view (consultant pass)
The Bain-style persona now challenges the emerging internal consensus: bring a
benchmark or market comparison, name what best-in-class does, surface a reframe
or option the insiders missed, and call out where the panel is rationalizing.

### 6. Build options
Derive 2–4 genuinely distinct options (not strawmen). Score each against the
success criteria from step 1 in a compact table. Include a "do nothing / defer"
option where it's legitimate.

### 7. CIO synthesis & recommendation
The CIO persona weighs the tensions and **decides** — it does not average. Output:
- The recommended option and the rationale tying back to success criteria.
- **Recorded dissents** — which personas object and what they'd give up.
- **Confidence level** (low/medium/high) and the assumptions it rests on.

### 8. Pre-mortem & decision triggers
- **Pre-mortem**: it's 12 months later and this failed — what happened? 2–4
  plausible failure modes with mitigations.
- **Decision triggers**: the specific new facts that would *flip* the
  recommendation. This is what makes the analysis revisable rather than final.
- **Open questions & next steps**: what to go find out, and the immediate moves.

## Output

Produce the deliverable using `output-template.md` as the structure. Lead with
the executive summary (decision + recommendation + confidence) so a busy reader
gets the answer first; the per-persona detail and tension map support it below.

Scale depth to the problem: a small call gets a tight pass (framing, top 3
weighted personas, tensions, recommendation); a major decision gets the full
treatment. State which mode you ran.

## Calibration notes

- **Disagreement is the product.** If the personas converge easily, you've either
  got an easy problem (say so) or you're not pushing the personas hard enough.
- **Don't flatter the proposal.** The panel exists to find what's wrong before
  reality does. The pre-mortem and red lines are not optional decoration.
- **Stay decision-useful.** Every section should change what the reader does next.
  Cut anything that doesn't move the decision.
- **Be honest about confidence.** Mark assumptions and unknowns plainly; a
  confident-sounding answer built on a shaky assumption is the dangerous output.
