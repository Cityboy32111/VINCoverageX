"""VIN validation, normalization, and derived vehicle attributes.

Pure functions, no network — fully unit-testable offline.

Rules (per phase1_plan.md):
  * VIN must be 17 characters.
  * Letters I, O, Q are not allowed.
  * Normalize to uppercase.
  * ISO 3779 check-digit (position 9) is validated as an extra confidence
    signal; format validity is the hard gate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .config import REFERENCE_YEAR

DISALLOWED_LETTERS = set("IOQ")
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")  # excludes I, O, Q

# ISO 3779 transliteration (letters -> numeric value) for check-digit.
_TRANSLITERATION = {
    **{str(d): d for d in range(10)},
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}
_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]


@dataclass(frozen=True)
class VinValidation:
    raw: str
    vin: str                 # normalized
    valid: bool              # format-valid (the hard gate)
    reason: str | None       # why invalid (None if valid)
    check_digit_valid: bool  # ISO 3779 check-digit passes


def normalize_vin(raw: str) -> str:
    if raw is None:
        return ""
    return re.sub(r"[\s\-]", "", str(raw)).strip().upper()


def compute_check_digit(vin: str) -> str:
    total = sum(_TRANSLITERATION[ch] * w for ch, w in zip(vin, _WEIGHTS))
    rem = total % 11
    return "X" if rem == 10 else str(rem)


def check_digit_valid(vin: str) -> bool:
    if not VIN_RE.match(vin):
        return False
    try:
        return compute_check_digit(vin) == vin[8]
    except KeyError:
        return False


def validate_vin(raw: str) -> VinValidation:
    vin = normalize_vin(raw)
    if len(vin) != 17:
        return VinValidation(raw, vin, False, f"length {len(vin)} != 17", False)
    if any(ch in DISALLOWED_LETTERS for ch in vin):
        bad = sorted({ch for ch in vin if ch in DISALLOWED_LETTERS})
        return VinValidation(raw, vin, False, f"disallowed letters {bad}", False)
    if not VIN_RE.match(vin):
        return VinValidation(raw, vin, False, "invalid characters", False)
    return VinValidation(raw, vin, True, None, check_digit_valid(vin))


def vehicle_age(model_year: int | None, reference_year: int = REFERENCE_YEAR) -> int | None:
    if not model_year:
        return None
    return max(0, reference_year - int(model_year))


# Mileage bands shared by data model + scoring.
def mileage_band(mileage: int | None) -> str:
    if mileage is None:
        return "unknown"
    m = int(mileage)
    if m < 40_000:
        return "<40k"
    if m < 70_000:
        return "40k-70k"
    if m < 100_000:
        return "70k-100k"
    if m < 130_000:
        return "100k-130k"
    return ">130k"


PRIME_MILEAGE_BANDS = {"40k-70k", "70k-100k", "100k-130k"}


def in_prime_mileage(mileage: int | None) -> bool:
    return mileage is not None and 40_000 <= int(mileage) <= 130_000
