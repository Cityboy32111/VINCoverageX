#!/usr/bin/env python3
"""Collect public dealer inventory via Apify, parse listings, upsert vehicles.

Per phase1_plan.md: start with a 3-dealer test (--test), save raw output, map
to the internal schema, log every run. Extracts VIN/mileage/price/listing_url
from JSON-LD Vehicle blocks, data-vin attributes, then a regex fallback.
Dedup is on (vin, dealer_id). No consumer data is collected.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex import db  # noqa: E402
from coveragex.config import RAW_DIR, ensure_dirs, source_config  # noqa: E402
from coveragex.extract import parse_apify_item  # noqa: E402
from coveragex.vin import normalize_vin  # noqa: E402


def _store_listing(conn, dealer_id: str, rec: dict) -> None:
    vid = db.get_or_create_vehicle(conn, dealer_id, rec["vin"])
    conn.execute(
        """INSERT INTO inventory_listings (listing_id, vehicle_id, dealer_id, vin, stock_number,
            mileage, price, listing_url, days_listed, listing_text, observed_date, source_name,
            source_url, confidence) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (db.new_id("lst_"), vid, dealer_id, normalize_vin(rec["vin"]), rec.get("stock_number"),
         rec.get("mileage"), rec.get("price"), rec.get("listing_url"), rec.get("days_listed"),
         (rec.get("listing_text") or "")[:1000], db.now_iso(), rec.get("source", "dealer_site"),
         rec.get("source_url"), 0.8),
    )
    db.insert_evidence(conn, entity_type="vehicle", entity_id=vid, field_name="vin",
                       value=normalize_vin(rec["vin"]), source_name="dealer inventory page",
                       source_url=rec.get("source_url"), source_type="dealer_site",
                       evidence_span=(rec.get("listing_text") or "")[:120], confidence=0.8,
                       inference_flag=0, risk_tier="SAFE_PUBLIC")


def _parse_items(items: list[dict]) -> list[dict]:
    records = []
    for it in items:
        records += parse_apify_item(it)
    return records


def run(conn, test: bool = False, limit: int | None = None) -> dict:
    from coveragex.apify import ApifyClient, ApifyError
    ensure_dirs()
    cfg = source_config()["apify"]["inventory_crawler_actor"]
    coll = source_config()["collection"]
    dealers = conn.execute(
        "SELECT dealer_id, dealer_name, inventory_url, website FROM dealers "
        "WHERE inventory_url IS NOT NULL OR website IS NOT NULL").fetchall()
    if test:
        dealers = dealers[: cfg.get("test_dealer_limit", 3)]
    elif limit:
        dealers = dealers[:limit]
    if not dealers:
        raise SystemExit("No dealers with inventory_url/website. Run discover_dealers.py first.")

    client = ApifyClient()
    total_records = 0
    all_vins: set[str] = set()
    errors: list[str] = []
    n = len(dealers)
    for i, d in enumerate(dealers, 1):
        start = d["inventory_url"] or d["website"]
        run_input = dict(cfg["input_template"])
        run_input["startUrls"] = [{"url": start}]
        run_input["maxCrawlPages"] = min(coll["max_pages_per_dealer"], cfg["input_template"]["maxCrawlPages"])
        print(f"\n[dealer {i}/{n}] {d['dealer_name']}", flush=True)
        print(f"    inventory_url: {start}", flush=True)
        try:
            items, meta = client.run_actor(cfg["actor_id"], run_input, timeout=900)
        except ApifyError as e:
            msg = str(e).splitlines()[0]
            print(f"    ERROR: {msg}", flush=True)
            db.log_run(conn, script_name="collect_inventory.py", source_name=d["dealer_name"],
                       apify_actor=cfg["actor_id"], status="error", error_detail=str(e))
            conn.commit()
            errors.append(f"{d['dealer_name']}: {msg}")
            continue

        raw_path = RAW_DIR / f"inventory_{d['dealer_id']}.json"
        raw_path.write_text(json.dumps(items[:3000], indent=2))
        records = _parse_items(items)
        for rec in records:
            _store_listing(conn, d["dealer_id"], rec)
        conn.commit()
        vins = {rec["vin"] for rec in records}
        total_records += len(records)
        all_vins |= vins
        print(f"    pages crawled: {len(items)}", flush=True)
        print(f"    records parsed: {len(records)} | unique VINs: {len(vins)}", flush=True)
        print(f"    raw saved: {raw_path}", flush=True)
        db.log_run(conn, script_name="collect_inventory.py", source_name=d["dealer_name"],
                   apify_actor=cfg["actor_id"], apify_run_id=meta.get("id"),
                   records_in=len(items), records_out=len(records),
                   notes=f"{len(records)} listings ({len(vins)} unique VINs) from {len(items)} pages")

    if errors:
        print(f"\n{len(errors)} dealer(s) errored:", flush=True)
        for e in errors:
            print(f"  - {e}", flush=True)
    return {"dealers": n, "listings": total_records, "unique_vins": len(all_vins), "errors": errors}


def main() -> None:
    p = argparse.ArgumentParser(description="Collect dealer inventory via Apify")
    p.add_argument("--test", action="store_true", help="3-dealer test run (per runbook)")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()
    conn = db.connect()
    db.init_db(conn)
    r = run(conn, test=args.test, limit=args.limit)
    conn.close()
    print(f"\nInventory: {r['listings']} listings, {r['unique_vins']} unique VINs across "
          f"{r['dealers']} dealers ({len(r['errors'])} errored).")


if __name__ == "__main__":
    main()
