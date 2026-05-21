# Source Rights Matrix — CoverageX Vehicle Signal Graph

**Purpose:** Classify every candidate data source by legal/commercial risk so
that Phase 1 collection only touches approved sources, and so every output can
be defended to the buyer.

**Tier definitions:**

| Tier | Meaning | Phase 1 use |
|------|---------|-------------|
| **SAFE PUBLIC** | Public, official, or company-owned content with low rights risk | Use freely for the proof of concept |
| **SAMPLE ONLY** | Public discussion/review content usable in small, attributed evidence spans | Use sparingly, demo-labeled, short spans only |
| **LICENSE / PERMISSION REQUIRED** | Valuable but gated by license, contract, or regulation | Do **not** collect in PoC; document as production path |
| **DO NOT USE** | Private, protected, or sensitive data | Never collect, in any phase |

**Field key for every source:**
`source_name` · `tier` · `sample_use` · `legal_risk` · `product_risk` ·
`production_replacement_path` · `production_ready_status` ·
`estimated_cost_if_known` · `recommended_buyer_language`

---

## TIER 1 — SAFE PUBLIC

### NHTSA VIN Decoder API (vPIC)
- **tier:** SAFE PUBLIC
- **sample_use:** Decode all valid VINs → make, model, year, body class, engine, fuel type, manufacturer, plant.
- **legal_risk:** Very low. U.S. government public API, no key required, intended for public/commercial use.
- **product_risk:** Low. Decode completeness varies by manufacturer (engine/trim sometimes sparse).
- **production_replacement_path:** Same API in production; optionally supplement with a commercial decode vendor (DataOne, Vincario) for richer trim/option data.
- **production_ready_status:** Production-ready.
- **estimated_cost_if_known:** Free.
- **recommended_buyer_language:** "Vehicle identity decoded from the official NHTSA vPIC database."

### NHTSA Recalls API / recall datasets
- **tier:** SAFE PUBLIC
- **sample_use:** Attach **model-level** recall counts and component themes by make/model/year. Label as model-level signal, not VIN-specific open-recall status.
- **legal_risk:** Very low. Public government data.
- **product_risk:** Medium **if mislabeled** — the public dataset is model-level; it does not confirm whether a *specific* VIN has an open/unremedied recall. Must not imply VIN-specific open recall.
- **production_replacement_path:** NHTSA "recalls by VIN" lookup for VIN-specific status; or licensed providers that resolve open-recall state per VIN.
- **production_ready_status:** Production-ready for model-level signal; VIN-specific open-recall requires the by-VIN endpoint/licensed source.
- **estimated_cost_if_known:** Free.
- **recommended_buyer_language:** "Model-level recall exposure from NHTSA. VIN-specific open-recall status requires a per-VIN lookup in production."

### NHTSA Complaints / Investigations / TSB metadata
- **tier:** SAFE PUBLIC
- **sample_use:** Derive component-pain themes (transmission, electrical, AC, powertrain) at the make/model/year level to support repair-risk scoring.
- **legal_risk:** Very low. Public government data.
- **product_risk:** Medium — complaints are unverified consumer reports; use as theme signal, not as defect proof.
- **production_replacement_path:** Licensed repair/claims data (see Tier 3) for verified repair frequency/severity.
- **production_ready_status:** Production-ready as a *theme* signal only.
- **estimated_cost_if_known:** Free.
- **recommended_buyer_language:** "Public complaint themes reported to NHTSA, used as a directional risk indicator."

### Public dealer websites & public inventory/VDP pages
- **tier:** SAFE PUBLIC
- **sample_use:** Collect VIN, year, make, model, trim, mileage, price, stock number, listing URL, dealer name/location from public inventory and vehicle-detail pages.
- **legal_risk:** Low–moderate. Public business content; respect robots.txt, rate limits, and site terms. Avoid any login-gated area.
- **product_risk:** Medium. Layout variability; some sites obfuscate VINs or render via JS (Apify handles dynamic rendering).
- **production_replacement_path:** Licensed inventory feeds (dealer DMS/inventory syndication, marketplace data partnerships) for stable, terms-clean scale.
- **production_ready_status:** PoC-ready as public collection; production scale should move to licensed/permissioned feeds.
- **estimated_cost_if_known:** Apify compute only in PoC (see actor pricing in phase1_plan.md).
- **recommended_buyer_language:** "Public dealer inventory listings, collected respecting site terms; production scale recommended via licensed feeds."

### Company-owned pages (CoverageX site, dealer's own About/Staff *business* pages)
- **tier:** SAFE PUBLIC
- **sample_use:** Confirm dealer identity, dealer type, business location, and **business** contact (main line) where publicly posted.
- **legal_risk:** Low for business info. Do not extract personal/consumer data.
- **product_risk:** Low.
- **production_replacement_path:** B2B data providers (Apollo) for structured dealer firmographics/business contacts.
- **production_ready_status:** Production-ready for business identity.
- **estimated_cost_if_known:** Free.
- **recommended_buyer_language:** "Publicly posted business information."

