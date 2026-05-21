#!/usr/bin/env python3
"""Generate the Manus demo package from the scored graph.

  outputs/coveragex_demo_summary.md   (one-dealer buyer demo, from real data)
  outputs/manus_demo_prompt.md        (interactive dashboard build spec)

If the graph is empty (e.g. collection blocked), still emits the build spec
and a summary that honestly states no data was collected. Offline.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex import db  # noqa: E402
from coveragex.config import OUTPUTS_DIR, ensure_dirs  # noqa: E402


def _market_stats(conn) -> dict:
    g = lambda q: conn.execute(q).fetchone()[0]  # noqa: E731
    return {
        "dealers": g("SELECT COUNT(*) FROM dealers"),
        "dealers_scored": g("SELECT COUNT(*) FROM dealer_scores"),
        "vehicles": g("SELECT COUNT(*) FROM vehicles"),
        "valid_vins": g("SELECT COUNT(*) FROM vehicles WHERE vin_valid=1"),
        "decoded": g("SELECT COUNT(*) FROM vin_decodes WHERE decode_success=1"),
        "scored": g("SELECT COUNT(*) FROM coverage_scores"),
        "coverage_ready": g("SELECT COUNT(*) FROM coverage_scores WHERE coverage_readiness_score>=70"),
        "high_repair_risk": g("SELECT COUNT(*) FROM coverage_scores WHERE repair_risk_score>=65"),
    }


def _flagship(conn):
    return conn.execute(
        """SELECT d.*, ds.dealer_coverage_opportunity_score AS opp, ds.recommended_partner_pitch AS pitch,
                  ds.recommended_plan_mix AS plan_mix
           FROM dealers d JOIN dealer_scores ds ON ds.dealer_id=d.dealer_id
           ORDER BY ds.dealer_coverage_opportunity_score DESC LIMIT 1""").fetchone()


def _demo_summary(conn) -> str:
    s = _market_stats(conn)
    decode_rate = (s["decoded"] / s["valid_vins"] * 100) if s["valid_vins"] else 0
    L = ["# CoverageX Vehicle Signal Graph — Demo Summary", "",
         "_Built from the Phase 1 sample. Scores are coverage-fit / repair-risk proxies "
         "(estimated, model-level), not actuarial or verified claims/title/recall determinations._", "",
         "## Market overview", "",
         f"- Dealers analyzed: **{s['dealers']}** ({s['dealers_scored']} scored)",
         f"- Vehicles: **{s['vehicles']}** | Valid VINs: **{s['valid_vins']}** | "
         f"Decoded: **{s['decoded']}** ({decode_rate:.0f}%)",
         f"- Coverage-ready VINs: **{s['coverage_ready']}** | High repair risk: **{s['high_repair_risk']}**", ""]

    if s["vehicles"] == 0:
        L += ["## No data collected yet", "",
              "The pipeline ran but no vehicles were collected — typically because the "
              "collection sources (Apify / dealer sites) were unreachable in this environment. "
              "No data was fabricated. Enable outbound network access (allow `api.apify.com`, "
              "`vpic.nhtsa.dot.gov`, `api.nhtsa.gov`, and dealer hosts) or run locally with "
              "`config/.env`, then re-run the pipeline. See docs/runbook.md.", ""]
        return "\n".join(L)

    d = _flagship(conn)
    if d:
        mix = json.loads(d["plan_mix"] or "{}")
        mix_str = ", ".join(f"{int(v*100)}% {k}" for k, v in mix.items()) or "n/a"
        top = conn.execute(
            """SELECT v.vin, v.year, v.make, v.model, cs.coverage_readiness_score AS crs,
                      cs.repair_risk_score AS rrs, cs.plan_fit_recommendation AS plan,
                      cs.recommended_message_angle AS angle
               FROM vehicles v JOIN coverage_scores cs ON cs.vehicle_id=v.vehicle_id
               WHERE v.dealer_id=? ORDER BY cs.buyer_urgency_score DESC LIMIT 5""",
            (d["dealer_id"],)).fetchall()
        L += [f"## Flagship dealer: {d['dealer_name']}", "",
              f"- **Dealer:** {d['dealer_name']} ({d['city'] or ''}, {d['state'] or ''}) — type: {d['dealer_type'] or 'n/a'}",
              f"- **Inventory:** {d['inventory_count']}",
              f"- **Coverage-ready VINs:** {d['coverage_ready_vehicle_count']}",
              f"- **High repair risk VINs:** {d['high_repair_risk_vehicle_count']}",
              f"- **Truck/SUV share:** {d['truck_suv_share']} | **Luxury:** {d['luxury_share']} | **EV:** {d['ev_share']}",
              f"- **Recommended plan mix:** {mix_str}",
              f"- **Opportunity score:** {d['opp']}",
              f"- **Recommended F&I pitch:** {d['pitch']}",
              f"- **Recommended target persona:** F&I Director", "",
              "### Top 5 VINs (by buyer urgency)", ""]
        for v in top:
            L.append(f"- `{v['vin']}` — {v['year']} {v['make']} {v['model']} | "
                     f"coverage **{v['crs']}**, repair **{v['rrs']}**, plan **{v['plan']}** — {v['angle']}")
        L += ["", "### Evidence & next action", "",
              "- Every figure is backed by `outputs/source_evidence.json` (source URL, timestamp, confidence).",
              "- **Recommended next action:** open F&I partnership conversation; lead with the "
              "coverage-ready set and the dominant repair-risk themes.",
              "- **No consumer names, emails, or phone numbers are used anywhere.**", ""]
    return "\n".join(L)


def _manus_prompt(conn) -> str:
    s = _market_stats(conn)
    d = _flagship(conn)
    wow = ""
    if d:
        mix = json.loads(d["plan_mix"] or "{}")
        mix_str = ", ".join(f"{int(v*100)}% {k}" for k, v in mix.items()) or "n/a"
        wow = (f"When the user clicks **{d['dealer_name']}**, show: {d['inventory_count']} vehicles, "
               f"{d['coverage_ready_vehicle_count']} coverage-ready, {d['high_repair_risk_vehicle_count']} "
               f"high repair risk; recommended plan mix {mix_str}; opportunity score {d['opp']}; "
               f"recommended target F&I Director with the pitch shown.")
    else:
        wow = ("When the user clicks the top-ranked dealer, show inventory count, coverage-ready count, "
               "high-repair-risk count, recommended plan mix, opportunity score, and the F&I pitch. "
               "(Populate from outputs/ once collection has run.)")

    return f"""# Manus Demo Prompt — CoverageX Vehicle Signal Graph

