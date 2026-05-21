"""SQLite store — schema + helpers. Mirrors docs/data_model.md.

Local SQLite only for the proof of concept. No production/Supabase writes.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS dealers (
  dealer_id TEXT PRIMARY KEY,
  dealer_name TEXT NOT NULL,
  website TEXT, inventory_url TEXT,
  street_address TEXT, city TEXT, state TEXT, zip TEXT, phone TEXT,
  dealer_type TEXT, market TEXT, county TEXT,
  inventory_count INTEGER, coverage_ready_vehicle_count INTEGER,
  high_repair_risk_vehicle_count INTEGER, avg_vehicle_age REAL, avg_mileage REAL,
  truck_suv_share REAL, luxury_share REAL, ev_share REAL,
  source_url TEXT, confidence REAL, first_seen TEXT, last_updated TEXT
);

CREATE TABLE IF NOT EXISTS vehicles (
  vehicle_id TEXT PRIMARY KEY,
  dealer_id TEXT REFERENCES dealers(dealer_id),
  vin TEXT NOT NULL, vin_valid INTEGER, vin_invalid_reason TEXT,
  check_digit_valid INTEGER,
  year INTEGER, make TEXT, model TEXT, trim TEXT, body_class TEXT,
  engine TEXT, drivetrain TEXT, fuel_type TEXT,
  vehicle_age INTEGER, mileage_band TEXT,
  first_seen TEXT, last_updated TEXT,
  UNIQUE (vin, dealer_id)
);
CREATE INDEX IF NOT EXISTS idx_vehicles_vin ON vehicles(vin);
CREATE INDEX IF NOT EXISTS idx_vehicles_dealer ON vehicles(dealer_id);

CREATE TABLE IF NOT EXISTS inventory_listings (
  listing_id TEXT PRIMARY KEY,
  vehicle_id TEXT REFERENCES vehicles(vehicle_id),
  dealer_id TEXT REFERENCES dealers(dealer_id),
  vin TEXT, stock_number TEXT, mileage INTEGER, price REAL,
  listing_url TEXT, days_listed INTEGER, listing_text TEXT,
  observed_date TEXT, source_name TEXT, source_url TEXT, confidence REAL
);
CREATE INDEX IF NOT EXISTS idx_listing_vehicle ON inventory_listings(vehicle_id);

CREATE TABLE IF NOT EXISTS vin_decodes (
  decode_id TEXT PRIMARY KEY,
  vehicle_id TEXT REFERENCES vehicles(vehicle_id),
  vin TEXT NOT NULL, make TEXT, model TEXT, model_year INTEGER,
  body_class TEXT, engine TEXT, fuel_type TEXT, drivetrain TEXT,
  transmission TEXT, manufacturer TEXT, plant TEXT,
  decode_source TEXT DEFAULT 'NHTSA vPIC', decode_raw_json TEXT,
  decode_success INTEGER, extraction_date TEXT, confidence REAL
);
CREATE INDEX IF NOT EXISTS idx_decode_vin ON vin_decodes(vin);

CREATE TABLE IF NOT EXISTS recalls (
  recall_id TEXT PRIMARY KEY,
  make TEXT, model TEXT, model_year INTEGER, campaign_number TEXT,
  component TEXT, summary TEXT, severity TEXT, report_date TEXT,
  level TEXT DEFAULT 'model-level',
  source_name TEXT DEFAULT 'NHTSA Recalls', source_url TEXT,
  extraction_date TEXT, confidence REAL
);
CREATE INDEX IF NOT EXISTS idx_recall_mmy ON recalls(make, model, model_year);

CREATE TABLE IF NOT EXISTS repair_signals (
  signal_id TEXT PRIMARY KEY,
  make TEXT, model TEXT, model_year INTEGER,
  component_theme TEXT, theme_intensity REAL, signal_kind TEXT,
  evidence_span TEXT, risk_tier TEXT, level TEXT DEFAULT 'model-level',
  source_name TEXT, source_url TEXT, extraction_date TEXT,
  confidence REAL, inference_flag INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_repair_mmy ON repair_signals(make, model, model_year);

CREATE TABLE IF NOT EXISTS competitor_signals (
  competitor_signal_id TEXT PRIMARY KEY,
  competitor_name TEXT, coverage_tier TEXT, covered_components TEXT,
  positioning_note TEXT, applies_to_segment TEXT,
  source_name TEXT, source_url TEXT, risk_tier TEXT,
  extraction_date TEXT, confidence REAL, inference_flag INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS coverage_scores (
  score_id TEXT PRIMARY KEY,
  vehicle_id TEXT REFERENCES vehicles(vehicle_id), vin TEXT,
  coverage_readiness_score REAL, repair_risk_score REAL,
  plan_fit_recommendation TEXT, plan_fit_reason TEXT,
  exclusion_review_flags TEXT, exclusion_review_score REAL,
  buyer_urgency_score REAL, recommended_message_angle TEXT,
  recall_count INTEGER, recall_severity TEXT, component_risk_themes TEXT,
  scoring_version TEXT, score_date TEXT, confidence REAL
);
CREATE INDEX IF NOT EXISTS idx_cov_vehicle ON coverage_scores(vehicle_id);

CREATE TABLE IF NOT EXISTS dealer_scores (
  dealer_score_id TEXT PRIMARY KEY,
  dealer_id TEXT REFERENCES dealers(dealer_id),
  dealer_coverage_opportunity_score REAL, coverage_ready_vehicle_share REAL,
  high_repair_risk_vehicle_count INTEGER, truck_suv_luxury_share REAL,
  avg_mileage_in_prime_range_share REAL, dealer_location_priority REAL,
  data_completeness REAL, recommended_partner_pitch TEXT,
  recommended_plan_mix TEXT, scoring_version TEXT, score_date TEXT, confidence REAL
);

CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
  field_name TEXT, value TEXT, source_name TEXT, source_url TEXT,
  source_type TEXT, evidence_span TEXT, confidence REAL,
  extraction_date TEXT, inference_flag INTEGER DEFAULT 0, risk_tier TEXT
);
CREATE INDEX IF NOT EXISTS idx_evidence_entity ON evidence(entity_type, entity_id);

CREATE TABLE IF NOT EXISTS run_logs (
  run_id TEXT PRIMARY KEY, script_name TEXT, source_name TEXT,
  apify_actor TEXT, apify_run_id TEXT, started_at TEXT, finished_at TEXT,
  status TEXT, records_in INTEGER, records_out INTEGER,
  records_rejected INTEGER, notes TEXT, error_detail TEXT
);

CREATE TABLE IF NOT EXISTS activation_contacts (
  dealer_id TEXT REFERENCES dealers(dealer_id),
  recommended_personas TEXT, activation_source TEXT,
  contact_enrichment_status TEXT, notes TEXT
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}" if prefix else uuid.uuid4().hex


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def insert_evidence(conn, *, entity_type, entity_id, field_name, value,
                    source_name, source_url, source_type=None, evidence_span=None,
                    confidence=None, inference_flag=0, risk_tier=None) -> str:
    eid = new_id("ev_")
    conn.execute(
        """INSERT INTO evidence (evidence_id, entity_type, entity_id, field_name,
            value, source_name, source_url, source_type, evidence_span, confidence,
            extraction_date, inference_flag, risk_tier)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (eid, entity_type, entity_id, field_name,
         str(value) if value is not None else None,
         source_name, source_url, source_type, evidence_span, confidence,
         now_iso(), inference_flag, risk_tier),
    )
    return eid


