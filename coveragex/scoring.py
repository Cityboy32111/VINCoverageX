"""Scoring engine — implements docs/scoring_methodology.md.

Pure functions driven by config/scoring_config.json. No network; fully
unit-testable. Every score is a 0-100 proxy/candidate score, never an
actuarial or verified figure.

A "vehicle" input is a dict with any of:
  make, model, model_year (or year), body_class, engine, drivetrain,
  fuel_type, trim, mileage, price, recall_count, recall_severity,
  component_themes (list of {"theme": str, "intensity": 0..1}),
  listing_text, decode_success (bool), licensed_title_status (str|None).
"""
from __future__ import annotations

from typing import Any

from .config import scoring_config
from .vin import mileage_band, vehicle_age, in_prime_mileage


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _lower(v: Any) -> str:
    return str(v or "").lower()


# --------------------------------------------------------------------------
# Feature derivation
# --------------------------------------------------------------------------
def derive_features(vehicle: dict, cfg: dict | None = None) -> dict:
    cfg = cfg or scoring_config()
    make = _lower(vehicle.get("make"))
    body = _lower(vehicle.get("body_class"))
    fuel = _lower(vehicle.get("fuel_type"))
    powertrain_text = " ".join(
        _lower(vehicle.get(k)) for k in ("engine", "drivetrain", "trim", "fuel_type")
    )

    def _match(keys: list[str], text: str) -> bool:
        return any(k in text for k in keys)

    is_luxury = any(m == make or m in make for m in cfg["luxury_makes"]) if make else False
    is_truck = _match(cfg["truck_body_keywords"], body)
    is_suv = _match(cfg["suv_body_keywords"], body)
    is_van = _match(cfg["van_body_keywords"], body)
    is_ev = _match(cfg["ev_fuel_keywords"], fuel) or "electric" in powertrain_text
    is_hybrid = _match(cfg["hybrid_fuel_keywords"], fuel)

    if is_truck:
        body_cat = "truck"
    elif is_suv:
        body_cat = "suv"
    elif is_van:
        body_cat = "van"
    elif _match(cfg["coupe_body_keywords"], body):
        body_cat = "coupe"
    elif _match(cfg["hatchback_body_keywords"], body):
        body_cat = "hatchback"
    elif _match(cfg["wagon_body_keywords"], body):
        body_cat = "wagon"
    elif _match(cfg["sedan_body_keywords"], body):
        body_cat = "sedan"
    else:
        body_cat = "default"

    lift_key = "luxury" if is_luxury else body_cat
    risk_key = "luxury" if is_luxury else body_cat
    class_lift = cfg["class_lift"].get(lift_key, cfg["class_lift"]["default"])
    class_risk = cfg["class_risk"].get(risk_key, cfg["class_risk"]["default"])
    if is_ev or is_hybrid:
        bonus = cfg["ev_hybrid_class_bonus"]
        class_lift = _clamp(class_lift + bonus)
        class_risk = _clamp(class_risk + bonus)

    return {
        "is_luxury": is_luxury, "is_truck": is_truck, "is_suv": is_suv,
        "is_van": is_van, "is_ev": is_ev, "is_hybrid": is_hybrid,
        "body_cat": body_cat, "class_lift": class_lift, "class_risk": class_risk,
        "powertrain_text": powertrain_text,
        "truck_suv_luxury": is_truck or is_suv or is_luxury,
    }


# --------------------------------------------------------------------------
# Sub-score curves
# --------------------------------------------------------------------------
def mileage_fit(mileage: int | None) -> float:
    if mileage is None:
        return 0.0
    m = int(mileage)
    if m < 40_000:
        return _clamp(30 + (m / 40_000) * 40)        # 30 -> 70
    if m <= 130_000:
        return 100.0
    if m <= 160_000:
        return _clamp(100 - ((m - 130_000) / 30_000) * 60)  # 100 -> 40
    return 20.0


