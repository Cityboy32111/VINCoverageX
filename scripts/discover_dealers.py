#!/usr/bin/env python3
"""Discover used-car dealers in the target market.

Two modes:
  * Apify Google Maps (default) — public business listings only.
  * Seed CSV (--seed PATH or --no-apify with config/dealers_seed.csv).

Collects BUSINESS info only (name, website, business address/phone). No
consumer data. Writes dealers + evidence and refreshes config/dealers_seed.csv.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex import db  # noqa: E402
from coveragex.config import CONFIG_DIR, source_config  # noqa: E402


def slugify(name: str, zip_code: str | None) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "dealer").lower()).strip("-")[:40]
    return f"{base}-{zip_code}" if zip_code else f"{base}-{db.new_id()[:6]}"


def _upsert_dealer(conn, rec: dict) -> str:
    dealer_id = rec.get("dealer_id") or slugify(rec.get("dealer_name", ""), rec.get("zip"))
    existing = conn.execute("SELECT dealer_id FROM dealers WHERE dealer_id=?", (dealer_id,)).fetchone()
    if existing:
        return dealer_id
    conn.execute(
        """INSERT INTO dealers (dealer_id, dealer_name, website, inventory_url, street_address,
            city, state, zip, phone, dealer_type, market, county, source_url, confidence,
            first_seen, last_updated)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (dealer_id, rec.get("dealer_name"), rec.get("website"), rec.get("inventory_url"),
         rec.get("street_address"), rec.get("city"), rec.get("state"), rec.get("zip"),
         rec.get("phone"), rec.get("dealer_type"), rec.get("market"), rec.get("county"),
         rec.get("source_url"), rec.get("confidence", 0.8), db.now_iso(), db.now_iso()),
    )
    for field in ("dealer_name", "website", "street_address"):
        if rec.get(field):
            db.insert_evidence(conn, entity_type="dealer", entity_id=dealer_id, field_name=field,
                               value=rec[field], source_name=rec.get("source_name", "discovery"),
                               source_url=rec.get("source_url"), source_type="business_listing",
                               confidence=rec.get("confidence", 0.8), inference_flag=0,
                               risk_tier="SAFE_PUBLIC")
    return dealer_id


def from_seed(conn, path: Path) -> int:
    n = 0
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if not row.get("dealer_name"):
                continue
            row.setdefault("source_name", "seed_csv")
            row.setdefault("source_url", str(path))
            _upsert_dealer(conn, row)
            n += 1
    conn.commit()
    return n


def from_apify(conn, market_cfg: dict) -> int:
    from coveragex.apify import ApifyClient, ApifyError
    sc = source_config()["apify"]["dealer_discovery_actor"]
    fmap = sc["output_field_map"]
    client = ApifyClient()
    searches = [f"used car dealers in {c}, {market_cfg['state']}" for c in market_cfg["counties"][:3]]
    run_input = dict(sc["input_template"])
    run_input["searchStringsArray"] = searches
    run_input["maxCrawledPlacesPerSearch"] = max(20, market_cfg["target_dealer_count"])
    try:
        items, run = client.run_actor(sc["actor_id"], run_input, timeout=600)
    except ApifyError as e:
        db.log_run(conn, script_name="discover_dealers.py", source_name="Apify Google Maps",
                   apify_actor=sc["actor_id"], status="error", error_detail=str(e))
        conn.commit()
        raise SystemExit(f"\n[BLOCKER] {e}\nNo dealers discovered. No data fabricated.")
    n = 0
    for it in items:
        rec = {target: it.get(src) for src, target in fmap.items()}
        rec["market"] = market_cfg["name"]
        rec["source_name"] = "Apify Google Maps"
        rec["confidence"] = 0.85
        if rec.get("dealer_name"):
            _upsert_dealer(conn, rec)
            n += 1
    conn.commit()
    db.log_run(conn, script_name="discover_dealers.py", source_name="Apify Google Maps",
               apify_actor=sc["actor_id"], apify_run_id=run.get("id"), records_out=n,
               notes=f"discovered {n} dealers")
    return n


def export_seed(conn) -> None:
    rows = conn.execute("SELECT dealer_id, dealer_name, website, inventory_url, city, state, zip, "
                        "phone, dealer_type, county, source_url FROM dealers").fetchall()
    with open(CONFIG_DIR / "dealers_seed.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dealer_id", "dealer_name", "website", "inventory_url", "city", "state",
                    "zip", "phone", "dealer_type", "county", "source_url"])
        for r in rows:
            w.writerow([r[k] for k in r.keys()])


def main() -> None:
    p = argparse.ArgumentParser(description="Discover dealers in the target market")
    p.add_argument("--seed", type=str, help="load dealers from a seed CSV")
    p.add_argument("--no-apify", action="store_true", help="use config/dealers_seed.csv, no Apify")
    args = p.parse_args()
    conn = db.connect()
    db.init_db(conn)
    market = source_config()["market"]

    if args.seed:
        n = from_seed(conn, Path(args.seed))
        src = args.seed
    elif args.no_apify:
        seed = CONFIG_DIR / "dealers_seed.csv"
        if not seed.exists():
            raise SystemExit("No config/dealers_seed.csv found. Provide --seed or run Apify discovery.")
        n = from_seed(conn, seed)
        src = str(seed)
    else:
        n = from_apify(conn, market)
        src = "Apify Google Maps"
    export_seed(conn)
    conn.close()
    print(f"Discovered/loaded {n} dealers (source: {src}). Seed written to config/dealers_seed.csv.")


if __name__ == "__main__":
    main()
