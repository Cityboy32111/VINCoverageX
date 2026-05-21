"""Exports: provenance on every record, no PII columns, well-formed files."""
import json

import pytest

from coveragex import db
from scripts.export_outputs import run as export_run, VEHICLE_COLUMNS
from scripts.generate_manus_demo_package import run as demo_run


@pytest.fixture
def populated(tmp_path):
    c = db.connect(tmp_path / "g.sqlite")
    db.init_db(c)
    c.execute("INSERT INTO dealers (dealer_id, dealer_name, city, state, dealer_type, "
              "inventory_count, coverage_ready_vehicle_count, high_repair_risk_vehicle_count, "
              "truck_suv_share, luxury_share, ev_share, source_url, confidence, last_updated) "
              "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("d1", "Sunset Auto", "Los Angeles", "CA", "independent used", 1, 1, 0,
               1.0, 0.0, 0.0, "https://dealer.example/inventory", 0.85, db.now_iso()))
    vid = db.get_or_create_vehicle(c, "d1", "11111111111111111")
    c.execute("UPDATE vehicles SET vin_valid=1, year=2017, make='Chevrolet', model='Tahoe', "
              "body_class='SUV', vehicle_age=9, mileage_band='70k-100k' WHERE vehicle_id=?", (vid,))
    c.execute("INSERT INTO inventory_listings (listing_id, vehicle_id, dealer_id, vin, mileage, "
              "price, listing_url, observed_date, source_name, source_url, confidence) "
              "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (db.new_id("lst_"), vid, "d1", "11111111111111111", 96000, 28995,
               "https://dealer.example/vdp/1", db.now_iso(), "dealer_site",
               "https://dealer.example/vdp/1", 0.8))
    c.execute("INSERT INTO coverage_scores (score_id, vehicle_id, vin, coverage_readiness_score, "
              "repair_risk_score, plan_fit_recommendation, plan_fit_reason, exclusion_review_flags, "
              "exclusion_review_score, buyer_urgency_score, recommended_message_angle, recall_count, "
              "recall_severity, component_risk_themes, scoring_version, score_date, confidence) "
              "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (db.new_id("cs_"), vid, "11111111111111111", 86.8, 50.3, "Premium",
               "Premium: truck/SUV exposure", "[]", 0.0, 70.0, "Strong Premium fit.",
               0, None, "[]", "phase1-v1", db.now_iso(), 0.7))
    c.execute("INSERT INTO dealer_scores (dealer_score_id, dealer_id, "
              "dealer_coverage_opportunity_score, coverage_ready_vehicle_share, "
              "high_repair_risk_vehicle_count, truck_suv_luxury_share, recommended_partner_pitch, "
              "recommended_plan_mix, scoring_version, score_date, confidence) "
              "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (db.new_id("ds_"), "d1", 78.0, 1.0, 0, 1.0, "F&I attach opportunity",
               '{"Premium": 1.0}', "phase1-v1", db.now_iso(), 0.7))
    db.insert_evidence(c, entity_type="vehicle", entity_id=vid, field_name="vin",
                       value="11111111111111111", source_name="dealer inventory page",
                       source_url="https://dealer.example/vdp/1", source_type="dealer_site",
                       confidence=0.8, inference_flag=0, risk_tier="SAFE_PUBLIC")
    c.commit()
    yield c, tmp_path
    c.close()


def test_no_pii_columns_in_vehicle_export():
    lowered = [c.lower() for c in VEHICLE_COLUMNS]
    for banned in ("email", "owner", "consumer", "home_address", "personal_phone"):
        assert not any(banned in c for c in lowered)


def test_exports_written_and_have_provenance(populated):
    conn, tmp = populated
    out = tmp / "outputs"
    res = export_run(conn, out_dir=out)
    assert res["vehicles"] == 1 and res["dealers"] == 1
    assert res["missing_provenance"] == []

    for fname in ("vehicle_signal_graph.csv", "vehicle_signal_graph.json",
                  "dealer_opportunity_rankings.csv", "source_evidence.json", "top_dealer_briefs.md"):
        assert (out / fname).exists(), fname

    vehicles = json.loads((out / "vehicle_signal_graph.json").read_text())
    assert len(vehicles) == 1
    for v in vehicles:
        assert v["source_url"] and v["extraction_date"]

    evidence = json.loads((out / "source_evidence.json").read_text())
    assert evidence and all("source_url" in e for e in evidence)


def test_demo_package_written(populated):
    conn, tmp = populated
    out = tmp / "outputs"
    demo_run(conn, out_dir=out)
    summary = (out / "coveragex_demo_summary.md").read_text()
    assert "Sunset Auto" in summary
    assert (out / "manus_demo_prompt.md").exists()
    assert "CoverageX Vehicle Signal Graph" in (out / "manus_demo_prompt.md").read_text()