def age_fit(age: int | None) -> float:
    if age is None:
        return 0.0
    if age <= 3:
        return 25.0
    if age <= 12:
        return 100.0
    if age <= 15:
        return _clamp(100 - ((age - 12) / 3) * 50)   # 100 -> 50
    return 30.0


def warranty_gap(age: int | None, mileage: int | None) -> float:
    if age is None:
        return 50.0
    if age <= 3 and (mileage is None or mileage < 36_000):
        return 10.0
    if age <= 5 and (mileage is None or mileage < 60_000):
        return 55.0
    return 90.0


def data_completeness(has_mileage: bool, decode_success: bool) -> float:
    return 100.0 if (has_mileage and decode_success) else (60.0 if (has_mileage or decode_success) else 20.0)


def _mileage_risk(mileage: int | None, cfg: dict) -> float:
    if mileage is None:
        return 50.0
    return _clamp(int(mileage) / cfg["repair_risk"]["mileage_risk_full_at"] * 100)


def _age_risk(age: int | None, cfg: dict) -> float:
    if age is None:
        return 50.0
    return _clamp(age / cfg["repair_risk"]["age_risk_full_at"] * 100)


def _powertrain_complexity(feat: dict, cfg: dict) -> float:
    pc = cfg["powertrain_complexity"]
    score = pc["base"]
    text = feat["powertrain_text"]
    for key, add in pc.items():
        if key in ("base", "cap"):
            continue
        if key in text:
            score += add
    if feat["is_ev"]:
        score += pc.get("electric", 0)
    if feat["is_hybrid"]:
        score += pc.get("hybrid", 0)
    return _clamp(score, 0, pc.get("cap", 100))


def _recall_component_risk(recall_count: int | None, severity: str | None) -> float:
    if recall_count is None:
        return 40.0
    count_part = min(60, recall_count * 12)
    sev = {"high": 40, "medium": 20, "low": 5, "none": 0}.get(_lower(severity), 0)
    return _clamp(count_part + sev)


def _public_complaint_intensity(themes: list[dict] | None, cfg: dict) -> float:
    if not themes:
        return cfg["repair_risk"]["neutral_complaint_score"]
    intensities = [float(t.get("intensity", 0)) for t in themes]
    max_i = max(intensities) if intensities else 0.0
    breadth = min(1.0, len(themes) / 4)
    return _clamp(100 * (0.6 * max_i + 0.4 * breadth))


# --------------------------------------------------------------------------
# Vehicle-level composite scores
# --------------------------------------------------------------------------
def repair_risk_score(vehicle: dict, feat: dict | None = None, cfg: dict | None = None) -> dict:
    cfg = cfg or scoring_config()
    feat = feat or derive_features(vehicle, cfg)
    w = cfg["repair_risk"]["weights"]
    age = vehicle.get("vehicle_age")
    if age is None:
        age = vehicle_age(vehicle.get("model_year") or vehicle.get("year"))
    mileage = vehicle.get("mileage")

    subs = {
        "mileage_risk": _mileage_risk(mileage, cfg),
        "age_risk": _age_risk(age, cfg),
        "class_risk": feat["class_risk"],
        "powertrain_complexity": _powertrain_complexity(feat, cfg),
        "recall_component": _recall_component_risk(
            vehicle.get("recall_count"), vehicle.get("recall_severity")
        ),
        "public_complaint": _public_complaint_intensity(vehicle.get("component_themes"), cfg),
    }
    score = sum(subs[k] * w[k] for k in w)
    th = cfg["repair_risk"]
    band = "high" if score >= th["high_threshold"] else (
        "moderate" if score >= th["moderate_threshold"] else "low")
    themes = [t.get("theme") for t in (vehicle.get("component_themes") or [])]
    return {"score": round(score, 1), "subscores": subs, "band": band, "themes": themes}


