#!/usr/bin/env python3
"""Live single-URL extraction probe (Apify). Network required.

Crawls ONE inventory URL with the current actor settings and reports how many
VINs are present vs. extracted. Use this to debug extraction on a known-good
used-inventory page BEFORE re-running the 3-dealer test. Does not touch the DB.

Example:
  python scripts/probe_inventory_url.py "https://www.somedealer.com/used-inventory/" --pages 10
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex.config import RAW_DIR, ensure_dirs, source_config  # noqa: E402
from coveragex.extract import _VIN_RE, parse_apify_item  # noqa: E402
from coveragex.vin import validate_vin  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Probe VIN extraction on one inventory URL")
    p.add_argument("url", help="a public dealer used-inventory (SRP) or VDP URL")
    p.add_argument("--pages", type=int, default=10, help="max pages to crawl (default 10)")
    args = p.parse_args()
    ensure_dirs()

    from coveragex.apify import ApifyClient, ApifyError
    cfg = source_config()["apify"]["inventory_crawler_actor"]
    run_input = dict(cfg["input_template"])
    run_input["startUrls"] = [{"url": args.url}]
    run_input["maxCrawlPages"] = args.pages

    print(f"Crawling up to {args.pages} page(s) from:\n  {args.url}\n(actor: {cfg['actor_id']})")
    try:
        items, meta = ApifyClient().run_actor(cfg["actor_id"], run_input, timeout=600)
    except ApifyError as e:
        raise SystemExit(f"[BLOCKER] {e}")

    out = RAW_DIR / "probe_last.json"
    out.write_text(json.dumps(items[:2000], indent=2))
    raw_text = json.dumps(items)
    raw_vins = {validate_vin(m).vin for m in _VIN_RE.findall(raw_text) if validate_vin(m).valid}
    parsed: set[str] = set()
    for it in items:
        if isinstance(it, dict):
            for rec in parse_apify_item(it):
                parsed.add(rec["vin"])
    keys: set[str] = set()
    for it in items[:50]:
        if isinstance(it, dict):
            keys |= set(it.keys())

    print("\n=== PROBE RESULT ===")
    print(f"pages/items returned: {len(items)}")
    print(f"item keys: {sorted(keys)}")
    print(f"json-ld present: {'ld+json' in raw_text} | data-vin present: {'data-vin' in raw_text.lower()}")
    print(f"VINs by raw regex: {len(raw_vins)} | VINs by parser: {len(parsed)}")
    print(f"sample VINs: {sorted(parsed)[:10]}")
    print(f"raw saved to: {out}")
    if len(parsed) >= 10:
        print(">> GOOD: extraction works on this URL. Use it as a seed inventory_url and scale the test.")
    elif len(raw_vins) > len(parsed):
        print(">> Parser gap: pull latest extract.py.")
    else:
        print(">> Few/no VINs on this page. Try the dealer's used-inventory listing (SRP) URL, raise --pages, "
              "or the page may be JS/anti-bot heavy — consider another dealer or a licensed feed.")


if __name__ == "__main__":
    main()
