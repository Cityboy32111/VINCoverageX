# Demo Storyboard — CoverageX Vehicle Signal Graph (Manus-ready)

**Product name (on screen):** CoverageX Vehicle Signal Graph
**Hero headline:** *Find the vehicles most ready for protection*
**Subheadline:** *CoverageX Vehicle Signal Graph ranks dealer inventories and
VINs by coverage fit, repair risk, plan recommendation, and partner
opportunity.*

**Hard rule for the demo:** no consumer names, no consumer emails, no consumer
phone numbers — anywhere. Every number on screen is backed by an evidence
drawer (source URL + timestamp + confidence + short span).

---

## Narrative arc (what the buyer feels)

1. **Market** — "There's real, rankable opportunity in this market."
2. **Dealers** — "These specific dealers are the best partner targets, and here's why."
3. **One dealer** — "Look inside this dealer: the inventory is sitting in the protection sweet spot."
4. **VINs** — "Down to the individual vehicle, here's the fit, the risk, and the plan."
5. **Action** — "Here's exactly who to call and what to say."
6. **Trust** — "And every claim is sourced."

---

## Screen-by-screen storyboard

### Section 1 — Market Overview
- KPI tiles: # dealers analyzed, # VINs analyzed, # valid VINs, % decoded,
  # coverage-ready VINs, # high-repair-risk VINs, avg coverage-readiness.
- Small map / market label ("Los Angeles County, CA").
- Distribution chart: vehicles by mileage band and by class (truck/SUV/luxury/EV/economy).
- **Message:** the market has a quantifiable, prioritizable opportunity surface.

### Section 2 — Dealer Opportunity Rankings
- Sortable table: dealer name, type, inventory count, coverage-ready count,
  coverage-ready share, high-repair-risk count, truck/SUV/luxury share,
  **Dealer Coverage Opportunity Score (0–100)**, recommended pitch angle.
- Color band: Priority (≥70) / Qualified (50–69) / Monitor (<50).
- **Interaction:** click a dealer → Section 3.

### Section 3 — Selected Dealer Profile  *(the wow moment)*
The flagship view. On clicking a dealer, the buyer sees:

```
Dealer: [Dealer Name]            Type: Independent used      Market: LA County
──────────────────────────────────────────────────────────────────────────
143 vehicles      61 coverage-ready      22 high repair risk
Recommended plan mix:  35% Signature   45% Premium   20% Executive
Top risk themes:  transmission · electrical · AC · powertrain
Best segment:  used full-size trucks & SUVs in 70k–130k mile window
Recommended target persona:  F&I Director
Recommended pitch:
  "Your used inventory is sitting in the prime protection window.
   CoverageX can attach protection to the vehicles where repair
   anxiety is highest."
Estimated attach opportunity:  [coverage-ready count × illustrative attach rate]
──────────────────────────────────────────────────────────────────────────
[ View VINs ]   [ View evidence ]   [ Activation layer ]
```

- Inventory-composition donut (class mix) and mileage-band histogram.
- **Message:** in one click, a named, prioritized, explained partner.

### Section 4 — VIN-Level Table
- One row per vehicle: VIN (or masked display VIN), year/make/model/trim, body
  class, mileage, price, mileage band, **coverage-readiness score**, **repair-risk
  score**, **plan-fit recommendation**, recall count (model-level), top risk
  themes, exclusion/review flags, listing URL.
- Two quick filters/tabs: **Top 25 by coverage readiness** · **Top 25 by repair risk**.
- **Interaction:** click a VIN → expands its scores + evidence drawer.

### Section 5 — Coverage Readiness Score (per VIN detail)
- Gauge (0–100) + the sub-score breakdown (mileage fit, age fit, repair-cost
  exposure, class lift, warranty gap, data completeness).
- Plain-language verdict: *Coverage-Ready / Watch / Low fit*.

### Section 6 — Repair Risk Score (per VIN detail)
- Gauge (0–100) + sub-score breakdown (mileage, age, class, powertrain
  complexity, recall/component, complaint themes).
- Top contributing **component risk themes** as chips. Labeled *estimated /
  model-level signal*.

### Section 7 — Plan Fit Recommendation (per VIN detail)
- Recommended tier badge (Essential / Signature / Premium / Executive).
- `plan_fit_reason` sentence.
- (Optional) competitor-coverage context chip ("competitors emphasize powertrain
  on this segment").

### Section 8 — Evidence Drawer (always one click away)
- For any number on screen: `source_name`, `source_url` (clickable),
  `extraction_date`, `confidence`, short `evidence_span`, and `risk_tier` badge
  (SAFE PUBLIC / SAMPLE ONLY / LICENSE REQUIRED).
- Inferred values are visibly tagged "estimated / model-level."
- **Message:** this is defensible, auditable intelligence — not a scrape.

### Section 9 — B2B Activation Layer
- Recommended **personas** to approach (F&I Director, GM, Used-Car Manager,
  Partnerships Lead) — **roles, not people**, in the demo.
- `activation_source` + `contact_enrichment_status` (= "not started" in Phase 1).
- Clear banner: **"No consumer data. B2B partner roles only."**
- Production note: "Named business contacts available via licensed B2B
  enrichment in a later, approved phase."

---

## The wow moment (scripted)

> The presenter clicks one dealer. The screen resolves to: **143 vehicles, 61
> coverage-ready, 22 high repair risk. Recommended plan mix 35% Signature / 45%
> Premium / 20% Executive. Top risk themes: transmission, electrical, AC,
> powertrain. Recommended target: F&I Director.** Then the pitch line appears:
> *"Your used inventory is sitting in the prime protection window. CoverageX can
> attach protection to the vehicles where repair anxiety is highest."* The buyer
> immediately sees a named partner, a sized opportunity, and a ready pitch — all
> sourced.

---

## Demo data integrity

- Built from the **real Phase-1 sample** (one flagship dealer + market context),
  not fabricated. If sample size falls short, the demo states the real numbers
  and labels any illustrative element.
- Attach-rate figures used for "estimated attach opportunity" are labeled
  **illustrative** unless CoverageX provides its own benchmark.
- The same storyboard is emitted as `outputs/coveragex_demo_summary.md` and the
  build spec as `outputs/manus_demo_prompt.md`.