### Public competitor vehicle-protection product pages
- **tier:** SAFE PUBLIC
- **sample_use:** Capture publicly stated competitor coverage tiers, covered components, and positioning to inform plan-fit context and competitive framing.
- **legal_risk:** Low for factual, public product descriptions. Do not copy proprietary text verbatim into outputs; summarize.
- **product_risk:** Low–medium. Marketing pages may not reflect actual contract terms.
- **production_replacement_path:** Licensed competitive-intelligence feeds; sample contract review by counsel.
- **production_ready_status:** Production-ready as positioning signal.
- **estimated_cost_if_known:** Free.
- **recommended_buyer_language:** "Publicly stated competitor coverage positioning."

### Google Maps / Google Search public business results (dealer discovery)
- **tier:** SAFE PUBLIC
- **sample_use:** Discover dealer names, websites, business addresses, business phone, category, public rating count for seeding the dealer list.
- **legal_risk:** Low–moderate. Public business listings; respect provider terms; collect business (not personal) data only.
- **product_risk:** Low. Good for discovery; verify inventory URLs manually/programmatically.
- **production_replacement_path:** Google Places API (official) or licensed business-firmographic data.
- **production_ready_status:** PoC-ready via Apify; production via official Places API.
- **estimated_cost_if_known:** Apify compute; Places API ~$17–32 per 1k requests if used in production.
- **recommended_buyer_language:** "Public business listings used to seed dealer discovery."

---

## TIER 2 — SAMPLE ONLY (demo-labeled, short evidence spans)

### Public owner forums by make/model/year/component
- **tier:** SAMPLE ONLY
- **sample_use:** Extract **short** evidence spans of recurring component-pain themes (e.g., "CVT shudder at ~90k"). Store the span + URL + date. Label "public discussion, not verified."
- **legal_risk:** Moderate. Respect forum terms; no bulk reproduction; no user PII (no usernames tied to people, no signatures, no contact info).
- **product_risk:** Medium–high. Anecdotal, self-selected, not statistically representative.
- **production_replacement_path:** Licensed repair-frequency/claims data (Tier 3) for verified, weighted signals.
- **production_ready_status:** Demo-only.
- **estimated_cost_if_known:** Apify compute only.
- **recommended_buyer_language:** "Illustrative public owner-discussion themes (demo only); production uses licensed repair data."

### Public review pages for competitors
- **tier:** SAMPLE ONLY
- **sample_use:** Short, attributed quotes illustrating competitor coverage sentiment, for demo validation only.
- **legal_risk:** Moderate. Review-platform terms often restrict scraping; keep to minimal, attributed spans; do not collect reviewer PII.
- **product_risk:** Medium. Sentiment is noisy and platform-biased.
- **production_replacement_path:** Licensed review-data partnership or official platform API; counsel review of terms.
- **production_ready_status:** Demo-only.
- **estimated_cost_if_known:** Apify compute only.
- **recommended_buyer_language:** "Illustrative public review sentiment (demo only)."

### Public discussion / Q&A pages (general automotive)
- **tier:** SAMPLE ONLY
- **sample_use:** Supplementary component-theme color; short spans only.
- **legal_risk:** Moderate. Platform terms vary; no PII.
- **product_risk:** Medium–high. Anecdotal.
- **production_replacement_path:** Licensed repair/claims data.
- **production_ready_status:** Demo-only.
- **estimated_cost_if_known:** Apify compute only.
- **recommended_buyer_language:** "Illustrative public discussion themes (demo only)."

---

## TIER 3 — LICENSE / PERMISSION REQUIRED (do NOT collect in PoC)

### Paid vehicle-history reports (Carfax / AutoCheck-style)
- **tier:** LICENSE / PERMISSION REQUIRED
- **sample_use:** None in PoC.
- **legal_risk:** High. Contractual + data-rights restrictions; scraping prohibited.
- **product_risk:** N/A in PoC.
- **production_replacement_path:** Commercial license / API partnership.
- **production_ready_status:** Requires license.
- **estimated_cost_if_known:** Negotiated; commonly per-report or enterprise subscription.
- **recommended_buyer_language:** "Vehicle-history depth available in production via licensed partnership."

### NMVTIS providers (title/brand/junk/salvage)
- **tier:** LICENSE / PERMISSION REQUIRED
- **sample_use:** None in PoC. Title/salvage status is **never** asserted without this.
- **legal_risk:** High. Federally governed access; approved-provider model.
- **product_risk:** N/A in PoC.
- **production_replacement_path:** Approved NMVTIS data provider.
- **production_ready_status:** Requires license.
- **estimated_cost_if_known:** Per-VIN fees (typically a few cents to dollars depending on provider/volume).
- **recommended_buyer_language:** "Title and brand status in production via an approved NMVTIS provider."