def coverage_readiness_score(vehicle: dict, repair: dict | None = None,
                             feat: dict | None = None, cfg: dict | None = None) -> dict:
    cfg = cfg or scoring_config()
    feat = feat or derive_features(vehicle, cfg)
    repair = repair or repair_risk_score(vehicle, feat, cfg)
    w = cfg["coverage_readiness"]["weights"]
    age = vehicle.get("vehicle_age")
    if age is None:
        age = vehicle_age(vehicle.get("model_year") or vehicle.get("year"))
    mileage = vehicle.get("mileage")
    has_mileage = mileage is not None
    decode_success = bool(vehicle.get("decode_success", True))

    subs = {
        "mileage_fit": mileage_fit(mileage),
        "age_fit": age_fit(age),
        "repair_cost_exposure": repair["score"],
        "class_lift": feat["class_lift"],
        "warranty_gap": warranty_gap(age, mileage),
        "data_completeness": data_completeness(has_mileage, decode_success),
    }
    score = sum(subs[k] * w[k] for k in w)
    th = cfg["coverage_readiness"]
    band = "Coverage-Ready" if score >= th["ready_threshold"] else (
        "Watch" if score >= th["watch_threshold"] else "Low fit")
    return {"score": round(score, 1), "subscores": subs, "band": band}


def plan_fit(vehicle: dict, repair: dict, feat: dict | None = None, cfg: dict | None = None) -> dict:
    cfg = cfg or scoring_config()
    feat = feat or derive_features(vehicle, cfg)
    pf = cfg["plan_fit"]
    rr = repair["score"]
    band = mileage_band(vehicle.get("mileage"))
    themes = set(repair.get("themes") or [])
    expensive = {"transmission", "engine", "powertrain", "hybrid", "electrical"}
    known_expensive = bool(themes & expensive)

    if feat["is_luxury"] or feat["is_ev"] or rr >= pf["executive_repair_risk"]:
        tier, why = "Executive", []
        if feat["is_luxury"]:
            why.append("luxury / high parts cost")
        if feat["is_ev"]:
            why.append("EV high-voltage components")
        if rr >= pf["executive_repair_risk"]:
            why.append(f"very high repair risk ({rr})")
    elif (feat["is_truck"] or feat["is_suv"] or rr >= pf["premium_repair_risk"]
          or band in (">130k", "100k-130k") or known_expensive):
        tier, why = "Premium", []
        if feat["is_truck"] or feat["is_suv"]:
            why.append("truck/SUV powertrain exposure")
        if rr >= pf["premium_repair_risk"]:
            why.append(f"high repair risk ({rr})")
        if band in (">130k", "100k-130k"):
            why.append(f"{band} mileage")
        if known_expensive:
            why.append("known expensive components: " + ", ".join(sorted(themes & expensive)))
    elif rr >= pf["signature_repair_risk_min"] or band == "70k-100k":
        tier, why = "Signature", [f"moderate repair risk ({rr})"]
        if band == "70k-100k":
            why.append("mid-mileage")
    else:
        tier, why = "Essential", [f"lower repair risk ({rr}), lower mileage"]

    reason = f"{tier}: " + "; ".join(why) if why else tier
    return {"tier": tier, "reason": reason}


def exclusion_review(vehicle: dict, cfg: dict | None = None) -> dict:
    cfg = cfg or scoring_config()
    er = cfg["exclusion_review"]
    w = er["weights"]
    flags: list[str] = []
    notes: list[str] = []
    score = 0.0
    text = _lower(vehicle.get("listing_text"))
    mileage = vehicle.get("mileage")
    age = vehicle.get("vehicle_age")
    if age is None:
        age = vehicle_age(vehicle.get("model_year") or vehicle.get("year"))

    if mileage is not None and int(mileage) > er["high_mileage"]:
        flags.append("high_mileage"); score += w["high_mileage"]
    if age is not None and age > er["very_old_age"]:
        flags.append("very_old"); score += w["very_old"]
    if any(k in text for k in er["commercial_keywords"]):
        flags.append("commercial_use"); score += w["commercial"]
    if any(k in text for k in er["rideshare_keywords"]):
        flags.append("rideshare"); score += w["rideshare"]
    if any(k in text for k in er["modification_keywords"]):
        flags.append("modifications"); score += w["modifications"]
    if _lower(vehicle.get("recall_severity")) == "high":
        flags.append("severe_recall_model_level"); score += w["severe_recall"]

    # Licensed-only signals: never asserted without a licensed source.
    title = _lower(vehicle.get("licensed_title_status"))
    if title in ("salvage", "rebuilt"):
        flags.append(f"title_{title}"); score += w["salvage"]
    else:
        notes.append("title/salvage: unknown — not asserted (no licensed source)")
    if vehicle.get("licensed_odometer_issue"):
        flags.append("odometer_issue"); score += w["odometer_issue"]
    else:
        notes.append("odometer: unknown — not asserted (no licensed source)")

    return {"score": round(_clamp(score), 1), "flags": flags, "notes": notes}


