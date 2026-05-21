# Phase 1 Plan — First Proof Sample

**Goal:** Produce a buyer-ready demo from one real market. Signal quality and a
defensible demo beat scale. **Do not begin until Phase 0 is approved.**

**Recommended market:** Los Angeles County / Southern California.

**Target sample (tiered, pick the largest that is reliably collectable):**
- Stretch: 50 dealers · 1,000–3,000 vehicles
- Base: 25–50 dealers · ≥500 valid VINs
- Floor: 25 dealers · ~500 vehicles

---

## Execution steps

| # | Step | Script | Engine | Output |
|---|------|--------|--------|--------|
| 1 | Discover 25–50 used-car dealers in the market | `discover_dealers.py` | Apify (Google Maps/Search) or seed CSV | `config/dealers_seed.csv`, `dealers` table |
| 2 | Collect public inventory pages | `collect_inventory.py` | **Apify** (dynamic pages) or `requests` (static) | `data/raw/`, `inventory_listings` |
| 3 | Extract VIN, mileage, price, year, make, model, trim, stock #, listing URL, dealer name/location | (in step 2 parser) | Claude Code | normalized listings |
| 4 | Validate VINs | `validate_vins.py` | Claude Code | `vehicles.vin_valid`, invalid set for QA |
| 5 | Decode VINs via NHTSA | `decode_vins.py` | Claude Code (NHTSA API) | `vin_decodes` |
| 6 | Add recall layer (model-level) | `collect_recalls.py` | Claude Code (NHTSA API) | `recalls` |
| 7 | Add simple repair-risk signals | `collect_repair_signals.py` | Claude Code + (optional Apify for public themes) | `repair_signals` |
| 8 | Score vehicles | `score_vehicles.py` | Claude Code | `coverage_scores` |
| 9 | Score dealers | `score_dealers.py` | Claude Code | `dealer_scores`, dealer rollups |
| 10 | Export CSV/JSON/evidence + demo package | `export_outputs.py`, `generate_manus_demo_package.py` | Claude Code | `outputs/*` |

`collect_competitor_signals.py` (optional, SAFE-PUBLIC competitor pages) and
`enrich_b2b_contacts.py` (**not run in Phase 1**; later phases, B2B-only) exist
in the structure but are out of scope for the first sample.

---

## Engine rule: Apify vs. code

**Use Apify** for: dealer discovery (Google Maps/Search), dynamic/JS-rendered
inventory pages, marketplace-style pages, and any public source where browser
automation is more reliable.

**Use Claude Code (no Apify)** for: NHTSA API calls (official public API),
static pages easily fetched with `requests`, and all parsing of
already-downloaded HTML.

### Apify actor evaluation checklist (before any actor runs)
1. Check **input schema**.
2. Check **pricing**.
3. Check **output fields**.
4. Check **source-terms risk** (cross-check `source_rights_matrix.md`).
5. Run a **small test on 3 dealers**.
6. **Save raw sample output** to `data/raw/`.
7. **Map** actor output → internal schema (`data_model.md`).
8. **Log** every source and run in `run_logs`.

**Candidate actors to investigate:** Website Content Crawler · Google Search
Results Scraper · Google Maps Scraper (dealer discovery) · a generic
web/inventory scraper · a Crawlee-based custom actor if needed. Review/marketplace
actors only where terms permit and only for demo validation.

---

## Project structure (created in Phase 1)

```
config/   source_config.json · scoring_config.json · dealers_seed.csv · .env.example
data/     raw/ · processed/ · final/
scripts/  discover_dealers.py · collect_inventory.py · validate_vins.py ·
          decode_vins.py · collect_recalls.py · collect_repair_signals.py ·
          collect_competitor_signals.py · score_vehicles.py · score_dealers.py ·
          enrich_b2b_contacts.py · export_outputs.py · generate_manus_demo_package.py
docs/     (Phase 0 artifacts, already created) + runbook.md
outputs/  vehicle_signal_graph.csv · vehicle_signal_graph.json ·
          dealer_opportunity_rankings.csv · source_evidence.json ·
          top_dealer_briefs.md · coveragex_demo_summary.md · manus_demo_prompt.md
logs/     run_log.json · errors.json
tests/    test_vin_validation.py · test_scoring.py · test_deduplication.py · test_exports.py
```

---

## Environment variables (`config/.env`, gitignored)

| Var | Use |
|-----|-----|
| `APIFY_TOKEN` | Apify collection engine (required for steps 1–2, possibly 7) |
| `NHTSA_API_BASE` | NHTSA vPIC + recalls base URL (no key) |
| `APOLLO_API_KEY` | optional; **B2B only, not used in Phase 1** |
| `DATABASE_URL` | optional; defaults to local SQLite |

`config/.env.example` (committed) lists names only — **no secret values are ever
committed**. Real values live in gitignored `config/.env`.

---

## VIN handling rules

