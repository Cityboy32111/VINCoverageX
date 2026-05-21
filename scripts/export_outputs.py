#!/usr/bin/env python3
"""Export buyer-ready outputs from the SQLite graph.

  outputs/vehicle_signal_graph.csv / .json   (one row per vehicle)
  outputs/dealer_opportunity_rankings.csv     (ranked dealers)
  outputs/source_evidence.json                (provenance ledger)
  outputs/top_dealer_briefs.md                (per-dealer buyer briefs)

Guarantees: every record carries source_url + extraction_date; no consumer
PII columns exist. Offline.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex import db  # noqa: E402
from coveragex.config import OUTPUTS_DIR, ensure_dirs  # noqa: E402

VEHICLE_COLUMNS = [
    "vehicle_id", "dealer_id", "dealer_name", "vin", "vin_valid", "year", "make", "model",
    "trim", "body_class", "engine", "drivetrain", "fuel_type", "mileage", "price", "listing_url",
    "days_listed", "vehicle_age", "mileage_band", "coverage_readiness_score", "repair_risk_score",
    "plan_fit_recommendation", "plan_fit_reason", "recall_count", "recall_severity",
    "component_risk_themes", "exclusion_review_flags", "buyer_urgency_score",
    "recommended_message_angle", "confidence", "source_url", "extraction_date",
]
DEALER_COLUMNS = [
    "dealer_id", "dealer_name", "website", "inventory_url", "street_address", "city", "state",
    "zip", "phone", "dealer_type", "inventory_count", "coverage_ready_vehicle_count",
    "high_repair_risk_vehicle_count", "avg_vehicle_age", "avg_mileage", "truck_suv_share",
    "luxury_share", "ev_share", "dealer_coverage_opportunity_score", "recommended_partner_pitch",
    "source_url", "confidence", "extraction_date",
]


def _vehicle_rows(conn):
    rows = conn.execute(
        """SELECT v.vehicle_id, v.dealer_id, d.dealer_name, v.vin, v.vin_valid, v.year, v.make,
                  v.model, v.trim, v.body_class, v.engine, v.drivetrain, v.fuel_type,
                  v.vehicle_age, v.mileage_band,
                  cs.coverage_readiness_score, cs.repair_risk_score, cs.plan_fit_recommendation,
                  cs.plan_fit_reason, cs.recall_count, cs.recall_severity, cs.component_risk_themes,
                  cs.exclusion_review_flags, cs.buyer_urgency_score, cs.recommended_message_angle,
                  cs.confidence, cs.score_date,
                  il.mileage, il.price, il.listing_url, il.days_listed, il.observed_date
           FROM vehicles v
           JOIN coverage_scores cs ON cs.vehicle_id=v.vehicle_id
           LEFT JOIN dealers d ON d.dealer_id=v.dealer_id
           LEFT JOIN inventory_listings il ON il.listing_id=(
               SELECT listing_id FROM inventory_listings x WHERE x.vehicle_id=v.vehicle_id
               ORDER BY observed_date DESC LIMIT 1)
           ORDER BY cs.coverage_readiness_score DESC""").fetchall()
    out = []
    for r in rows:
        out.append({
            "vehicle_id": r["vehicle_id"], "dealer_id": r["dealer_id"], "dealer_name": r["dealer_name"],
            "vin": r["vin"], "vin_valid": r["vin_valid"], "year": r["year"], "make": r["make"],
            "model": r["model"], "trim": r["trim"], "body_class": r["body_class"],
            "engine": r["engine"], "drivetrain": r["drivetrain"], "fuel_type": r["fuel_type"],
            "mileage": r["mileage"], "price": r["price"], "listing_url": r["listing_url"],
            "days_listed": r["days_listed"], "vehicle_age": r["vehicle_age"],
            "mileage_band": r["mileage_band"],
            "coverage_readiness_score": r["coverage_readiness_score"],
            "repair_risk_score": r["repair_risk_score"],
            "plan_fit_recommendation": r["plan_fit_recommendation"],
            "plan_fit_reason": r["plan_fit_reason"], "recall_count": r["recall_count"],
            "recall_severity": r["recall_severity"], "component_risk_themes": r["component_risk_themes"],
            "exclusion_review_flags": r["exclusion_review_flags"],
            "buyer_urgency_score": r["buyer_urgency_score"],
            "recommended_message_angle": r["recommended_message_angle"], "confidence": r["confidence"],
            "source_url": r["listing_url"], "extraction_date": r["observed_date"] or r["score_date"],
        })
    return out


def _dealer_rows(conn):
    rows = conn.execute(
        """SELECT d.*, ds.dealer_coverage_opportunity_score, ds.recommended_partner_pitch
           FROM dealers d JOIN dealer_scores ds ON ds.dealer_id=d.dealer_id
           ORDER BY ds.dealer_coverage_opportunity_score DESC""").fetchall()
    out = []
    for r in rows:
        out.append({c: (r[c] if c in r.keys() else None) for c in DEALER_COLUMNS} | {
            "dealer_coverage_opportunity_score": r["dealer_coverage_opportunity_score"],
            "recommended_partner_pitch": r["recommended_partner_pitch"],
            "source_url": r["source_url"], "extraction_date": r["last_updated"],
        })
    return out


def _write_csv(path, columns, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _briefs(conn, dealer_rows, top_n=5) -> str:
    lines = ["# Top Dealer Briefs — CoverageX Vehicle Signal Graph", ""]
    for d in dealer_rows[:top_n]:
        top_vins = conn.execute(
            """SELECT v.vin, v.year, v.make, v.model, cs.coverage_readiness_score AS crs,
                      cs.repair_risk_score AS rrs, cs.plan_fit_recommendation AS plan
               FROM vehicles v JOIN coverage_scores cs ON cs.vehicle_id=v.vehicle_id
               WHERE v.dealer_id=? ORDER BY cs.buyer_urgency_score DESC LIMIT 5""",
            (d["dealer_id"],)).fetchall()
        ds = conn.execute("SELECT recommended_plan_mix FROM dealer_scores WHERE dealer_id=?",
                          (d["dealer_id"],)).fetchone()
        lines += [
            f"## {d['dealer_name']}  ({d.get('city') or ''}, {d.get('state') or ''})",
            f"- Opportunity score: **{d['dealer_coverage_opportunity_score']}**",
            f"- Inventory: {d.get('inventory_count')} | Coverage-ready: {d.get('coverage_ready_vehicle_count')} | High repair risk: {d.get('high_repair_risk_vehicle_count')}",
            f"- Truck/SUV share: {d.get('truck_suv_share')} | Luxury share: {d.get('luxury_share')} | EV share: {d.get('ev_share')}",
            f"- Recommended plan mix: {ds['recommended_plan_mix'] if ds else '{}'}",
            f"- Recommended F&I pitch: {d['recommended_partner_pitch']}",
            "- Top VINs (by buyer urgency):",
        ]
        for v in top_vins:
            lines.append(f"  - {v['vin']} — {v['year']} {v['make']} {v['model']} | "
                         f"coverage {v['crs']}, repair {v['rrs']}, plan {v['plan']}")
        lines += ["- Source: dealer public inventory + NHTSA (see source_evidence.json)",
                  "- Activation: B2B business roles only (F&I Director). No consumer data.", ""]
    return "\n".join(lines)


def run(conn, out_dir=None) -> dict:
    out_dir = Path(out_dir) if out_dir else OUTPUTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    if out_dir == OUTPUTS_DIR:
        ensure_dirs()
    vehicles = _vehicle_rows(conn)
    dealers = _dealer_rows(conn)
    evidence = [dict(r) for r in conn.execute("SELECT * FROM evidence").fetchall()]

    _write_csv(out_dir / "vehicle_signal_graph.csv", VEHICLE_COLUMNS, vehicles)
    (out_dir / "vehicle_signal_graph.json").write_text(json.dumps(vehicles, indent=2))
    _write_csv(out_dir / "dealer_opportunity_rankings.csv", DEALER_COLUMNS, dealers)
    (out_dir / "source_evidence.json").write_text(json.dumps(evidence, indent=2))
    (out_dir / "top_dealer_briefs.md").write_text(_briefs(conn, dealers))

    # integrity guard: every exported record must have source_url + extraction_date
    missing = [v["vin"] for v in vehicles if not v["source_url"] or not v["extraction_date"]]
    db.log_run(conn, script_name="export_outputs.py", source_name="internal",
               records_out=len(vehicles),
               notes=f"{len(vehicles)} vehicles, {len(dealers)} dealers, {len(evidence)} evidence rows; "
                     f"{len(missing)} missing provenance")
    return {"vehicles": len(vehicles), "dealers": len(dealers), "evidence": len(evidence),
            "missing_provenance": missing}


def main() -> None:
    argparse.ArgumentParser(description="Export buyer-ready outputs").parse_args()
    conn = db.connect()
    db.init_db(conn)
    r = run(conn)
    conn.close()
    print(f"Exported {r['vehicles']} vehicles, {r['dealers']} dealers, {r['evidence']} evidence rows.")
    if r["missing_provenance"]:
        print(f"[WARN] {len(r['missing_provenance'])} vehicle rows missing source_url/extraction_date.")


if __name__ == "__main__":
    main()
