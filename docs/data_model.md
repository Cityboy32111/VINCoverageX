# Data Model — CoverageX Vehicle Signal Graph

**Store:** Local SQLite for the proof of concept (`data/vehicle_signal_graph.sqlite`).
**No production Supabase writes** unless explicitly approved.

The model is **VIN-anchored**: `vehicles.vin` is the canonical key that ties
identity, inventory, recalls, repair risk, competitor context, scores, and
evidence together, and rolls up to `dealers`.

---

## 1. Entity overview

```
                         ┌─────────────┐
                         │   dealers   │
                         └──────┬──────┘
                                │ 1
                                │
                                │ N
                         ┌──────┴───────┐        ┌──────────────────┐
                         │   vehicles   │────1:1─│   vin_decodes    │
                         │  (VIN anchor)│        └──────────────────┘
                         └──┬───┬───┬───┘
              1:N           │   │   │            1:N
        ┌───────────────────┘   │   └───────────────────────┐
        │                       │                            │
┌───────┴─────────┐   ┌─────────┴────────┐         ┌─────────┴────────┐
│inventory_listings│  │  coverage_scores │         │  repair_signals  │
└─────────────────┘   └──────────────────┘         └──────────────────┘
        │                       │                            │
        │              ┌────────┴─────────┐                  │
        │              │     recalls      │ (model-level)    │
        │              └──────────────────┘                  │
        │                                                     │
        └──────────────► competitor_signals (model-level) ◄──┘

   dealers ──1:N──► dealer_scores          dealers ──1:N──► activation_contacts
   (any entity) ──1:N──► evidence  (fact/provenance ledger)
   pipeline runs ──► run_logs
```

Cardinality notes:
- A **dealer** has many **vehicles**; a vehicle belongs to one dealer (per
  observation; the same VIN at two dealers is deduped by `(vin, dealer_id)` and
  treated as two listings of one vehicle identity).
- A **vehicle** has one current **vin_decode**, one current **coverage_scores**
  row, and one or more **inventory_listings** observations over time.
- **recalls**, **repair_signals** (themes), and **competitor_signals** attach at
  the **make/model/year** level and are joined to vehicles via decode keys; they
  are explicitly **model-level**, not VIN-specific, unless a licensed VIN-level
  source is added.

---

## 2. Universal provenance — the fact ledger

**Every fact in the system must be traceable.** The `evidence` table is the
provenance ledger; each row records one fact (field-level) with full lineage.
Structured entity tables (below) hold the working values for fast querying; the
ledger holds the *why we believe it*.

Required columns on every fact (per the operating rules):

| column | meaning |
|--------|---------|
| `entity_type` | dealer / vehicle / inventory_listing / vin_decode / recall / repair_signal / competitor_signal / coverage_score / dealer_score / activation_contact |
| `entity_id` | PK of the referenced entity |
| `field_name` | the specific field this fact supports |
| `value` | the value asserted |
| `source_name` | human-readable source (e.g., "NHTSA vPIC") |
| `source_url` | exact URL fetched |
| `evidence_span` | short verbatim span / snippet supporting the value |
| `confidence` | 0.0–1.0 |
| `extraction_date` | ISO8601 timestamp |
| `inference_flag` | 0 = observed/decoded, 1 = inferred/estimated/model-level |

The same table also carries `source_type` and `risk_tier` (from the source
rights matrix) so any output can be filtered by rights tier.

---

## 3. SQLite table definitions

> Types are SQLite affinities. Timestamps are ISO8601 TEXT. Scores are REAL
> 0–100 unless noted. Booleans are INTEGER 0/1.

### 3.1 `dealers`
```sql
CREATE TABLE dealers (
  dealer_id                       TEXT PRIMARY KEY,   -- slug/uuid
  dealer_name                     TEXT NOT NULL,
  website                         TEXT,
  inventory_url                   TEXT,
  street_address                  TEXT,               -- business address only, if public
  city                            TEXT,
  state                           TEXT,
  zip                             TEXT,
  phone                           TEXT,               -- public business line only
  dealer_type                     TEXT,               -- independent / franchise / buy-here-pay-here / specialty
  market                          TEXT,               -- e.g., "Los Angeles County, CA"
  -- denormalized rollups (populated by score_dealers.py)
  inventory_count                 INTEGER,
  coverage_ready_vehicle_count    INTEGER,
  high_repair_risk_vehicle_count  INTEGER,
  avg_vehicle_age                 REAL,
  avg_mileage                     REAL,
  truck_suv_share                 REAL,               -- 0–1
  luxury_share                    REAL,               -- 0–1
  ev_share                        REAL,               -- 0–1
  source_url                      TEXT,
  confidence                      REAL,
  first_seen                      TEXT,
  last_updated                    TEXT
);
```

