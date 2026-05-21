# Buyer Strategy Alignment — CoverageX Vehicle Signal Graph

**Buyer:** CoverageX
**Prepared by:** Accel Corporate Solutions
**Phase:** 0 (Strategy & Design — pre-collection)
**Status:** Draft for buyer review

---

## 1. What CoverageX sells

CoverageX sells **vehicle protection plans** (also called vehicle service
contracts / extended protection) that cover the cost of mechanical and
electrical repairs after a vehicle's original manufacturer warranty expires.
The product line is tiered:

| Plan | Positioning | Typical fit |
|------|-------------|-------------|
| **Essential** | Entry / powertrain-leaning coverage | Lower-risk, lower-mileage, economy vehicles |
| **Signature** | Mainstream mid-tier coverage | Moderate mileage, mainstream vehicles, moderate repair risk |
| **Premium** | Broad component coverage | Trucks, SUVs, luxury, higher mileage, known component risk |
| **Executive** | Top-tier / high-value coverage | High-value, luxury, advanced-tech, EV, high parts cost, higher claim severity |

CoverageX makes money when it attaches a plan to a vehicle whose **expected
repair exposure justifies the premium** but whose **risk profile is still
underwritable and profitable**. The economics are a balance:

- **Too little risk** (new car, under OEM warranty) → low consumer demand, weak conversion.
- **Too much risk** (very old, very high mileage, salvage, commercial use) → adverse selection, claims losses, underwriting review.
- **The profitable middle** → vehicles squarely in the *prime protection window* where consumers feel repair anxiety, repairs are plausible and costly, but the loss ratio is still manageable.

**Critical framing:** CoverageX already converts well *once a customer is in the
quote flow.* The unsolved problem is **upstream** — finding the right vehicles,
dealers, and channels to put into that funnel in the first place.

---

## 2. Where VIN, year, make, model, trim, mileage, and eligibility matter

Every lever in the protection-plan business is anchored to vehicle identity.
The VIN is the join key that makes all of it computable at scale.

| Attribute | Why it matters to CoverageX |
|-----------|-----------------------------|
| **VIN** | Canonical identity. The deterministic anchor that lets us decode the vehicle, attach recalls, attach repair-risk priors, dedupe inventory, and build an evidence trail per vehicle. Without a clean VIN, every downstream signal is fuzzy. |
| **Year (model year)** | Drives age, OEM-warranty-expiration likelihood, and the age-risk curve. Age is one of the two strongest coverage-eligibility signals. |
| **Make / Model** | The single best public predictor of repair-cost profile and component pain (e.g., known transmission, electrical, or turbo issues by platform). Drives plan tier and pricing posture. |
| **Trim / Engine / Drivetrain** | Separates a base 4-cylinder FWD from a turbocharged AWD performance variant — very different parts cost, claim severity, and plan fit, even on the same model. |
| **Mileage** | The other strongest eligibility signal. Defines the *prime coverage band* (≈40k–130k), warranty-gap timing, and exclusion/review thresholds. |
| **Eligibility (age + mileage + condition flags)** | Determines whether a vehicle can be offered a plan at all, which tier, and whether it needs underwriting review. This is the gate between "marketable lead" and "claims liability." |

The Signal Graph turns each of these from a static field into a *scored,
evidence-backed signal* that a sales or partnerships team can act on.

---

## 3. How a VIN Signal Graph improves the business

A VIN-anchored signal graph improves five distinct CoverageX functions:

**3.1 Targeting (the core wedge)**
Instead of buying broad lists or waiting for inbound quotes, CoverageX can
rank *actual, currently-listed vehicles* and *actual dealers* by coverage-fit
proxy. The funnel is seeded with the highest-probability candidates before any
ad spend or outreach. This is the difference between "market to everyone with a
car" and "approach the 12 dealers whose lots are full of prime-window trucks
and SUVs."

**3.2 Plan fit**
By decoding the VIN and scoring repair risk and class, each vehicle maps to a
recommended tier (Essential → Executive) with a stated reason. Sales
conversations start with a *right-sized* offer instead of a generic pitch,
which lifts conversion and reduces churn/cancellation from mis-sold plans.

**3.3 Pricing support (decision support, not actuarial pricing)**
The graph supplies *risk context* — class, age, mileage band, recall exposure,
public component-pain themes — that informs how aggressively to price and which
segments to lean into. This is **pricing support, not a rating engine**: it
does not replace actuarial loss data. It is explicitly labeled as estimated /
proxy signal until joined to licensed claims data.

