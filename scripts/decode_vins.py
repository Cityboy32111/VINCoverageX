#!/usr/bin/env python3
"""Decode valid VINs via NHTSA vPIC (SAFE PUBLIC). Network-dependent.

Writes vin_decodes, updates vehicles identity + vehicle_age + mileage_band,
and records evidence rows. Decodes only vin_valid=1 vehicles. On a blocked
host it reports the blocker honestly and exits non-zero (no fabricated data).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex import db  # noqa: E402
from coveragex.config import source_config  # noqa: E402
from coveragex.nhtsa import NhtsaError, decode_vin  # noqa: E402
from coveragex.vin import mileage_band, vehicle_age  # noqa: E402


def _latest_mileage(conn, vehicle_id: str) -> int | None:
    row = conn.execute(
        "SELECT mileage FROM inventory_listings WHERE vehicle_id=? AND mileage IS NOT NULL "
        "ORDER BY observed_date DESC LIMIT 1", (vehicle_id,)).fetchone()
    return row["mileage"] if row else None


def run(conn, limit: int | None = None) -> dict:
    rate = source_config().get("nhtsa", {}).get("rate_limit_per_sec", 5)
    rows = conn.execute(
        "SELECT v.vehicle_id, v.vin FROM vehicles v "
        "LEFT JOIN vin_decodes d ON d.vehicle_id=v.vehicle_id "
        "WHERE v.vin_valid=1 AND d.decode_id IS NULL").fetchall()
    if limit:
        rows = rows[:limit]

    ok = fail = 0
    for row in rows:
        try:
            d = decode_vin(row["vin"])
        except NhtsaError as e:
            db.log_run(conn, script_name="decode_vins.py", source_name="NHTSA vPIC",
                       status="error", records_in=len(rows), records_out=ok,
                       error_detail=str(e))
            conn.commit()
            raise SystemExit(f"\n[BLOCKER] {e}\nDecoded {ok} before failure. No data fabricated.")
        conn.execute(
            """INSERT INTO vin_decodes (decode_id, vehicle_id, vin, make, model, model_year,
                body_class, engine, fuel_type, drivetrain, transmission, manufacturer, plant,
                decode_source, decode_raw_json, decode_success, extraction_date, confidence)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (db.new_id("dec_"), row["vehicle_id"], row["vin"], d["make"], d["model"],
             d["model_year"], d["body_class"], d["engine"], d["fuel_type"], d["drivetrain"],
             d["transmission"], d["manufacturer"], d["plant"], "NHTSA vPIC",
             db.jdump(d["raw"]), 1 if d["decode_success"] else 0, db.now_iso(),
             0.95 if d["decode_success"] else 0.4),
        )
        age = vehicle_age(d["model_year"])
        mileage = _latest_mileage(conn, row["vehicle_id"])
        conn.execute(
            """UPDATE vehicles SET year=?, make=?, model=?, body_class=?, engine=?,
                drivetrain=?, fuel_type=?, vehicle_age=?, mileage_band=?, last_updated=?
               WHERE vehicle_id=?""",
            (d["model_year"], d["make"], d["model"], d["body_class"], d["engine"],
             d["drivetrain"], d["fuel_type"], age, mileage_band(mileage), db.now_iso(),
             row["vehicle_id"]),
        )
        url = f"{source_config()['nhtsa']['vpic_base']}/vehicles/DecodeVinValues/{row['vin']}?format=json"
        for field in ("make", "model", "model_year", "body_class"):
            if d.get(field):
                db.insert_evidence(conn, entity_type="vehicle", entity_id=row["vehicle_id"],
                                   field_name=field, value=d[field], source_name="NHTSA vPIC",
                                   source_url=url, source_type="official_api",
                                   confidence=0.95, inference_flag=0, risk_tier="SAFE_PUBLIC")
        if d["decode_success"]:
            ok += 1
        else:
            fail += 1
        time.sleep(1.0 / max(1, rate))
    conn.commit()

    total = ok + fail
    db.log_run(conn, script_name="decode_vins.py", source_name="NHTSA vPIC",
               records_in=len(rows), records_out=ok, records_rejected=fail,
               notes=f"decode success {ok}/{total}" if total else "nothing to decode")
    return {"attempted": len(rows), "success": ok, "fail": fail}


def main() -> None:
    p = argparse.ArgumentParser(description="Decode valid VINs via NHTSA vPIC")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()
    conn = db.connect()
    db.init_db(conn)
    r = run(conn, args.limit)
    conn.close()
    rate = (r["success"] / r["attempted"] * 100) if r["attempted"] else 0
    print(f"Decode: {r['success']}/{r['attempted']} succeeded ({rate:.0f}%).")


if __name__ == "__main__":
    main()
