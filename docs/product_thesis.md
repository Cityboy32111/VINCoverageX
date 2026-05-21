# Product Thesis — CoverageX Vehicle Signal Graph

**One-line definition:**
The CoverageX Vehicle Signal Graph identifies the vehicles and dealers most
likely to convert into *profitable* vehicle protection plans, using VIN-level
risk, mileage, repair exposure, recall exposure, inventory composition, and
partner-activation data — each signal evidence-backed and provenance-stamped.

---

## 1. Buyer problem

CoverageX is good at the *bottom* of the funnel and blind at the *top*.

Once a customer reaches the quote flow, CoverageX converts and prices well. But
the company has no systematic way to answer the upstream question: **which
vehicles, dealers, and channels should we be putting into the funnel in the
first place?** Today that decision is made with broad demographic targeting,
bought lists, and intuition. The consequences:

- **Wasted acquisition spend** on vehicles that are under OEM warranty (won't convert) or too old/high-mileage (convert but lose money on claims).
- **Generic pitches** that don't match the vehicle's actual risk profile, hurting conversion and inflating cancellations.
- **No structured dealer pipeline.** The highest-leverage channel — dealer F&I partnerships — is worked ad hoc, with no data telling the team *which* dealers are sitting on the most coverage-ready inventory.
- **No claims-risk foresight at the targeting stage.** Adverse selection is discovered after the plan is sold, not before.

The problem is not "how do we sell a plan." It is **"who and what should we be selling to, and why."**

---

## 2. Product promise

> **Show CoverageX the vehicles and dealers most ready for protection — ranked,
> explained, plan-matched, and backed by evidence — before a single quote
> begins.**

For every vehicle in scope, the graph delivers:
- A **coverage-readiness score** (is this in the profitable prime window?)
- A **repair-risk score** (how much future repair exposure?)
- A **plan-fit recommendation** with a stated reason (Essential → Executive)
- **Exclusion/review flags** (what to avoid or send to underwriting)
- A **recommended message angle**

For every dealer, the graph rolls those up into:
- A **dealer coverage-opportunity score** (0–100)
- An **inventory-composition fingerprint** (truck/SUV/luxury/EV mix, age, mileage)
- A **recommended partner pitch angle** and **F&I target persona**

And for every signal, the graph stores **source URL, timestamp, confidence, and
a short evidence span** — so CoverageX can trust, audit, and defend every claim.

---

## 3. First use case

**"Rank the used-car dealers in one market by F&I partnership opportunity, and
show me the best vehicles to attach protection to."**

Concretely, for a single market (recommended: Los Angeles County / Southern
California):

1. Discover 25–50 public used-car dealers.
2. Collect public inventory (VIN, year, make, model, trim, mileage, price, listing URL).
3. Validate and decode VINs (NHTSA).
4. Layer recalls (model-level) and a simple repair-risk model.
5. Score each vehicle (coverage readiness, repair risk, plan fit).
6. Roll up to dealer-opportunity scores and rankings.
7. Produce a buyer-ready demo for one flagship dealer plus a market overview.

The deliverable a CoverageX partnerships lead can act on Monday morning: a
ranked dealer list, a top-VIN list, a recommended plan mix, and an F&I pitch.

---

## 4. Why now

- **VIN identity is free and open.** NHTSA's vGate VIN decoder and recall data
  are public APIs with no per-call licensing cost — the identity backbone is
  available today at zero data cost.
- **Dealer inventory is publicly observable.** Modern dealer sites and
  inventory pages expose VIN, mileage, and price as public business content,
  collectable compliantly without touching any consumer PII.
- **Browser-automation collection is mature.** Apify actors (Website Content
  Crawler, Google Maps Scraper) make dealer discovery and dynamic inventory
  pages tractable without bespoke infrastructure.
- **Protection-plan economics reward precision.** Margins live or die on loss
  ratio. Any tool that improves *which* vehicles enter the funnel has direct,
  compounding P&L impact — and AI scoring makes per-VIN reasoning cheap enough
  to run across an entire market.
- **F&I channel is consolidating and data-hungry.** Dealers and their F&I
  desks increasingly expect partners to arrive with data. A provider who shows
  up with an inventory-level opportunity analysis differentiates immediately.

The enabling pieces — open VIN identity, observable inventory, cheap automation,
cheap AI reasoning — have only recently all been true at once.

---

## 5. What makes it differentiated

1. **It is a decision system, not a lookup.** A VIN decoder says *what* a
   vehicle is. The Signal Graph says *which vehicles matter, why, what to offer,
   and who to call.* That is the difference between data and a product.

2. **It is VIN-anchored and graph-shaped.** Every signal — identity, inventory,
   recall, repair pain, competitor coverage, plan fit, dealer rollup — hangs off
   a single clean VIN key and connects upward to dealers and channels. The
   connections *are* the value; isolated facts are commodities.

3. **It is evidence-backed by construction.** Every fact carries source URL,
   timestamp, confidence, and evidence span. The product can defend its claims —
   essential for a buyer making revenue and underwriting decisions.

4. **It is honest about inference.** Estimated signals are labeled estimated;
   model-level recall patterns are never presented as VIN-specific open recalls;
   no claims, title, or salvage status is asserted without a licensed source.
   This rigor is itself a differentiator versus scraped-data vendors who
   overclaim.

5. **It is compliant by design.** Public/permissioned/licensed data only, zero
   consumer PII, B2B-only enrichment. CoverageX can deploy it without inheriting
   privacy or data-rights liability.

6. **It is built as a repeatable pipeline, not a one-off scrape.** The same
   engine that scores one LA market re-runs on any market, scales to marketplace
   feeds, and upgrades to licensed claims/title data for true actuarial pricing
   support. The proof of concept is the first turn of a reusable crank.

---

## What this product is *not*

- Not a generic VIN decoder.
- Not a scraped dealer-inventory file.
- Not a consumer contact list.
- Not an actuarial rating engine (it is *pricing support* until joined to licensed claims data).
- Not a source of title/salvage/odometer truth (those require licensed providers; until then they are absent or flagged, never asserted).
