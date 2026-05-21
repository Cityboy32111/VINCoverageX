#!/usr/bin/env python3
"""OFFLINE diagnostic for the inventory-collection step. No network.

Inspects data/raw/inventory_*.json (saved by the 3-dealer test) and the local
DB to explain thin VIN yield: which dealers were crawled, their URLs, whether
raw files contain VIN strings at all, and whether the parser or the crawler is
the bottleneck. Run this and paste the output back.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex import db  # noqa: E402
from coveragex.config import RAW_DIR  # noqa: E402
from coveragex.extract import _VIN_RE, parse_apify_item  # noqa: E402
from coveragex.vin import validate_vin  # noqa: E402


def _raw_vins(blob: str) -> set[str]:
    out = set()
    for m in _VIN_RE.findall(blob):
        v = validate_vin(m)
        if v.valid:
            out.add(v.vin)
    return out


def main() -> None:
    conn = db.connect()
    db.init_db(conn)
    g = lambda q: conn.execute(q).fetchone()[0]  # noqa: E731

    print("=== DB SUMMARY ===")
    print(f"dealers total:        {g('SELECT COUNT(*) FROM dealers')}")
    print(f"  with website:       {g('SELECT COUNT(*) FROM dealers WHERE website IS NOT NULL')}")
    print(f"  with inventory_url: {g('SELECT COUNT(*) FROM dealers WHERE inventory_url IS NOT NULL')}")
    print(f"vehicles:             {g('SELECT COUNT(*) FROM vehicles')}")
    print(f"valid VINs:           {g('SELECT COUNT(*) FROM vehicles WHERE vin_valid=1')}")
    print(f"inventory_listings:   {g('SELECT COUNT(*) FROM inventory_listings')}")

    files = sorted(RAW_DIR.glob("inventory_*.json"))
    print(f"\n=== RAW FILES: {len(files)} in {RAW_DIR} ===")
    if not files:
        print("No raw inventory files -> collect_inventory saved nothing (likely blocked or 0 pages).")
        rows = conn.execute("SELECT dealer_name, website, inventory_url FROM dealers "
                            "WHERE inventory_url IS NOT NULL OR website IS NOT NULL LIMIT 3").fetchall()
        print("\nFirst 3 dealers that WOULD be crawled (current ordering):")
        for r in rows:
            print(f"  - {r['dealer_name']}\n      inventory_url={r['inventory_url']}\n      website={r['website']}")
        conn.close()
        return

    for f in files:
        dealer_id = f.stem.replace("inventory_", "")
        d = conn.execute("SELECT dealer_name, website, inventory_url FROM dealers WHERE dealer_id=?",
                         (dealer_id,)).fetchone()
        name = d["dealer_name"] if d else "(unknown dealer)"
        raw_text = f.read_text()
        try:
            items = json.loads(raw_text)
        except json.JSONDecodeError as e:
            print(f"\n[{name}] {f.name}: JSON parse error ({e}); regex VINs in raw: {len(_raw_vins(raw_text))}")
            continue
        items = items if isinstance(items, list) else [items]

        keys: set[str] = set()
        for it in items[:50]:
            if isinstance(it, dict):
                keys |= set(it.keys())
        n_html = sum(1 for it in items if isinstance(it, dict) and it.get("html"))
        n_text = sum(1 for it in items if isinstance(it, dict) and it.get("text"))
        urls = [(it.get("url") or it.get("loadedUrl") or "") for it in items if isinstance(it, dict)]
        raw_vins = _raw_vins(raw_text)
        parsed: set[str] = set()
        for it in items:
            if isinstance(it, dict):
                for rec in parse_apify_item(it):
                    parsed.add(rec["vin"])

        print(f"\n[{name}]  file={f.name}  size={f.stat().st_size // 1024}KB")
        print(f"  DB inventory_url: {d['inventory_url'] if d else '?'}")
        print(f"  DB website:       {d['website'] if d else '?'}")
        print(f"  apify items: {len(items)} | with html: {n_html} | with text: {n_text}")
        print(f"  item keys: {sorted(keys)}")
        print(f"  json-ld in raw: {'ld+json' in raw_text} | data-vin in raw: {'data-vin' in raw_text.lower()} "
              f"| 'vin' occurrences: {raw_text.lower().count('vin')}")
        print(f"  VINs by raw regex: {len(raw_vins)} | VINs by parser: {len(parsed)}")
        print("  sample crawled URLs:")
        for u in urls[:8]:
            print(f"     {u}")
        if len(raw_vins) == 0:
            print("  >> HINT: NO VINs in raw at all. The crawler isn't reaching listing/VDP pages, or "
                  "scripts were stripped. Fix = start at the inventory URL + keep scripts (new config), "
                  "or switch source.")
        elif len(parsed) < len(raw_vins):
            print(f"  >> HINT: raw has {len(raw_vins)} VINs but parser got {len(parsed)}. PARSER GAP — "
                  "pull the latest extract.py and re-run.")
        else:
            print("  >> HINT: parser captured all VINs present. Yield limited by pages crawled / wrong "
                  "start page. Point start URL at the used-inventory SRP and raise maxCrawlPages.")
    conn.close()


if __name__ == "__main__":
    main()
