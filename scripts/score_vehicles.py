#!/usr/bin/env python3
"""Score every decoded vehicle: coverage readiness, repair risk, plan fit,
exclusion/review, buyer urgency, message angle.

Joins latest listing (mileage/price/text), model-level recalls, and
model-level repair themes. Writes coverage_scores + derived-fact evidence.
Offline (pure scoring engine). Re-runnable (replaces prior scores).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex import db, scoring  # noqa: E402
from coveragex.config import scoring_config  # noqa: E402

_SEV_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


def _recall_summary(conn, make, model, year) -> tuple[int, str | None]:
    rows = conn.execute(
        "SELECT severity FROM recalls WHERE make=? AND model=? AND model_year=?",
        (make, model, year)).fetchall()
    if not rows:
        return 0, None
    best = max((r["severity"] or "none" for r in rows), key=lambda s: _SEV_RANK.get(s, 0))
    return len(rows), best


def _themes(conn, make, model, year) -> list[dict]:
    rows = conn.execute(
        "SELECT component_theme, MAX(theme_intensity) AS intensity FROM repair_signals "
        "WHERE make=? AND model=? AND model_year=? GROUP BY component_theme "
        "ORDER BY intensity DESC", (make, model, year)).fetchall()
    return [{"theme": r["component_theme"], "intensity": r["intensity"]} for r in rows]


def _latest_listing(conn, vehicle_id):
    return conn.execute(
        "SELECT mileage, price, listing_text FROM inventory_listings WHERE vehicle_id=? "
        "ORDER BY observed_date DESC LIMIT 1", (vehicle_id,)).fetchone()


def run(conn) -> dict:
    cfg = scoring_config()
    rows = conn.execute(
        "SELECT * FROM vehicles WHERE vin_valid=1 AND make IS NOT NULL").fetchall()
    scored = 0
    for v in rows:
        listing = _latest_listing(conn, v["vehicle_id"])
        recall_count, recall_sev = _recall_summary(conn, v["make"], v["model"], v["year"])
        vehicle = {
            "make": v["make"], "model": v["model"], "model_year": v["year"],
            "body_class": v["body_class"], "engine": v["engine"],
            "drivetrain": v["drivetrain"], "fuel_type": v["fuel_type"], "trim": v["trim"],
            "vehicle_age": v["vehicle_age"],
            "mileage": listing["mileage"] if listing else None,
            "price": listing["price"] if listing else None,
            "listing_text": listing["listing_text"] if listing else None,
            "recall_count": recall_count, "recall_severity": recall_sev,
            "component_themes": _themes(conn, v["make"], v["model"], v["year"]),
            "decode_success": True,
        }
        s = scoring.score_vehicle(vehicle, cfg)

        conn.execute("DELETE FROM coverage_scores WHERE vehicle_id=?", (v["vehicle_id"],))
        conn.execute(
            """INSERT INTO coverage_scores (score_id, vehicle_id, vin, coverage_readiness_score,
                repair_risk_score, plan_fit_recommendation, plan_fit_reason, exclusion_review_flags,
                exclusion_review_score, buyer_urgency_score, recommended_message_angle, recall_count,
                recall_severity, component_risk_themes, scoring_version, score_date, confidence)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (db.new_id("cs_"), v["vehicle_id"], v["vin"], s["coverage_readiness_score"],
             s["repair_risk_score"], s["plan_fit_recommendation"], s["plan_fit_reason"],
             db.jdump(s["exclusion_review_flags"]), s["exclusion_review_score"],
             s["buyer_urgency_score"], s["recommended_message_angle"], recall_count, recall_sev,
             db.jdump(s["component_risk_themes"]), s["scoring_version"], db.now_iso(), 0.7),
        )
        for field, val in (("coverage_readiness_score", s["coverage_readiness_score"]),
                           ("repair_risk_score", s["repair_risk_score"]),
                           ("plan_fit_recommendation", s["plan_fit_recommendation"])):
            db.insert_evidence(conn, entity_type="coverage_score", entity_id=v["vehicle_id"],
                               field_name=field, value=val,
                               source_name=f"CoverageX scoring {s['scoring_version']}",
                               source_url="internal:docs/scoring_methodology.md",
                               source_type="derived", evidence_span=s["plan_fit_reason"][:200],
                               confidence=0.7, inference_flag=1, risk_tier="SAFE_PUBLIC")
        scored += 1
    conn.commit()
    db.log_run(conn, script_name="score_vehicles.py", source_name="internal",
               records_in=len(rows), records_out=scored, notes=f"scored {scored} vehicles")
    return {"eligible": len(rows), "scored": scored}


def main() -> None:
    argparse.ArgumentParser(description="Score vehicles").parse_args()
    conn = db.connect()
    db.init_db(conn)
    r = run(conn)
    conn.close()
    print(f"Scored {r['scored']} of {r['eligible']} eligible vehicles.")


if __name__ == "__main__":
    main()
