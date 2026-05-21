#!/usr/bin/env python3
"""OPTIONAL: collect public competitor vehicle-protection positioning (SAFE PUBLIC).

Summarizes publicly stated coverage tiers/positioning from competitor product
pages. Does NOT copy proprietary text verbatim. Requires explicit public URLs
(no fabricated sources). Out of the core Phase 1 success criteria.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex import db  # noqa: E402
from coveragex.config import source_config  # noqa: E402

_TIER_KEYWORDS = ["powertrain", "bumper-to-bumper", "exclusionary", "stated component",
                  "high-tech", "ev", "hybrid", "deductible"]


def run(conn, url_map: dict[str, str]) -> dict:
    from coveragex.apify import ApifyClient, ApifyError
    actor = source_config()["apify"]["inventory_crawler_actor"]["actor_id"]
    client = ApifyClient()
    n = 0
    for name, url in url_map.items():
        try:
            items = client.run_actor(actor, {"startUrls": [{"url": url}], "maxCrawlPages": 5,
                                     "respectRobotsTxtFile": True}, timeout=300)[0]
        except ApifyError as e:
            print(f"[WARN] competitor crawl blocked/failed for {name} ({e}); skipping.")
            continue
        text = " ".join((it.get("text") or "") for it in items).lower()
        tiers = [k for k in _TIER_KEYWORDS if k in text]
        conn.execute(
            """INSERT INTO competitor_signals (competitor_signal_id, competitor_name, coverage_tier,
                covered_components, positioning_note, applies_to_segment, source_name, source_url,
                risk_tier, extraction_date, confidence, inference_flag)
               VALUES (?,?,?,?,?,?,?,?, 'SAFE_PUBLIC', ?,?, 1)""",
            (db.new_id("comp_"), name, ", ".join(tiers) or None, ", ".join(tiers) or None,
             f"Public positioning keywords observed: {', '.join(tiers) or 'none'}", None,
             "Competitor public page", url, db.now_iso(), 0.5),
        )
        db.insert_evidence(conn, entity_type="competitor_signal", entity_id=name,
                           field_name="positioning", value=", ".join(tiers),
                           source_name="Competitor public page", source_url=url,
                           source_type="competitor_page", confidence=0.5, inference_flag=1,
                           risk_tier="SAFE_PUBLIC")
        n += 1
    conn.commit()
    db.log_run(conn, script_name="collect_competitor_signals.py", source_name="competitor pages",
               records_out=n, notes=f"{n} competitor signals")
    return {"signals": n}


def main() -> None:
    p = argparse.ArgumentParser(description="Collect public competitor positioning (optional)")
    p.add_argument("--urls", nargs="+", metavar="NAME=URL",
                   help="public competitor pages, e.g. Endurance=https://...")
    args = p.parse_args()
    if not args.urls:
        raise SystemExit("Provide --urls NAME=URL ... (public competitor pages). No URLs are fabricated.")
    url_map = dict(u.split("=", 1) for u in args.urls)
    conn = db.connect()
    db.init_db(conn)
    r = run(conn, url_map)
    conn.close()
    print(f"Competitor signals: {r['signals']}.")


if __name__ == "__main__":
    main()
