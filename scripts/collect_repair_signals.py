#!/usr/bin/env python3
"""Build MODEL-LEVEL repair-risk theme signals.

Sources, in order of rigor:
  1. NHTSA recall-derived themes (SAFE PUBLIC) -- from recalls already in DB.
  2. NHTSA complaint themes (SAFE PUBLIC, --complaints) -- unverified reports.
  3. Public owner-forum spans (SAMPLE ONLY, --forums via Apify) -- short,
     demo-labeled spans, "public discussion, not verified".

All signals are level='model-level'. Production path = licensed repair/claims
data. Themes feed the repair-risk public_complaint sub-score.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex import db  # noqa: E402
from coveragex.config import scoring_config, source_config  # noqa: E402
from coveragex.extract import classify_repair_themes  # noqa: E402


def _insert_themes(conn, mmy, themes, *, kind, risk_tier, source_name, source_url, span=None):
    n = 0
    for t in themes:
        conn.execute(
            """INSERT INTO repair_signals (signal_id, make, model, model_year,
                component_theme, theme_intensity, signal_kind, evidence_span, risk_tier,
                level, source_name, source_url, extraction_date, confidence, inference_flag)
               VALUES (?,?,?,?,?,?,?,?,?, 'model-level', ?,?,?,?, 1)""",
            (db.new_id("sig_"), mmy[0], mmy[1], mmy[2], t["theme"], t["intensity"],
             kind, span, risk_tier, source_name, source_url, db.now_iso(),
             0.6 if kind != "public_forum" else 0.4),
        )
        n += 1
    return n


def run(conn, use_complaints: bool = True, use_forums: bool = False) -> dict:
    cfg = scoring_config()
    combos = conn.execute(
        "SELECT DISTINCT make, model, model_year FROM vin_decodes "
        "WHERE make IS NOT NULL AND model IS NOT NULL AND model_year IS NOT NULL").fetchall()
    inserted = 0

    for c in combos:
        mmy = (c["make"], c["model"], c["model_year"])
        # 1) recall-derived themes (offline; reads recalls table)
        recall_text = [r["component"] or "" for r in conn.execute(
            "SELECT component, summary FROM recalls WHERE make=? AND model=? AND model_year=?", mmy)]
        recall_text += [r["summary"] or "" for r in conn.execute(
            "SELECT summary FROM recalls WHERE make=? AND model=? AND model_year=?", mmy)]
        themes = classify_repair_themes(recall_text, cfg)
        url = (f"{source_config()['nhtsa']['recalls_base']}?make={mmy[0]}&model={mmy[1]}&modelYear={mmy[2]}")
        inserted += _insert_themes(conn, mmy, themes, kind="nhtsa_recall_derived",
                                   risk_tier="SAFE_PUBLIC", source_name="NHTSA Recalls", source_url=url)

        # 2) NHTSA complaints (network)
        if use_complaints:
            from coveragex.nhtsa import NhtsaError, get_complaints
            try:
                complaints = get_complaints(*mmy)
            except NhtsaError as e:
                db.log_run(conn, script_name="collect_repair_signals.py",
                           source_name="NHTSA Complaints", status="partial", error_detail=str(e))
                conn.commit()
                print(f"[WARN] complaints unavailable ({e}); continuing with recall-derived themes.")
                use_complaints = False
            else:
                ctext = [(x.get("component") or "") + " " + (x.get("summary") or "") for x in complaints]
                cthemes = classify_repair_themes(ctext, cfg)
                curl = (f"{source_config()['nhtsa']['complaints_base']}?make={mmy[0]}&model={mmy[1]}&modelYear={mmy[2]}")
                inserted += _insert_themes(conn, mmy, cthemes, kind="nhtsa_complaint",
                                           risk_tier="SAFE_PUBLIC", source_name="NHTSA Complaints",
                                           source_url=curl)
                time.sleep(0.2)

    if use_forums:
        inserted += _collect_forum_samples(conn, combos, cfg)

    conn.commit()
    db.log_run(conn, script_name="collect_repair_signals.py", source_name="NHTSA + sample",
               records_in=len(combos), records_out=inserted,
               notes=f"{inserted} model-level repair-theme signals")
    return {"combos": len(combos), "signals": inserted}


def _collect_forum_samples(conn, combos, cfg) -> int:
    """SAMPLE-ONLY: short public owner-forum spans via Apify. Demo-labeled."""
    from coveragex.apify import ApifyClient, ApifyError
    fa = source_config()["apify"]["repair_forum_actor"]
    max_chars = fa.get("max_span_chars", 240)
    client = ApifyClient()
    inserted = 0
    for c in combos[:25]:  # cap to keep sample small + cheap
        mmy = (c["make"], c["model"], c["model_year"])
        query_url = f"https://www.google.com/search?q={mmy[0]}+{mmy[1]}+{mmy[2]}+common+problems+forum"
        try:
            items = client.run_actor(fa["actor_id"], {"startUrls": [{"url": query_url}],
                                     "maxCrawlPages": 3, "respectRobotsTxtFile": True})[0]
        except ApifyError as e:
            print(f"[WARN] forum sampling blocked/failed ({e}); skipping SAMPLE-ONLY layer.")
            return inserted
        texts = [(it.get("text") or "")[:2000] for it in items]
        themes = classify_repair_themes(texts, cfg)
        span = (texts[0][:max_chars] + " ...") if texts else None
        inserted += _insert_themes(conn, mmy, themes, kind="public_forum",
                                   risk_tier="SAMPLE_ONLY", source_name="Public owner forum (demo)",
                                   source_url=query_url, span=span)
    return inserted


def main() -> None:
    p = argparse.ArgumentParser(description="Build model-level repair-theme signals")
    p.add_argument("--no-complaints", action="store_true", help="skip NHTSA complaints (network)")
    p.add_argument("--forums", action="store_true", help="include SAMPLE-ONLY forum spans (Apify)")
    args = p.parse_args()
    conn = db.connect()
    db.init_db(conn)
    r = run(conn, use_complaints=not args.no_complaints, use_forums=args.forums)
    conn.close()
    print(f"Repair signals: {r['signals']} model-level theme signals across {r['combos']} combos.")


if __name__ == "__main__":
    main()