- VIN must be **17 chars**; exclude letters **I, O, Q**; normalize uppercase;
  (optional) ISO 3779 check-digit validation.
- **Dedup** on `(vin, dealer_id)`.
- Store invalid VINs separately for QA (`vin_valid = 0`, with reason).
- **Decode only valid VINs** (NHTSA vPIC): make, model, model year, body class,
  engine (if available), fuel type (if available), manufacturer, plant (if
  available); store full payload for audit.
- **Recalls:** prefer NHTSA; if VIN-specific is unavailable, use make/model/year
  patterns labeled **model-level** — never imply VIN-specific open recall.
- **Repair risk:** start simple (age, mileage, class, luxury, truck/SUV, EV/hybrid,
  recall component, public complaint themes). Public-forum spans kept **short**
  and labeled "public discussion, not verified." Production path = licensed
  repair/claims data.

---

## Phase 1 schema (collected fields)

**Dealer:** dealer_id, dealer_name, website, inventory_url, street_address (if
public), city, state, zip, phone (public business line), dealer_type,
inventory_count, coverage_ready_vehicle_count, high_repair_risk_vehicle_count,
avg_vehicle_age, avg_mileage, truck_suv_share, luxury_share, ev_share,
dealer_coverage_opportunity_score, recommended_partner_pitch, source_url,
confidence.

**Vehicle:** vehicle_id, dealer_id, vin, vin_valid, year, make, model, trim,
body_class, engine, drivetrain, fuel_type, mileage, price, listing_url,
days_listed (if available), vehicle_age, mileage_band,
coverage_readiness_score, repair_risk_score, plan_fit_recommendation,
plan_fit_reason, recall_count, recall_severity, component_risk_themes,
exclusion_review_flags, buyer_urgency_score, recommended_message_angle,
confidence.

**Evidence:** evidence_id, entity_type, entity_id, source_name, source_url,
source_type, evidence_span, extraction_date, confidence, risk_tier.

**B2B activation (not populated in Phase 1):** dealer_id, recommended_personas,
activation_source, contact_enrichment_status, notes. Business roles only; never
attached to a VIN; no consumer data.

---

## Outputs for CoverageX

1. Ranked dealers (`dealer_opportunity_rankings.csv`)
2. Top 25 VINs by coverage readiness
3. Top 25 VINs by repair risk
4. Dealer pitch angle per dealer (`top_dealer_briefs.md`)
5. Recommended plan mix per dealer
6. Evidence-backed source file (`source_evidence.json`)
7. Manus demo prompt (`manus_demo_prompt.md`) + demo summary (`coveragex_demo_summary.md`)

**First buyer demo** is built around one flagship dealer using the
`demo_storyboard.md` structure (Dealer / Inventory / Coverage-ready VINs /
High-repair-risk VINs / Best segment / Recommended plan mix / Estimated attach
opportunity / F&I pitch / Top 5 VINs / Evidence / Next action).

---

## Success criteria

| # | Criterion | Target |
|---|-----------|--------|
| 1 | Dealers discovered | ≥ 25 |
| 2 | Valid VINs collected | ≥ 500 |
| 3 | VIN decode success | ≥ 80% |
| 4 | Vehicles with a coverage-readiness score | ≥ 50% |
| 5 | Dealers with an opportunity score | ≥ 10 |
| 6 | Every output record has source URL + extraction date | 100% |
| 7 | Consumer personal data collected | **0** |
| 8 | Production database writes | **0** (local SQLite only) |
| 9 | Buyer demo package created | yes |

---

## If we fall short of 500 VINs

**Do not fabricate data.** Instead:
1. Report the actual number collected and the per-dealer breakdown.
2. Explain the blocker (JS rendering, anti-bot, VIN obfuscation, terms risk, sparse inventory).
3. Recommend one of: change market, change source strategy (different dealer
   platforms / Apify marketplace actors where terms permit), reduce dealer count
   but deepen per-dealer, or escalate to a licensed inventory feed.
4. Keep all collected signal honest and evidence-backed regardless of count.

---

## Testing (Phase 1)

- `test_vin_validation.py` — 17-char, I/O/Q exclusion, normalization, dedup, invalid handling.
- `test_scoring.py` — sub-score curves, weight sums = 1.0, banding thresholds, plan-fit decision order, worked example from `scoring_methodology.md`.
- `test_deduplication.py` — `(vin, dealer_id)` dedup; same VIN across dealers preserved.
- `test_exports.py` — every export row has `source_url` + `extraction_date`; no PII columns; schema conformance.

---

## Guardrails (every step)

- Public/permissioned/licensed/customer-provided data only; respect robots.txt, rate limits, terms.
- No consumer PII, ever. B2B enrichment off in Phase 1.
- Provenance on every fact (source URL, timestamp, confidence, evidence span).
- Label inferred/model-level/demo signals; never assert verified claims/title/open-recall without a licensed source.
- No Supabase/production writes without explicit approval. No secrets committed.
- Log every source and run in `run_logs` / `logs/`.