def buyer_urgency(coverage: dict, repair: dict, vehicle: dict,
                  exclusion: dict, cfg: dict | None = None) -> float:
    cfg = cfg or scoring_config()
    bu = cfg["buyer_urgency"]
    w = bu["weights"]
    age = vehicle.get("vehicle_age")
    if age is None:
        age = vehicle_age(vehicle.get("model_year") or vehicle.get("year"))
    wg = warranty_gap(age, vehicle.get("mileage"))
    score = w["coverage_readiness"] * coverage["score"] + w["repair_risk"] * repair["score"] + w["warranty_gap"] * wg
    if exclusion["score"] > bu["suppress_if_exclusion_over"]:
        score *= 0.2
    return round(_clamp(score), 1)


def message_angle(coverage: dict, repair: dict, plan: dict, vehicle: dict) -> str:
    bits = []
    age = vehicle.get("vehicle_age") or vehicle_age(vehicle.get("model_year") or vehicle.get("year"))
    if age and age >= 4:
        bits.append("out of factory warranty")
    band = mileage_band(vehicle.get("mileage"))
    if in_prime_mileage(vehicle.get("mileage")):
        bits.append(f"in the prime protection window ({band})")
    themes = repair.get("themes") or []
    if themes:
        bits.append(f"known pain point: {themes[0]}")
    lead = ", ".join(bits) if bits else "candidate for protection"
    return f"{lead.capitalize()} — strong {plan['tier']} fit."


def score_vehicle(vehicle: dict, cfg: dict | None = None) -> dict:
    """Full vehicle scoring bundle."""
    cfg = cfg or scoring_config()
    feat = derive_features(vehicle, cfg)
    repair = repair_risk_score(vehicle, feat, cfg)
    coverage = coverage_readiness_score(vehicle, repair, feat, cfg)
    plan = plan_fit(vehicle, repair, feat, cfg)
    excl = exclusion_review(vehicle, cfg)
    urgency = buyer_urgency(coverage, repair, vehicle, excl, cfg)
    angle = message_angle(coverage, repair, plan, vehicle)
    return {
        "features": feat,
        "coverage_readiness_score": coverage["score"],
        "coverage_band": coverage["band"],
        "coverage_subscores": coverage["subscores"],
        "repair_risk_score": repair["score"],
        "repair_band": repair["band"],
        "repair_subscores": repair["subscores"],
        "component_risk_themes": repair["themes"],
        "plan_fit_recommendation": plan["tier"],
        "plan_fit_reason": plan["reason"],
        "exclusion_review_score": excl["score"],
        "exclusion_review_flags": excl["flags"],
        "exclusion_notes": excl["notes"],
        "buyer_urgency_score": urgency,
        "recommended_message_angle": angle,
        "scoring_version": cfg["scoring_version"],
    }


# --------------------------------------------------------------------------
# Dealer-level scores
# --------------------------------------------------------------------------
def location_priority(city: str | None, county: str | None, cfg: dict) -> float:
    table = cfg["market_location_priority"]
    for loc in (_lower(county), _lower(city)):
        for key, val in table.items():
            if key != "default" and key in loc:
                return val
    return table["default"]


