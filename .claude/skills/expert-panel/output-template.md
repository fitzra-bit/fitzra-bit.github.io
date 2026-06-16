# Output template

Structure for the `expert-panel` deliverable. Lead with the executive summary so
the answer comes first. Fill every section; if a section is N/A for a quick-mode
run, say so rather than omitting it silently. Keep prose tight and
decision-useful — cut anything that doesn't change what the reader does next.

---

## Executive summary
- **Decision**: <the actual fork being decided>
- **Recommendation**: <the chosen option, one sentence>
- **Confidence**: <low | medium | high> — <the load-bearing assumption it rests on>
- **The one tension that matters most**: <the central trade-off in a sentence>

## 1. Framing
- **Decision to be made**: …
- **Success criteria** (the scoring axes): 1) … 2) … 3) … (3–6)
- **Constraints**: budget / time / regulatory / technical / political …
- **Key assumptions**: …
- **Unknowns that matter**: …
- **Considerations sweep** (mark live / not live; note if unowned):
  - IP & ownership: …
  - Data sovereignty & government compliance: …
  - Customer & personal data: …
  - Change velocity & obsolescence: …
- **Mode**: <quick pass | full treatment> and any personas added/dropped + why.

## 2. Panel weighting
Score the full roster; bench rows that score 0 can be dropped from the table.

| Persona | Weight (0–3) | Why this weight here |
|---|---|---|
| CIO | | |
| Business leaders | | |
| Sourcing | | |
| Legal | | |
| Cyber | | |
| Infrastructure | | |
| Operations | | |
| Consultant | | |
| CDAIO | | |
| Privacy / Customer-Data | | |
| IP Counsel | | |
| Gov / Reg Compliance | | |
| Change-Velocity | | |
| _other bench (CFO, EA, Change mgmt)_ | | |

## 3. Independent positions
For each persona with weight ≥ 1:

### <Persona> (weight N)
- **Position**: …
- **Why**: …
- **Steelman (for)**: …
- **Attack (against)**: …
- **Red lines**: …
- **Needs answered**: …

## 4. Tension map
The core of the analysis — the real disagreements.

| Tension | Side A | Side B | The actual trade-off | What resolves it |
|---|---|---|---|---|
| | | | | |

- **False conflicts** (dissolve under a clarifying fact): …

## 5. Outside view (consultant)
- **Benchmark / what best-in-class does**: …
- **Reframe or missed option**: …
- **Where the panel is rationalizing**: …

## 6. Options
| Option | <criterion 1> | <criterion 2> | <criterion 3> | <criterion 4> | Net |
|---|---|---|---|---|---|
| A — … | | | | | |
| B — … | | | | | |
| C — defer/do nothing | | | | | |

Brief note on each option's character (1–2 lines) so the table isn't read cold.

## 7. Recommendation (CIO synthesis)
- **Recommended option**: … — **why**, tied to the success criteria.
- **Recorded dissents**: <persona> objects because …; they're being asked to
  accept …
- **Confidence**: <low | medium | high> and the assumptions it rests on.

## 8. Pre-mortem & decision triggers
- **Pre-mortem** (it's 12 months on and this failed):
  - Failure mode → mitigation
  - Failure mode → mitigation
- **Decision triggers** (new facts that would flip the recommendation):
  - If <X> turns out true → switch to <option>.
- **Open questions & next steps**:
  - [ ] Go find out: …
  - [ ] Immediate move: …
