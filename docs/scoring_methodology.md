# Scoring Methodology — CoverageX Vehicle Signal Graph

All weights, thresholds, and band definitions live in
`config/scoring_config.json` and are versioned (`scoring_version`) so every
stored score is reproducible. Scores are **0–100**. Every score is a **proxy /
candidate score**, not an actuarial or verified figure, and is labeled as such.

**Honesty rules baked into scoring:**
- Repair risk is an **estimated** signal until joined to licensed claims data.
- Recall inputs are **model-level** unless a licensed VIN-level source exists.
- Title/salvage/odometer inputs are **absent** unless from a licensed source; the exclusion model treats them as "unknown," never assumed.

---

## Part A — Vehicle-level scores

### A1. Coverage Readiness Score (0–100)

> *How strong a candidate is this vehicle for an extended protection plan?*
> High = squarely in the profitable "prime protection window."

**Sub-scores (each normalized 0–100), weighted:**

| Sub-score | Weight | Logic |
|-----------|:-----:|-------|
| Mileage fit | 0.30 | Peaks in the prime band **40k–130k**; ramps up from <40k (likely under warranty), declines above 130k. |
| Age fit | 0.20 | Peaks in **4–12 years**; low for <4 yrs (OEM warranty) and declines after 12 yrs. |
| Repair-cost exposure | 0.20 | Derived from Repair Risk Score (A2) — moderate-to-high exposure is *good* for coverage demand. |
| Vehicle-class lift | 0.15 | Truck / SUV / luxury / high-parts-cost classes get lift (higher protection value). |
| Warranty-gap likelihood | 0.10 | Proxy: vehicle past typical 3yr/36k b-t-b and approaching/past 5yr/60k powertrain → higher. |
| Data completeness | 0.05 | Penalizes missing mileage or failed decode. |

**Mileage-fit curve (piecewise):**
```
< 40,000        : linear 30 → 70   (rising; some still under warranty)
40,000–130,000  : 100              (prime band, plateau)
130,001–160,000 : linear 100 → 40  (declining eligibility)
> 160,000       : 20               (high exclusion risk)
unknown mileage : 0  (and sets data_completeness penalty)
```

**Age-fit curve (piecewise, age = current_year − model_year):**
```
0–3 yrs   : 25      (OEM warranty suppresses demand)
4–12 yrs  : 100     (prime)
13–15 yrs : linear 100 → 50
> 15 yrs  : 30
```

**Formula:**
```
coverage_readiness =
   0.30*mileage_fit + 0.20*age_fit + 0.20*repair_cost_exposure
 + 0.15*class_lift  + 0.10*warranty_gap + 0.05*data_completeness
```

**Banding:** ≥70 = *Coverage-Ready* · 45–69 = *Watch* · <45 = *Low fit*.
A vehicle counts toward a dealer's `coverage_ready_vehicle_count` when
`coverage_readiness ≥ 70` **and** `vin_valid = 1` **and** mileage is known.

---

### A2. Repair Risk Score (0–100)

> *Estimated likelihood/severity of future repair need.* Higher = more repair
> exposure (which raises consumer demand **and** claims cost — interpreted in
> context, never as verified claims data).

| Sub-score | Weight | Logic |
|-----------|:-----:|-------|
| Mileage risk | 0.25 | Monotonic rising with mileage (wear). |
| Age risk | 0.20 | Monotonic rising with age. |
| Class risk | 0.15 | Luxury > truck/SUV > mainstream > economy (parts/labor cost). EV/hybrid add complexity weighting. |
| Powertrain-complexity risk | 0.15 | Turbo, CVT, AWD/4WD, diesel, high-tech drivetrains raise expected severity. |
| Recall/component risk | 0.15 | Model-level recall count + severity for the make/model/year. |
| Public complaint themes | 0.10 | Intensity of NHTSA-complaint / public-forum themes (transmission, electrical, AC, powertrain). Neutral (50) when no data. |