def log_run(conn, *, script_name, source_name=None, apify_actor=None,
            apify_run_id=None, started_at=None, status="success",
            records_in=0, records_out=0, records_rejected=0,
            notes=None, error_detail=None) -> str:
    rid = new_id("run_")
    conn.execute(
        """INSERT INTO run_logs (run_id, script_name, source_name, apify_actor,
            apify_run_id, started_at, finished_at, status, records_in, records_out,
            records_rejected, notes, error_detail)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (rid, script_name, source_name, apify_actor, apify_run_id,
         started_at or now_iso(), now_iso(), status, records_in, records_out,
         records_rejected, notes, error_detail),
    )
    conn.commit()
    return rid


def get_or_create_vehicle(conn, dealer_id: str, vin: str) -> str:
    """Dedup on (vin, dealer_id). Returns the vehicle_id (existing or new).

    The same VIN at two different dealers is preserved as two vehicle rows
    (two listings of one identity); the same VIN at one dealer is deduped.
    """
    from .vin import normalize_vin
    vin = normalize_vin(vin)
    row = conn.execute(
        "SELECT vehicle_id FROM vehicles WHERE vin=? AND dealer_id=?", (vin, dealer_id)
    ).fetchone()
    if row:
        return row["vehicle_id"]
    vid = new_id("veh_")
    conn.execute(
        "INSERT INTO vehicles (vehicle_id, dealer_id, vin, first_seen, last_updated) "
        "VALUES (?,?,?,?,?)", (vid, dealer_id, vin, now_iso(), now_iso()))
    return vid


def jdump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)