### 3.2 `vehicles` (VIN anchor)
```sql
CREATE TABLE vehicles (
  vehicle_id        TEXT PRIMARY KEY,
  dealer_id         TEXT REFERENCES dealers(dealer_id),
  vin               TEXT NOT NULL,
  vin_valid         INTEGER,            -- 0/1 from validate_vins.py
  vin_invalid_reason TEXT,              -- for QA when vin_valid = 0
  -- identity (mirrors current vin_decode for convenience)
  year              INTEGER,
  make              TEXT,
  model             TEXT,
  trim              TEXT,
  body_class        TEXT,
  engine            TEXT,
  drivetrain        TEXT,
  fuel_type         TEXT,
  -- derived
  vehicle_age       INTEGER,            -- current_year - model_year
  mileage_band      TEXT,               -- e.g., "40k-70k","70k-100k","100k-130k",">130k","<40k"
  first_seen        TEXT,
  last_updated      TEXT,
  UNIQUE (vin, dealer_id)               -- dedup key
);
CREATE INDEX idx_vehicles_vin ON vehicles(vin);
CREATE INDEX idx_vehicles_dealer ON vehicles(dealer_id);
```

### 3.3 `inventory_listings` (time-series of observations)
```sql
CREATE TABLE inventory_listings (
  listing_id     TEXT PRIMARY KEY,
  vehicle_id     TEXT REFERENCES vehicles(vehicle_id),
  dealer_id      TEXT REFERENCES dealers(dealer_id),
  vin            TEXT,
  stock_number   TEXT,
  mileage        INTEGER,
  price          REAL,
  listing_url    TEXT,
  days_listed    INTEGER,               -- if available
  observed_date  TEXT,
  source_name    TEXT,
  source_url     TEXT,
  confidence     REAL
);
CREATE INDEX idx_listing_vehicle ON inventory_listings(vehicle_id);
```

### 3.4 `vin_decodes`
```sql
CREATE TABLE vin_decodes (
  decode_id      TEXT PRIMARY KEY,
  vehicle_id     TEXT REFERENCES vehicles(vehicle_id),
  vin            TEXT NOT NULL,
  make           TEXT,
  model          TEXT,
  model_year     INTEGER,
  body_class     TEXT,
  engine         TEXT,                  -- displacement/cylinders if available
  fuel_type      TEXT,
  drivetrain     TEXT,
  transmission   TEXT,
  manufacturer   TEXT,
  plant          TEXT,
  decode_source  TEXT DEFAULT 'NHTSA vPIC',
  decode_raw_json TEXT,                 -- full API payload for audit
  decode_success INTEGER,               -- 0/1
  extraction_date TEXT,
  confidence     REAL
);
CREATE INDEX idx_decode_vin ON vin_decodes(vin);
```

### 3.5 `recalls` (model-level)
```sql
CREATE TABLE recalls (
  recall_id        TEXT PRIMARY KEY,
  make             TEXT,
  model            TEXT,
  model_year       INTEGER,
  campaign_number  TEXT,
  component        TEXT,
  summary          TEXT,
  severity         TEXT,                -- low/medium/high (derived) 
  report_date      TEXT,
  level            TEXT DEFAULT 'model-level',  -- NEVER 'vin-specific' without licensed source
  source_name      TEXT DEFAULT 'NHTSA Recalls',
  source_url       TEXT,
  extraction_date  TEXT,
  confidence       REAL
);
CREATE INDEX idx_recall_mmy ON recalls(make, model, model_year);
```

### 3.6 `repair_signals` (model-level themes + computed risk inputs)
```sql
CREATE TABLE repair_signals (
  signal_id        TEXT PRIMARY KEY,
  make             TEXT,
  model            TEXT,
  model_year       INTEGER,
  component_theme  TEXT,                -- transmission/electrical/AC/powertrain/etc.
  theme_intensity  REAL,               -- 0–1 normalized signal strength
  signal_kind      TEXT,               -- 'nhtsa_complaint' / 'public_forum' / 'heuristic'
  evidence_span    TEXT,               -- short span only
  risk_tier        TEXT,               -- from source rights matrix
  level            TEXT DEFAULT 'model-level',
  source_name      TEXT,
  source_url       TEXT,
  extraction_date  TEXT,
  confidence       REAL,
  inference_flag   INTEGER DEFAULT 1
);
CREATE INDEX idx_repair_mmy ON repair_signals(make, model, model_year);
```

### 3.7 `competitor_signals` (model-level)
```sql
CREATE TABLE competitor_signals (
  competitor_signal_id TEXT PRIMARY KEY,
  competitor_name      TEXT,
  coverage_tier        TEXT,
  covered_components    TEXT,
  positioning_note     TEXT,
  applies_to_segment   TEXT,           -- e.g., "trucks", "EVs", "luxury"
  source_name          TEXT,
  source_url           TEXT,
  risk_tier            TEXT,
  extraction_date      TEXT,
  confidence           REAL,
  inference_flag       INTEGER DEFAULT 1
);
```