def dealer_opportunity_score(rollup: dict, cfg: dict | None = None) -> dict:
    """rollup keys: inventory_count, coverage_ready_count, high_repair_risk_count,
    truck_suv_luxury_count, prime_mileage_count, valid_decode_count, city, county."""
    cfg = cfg or scoring_config()
    do = cfg["dealer_opportunity"]
    w = do["weights"]
    inv = max(1, rollup.get("inventory_count", 0))

    coverage_ready_share = rollup.get("coverage_ready_count", 0) / inv
    inv_norm = min(1.0, rollup.get("inventory_count", 0) / do["inventory_count_saturation"])
    hrr_norm = min(1.0, rollup.get("high_repair_risk_count", 0) / do["high_repair_risk_saturation"])
    tsl_share = rollup.get("truck_suv_luxury_count", 0) / inv
    prime_share = rollup.get("prime_mileage_count", 0) / inv
    loc = location_priority(rollup.get("city"), rollup.get("county"), cfg)
    completeness = rollup.get("valid_decode_count", 0) / inv

    components = {
        "coverage_ready_share": coverage_ready_share * 100,
        "inventory_count": inv_norm * 100,
        "high_repair_risk_count": hrr_norm * 100,
        "truck_suv_luxury_share": tsl_share * 100,
        "prime_mileage_share": prime_share * 100,
        "location_priority": loc * 100,
        "data_completeness": completeness * 100,
    }
    score = sum(components[k] * w[k] for k in w)
    band = "Priority partner" if score >= do["priority_threshold"] else (
        "Qualified" if score >= do["qualified_threshold"] else "Monitor")
    return {
        "score": round(_clamp(score), 1), "band": band, "components": components,
        "coverage_ready_share": round(coverage_ready_share, 3),
        "truck_suv_luxury_share": round(tsl_share, 3),
        "prime_mileage_share": round(prime_share, 3),
    }


def dealer_pitch(rollup: dict, plan_mix: dict, cfg: dict | None = None) -> dict:
    cfg = cfg or scoring_config()
    pt = cfg["pitch_thresholds"]
    inv = max(1, rollup.get("inventory_count", 0))
    truck_suv_share = (rollup.get("truck_count", 0) + rollup.get("suv_count", 0)) / inv
    luxury_share = rollup.get("luxury_count", 0) / inv
    ev_share = rollup.get("ev_count", 0) / inv
    prime_share = rollup.get("prime_mileage_count", 0) / inv
    ready_share = rollup.get("coverage_ready_count", 0) / inv
    recall_density = rollup.get("total_recalls", 0) / inv

    angles = []
    if truck_suv_share >= pt["truck_suv_share_high"]:
        angles.append("High truck & SUV inventory — premium powertrain protection fit")
    if luxury_share >= pt["luxury_share_high"]:
        angles.append("Used-luxury exposure — high parts cost, strong Executive/Premium attach")
    if prime_share >= pt["prime_mileage_share_high"]:
        angles.append("Inventory sits in the prime protection mileage window")
    if ev_share >= pt["ev_share_high"]:
        angles.append("EV protection opportunity — high-voltage/component coverage")
    if recall_density >= pt["recall_density_high"]:
        angles.append("Recall-service + protection bundle opportunity")
    if ready_share >= pt["coverage_ready_share_high"]:
        angles.append("Large coverage-ready set — direct F&I attach opportunity")
    if not angles:
        angles.append("Mixed used inventory with selective protection-attach opportunity")

    top = angles[:2]
    pitch = (
        "Your used inventory is sitting in the prime protection window. "
        "CoverageX can attach protection to the vehicles where repair anxiety is highest. "
        f"({'; '.join(top)}.)"
    )
    return {
        "recommended_partner_pitch": pitch,
        "pitch_angles": angles,
        "recommended_personas": ["F&I Director", "Used-Car Manager", "General Manager"],
        "recommended_plan_mix": plan_mix,
        "truck_suv_share": round(truck_suv_share, 3),
        "luxury_share": round(luxury_share, 3),
        "ev_share": round(ev_share, 3),
    }