### Auction history / wholesale data (Manheim-style)
- **tier:** LICENSE / PERMISSION REQUIRED
- **sample_use:** None in PoC.
- **legal_risk:** High. Proprietary/contractual.
- **product_risk:** N/A in PoC.
- **production_replacement_path:** Commercial data partnership.
- **production_ready_status:** Requires license.
- **estimated_cost_if_known:** Enterprise.
- **recommended_buyer_language:** "Wholesale/auction valuation context available via licensed partnership."

### Proprietary repair-history / claims data
- **tier:** LICENSE / PERMISSION REQUIRED
- **sample_use:** None in PoC. This is the upgrade path that turns *estimated* repair risk into *actuarial* risk.
- **legal_risk:** High. Contractual; possibly regulated.
- **product_risk:** N/A in PoC.
- **production_replacement_path:** Licensed repair-order/claims datasets; CoverageX's own historical claims.
- **production_ready_status:** Requires license / internal data-sharing agreement.
- **estimated_cost_if_known:** Enterprise.
- **recommended_buyer_language:** "Repair-risk scoring upgrades to actuarial grade once joined to licensed claims data."

### Large-scale marketplace inventory feeds
- **tier:** LICENSE / PERMISSION REQUIRED
- **sample_use:** None at scale in PoC (small public sampling only where terms permit).
- **legal_risk:** High at scale. Marketplace ToS typically prohibit bulk scraping.
- **product_risk:** N/A in PoC.
- **production_replacement_path:** Official data partnership / licensed feed.
- **production_ready_status:** Requires license for scale.
- **estimated_cost_if_known:** Enterprise / revenue-share.
- **recommended_buyer_language:** "National inventory coverage in production via licensed marketplace feeds."

### Consumer ownership / credit / insurance data
- **tier:** LICENSE / PERMISSION REQUIRED (and partially DO NOT USE — see below)
- **sample_use:** None.
- **legal_risk:** Very high. FCRA/GLBA/DPPA and similar regimes; permissible-purpose constraints.
- **product_risk:** N/A in PoC.
- **production_replacement_path:** Only via fully compliant, permissible-purpose licensed channels with counsel sign-off.
- **production_ready_status:** Requires license + legal review; out of scope for this product's targeting use.
- **estimated_cost_if_known:** Enterprise + compliance overhead.
- **recommended_buyer_language:** Not used for targeting in this product.

---

## TIER 4 — DO NOT USE (never, any phase)

| source_name | why |
|-------------|-----|
| Private consumer data (names, home addresses, personal emails/phones tied to a vehicle or owner) | Privacy law + product policy. Never collected or attached to a VIN. |
| Login-protected / account-gated data | Unauthorized access risk; ToS violation. |
| Paywalled content accessed without license | Contract/IP violation. |
| Sensitive personal data (driver behavior, location/telematics without consent, demographics) | Privacy law; sensitive-category data. |
| Unauthorized DMV / registration data | DPPA and state-law restrictions. |
| Personal social media profiles | Privacy + platform ToS. |
| Driver behavior / telematics without explicit consent | Sensitive personal data. |
| Consumer contact data for outreach | Out of scope; CAN-SPAM/privacy; product policy prohibits consumer contact. |

- **legal_risk (all):** High to severe.
- **product_risk (all):** Severe reputational/regulatory.
- **production_replacement_path (all):** None — these are categorically excluded from this product. Where a *business* need exists (e.g., dealer business contact), satisfy it via Tier 1 public business info or licensed **B2B** providers only.
- **recommended_buyer_language:** "This product collects no consumer personal data and no protected/sensitive data, by design."

---

## B2B enrichment note (Apollo and similar)

- **tier:** LICENSE / PERMISSION REQUIRED (vendor-licensed), **B2B only**
- **sample_use:** **Not in Phase 1.** Later phases only, for **dealer/partner business roles** (dealer principal, GM, F&I director, used-car manager, operations manager, partnerships lead).
- **legal_risk:** Moderate, governed by vendor terms and applicable B2B-data law. Never for consumers.
- **product_risk:** Low if scoped to business contacts.
- **production_replacement_path:** Apollo / ZoomInfo / equivalent under license.
- **production_ready_status:** Available later under license; **excluded from Phase 1**.
- **estimated_cost_if_known:** Per-seat / per-credit subscription.
- **recommended_buyer_language:** "B2B partner contacts (business roles only) available via licensed enrichment in a later phase; no consumer contacts, ever."

---

## Standing rules applied to every source

1. Store `source_url`, `extraction_date`, `confidence`, `evidence_span`, and `risk_tier` for every fact.
2. Respect robots.txt, rate limits, and site terms; never access login-gated content.
3. Label inferred/model-level/demo signals explicitly; never present them as verified VIN-level fact.
4. No consumer PII enters the system at any point.
5. Anything Tier 3/4 stays out of the PoC and is represented only as a documented production path.