### 3.8 `coverage_scores` (vehicle-level)
```sql
CREATE TABLE coverage_scores (
  score_id                  TEXT PRIMARY KEY,
  vehicle_id                TEXT REFERENCES vehicles(vehicle_id),
  vin                       TEXT,
  coverage_readiness_score  REAL,      -- 0–100
  repair_risk_score         REAL,      -- 0–100
  plan_fit_recommendation   TEXT,      -- Essential/Signature/Premium/Executive
  plan_fit_reason           TEXT,
  exclusion_review_flags    TEXT,      -- JSON array of flags
  buyer_urgency_score       REAL,      -- 0–100
  recommended_message_angle TEXT,
  recall_count              INTEGER,
  recall_severity           TEXT,
  component_risk_themes      TEXT,      -- JSON array
  scoring_version           TEXT,      -- ties to scoring_config.json version
  score_date                TEXT,
  confidence                REAL
);
CREATE INDEX idx_cov_vehicle ON coverage_scores(vehicle_id);
```

### 3.9 `dealer_scores`
```sql
CREATE TABLE dealer_scores (
  dealer_score_id                TEXT PRIMARY KEY,
  dealer_id                      TEXT REFERENCES dealers(dealer_id),
  dealer_coverage_opportunity_score REAL,   -- 0–100
  coverage_ready_vehicle_share   REAL,       -- 0–1
  high_repair_risk_vehicle_count INTEGER,
  truck_suv_luxury_share         REAL,
  avg_mileage_in_prime_range_share REAL,
  dealer_location_priority       REAL,
  data_completeness              REAL,
  recommended_partner_pitch      TEXT,
  recommended_plan_mix           TEXT,        -- JSON: {Signature: .35, Premium: .45, Executive: .20}
  scoring_version                TEXT,
  score_date                     TEXT,
  confidence                     REAL
);
```

### 3.10 `evidence` (fact/provenance ledger — see §2)
```sql
CREATE TABLE evidence (
  evidence_id     TEXT PRIMARY KEY,
  entity_type     TEXT NOT NULL,
  entity_id       TEXT NOT NULL,
  field_name      TEXT,
  value           TEXT,
  source_name     TEXT,
  source_url      TEXT,
  source_type     TEXT,                -- official_api / dealer_site / forum / review / business_listing
  evidence_span   TEXT,
  confidence      REAL,
  extraction_date TEXT,
  inference_flag  INTEGER DEFAULT 0,   -- 0 observed, 1 inferred/model-level
  risk_tier       TEXT                 -- SAFE_PUBLIC / SAMPLE_ONLY / LICENSE_REQUIRED
);
CREATE INDEX idx_evidence_entity ON evidence(entity_type, entity_id);
```

### 3.11 `run_logs`
```sql
CREATE TABLE run_logs (
  run_id          TEXT PRIMARY KEY,
  script_name     TEXT,
  source_name     TEXT,
  apify_actor     TEXT,                -- if applicable
  apify_run_id    TEXT,                -- if applicable
  started_at      TEXT,
  finished_at     TEXT,
  status          TEXT,                -- success / partial / error
  records_in      INTEGER,
  records_out     INTEGER,
  records_rejected INTEGER,
  notes           TEXT,
  error_detail    TEXT
);
```

### 3.12 `activation_contacts` (B2B only — empty in Phase 1)
```sql
CREATE TABLE activation_contacts (
  dealer_id                 TEXT REFERENCES dealers(dealer_id),
  recommended_personas      TEXT,      -- JSON array: F&I director, GM, used-car mgr...
  activation_source         TEXT,      -- 'apollo' (later phases only)
  contact_enrichment_status TEXT,      -- 'not_started' in Phase 1
  notes                     TEXT
  -- NOTE: business roles only. NEVER consumer names/emails/phones.
  -- NOTE: not attached to any VIN. Populated only in a later, approved phase.
);
```

---

## 4. Export views (denormalized)

The buyer-facing exports (see `export_outputs.py`) are denormalized joins, not
new sources of truth:

- **`vehicle_signal_graph.csv` / `.json`** — one row per vehicle: `vehicles`
  ⨝ `vin_decodes` ⨝ latest `inventory_listings` ⨝ `coverage_scores` ⨝
  model-level `recalls`/`repair_signals` aggregates. Matches the Phase 1
  "Vehicle fields" schema.
- **`dealer_opportunity_rankings.csv`** — `dealers` ⨝ `dealer_scores`, ordered
  by `dealer_coverage_opportunity_score`. Matches the Phase 1 "Dealer fields".
- **`source_evidence.json`** — the `evidence` ledger, optionally filtered to the
  entities present in an export. Matches the Phase 1 "Evidence fields".

---

## 5. Data-integrity rules

1. **Dedup** on `(vin, dealer_id)`; the same VIN across dealers is preserved as
   distinct listings of one identity.
2. **Invalid VINs** are stored (`vin_valid = 0`, with `vin_invalid_reason`) for
   QA but are **not** decoded or scored.
3. **Model-level vs VIN-level**: `recalls`, `repair_signals`,
   `competitor_signals` carry `level = 'model-level'` and may not be relabeled
   VIN-specific without a licensed VIN-level source.
4. **No consumer PII** column exists anywhere by design. `activation_contacts`
   holds B2B business roles only and is empty in Phase 1.
5. **Provenance or it didn't happen**: a value without an `evidence` row (or
   inline source fields) is not export-eligible.
6. **Scoring reproducibility**: every score row carries `scoring_version` tying
   it to a specific `scoring_config.json`.
