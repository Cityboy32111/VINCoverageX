"""VIN validation, normalization, check-digit, derived attributes."""
from coveragex.vin import (
    compute_check_digit, in_prime_mileage, mileage_band, normalize_vin,
    validate_vin, vehicle_age,
)

# "11111111111111111" is check-digit valid: weighted sum 89 % 11 == 1,
# and position 9 already holds '1'.
VALID_VIN = "11111111111111111"


def make_valid_vin(seed17: str) -> str:
    s = list(seed17.upper())
    s[8] = compute_check_digit("".join(s))
    return "".join(s)


def test_valid_vin_passes():
    v = validate_vin(VALID_VIN)
    assert v.valid is True
    assert v.reason is None
    assert v.check_digit_valid is True


def test_letter_vin_check_digit_roundtrip():
    vin = make_valid_vin("1HGCM8263XA00435Z")
    v = validate_vin(vin)
    assert v.valid and v.check_digit_valid


def test_normalization_uppercases_and_strips():
    assert normalize_vin("  1hg-cm 826  ") == "1HGCM826"
    # a lowercase valid VIN still validates and is normalized to uppercase
    vin = make_valid_vin("JHMCM56557C40445Z")
    v = validate_vin(vin.lower())
    assert v.valid and v.vin == vin


def test_wrong_length_invalid():
    v = validate_vin("12345")
    assert not v.valid and "length" in v.reason


def test_disallowed_letters_invalid():
    for bad in ("I", "O", "Q"):
        vin = VALID_VIN[:5] + bad + VALID_VIN[6:]
        v = validate_vin(vin)
        assert not v.valid and "disallowed" in v.reason


def test_bad_check_digit_format_valid_but_flagged():
    # change the check-digit position to a value != computed -> format ok, cd false
    bad = VALID_VIN[:8] + "2" + VALID_VIN[9:]
    v = validate_vin(bad)
    assert v.valid is True          # format still valid
    assert v.check_digit_valid is False


def test_mileage_bands():
    assert mileage_band(None) == "unknown"
    assert mileage_band(10_000) == "<40k"
    assert mileage_band(55_000) == "40k-70k"
    assert mileage_band(85_000) == "70k-100k"
    assert mileage_band(120_000) == "100k-130k"
    assert mileage_band(200_000) == ">130k"


def test_prime_mileage():
    assert in_prime_mileage(96_000)
    assert not in_prime_mileage(30_000)
    assert not in_prime_mileage(160_000)
    assert not in_prime_mileage(None)


def test_vehicle_age():
    assert vehicle_age(2016, reference_year=2026) == 10
    assert vehicle_age(None) is None
    assert vehicle_age(2030, reference_year=2026) == 0  # floored at 0
