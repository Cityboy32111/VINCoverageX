"""Extraction helpers: VIN / mileage / price / repair-theme classification, and
best-effort parsing of dealer inventory HTML (JSON-LD Vehicle + data-vin +
regex). Used to map Apify/static collection output into the internal schema.

Parsing already-downloaded HTML is a Claude Code job (not Apify).
"""
from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from .vin import validate_vin

_VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b", re.IGNORECASE)
_MILEAGE_RE = re.compile(r"([\d][\d,\.]{1,7})\s*(?:k\b|miles|mi\b|mileage|odometer)", re.IGNORECASE)
_MILEAGE_K_RE = re.compile(r"\b(\d{1,3})\s*k\s*(?:miles|mi)\b", re.IGNORECASE)
_PRICE_RE = re.compile(r"\$\s*([\d]{1,3}(?:,\d{3})+|\d{4,6})")


def extract_vins(text: str) -> list[str]:
    """Return validated, deduped VINs found in text (check-digit-valid first)."""
    if not text:
        return []
    seen: dict[str, bool] = {}
    for m in _VIN_RE.findall(text):
        v = validate_vin(m)
        if v.valid:
            seen.setdefault(v.vin, v.check_digit_valid)
            if v.check_digit_valid:
                seen[v.vin] = True
    return sorted(seen, key=lambda k: (not seen[k], k))


def extract_mileage(text: str) -> int | None:
    if not text:
        return None
    mk = _MILEAGE_K_RE.search(text)
    if mk:
        return int(mk.group(1)) * 1000
    m = _MILEAGE_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    try:
        val = float(raw)
    except ValueError:
        return None
    if "k" in m.group(0).lower() and val < 1000:
        val *= 1000
    val = int(val)
    return val if 0 < val < 500_000 else None


def extract_price(text: str) -> float | None:
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return val if 500 <= val <= 500_000 else None


def classify_repair_themes(texts, cfg: dict) -> list[dict]:
    """Map free text to component themes with a crude intensity (hit density)."""
    keywords = cfg.get("repair_theme_keywords", {})
    blob = " ".join(t for t in texts if t).lower()
    if not blob:
        return []
    out = []
    for theme, kws in keywords.items():
        hits = sum(blob.count(k.lower()) for k in kws)
        if hits:
            intensity = min(1.0, hits / 10.0)
            out.append({"theme": theme, "intensity": round(intensity, 2), "hits": hits})
    out.sort(key=lambda d: d["hits"], reverse=True)
    return out


def _coerce_int(v):
    try:
        return int(re.sub(r"[^\d]", "", str(v)))
    except (ValueError, TypeError):
        return None


def parse_vehicle_listings_from_html(html: str, url: str) -> list[dict]:
    """Best-effort: JSON-LD Vehicle/Car blocks, then data-vin attributes, then
    a page-level regex fallback. Returns partial vehicle dicts."""
    records: list[dict] = []
    if not html:
        return records
    soup = BeautifulSoup(html, "html.parser")

    # 1) JSON-LD structured data
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in data if isinstance(data, list) else [data]:
            if not isinstance(node, dict):
                continue
            typ = str(node.get("@type", "")).lower()
            if typ in ("vehicle", "car", "product") and (node.get("vehicleIdentificationNumber") or node.get("vin")):
                vin_raw = node.get("vehicleIdentificationNumber") or node.get("vin")
                v = validate_vin(vin_raw)
                if not v.valid:
                    continue
                offers = node.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                odo = node.get("mileageFromOdometer") or {}
                records.append({
                    "vin": v.vin,
                    "make": (node.get("brand") or {}).get("name") if isinstance(node.get("brand"), dict) else node.get("brand"),
                    "model": node.get("model"),
                    "year": _coerce_int(node.get("vehicleModelDate") or node.get("modelDate")),
                    "mileage": _coerce_int(odo.get("value") if isinstance(odo, dict) else odo),
                    "price": _coerce_int(offers.get("price")) if offers else None,
                    "listing_url": node.get("url") or url,
                    "source_url": url,
                    "source": "jsonld",
                })

    # 2) data-vin attributes
    if not records:
        for el in soup.select("[data-vin], [data-vehicle-vin]"):
            vin_raw = el.get("data-vin") or el.get("data-vehicle-vin")
            v = validate_vin(vin_raw or "")
            if v.valid:
                txt = el.get_text(" ", strip=True)
                records.append({
                    "vin": v.vin, "mileage": extract_mileage(txt),
                    "price": extract_price(txt), "listing_url": url,
                    "source_url": url, "listing_text": txt[:500], "source": "data-vin",
                })

    # 3) regex fallback over whole page
    if not records:
        text = soup.get_text(" ", strip=True)
        for vin in extract_vins(text):
            records.append({
                "vin": vin, "mileage": extract_mileage(text),
                "price": extract_price(text), "listing_url": url,
                "source_url": url, "source": "regex",
            })

    # dedup by vin within page
    by_vin = {}
    for r in records:
        by_vin.setdefault(r["vin"], r)
    return list(by_vin.values())
