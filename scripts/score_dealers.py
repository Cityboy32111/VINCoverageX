#!/usr/bin/env python3
"""Roll up vehicle scores into dealer-level opportunity scores, plan mix, and
pitch angles. Updates dealers rollup columns + dealer_scores. Offline.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex import db, scoring  # noqa: E402
from coveragex.config import scoring_config  # noqa: E402
from coveragex.vin import in_prime_mileage  # noqa: E402


def _dealer_vehicles(conn, dealer_id):
    return conn.execute(
        """SELECT v.vehicle_id, v.make, v.model, v.body_class, v.fuel_type, v.vehicle_age,
                  cs.coverage_readiness_score AS crs, cs.repair_risk_score AS rrs,
                  cs.plan_fit_recommendation AS plan, cs.recall_count AS rc,
                  (SELECT mileage FROM inventory_listings il WHERE il.vehicle_id=v.vehicle_id
                   ORDER BY observed_date DESC LIMIT 1) AS mileage
           FROM vehicles v JOIN coverage_scores cs ON cs.vehicle_id=v.vehicle_id
           WHERE v.dealer_id=? AND v.vin_valid=1""", (dealer_id,)).fetchall()


def run(conn) -> dict:
    cfg = scoring_config()
    ready_th = cfg["coverage_readiness"]["ready_threshold"]
    high_th = cfg["repair_risk"]["high_threshold"]
    dealers = conn.execute("SELECT * FROM dealers").fetchall()
    scored = 0

    for d in dealers:
        vehicles = _dealer_vehicles(conn, d["dealer_id"])
        if not vehicles:
            continue
        inv = len(vehicles)
        ready = [v for v in vehicles if (v["crs"] or 0) >= ready_th]
        counts = Counter()
        ages, mileages, total_recalls = [], [], 0
        for v in vehicles:
            feat = scoring.derive_features(
                {"make": v["make"], "body_class": v["body_class"], "fuel_type": v["fuel_type"]}, cfg)
            counts["truck"] += feat["is_truck"]
            counts["suv"] += feat["is_suv"]
            counts["luxury"] += feat["is_luxury"]
            counts["ev"] += feat["is_ev"]
            counts["tsl"] += feat["truck_suv_luxury"]
            if v["vehicle_age"] is not None:
                ages.append(v["vehicle_age"])
            if v["mileage"] is not None:
                mileages.append(v["mileage"])
            if in_prime_mileage(v["mileage"]):
                counts["prime"] += 1
            if v["make"]:
                counts["decoded"] += 1
            total_recalls += (v["rc"] or 0)

        rollup = {
            "inventory_count": inv,
            "coverage_ready_count": len(ready),
            "high_repair_risk_count": sum(1 for v in vehicles if (v["rrs"] or 0) >= high_th),
            "truck_suv_luxury_count": counts["tsl"], "truck_count": counts["truck"],
            "suv_count": counts["suv"], "luxury_count": counts["luxury"], "ev_count": counts["ev"],
            "prime_mileage_count": counts["prime"], "valid_decode_count": counts["decoded"],
            "total_recalls": total_recalls, "city": d["city"], "county": d["county"],
        }
        opp = scoring.dealer_opportunity_score(rollup, cfg)

        mix_counter = Counter(v["plan"] for v in ready if v["plan"])
        total_mix = sum(mix_counter.values()) or 1
        plan_mix = {k: round(c / total_mix, 2) for k, c in mix_counter.items()}
        pitch = scoring.dealer_pitch(rollup, plan_mix, cfg)

        avg_age = round(sum(ages) / len(ages), 1) if ages else None
        avg_mileage = round(sum(mileages) / len(mileages)) if mileages else None
        conn.execute(
            """UPDATE dealers SET inventory_count=?, coverage_ready_vehicle_count=?,
                high_repair_risk_vehicle_count=?, avg_vehicle_age=?, avg_mileage=?,
                truck_suv_share=?, luxury_share=?, ev_share=?, last_updated=? WHERE dealer_id=?""",
            (inv, len(ready), rollup["high_repair_risk_count"], avg_age, avg_mileage,
             pitch["truck_suv_share"], pitch["luxury_share"], pitch["ev_share"],
             db.now_iso(), d["dealer_id"]),
        )
        conn.execute("DELETE FROM dealer_scores WHERE dealer_id=?", (d["dealer_id"],))
        conn.execute(
            """INSERT INTO dealer_scores (dealer_score_id, dealer_id,
                dealer_coverage_opportunity_score, coverage_ready_vehicle_share,
                high_repair_risk_vehicle_count, truck_suv_luxury_share,
                avg_mileage_in_prime_range_share, dealer_location_priority, data_completeness,
                recommended_partner_pitch, recommended_plan_mix, scoring_version, score_date, confidence)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (db.new_id("ds_"), d["dealer_id"], opp["score"], opp["coverage_ready_share"],
             rollup["high_repair_risk_count"], opp["truck_suv_luxury_share"],
             opp["prime_mileage_share"], opp["components"]["location_priority"] / 100,
             opp["components"]["data_completeness"] / 100, pitch["recommended_partner_pitch"],
             db.jdump(plan_mix), cfg["scoring_version"], db.now_iso(), 0.7),
        )
        conn.execute("DELETE FROM activation_contacts WHERE dealer_id=?", (d["dealer_id"],))
        conn.execute(
            "INSERT INTO activation_contacts (dealer_id, recommended_personas, activation_source, contact_enrichment_status, notes) VALUES (?,?,?,?,?)",
            (d["dealer_id"], db.jdump(pitch["recommended_personas"]), None, "not_started",
             "B2B business roles only; no consumer data; not attached to any VIN."),
        )
        db.insert_evidence(conn, entity_type="dealer_score", entity_id=d["dealer_id"],
                           field_name="dealer_coverage_opportunity_score", value=opp["score"],
                           source_name=f"CoverageX scoring {cfg['scoring_version']}",
                           source_url="internal:docs/scoring_methodology.md", source_type="derived",
                           evidence_span=opp["band"], confidence=0.7, inference_flag=1,
                           risk_tier="SAFE_PUBLIC")
        scored += 1
    conn.commit()
    db.log_run(conn, script_name="score_dealers.py", source_name="internal",
               records_in=len(dealers), records_out=scored, notes=f"scored {scored} dealers")
    return {"dealers": len(dealers), "scored": scored}


def main() -> None:
    argparse.ArgumentParser(description="Score dealers").parse_args()
    conn = db.connect()
    db.init_db(conn)
    r = run(conn)
    conn.close()
    print(f"Scored {r['scored']} of {r['dealers']} dealers.")


if __name__ == "__main__":
    main()