**3.4 Claims-risk awareness**
The exclusion/review-risk score surfaces vehicles likely to generate adverse
selection (very high mileage, very old, commercial/rideshare indicators, salvage
where licensed data is available). This protects the loss ratio by flagging
what *not* to chase, or what to route to underwriting review — before a costly
plan is sold.

**3.5 Dealer partnerships (F&I)**
The dealer-level rollup converts thousands of VIN signals into a short list of
**partner-ready dealers**, each with an inventory-composition fingerprint and a
ready-made pitch angle. This is the engine for B2B activation: CoverageX walks
into a dealer conversation already knowing the dealer's lot is 45% prime-window
SUVs with high repair-risk themes.

---

## 4. Why this is more valuable than a VIN decoder

A VIN decoder answers *"what is this vehicle?"* — make, model, year, body class.
That is a **commodity**: NHTSA gives it away for free, and dozens of vendors
resell it. A decoder is a *fact lookup*. It has no opinion, no ranking, and no
commercial recommendation.

The Vehicle Signal Graph answers a fundamentally different and far more
valuable question: **"which vehicles and dealers are most ready to convert into
profitable protection, why, what should we offer, and who should we approach?"**

The difference, concretely:

| VIN Decoder | Vehicle Signal Graph |
|-------------|----------------------|
| One vehicle, static facts | Many vehicles, scored and ranked against a business goal |
| No risk view | Repair-risk, recall, and exclusion/review scoring |
| No demand view | Coverage-readiness (prime-window) scoring |
| No commercial recommendation | Plan-fit tier + reason + pitch angle |
| No aggregation | Dealer-level opportunity scoring and ranking |
| No provenance | Every fact carries source URL, timestamp, confidence, evidence span |
| No activation path | B2B (F&I) partner targeting layer |

A decoder is an **input**. The Signal Graph is a **decision system** that
consumes the decode and turns it into prioritized, evidence-backed revenue
actions. The decode is one column; the product is everything built on top of it.

---

## 5. Why the first wedge should be dealer inventory + F&I partner opportunity

Of all the places CoverageX could start, **public used-car dealer inventory** is
the sharpest opening wedge for five reasons:

1. **It is where prime-window vehicles physically concentrate.** Used-car lots
   are full of 4–12-year-old, 40k–130k-mile vehicles — exactly the coverage
   sweet spot. The supply of high-fit candidates is dense and observable.

2. **It is publicly observable and compliant.** Dealer inventory pages are
   public business content (VIN, mileage, price, trim, listing URL). We can
   build the entire proof on **public, permissioned, or licensed data only**,
   with **no consumer personal data** — names, emails, phones, and home
   addresses are never collected.

3. **It naturally aggregates into a B2B target.** Individual VINs roll up into a
   dealer fingerprint. A dealer with a high coverage-opportunity score is a
   concrete, nameable partner — not an anonymous consumer. This gives CoverageX
   a *named account* to approach, which is how B2B sales actually works.

4. **F&I is the highest-leverage channel.** The Finance & Insurance desk already
   sells protection products at point of sale. A dealer partnership produces
   *recurring attach*, not one-off leads. Landing one F&I relationship can be
   worth thousands of plan attachments — far more leverage than chasing
   individual consumers.

5. **The "wow" is immediate and demoable.** "This dealer has 143 vehicles, 61
   coverage-ready, 22 high-repair-risk, recommended plan mix is 45% Premium, and
   here is the F&I pitch" is a self-evident value story a buyer can grasp in ten
   seconds. It de-risks the sale of the data product itself.

**Sequencing logic:** Dealer inventory + F&I is the *land*. Once the graph
proves it can rank dealers and VINs, the same engine extends to (a) direct
consumer marketing targeting, (b) marketplace-wide inventory scoring, and (c)
licensed claims/title data for true actuarial pricing support. We land on the
compliant, high-leverage, easily-demoed wedge and expand from there.

---

## Compliance posture (carried through every phase)

- Public, permissioned, licensed, or customer-provided data **only**.
- **No** consumer names, emails, phone numbers, or home addresses.
- **No** login-protected, paywalled, or sensitive personal data.
- B2B enrichment (e.g., Apollo) is for **dealer/partner business contacts only**, never consumers, and never attached to a VIN.
- Every fact stores source URL, timestamp, confidence, and a short evidence span.
- Inferred signals are labeled as estimated / model-level / proxy — never presented as verified claims, title, or open-recall status without a supporting licensed source.
