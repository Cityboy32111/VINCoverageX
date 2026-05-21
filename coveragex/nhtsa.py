"""NHTSA clients — vPIC VIN decode + recalls. SAFE PUBLIC, no key required.

Network-dependent. In restricted environments the host may be blocked
(HTTP 403 host_not_allowed); callers should handle NhtsaError and report
the blocker honestly rather than fabricating data.
"""
from __future__ import annotations

import time

import requests

from .config import nhtsa_base

RECALLS_BASE = "https://api.nhtsa.gov/recalls/recallsByVehicle"
COMPLAINTS_BASE = "https://api.nhtsa.gov/complaints/complaintsByVehicle"
_TIMEOUT = 20
_RETRIES = 3


class NhtsaError(RuntimeError):
    pass


def _get(url: str, params: dict | None = None) -> dict:
    last = None
    for attempt in range(_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=_TIMEOUT,
                             headers={"User-Agent": "CoverageX-SignalGraph/0.1 (PoC)"})
            if r.status_code == 403:
                raise NhtsaError(
                    f"403 from {url} (host may be blocked by network policy: "
                    f"'{r.headers.get('x-deny-reason', 'unknown')}'). "
                    f"Allow vpic.nhtsa.dot.gov + api.nhtsa.gov, or run locally."
                )
            r.raise_for_status()
            return r.json()
        except NhtsaError:
            raise
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 ** attempt)
    raise NhtsaError(f"NHTSA request failed after {_RETRIES} tries: {url} :: {last}")


def decode_vin(vin: str) -> dict:
    """Decode one VIN via vPIC DecodeVinValues. Returns normalized fields + raw."""
    url = f"{nhtsa_base()}/vehicles/DecodeVinValues/{vin}"
    data = _get(url, {"format": "json"})
    results = data.get("Results") or [{}]
    r = results[0]

    def _v(key: str) -> str | None:
        val = r.get(key)
        return val if val not in ("", None) else None

    year = _v("ModelYear")
    decoded = {
        "vin": vin,
        "make": _v("Make"),
        "model": _v("Model"),
        "model_year": int(year) if year and str(year).isdigit() else None,
        "body_class": _v("BodyClass"),
        "engine": " ".join(
            x for x in [_v("EngineCylinders") and f"{_v('EngineCylinders')}cyl",
                        _v("DisplacementL") and f"{_v('DisplacementL')}L",
                        _v("EngineModel")] if x
        ) or None,
        "fuel_type": _v("FuelTypePrimary"),
        "drivetrain": _v("DriveType"),
        "transmission": _v("TransmissionStyle"),
        "manufacturer": _v("Manufacturer"),
        "plant": _v("PlantCity"),
        "error_code": _v("ErrorCode"),
        "raw": r,
    }
    decoded["decode_success"] = bool(decoded["make"] and decoded["model"] and decoded["model_year"])
    return decoded


def get_recalls(make: str, model: str, model_year: int | str) -> list[dict]:
    """Model-level recalls. Never implies VIN-specific open-recall status."""
    data = _get(RECALLS_BASE, {"make": make, "model": model, "modelYear": model_year})
    out = []
    for item in data.get("results", []) or []:
        out.append({
            "campaign_number": item.get("NHTSACampaignNumber"),
            "component": item.get("Component"),
            "summary": item.get("Summary"),
            "report_date": item.get("ReportReceivedDate"),
            "consequence": item.get("Consequence"),
            "remedy": item.get("Remedy"),
        })
    return out


def get_complaints(make: str, model: str, model_year: int | str) -> list[dict]:
    """Model-level consumer complaints (unverified). Theme signal only."""
    data = _get(COMPLAINTS_BASE, {"make": make, "model": model, "modelYear": model_year})
    out = []
    for item in data.get("results", []) or []:
        out.append({
            "component": item.get("components"),
            "summary": item.get("summary"),
            "odi_number": item.get("odiNumber"),
            "date": item.get("dateOfIncident") or item.get("dateComplaintFiled"),
        })
    return out
