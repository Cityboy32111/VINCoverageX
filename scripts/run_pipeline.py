#!/usr/bin/env python3
"""Run the full Phase 1 pipeline end-to-end against local SQLite.

Order: discover -> collect inventory -> validate -> decode -> recalls ->
repair signals -> score vehicles -> score dealers -> export -> demo package.

Network stages (discover/collect/decode/recalls/complaints) require outbound
access to Apify + NHTSA. If a stage is blocked, the orchestrator prints the
honest blocker, skips remaining collection, and still runs the offline scoring
+ export + demo on whatever data exists (which may be none — never fabricated).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex import db  # noqa: E402
from coveragex.config import CONFIG_DIR, source_config  # noqa: E402
from scripts import (  # noqa: E402
    collect_inventory, collect_recalls, collect_repair_signals, decode_vins,
    discover_dealers, export_outputs, generate_manus_demo_package, score_dealers,
    score_vehicles, validate_vins,
)


def _stage(name: str, fn, *args, **kwargs) -> bool:
    print(f"\n=== {name} ===")
    try:
        fn(*args, **kwargs)
        return True
    except (SystemExit, Exception) as e:  # noqa: BLE001 — pipeline must stay resilient
        print(str(e) or repr(e))
        print(f"[skip] '{name}' did not complete; continuing with remaining stages.")
        return False


def main() -> None:
    p = argparse.ArgumentParser(description="Run the Phase 1 pipeline")
    p.add_argument("--no-apify", action="store_true", help="use config/dealers_seed.csv for discovery")
    p.add_argument("--test", action="store_true", help="3-dealer inventory test run")
    p.add_argument("--forums", action="store_true", help="include SAMPLE-ONLY forum repair signals")
    p.add_argument("--skip-collect", action="store_true", help="score/export existing DB only")
    args = p.parse_args()

    conn = db.connect()
    db.init_db(conn)
    market = source_config()["market"]

    if not args.skip_collect:
        if args.no_apify:
            _stage("discover dealers (seed)", discover_dealers.from_seed, conn, CONFIG_DIR / "dealers_seed.csv")
        else:
            _stage("discover dealers (Apify)", discover_dealers.from_apify, conn, market)
        discover_dealers.export_seed(conn)
        _stage("collect inventory", collect_inventory.run, conn, args.test)

    # validate must run before decode and before scoring
    _stage("validate VINs", validate_vins.run, conn)

    if not args.skip_collect:
        _stage("decode VINs (NHTSA)", decode_vins.run, conn)
        _stage("collect recalls (NHTSA)", collect_recalls.run, conn)
        _stage("collect repair signals", collect_repair_signals.run, conn, True, args.forums)

    # offline stages always run
    _stage("score vehicles", score_vehicles.run, conn)
    _stage("score dealers", score_dealers.run, conn)
    _stage("export outputs", export_outputs.run, conn)
    _stage("generate demo package", generate_manus_demo_package.run, conn)

    stats = generate_manus_demo_package._market_stats(conn)
    conn.close()
    print("\n=== pipeline complete ===")
    print(f"dealers={stats['dealers']} valid_vins={stats['valid_vins']} "
          f"decoded={stats['decoded']} scored={stats['scored']} "
          f"coverage_ready={stats['coverage_ready']} high_repair_risk={stats['high_repair_risk']}")
    if stats["vehicles"] == 0:
        print("No vehicles collected. See outputs/coveragex_demo_summary.md and docs/runbook.md "
              "for how to enable collection. No data was fabricated.")


if __name__ == "__main__":
    main()