Build an interactive dashboard named **CoverageX Vehicle Signal Graph**.

**Hero headline:** Find the vehicles most ready for protection
**Subheadline:** CoverageX Vehicle Signal Graph ranks dealer inventories and VINs by
coverage fit, repair risk, plan recommendation, and partner opportunity.

## Data sources (load these files)
- `outputs/vehicle_signal_graph.json` — one record per vehicle (scores, plan fit, themes).
- `outputs/dealer_opportunity_rankings.csv` — ranked dealers.
- `outputs/source_evidence.json` — provenance for the evidence drawer.

Current sample: {s['dealers']} dealers, {s['valid_vins']} valid VINs, {s['coverage_ready']} coverage-ready,
{s['high_repair_risk']} high repair risk.

## Sections to render
1. **Market overview** — KPI tiles (dealers, VINs, % decoded, coverage-ready, high repair risk),
   mileage-band + class distribution charts.
2. **Dealer opportunity rankings** — sortable table, color band Priority(>=70)/Qualified(50-69)/Monitor(<50),
   click-through to dealer profile.
3. **Selected dealer profile** — inventory count, coverage-ready, high repair risk, plan mix donut,
   top risk themes, recommended F&I pitch + persona.
4. **VIN-level table** — per-vehicle scores; tabs for Top 25 by coverage readiness / Top 25 by repair risk.
5. **Coverage readiness score** — gauge + sub-score breakdown.
6. **Repair risk score** — gauge + sub-score breakdown; theme chips labeled "estimated / model-level".
7. **Plan fit recommendation** — tier badge + reason.
8. **Evidence drawer** — source_name, clickable source_url, extraction_date, confidence, evidence_span,
   risk_tier badge; inferred values tagged "estimated / model-level".
9. **B2B activation layer** — recommended personas (roles only); banner "No consumer data. B2B partner roles only."

## Wow moment
{wow}

## Hard rules (must enforce in UI)
- Never display consumer names, emails, or phone numbers.
- Tag every inferred/model-level/sample value visibly.
- Every number is one click from its evidence (source URL + timestamp + confidence).
"""


def run(conn, out_dir=None) -> dict:
    out_dir = Path(out_dir) if out_dir else OUTPUTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    if out_dir == OUTPUTS_DIR:
        ensure_dirs()
    (out_dir / "coveragex_demo_summary.md").write_text(_demo_summary(conn))
    (out_dir / "manus_demo_prompt.md").write_text(_manus_prompt(conn))
    db.log_run(conn, script_name="generate_manus_demo_package.py", source_name="internal",
               notes="demo summary + manus prompt written")
    return {"files": ["coveragex_demo_summary.md", "manus_demo_prompt.md"]}


def main() -> None:
    argparse.ArgumentParser(description="Generate Manus demo package").parse_args()
    conn = db.connect()
    db.init_db(conn)
    r = run(conn)
    conn.close()
    print("Demo package written:", ", ".join(r["files"]))


if __name__ == "__main__":
    main()
