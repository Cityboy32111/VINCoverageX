"""Dedup on (vin, dealer_id): same VIN at one dealer collapses; across dealers stays distinct."""
import pytest

from coveragex import db


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.sqlite")
    db.init_db(c)
    for did in ("dealer-a", "dealer-b"):
        c.execute("INSERT INTO dealers (dealer_id, dealer_name, first_seen, last_updated) VALUES (?,?,?,?)",
                  (did, did.upper(), db.now_iso(), db.now_iso()))
    c.commit()
    yield c
    c.close()


VIN = "11111111111111111"


def test_same_vin_same_dealer_dedups(conn):
    a = db.get_or_create_vehicle(conn, "dealer-a", VIN)
    b = db.get_or_create_vehicle(conn, "dealer-a", VIN)
    assert a == b
    n = conn.execute("SELECT COUNT(*) FROM vehicles WHERE dealer_id='dealer-a'").fetchone()[0]
    assert n == 1


def test_same_vin_different_dealers_kept(conn):
    a = db.get_or_create_vehicle(conn, "dealer-a", VIN)
    b = db.get_or_create_vehicle(conn, "dealer-b", VIN)
    assert a != b
    n = conn.execute("SELECT COUNT(*) FROM vehicles WHERE vin=?", (VIN,)).fetchone()[0]
    assert n == 2


def test_vin_is_normalized_before_dedup(conn):
    a = db.get_or_create_vehicle(conn, "dealer-a", VIN)
    b = db.get_or_create_vehicle(conn, "dealer-a", f"  {VIN.lower()} ")
    assert a == b


def test_unique_constraint_enforced(conn):
    db.get_or_create_vehicle(conn, "dealer-a", VIN)
    with pytest.raises(Exception):
        conn.execute(
            "INSERT INTO vehicles (vehicle_id, dealer_id, vin, first_seen, last_updated) VALUES (?,?,?,?,?)",
            (db.new_id("veh_"), "dealer-a", VIN, db.now_iso(), db.now_iso()))
        conn.commit()
