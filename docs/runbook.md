# Runbook — CoverageX Vehicle Signal Graph (Phase 1)

How to run the pipeline, what each step does, and how to clear the network
blocker. **Claude Code is the product engine; Apify is the collection engine.**

---

## 0. Prerequisites

```bash
pip install -r requirements.txt           # requests, beautifulsoup4, pytest
cp config/.env.example config/.env        # then fill in APIFY_TOKEN (Apollo optional, Phase 2)
```

`config/.env` is **gitignored** — secrets are never committed. NHTSA needs no key.

### Network access (REQUIRED for collection)
Collection calls these hosts. In a restricted environment they must be on the
allowlist (symptom when blocked: `HTTP 403 x-deny-reason: host_not_allowed`):

| Host | Used for | Engine |
|------|----------|--------|
| `api.apify.com` | dealer discovery + inventory crawling | Apify |
| dealer websites | inventory pages (crawled via Apify) | Apify |
| `vpic.nhtsa.dot.gov` | VIN decode | code |
| `api.nhtsa.gov` | recalls + complaints | code |

If these are blocked, the pipeline still runs but collects nothing and says so
honestly (no fabricated data). Either widen the environment network policy to
allow the hosts above, or run the pipeline locally with `config/.env`.

---

## 1. One-command pipeline

```bash
python scripts/run_pipeline.py                 # Apify discovery -> full pipeline
python scripts/run_pipeline.py --test          # 3-dealer inventory test (do this first)
python scripts/run_pipeline.py --no-apify      # discovery from config/dealers_seed.csv
python scripts/run_pipeline.py --forums        # also collect SAMPLE-ONLY forum repair signals
python scripts/run_pipeline.py --skip-collect  # re-score/re-export existing local data only
```

The orchestrator runs each stage resiliently: if a network stage is blocked it
prints the blocker, skips it, and continues with the offline stages.

---

## 2. Step-by-step (individual scripts)

| Order | Command | Engine | Needs network |
|------|---------|--------|:---:|
| 1 | `python scripts/discover_dealers.py` (or `--no-apify`, `--seed PATH`) | Apify Maps | yes |
| 2 | `python scripts/collect_inventory.py --test` then full | Apify crawler | yes |
| 3 | `python scripts/validate_vins.py` | code | no |
| 4 | `python scripts/decode_vins.py` | NHTSA | yes |
| 5 | `python scripts/collect_recalls.py` | NHTSA | yes |
| 6 | `python scripts/collect_repair_signals.py [--forums]` | NHTSA + sample | yes |
| 7 | `python scripts/score_vehicles.py` | code | no |
| 8 | `python scripts/score_dealers.py` | code | no |
| 9 | `python scripts/export_outputs.py` | code | no |
| 10 | `python scripts/generate_manus_demo_package.py` | code | no |

`collect_competitor_signals.py` is optional (provide `--urls NAME=URL`).
`enrich_b2b_contacts.py` is **disabled in Phase 1** (B2B business roles only, later phase).

**Always start collection with the 3-dealer test** (`collect_inventory.py
--test`): inspect `data/raw/inventory_*.json`, confirm VIN/mileage/price parse
correctly, then scale up.

---

## 3. Outputs

Written to `outputs/` (gitignored):
- `vehicle_signal_graph.csv` / `.json` — one row per scored vehicle.
- `dealer_opportunity_rankings.csv` — ranked dealers.
- `source_evidence.json` — provenance ledger (source URL, timestamp, confidence, span).
- `top_dealer_briefs.md` — per-dealer buyer briefs.
- `coveragex_demo_summary.md` — one-dealer buyer demo (from real data).
- `manus_demo_prompt.md` — interactive-dashboard build spec for Manus.

Local store: `data/vehicle_signal_graph.sqlite` (gitignored). QA: invalid VINs
in `data/processed/invalid_vins.json`; run history in the `run_logs` table.

---

## 4. Tests

```bash
python -m pytest -q          # VIN validation, scoring, dedup, exports (all offline)
```

---

## 5. Success criteria (Phase 1)

≥25 dealers · ≥500 valid VINs · ≥80% decode · ≥50% scored · ≥10 dealers scored ·
100% records with source URL + extraction date · 0 consumer PII · 0 production DB
writes · demo package created.

**If short of 500 VINs:** do not fabricate. Report the count + per-dealer
breakdown (`run_logs`), explain the blocker, and recommend changing market,
source strategy, or using Apify marketplace actors where terms permit.

---

## 6. Compliance reminders (every run)

- Public/permissioned/licensed data only; respect robots.txt, rate limits, terms.
- **No consumer PII, ever.** B2B enrichment off in Phase 1.
- Provenance on every fact; inferred/model-level/sample values labeled as such.
- Never assert verified claims/title/open-recall without a licensed source.
- Local SQLite only — no Supabase/production writes without explicit approval.
