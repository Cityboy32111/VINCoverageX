"""Scoring engine: weight integrity, curves, plan-fit logic, dealer rollup."""
import pytest

from coveragex.config import scoring_config
from coveragex import scoring

CFG = scoring_config()


def test_weight_sums_are_one():
    for block in ("coverage_readiness", "repair_risk"):
        assert sum(CFG[block]["weights"].values()) == pytest.approx(1.0)
    assert sum(CFG["dealer_opportunity"]["weights"].values()) == pytest.approx(1.0)
    assert sum(CFG["buyer_urgency"]["weights"].values()) == pytest.approx(1.0)


def test_mileage_fit_curve():
    assert scoring.mileage_fit(96_000) == 100
    assert scoring.mileage_fit(None) == 0
    assert 30 <= scoring.mileage_fit(20_000) <= 70
    assert scoring.mileage_fit(200_000) == 20


def test_age_fit_curve():
    assert scoring.age_fit(8) == 100
    assert scoring.age_fit(2) == 25
    assert scoring.age_fit(20) == 30


def test_worked_example_suv_is_coverage_ready_premium():
    v = {"make": "Chevrolet", "model": "Tahoe", "model_year": 2017,
         "body_class": "Sport Utility Vehicle (SUV)/Multipurpose",
         "drivetrain": "AWD/All-Wheel Drive", "fuel_type": "Gasoline",
         "mileage": 96_000, "vehicle_age": 9}
    s = scoring.score_vehicle(v, CFG)
    assert s["coverage_band"] == "Coverage-Ready"
    assert s["coverage_readiness_score"] >= 70
    assert s["plan_fit_recommendation"] == "Premium"


def test_economy_new_car_is_low_fit_essential():
    v = {"make": "Toyota", "model": "Corolla", "model_year": 2024,
         "body_class": "Sedan/Saloon", "fuel_type": "Gasoline",
         "mileage": 12_000, "vehicle_age": 2}
    s = scoring.score_vehicle(v, CFG)
    assert s["coverage_band"] == "Low fit"
    assert s["plan_fit_recommendation"] == "Essential"


def test_luxury_maps_to_executive():
    v = {"make": "BMW", "model": "5 Series", "model_year": 2018,
         "body_class": "Sedan", "fuel_type": "Gasoline", "mileage": 70_000, "vehicle_age": 8}
    assert scoring.score_vehicle(v, CFG)["plan_fit_recommendation"] == "Executive"


def test_ev_maps_to_executive():
    v = {"make": "Nissan", "model": "Leaf", "model_year": 2019,
         "body_class": "Hatchback", "fuel_type": "Electric", "mileage": 50_000, "vehicle_age": 7}
    assert scoring.score_vehicle(v, CFG)["plan_fit_recommendation"] == "Executive"


def test_exclusion_review_flags_high_mileage_and_title_unknown():
    v = {"make": "Ford", "model": "Focus", "model_year": 2008, "vehicle_age": 18,
         "mileage": 200_000, "body_class": "Sedan", "listing_text": ""}
    excl = scoring.exclusion_review(v, CFG)
    assert "high_mileage" in excl["flags"]
    assert "very_old" in excl["flags"]
    assert any("title" in n for n in excl["notes"])  # never asserted without licensed source


def test_commercial_keyword_raises_exclusion():
    v = {"make": "Ford", "model": "Transit", "model_year": 2019, "vehicle_age": 7,
         "mileage": 80_000, "body_class": "Van", "listing_text": "former rental fleet vehicle"}
    excl = scoring.exclusion_review(v, CFG)
    assert "commercial_use" in excl["flags"]


def test_dealer_opportunity_in_range_and_banded():
    rollup = {"inventory_count": 100, "coverage_ready_count": 45, "high_repair_risk_count": 20,
              "truck_suv_luxury_count": 55, "prime_mileage_count": 50, "valid_decode_count": 95,
              "city": "Los Angeles", "county": "Los Angeles"}
    opp = scoring.dealer_opportunity_score(rollup, CFG)
    assert 0 <= opp["score"] <= 100
    assert opp["band"] in ("Priority partner", "Qualified", "Monitor")


def test_score_vehicle_has_required_keys():
    s = scoring.score_vehicle({"make": "Honda", "model": "CR-V", "model_year": 2016,
                               "body_class": "SUV", "mileage": 88_000, "vehicle_age": 10}, CFG)
    for k in ("coverage_readiness_score", "repair_risk_score", "plan_fit_recommendation",
              "plan_fit_reason", "exclusion_review_flags", "buyer_urgency_score",
              "recommended_message_angle", "scoring_version"):
        assert k in s