**Formula:**
```
repair_risk =
   0.25*mileage_risk + 0.20*age_risk + 0.15*class_risk
 + 0.15*powertrain_complexity + 0.15*recall_component_risk
 + 0.10*public_complaint_intensity
```

**Banding:** ≥65 = *High repair risk* · 40–64 = *Moderate* · <40 = *Low*.
`high_repair_risk_vehicle_count` increments at `repair_risk ≥ 65`.
`component_risk_themes` stores the top contributing themes for the evidence drawer.

---

### A3. Plan Fit Recommendation (Essential / Signature / Premium / Executive)

Maps each VIN to a CoverageX tier using repair risk, class/value, and
technology exposure. Deterministic decision logic (first match wins):

```
IF class in {luxury, high-value} OR fuel_type = EV
   OR (advanced_tech AND high parts cost) OR repair_risk ≥ 80
        → Executive
ELSE IF class in {truck, SUV} OR repair_risk ≥ 65
   OR mileage_band in {100k-130k, >130k} OR known_expensive_components
        → Premium
ELSE IF repair_risk in [40,65) OR mileage_band in {70k-100k}
   OR mainstream brand
        → Signature
ELSE  (low repair risk, lower mileage, economy)
        → Essential
```

**`plan_fit_reason`** is always populated with the deciding factors, e.g.
*"Premium: full-size SUV, 96k mi in prime band, model-level transmission theme."*

Tier intent recap: **Essential** (low risk/mileage economy) · **Signature**
(mainstream, moderate) · **Premium** (truck/SUV/luxury, higher mileage, known
component risk) · **Executive** (high-value, luxury, advanced-tech, EV, high
parts cost / higher claim severity).

---

### A4. Exclusion / Review Risk Score (0–100) + flags

> *Should this vehicle be avoided or routed to underwriting review?* High = more
> likely adverse selection. This **protects loss ratio** at the targeting stage.

Flag inputs (each adds weighted risk and an entry to `exclusion_review_flags`):

| Input | Effect | Note |
|-------|--------|------|
| Mileage > 150k | strong | eligibility edge |
| Age > 15 yrs | strong | eligibility edge |
| Commercial-use indicator (e.g., box/cargo/fleet trim, "former rental" text) | strong | from listing text only |
| Rideshare indicator | strong | from listing text only |
| Salvage / rebuilt title | **flag only if licensed source present** | otherwise "unknown — not asserted" |
| Visible modifications | moderate | from listing text/photos text |
| Odometer issue | **flag only if licensed source present** | otherwise unknown |
| Severe recall (high severity, model-level) | moderate | model-level caveat |

**Output:** `exclusion_review_score` (0–100) and a `exclusion_review_flags` JSON
array. High score does **not** mean "reject" — it means "review / likely
unprofitable to chase," and the demo presents it as a guardrail.

---

### A5. Buyer Urgency Score (0–100) — supporting signal

