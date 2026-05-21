#!/usr/bin/env python3
"""Validate VINs already collected into the vehicles table.

Sets vin_valid / vin_invalid_reason / check_digit_valid. Invalid VINs are
kept for QA (written to data/processed/invalid_vins.json) but are not decoded
or scored. Offline (no network).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex import db  # noqa: E402
from coveragex.config import PROCESSED_DIR, ensure_dirs  # noqa: E402
from coveragex.vin import validate_vin  # noqa: E402


def run(conn) -> dict:
    rows = conn.execute("SELECT vehicle_id, vin FROM vehicles").fetchall()
    valid = invalid = 0
    invalid_rows = []
    for row in rows:
        v = validate_vin(row["vin"])
        conn.execute(
            "UPDATE vehicles SET vin_valid=?, vin_invalid_reason=?, check_digit_valid=?, last_updated=? WHERE vehicle_id=?",
            (1 if v.valid else 0, v.reason, 1 if v.check_digit_valid else 0, db.now_iso(), row["vehicle_id"]),
        )
        if v.valid:
            valid += 1
        else:
            invalid += 1
            invalid_rows.append({"vehicle_id": row["vehicle_id"], "vin": row["vin"], "reason": v.reason})
    conn.commit()

    ensure_dirs()
    (PROCESSED_DIR / "invalid_vins.json").write_text(json.dumps(invalid_rows, indent=2))
    db.log_run(conn, script_name="validate_vins.py", source_name="internal",
               records_in=len(rows), records_out=valid, records_rejected=invalid,
               notes=f"{valid} valid / {invalid} invalid")
    return {"total": len(rows), "valid": valid, "invalid": invalid}


def main() -> None:
    argparse.ArgumentParser(description="Validate collected VINs").parse_args()
    conn = db.connect()
    db.init_db(conn)
    result = run(conn)
    conn.close()
    print(f"VIN validation: {result['valid']} valid, {result['invalid']} invalid "
          f"of {result['total']} total.")


if __name__ == "__main__":
    main()
