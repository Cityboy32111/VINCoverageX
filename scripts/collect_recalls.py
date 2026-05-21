#!/usr/bin/env python3
"""Collect MODEL-LEVEL recalls from NHTSA for decoded make/model/year combos.

Network-dependent. Recalls are stored as level='model-level' and must never be
presented as VIN-specific open-recall status. Severity is derived from the
recall components + count per scoring_config.json.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex import db  # noqa: E402
from coveragex.config import scoring_config, source_config  # noqa: E402
from coveragex.nhtsa import NhtsaError, get_recalls  # noqa: E402


def derive_severity(components: list[str], count: int, cfg: dict) -> str:
    rs = cfg["recall_severity"]
    text = " ".join(components).lower()
    if any(h in text for h in rs["high_components"]) or count >= rs["high_count_threshold"]:
        return "high"
    if count >= rs["medium_count_threshold"]:
        return "medium"
    return "low" if count else "none"


def run(conn, limit: int | None = None) -> dict:
    cfg = scoring_config()
    rate = source_config().get("nhtsa", {}).get("rate_limit_per_sec", 5)
    combos = conn.execute(
        "SELECT DISTINCT make, model, model_year FROM vin_decodes "
        "WHERE make IS NOT NULL AND model IS NOT NULL AND model_year IS NOT NULL").fetchall()
    if limit:
        combos = combos[:limit]

    total_recalls = 0
    for c in combos:
        try:
            recalls = get_recalls(c["make"], c["model"], c["model_year"])
        except NhtsaError as e:
            db.log_run(conn, script_name="collect_recalls.py", source_name="NHTSA Recalls",
                       status="error", error_detail=str(e))
            conn.commit()
            raise SystemExit(f"\n[BLOCKER] {e}\nCollected {total_recalls} recalls before failure.")
        components = [r.get("component", "") for r in recalls]
        severity = derive_severity(components, len(recalls), cfg)
        url = (f"{source_config()['nhtsa']['recalls_base']}?make={c['make']}"
               f"&model={c['model']}&modelYear={c['model_year']}")
        for r in recalls:
            rid = db.new_id("rec_")
            conn.execute(
                """INSERT INTO recalls (recall_id, make, model, model_year, campaign_number,
                    component, summary, severity, report_date, level, source_name, source_url,
                    extraction_date, confidence)
                   VALUES (?,?,?,?,?,?,?,?,?, 'model-level', 'NHTSA Recalls', ?,?,?)""",
                (rid, c["make"], c["model"], c["model_year"], r.get("campaign_number"),
                 r.get("component"), (r.get("summary") or "")[:1000], severity,
                 r.get("report_date"), url, db.now_iso(), 0.9),
            )
            db.insert_evidence(conn, entity_type="recall", entity_id=rid,
                               field_name="campaign", value=r.get("campaign_number"),
                               source_name="NHTSA Recalls", source_url=url,
                               source_type="official_api", evidence_span=(r.get("component") or "")[:120],
                               confidence=0.9, inference_flag=1, risk_tier="SAFE_PUBLIC")
            total_recalls += 1
        time.sleep(1.0 / max(1, rate))
    conn.commit()
    db.log_run(conn, script_name="collect_recalls.py", source_name="NHTSA Recalls",
               records_in=len(combos), records_out=total_recalls,
               notes=f"{total_recalls} model-level recalls across {len(combos)} combos")
    return {"combos": len(combos), "recalls": total_recalls}


def main() -> None:
    p = argparse.ArgumentParser(description="Collect model-level NHTSA recalls")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()
    conn = db.connect()
    db.init_db(conn)
    r = run(conn, args.limit)
    conn.close()
    print(f"Recalls: {r['recalls']} model-level recalls across {r['combos']} make/model/year combos.")


if __name__ == "__main__":
    main()