A blended signal for prioritizing outreach within the coverage-ready set:
```
buyer_urgency = 0.5*coverage_readiness + 0.3*repair_risk + 0.2*warranty_gap_proximity
                (capped/zeroed when exclusion_review_score is very high)
```
Used to order the "Top VINs to act on" list and to set
`recommended_message_angle` (e.g., *"Out of factory warranty, transmission is a
known pain point at this mileage — strong Premium fit."*).

---

## Part B — Dealer-level scores

### B1. Dealer Coverage Opportunity Score (0–100)

> *How attractive is this dealer as a CoverageX F&I partner target?*

**Weighting (per buyer spec):**

| Component | Weight | Normalization |
|-----------|:-----:|---------------|
| Coverage-ready vehicle share | 0.30 | `coverage_ready_count / inventory_count`, scaled 0–100 |
| Inventory count | 0.15 | log-scaled vs market (more inventory = more attach surface) |
| High-repair-risk vehicle count | 0.20 | scaled 0–100 vs market (repair anxiety = demand) |
| Truck/SUV/luxury share | 0.15 | `(truck_suv_share + luxury_share)` scaled 0–100 |
| Avg mileage in prime range | 0.10 | share of inventory with mileage in 40k–130k |
| Dealer location priority | 0.05 | market-tier multiplier from `scoring_config.json` |
| Data completeness | 0.05 | share of VINs with valid decode + mileage |

**Formula:**
```
dealer_opportunity =
   0.30*coverage_ready_share_n + 0.15*inventory_count_n
 + 0.20*high_repair_risk_n     + 0.15*truck_suv_luxury_n
 + 0.10*prime_mileage_share_n  + 0.05*location_priority_n
 + 0.05*data_completeness_n
```

**Banding:** ≥70 = *Priority partner* · 50–69 = *Qualified* · <50 = *Monitor*.

**Recommended plan mix** is the distribution of `plan_fit_recommendation`
across the dealer's coverage-ready vehicles (e.g., `{Signature: .35, Premium:
.45, Executive: .20}`), exported as `recommended_plan_mix`.

---

### B2. Dealer Pitch Angle

Rule-based selection of the dominant, evidence-backed angle(s):

| Trigger | Pitch angle |
|---------|-------------|
| truck_suv_share high | "High truck & SUV inventory — premium powertrain protection fit." |
| luxury_share high | "Used-luxury exposure — high parts cost, strong Executive/Premium attach." |
| prime_mileage_share high | "Inventory sits in the prime protection mileage window." |
| ev_share high | "EV protection opportunity — high-voltage/component coverage." |
| recall density high | "Recall-service + protection bundle opportunity." |
| coverage_ready_share high | "Large coverage-ready set — direct F&I attach opportunity." |

The exported `recommended_partner_pitch` composes the top 1–2 triggers into a
sentence and names the target persona (default: **F&I Director**).

---

## Worked example (illustrative)

**Vehicle:** 2017 full-size SUV, AWD, 96,000 mi, listed at a used-car dealer.
- Mileage fit = 100 (prime band) · Age fit = 100 (age 9) · Repair-cost exposure = 72 · Class lift = 85 (SUV) · Warranty gap = 90 · Data completeness = 100.
- **Coverage readiness** = .30(100)+.20(100)+.20(72)+.15(85)+.10(90)+.05(100) = **91.9** → *Coverage-Ready*.
- Repair risk sub-scores → ~68 → *High repair risk*.
- **Plan fit** → *Premium* (SUV + prime-band mileage + model-level transmission theme).
- Exclusion/review flags → none (mileage < 150k, age < 15, no commercial indicator). Title = unknown (not asserted).
- **Message angle:** "Out of factory warranty, in the prime mileage window, with a known transmission pain point — strong Premium fit."

**Dealer (rolled up):** 143 vehicles, 61 coverage-ready (share .43), 22 high
repair risk, truck/SUV+luxury share .58, prime-mileage share .51, market = LA
(priority 1.0), data completeness .92 → **dealer_opportunity ≈ 78** → *Priority
partner*; plan mix ≈ {Signature .35, Premium .45, Executive .20}; pitch = "High
truck & SUV inventory in the prime protection window — direct F&I attach
opportunity"; target = F&I Director.

---

## Calibration & limits

- **Cold-start / heuristic weights**: Phase-1 weights are reasoned defaults, not
  fitted to outcomes. They are tunable in `scoring_config.json`.
- **Upgrade path to actuarial**: once licensed claims/repair data is available,
  repair-risk and plan-fit sub-models can be re-weighted/fitted to true loss
  experience, replacing the heuristic priors. The scoring *interface* (0–100
  scores + reasons + evidence) stays stable.
- **Never overclaim**: outputs use "candidate score," "estimated risk,"
  "coverage-fit proxy," and "model-level signal." No score is presented as a
  verified claims, title, or open-recall determination.
