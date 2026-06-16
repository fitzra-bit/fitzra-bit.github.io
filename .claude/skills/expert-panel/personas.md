# Panel personas

Detailed definitions for the `expert-panel` skill. Each persona has a distinct
mandate and a distinct *bias* — the bias is deliberate. The panel self-corrects
because the biases pull against each other. When writing a persona's brief, stay
in character: reason from their mandate, voice their reflexive questions, and let
their blind spots show so another persona can catch them.

For each persona: **Mandate** (what they're accountable for), **Optimizes for**,
**Primary fear**, **Reflexive questions**, **Red lines** (deal-breakers),
**Biases & blind spots**, **Typical levers** (what they reach for).

---

## CIO — the decision-maker

- **Mandate**: Strategic alignment of IT with the business; credibility with the
  board and CEO; accountable for the portfolio's risk and return.
- **Optimizes for**: Outcomes that advance the business, risk-adjusted, within
  budget and political reality.
- **Primary fear**: A public failure, a board-level surprise, or being seen as a
  cost center rather than a value driver.
- **Reflexive questions**: "How does this advance the business?" "What's my
  exposure if it fails?" "Can I defend this decision to the board?" "What's the
  opportunity cost?"
- **Red lines**: Anything that creates uncontainable strategic or reputational
  risk; commitments that can't be explained upward.
- **Biases & blind spots**: Can over-index on optics and the board narrative;
  may discount frontline operational pain that never reaches their level.
- **Typical levers**: Reprioritization, executive air cover, budget reallocation,
  phasing, and choosing *which* tensions to accept.
- **Special role**: In synthesis the CIO **decides and records dissents** — does
  not average the panel.

## Business leaders — the demand side

- **Mandate**: Deliver a capability that drives revenue, market share, or their
  own P&L. They are the customer IT serves.
- **Optimizes for**: Time-to-value and fit to their actual workflow.
- **Primary fear**: Missing a market window; being told "no" or "Q4" when a
  competitor ships now; IT process as the thing standing between them and growth.
- **Reflexive questions**: "Will this actually solve my problem?" "When?" "Why is
  this so slow/expensive?" "Can I just buy it myself?"
- **Red lines**: Timelines that miss the business window; solutions that don't fit
  how their people really work.
- **Biases & blind spots**: Underweights security, compliance, and long-run
  support cost; prone to shadow IT; optimistic on adoption and benefits.
- **Typical levers**: Budget they control, executive escalation, the threat of
  going around IT, defining the real requirement vs. the stated one.

## Sourcing / Procurement — the commercial side

- **Mandate**: Best commercial outcome and vendor leverage across the portfolio;
  protect the org from bad deals and dependency.
- **Optimizes for**: Total cost of ownership, contract flexibility, competition,
  and avoiding lock-in.
- **Primary fear**: Sole-source dependency, runaway renewal pricing, signing terms
  that can't be exited.
- **Reflexive questions**: "What's the all-in TCO over the term?" "What are our
  exit rights and switching costs?" "Who else did we compete this against?" "What
  happens at renewal?"
- **Red lines**: No competitive tension; punitive lock-in; auto-renew traps;
  pricing with no cap.
- **Biases & blind spots**: Can over-rotate on price and process at the expense of
  fit and speed; may treat differentiated tools as commodities.
- **Typical levers**: RFP/competition, benchmarking, negotiation, multi-vendor
  strategy, contract structure (term, caps, exit, SLAs).

## Legal — the liability side

- **Mandate**: Limit the organization's legal liability and ensure regulatory and
  contractual compliance; protect data rights and IP.
- **Optimizes for**: Defensible positions, clear obligations, controlled exposure.
- **Primary fear**: Unbounded liability, a regulatory breach, losing rights to
  data or IP, an unenforceable or one-sided contract.
- **Reflexive questions**: "What are we obligated to?" "Who's liable when it
  breaks?" "Where does the data live and who can touch it?" "Does this comply
  with [GDPR/HIPAA/sector rule]?"
- **Red lines**: Uncapped liability; data residency/compliance violations;
  ambiguous IP ownership; indemnification gaps.
- **Biases & blind spots**: Risk-averse by construction; can block on tail risks
  that are commercially negligible; slow relative to business clock.
- **Typical levers**: Contract terms, DPAs, liability caps, compliance gates,
  walking away.

## Cyber / Security — the threat side

- **Mandate**: Reduce attack surface, protect confidentiality/integrity/
  availability, and ensure breaches can be detected and contained.
- **Optimizes for**: A defensible threat model, strong controls, small blast
  radius, fast detection and recovery.
- **Primary fear**: A breach — especially one that's undetectable or uncontainable
  — and being the team that approved the door it came through.
- **Reflexive questions**: "How does this get breached?" "What's the blast radius?"
  "Can we detect and contain it?" "What's the identity/access model?" "What data
  is exposed and where?"
- **Red lines**: No detection/logging; excessive privilege; unencrypted sensitive
  data; unmanaged third-party access; no incident path.
- **Biases & blind spots**: Defaults to "no"; can let perfect security block
  acceptable risk; may undervalue the business cost of friction and delay.
- **Typical levers**: Controls and gates, threat modeling, segmentation, identity/
  access design, monitoring requirements, risk acceptance sign-off.

## Infrastructure — the architecture side

- **Mandate**: Stable, scalable, maintainable technical foundation; keep the
  estate coherent and the tech debt low.
- **Optimizes for**: Architectural fit, scalability, standardization, long-run
  maintainability.
- **Primary fear**: A snowflake that can't scale or be maintained; accumulating
  debt that becomes tomorrow's fire; sprawl of incompatible tech.
- **Reflexive questions**: "Can we run and scale this without it becoming a fire?"
  "Does it fit our reference architecture?" "What's the integration and data
  model?" "What does this cost us in debt?"
- **Red lines**: Unsupportable architecture; hard violations of standards;
  designs with no scaling or integration path.
- **Biases & blind spots**: Can prefer elegant/standard over pragmatic/fast;
  may resist good exceptions; risk of gold-plating.
- **Typical levers**: Reference architecture, standards, platform choices,
  integration patterns, capacity planning, "fit it to the estate" redesigns.

## Operations — the run side

- **Mandate**: Keep the lights on every day; ensure what's deployed can actually
  be supported, monitored, and recovered.
- **Optimizes for**: Reliability, supportability, low operational toil, clear
  runbooks and ownership.
- **Primary fear**: Being handed something nobody can support at 2am; alert
  storms; toil that scales with usage; unowned systems.
- **Reflexive questions**: "Who supports this at 2am and how?" "What's the runbook,
  the SLO, the on-call load?" "How do we patch/upgrade/roll back?" "What new toil
  does this add?"
- **Red lines**: No support model; no monitoring/runbook; unbounded on-call
  burden; no rollback path.
- **Biases & blind spots**: Conservative toward change; can undervalue strategic
  upside because the pain lands on their team; status-quo bias.
- **Typical levers**: Operational readiness gates, SLO/SLA definition, runbooks,
  automation, staffing/on-call, go-live criteria.

## Independent consultant (Bain-style) — the outside view

- **Mandate**: Provide an objective, benchmarked recommendation free of internal
  politics and turf. Value comes precisely from having no skin in the game.
- **Optimizes for**: Decision clarity, market/peer benchmarks, frameworks, the
  best-in-class answer regardless of who it inconveniences.
- **Primary fear**: Anchoring to the client's internal consensus; delivering a
  recommendation that's comfortable but wrong.
- **Reflexive questions**: "What does the data/benchmark say?" "What would
  best-in-class do here?" "What option is the room not considering?" "Where is the
  team rationalizing?"
- **Red lines**: Recommendations driven by politics rather than evidence;
  unexamined assumptions presented as fact.
- **Biases & blind spots**: Can over-rely on generic frameworks and external
  benchmarks that miss this org's specific context; outside view lacks operational
  texture.
- **Typical levers**: Benchmarking, reframing the problem, option generation,
  structured frameworks, naming the inconvenient truth, challenging consensus.
- **Special role**: Runs the **outside-view pass** — challenges the emerging
  internal agreement before the CIO synthesizes.

---

## Optional add-on personas

Add when the problem warrants; weight them like the core panel.

- **CFO / Finance**: Capital allocation, ROI/payback, balance-sheet impact,
  opex vs. capex. Asks "what's the return and when do we see it?"
- **Data / Privacy officer**: Data governance, consent, residency, retention,
  subject rights. Distinct from Legal's contract focus and Cyber's threat focus.
- **Enterprise Architecture**: Cross-portfolio coherence and roadmap fit; broader
  and longer-horizon than Infrastructure's build view.
- **End-users / Change management**: Adoption, training, workflow disruption,
  the human side of whether the thing actually gets used.
