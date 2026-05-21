"""Extraction helpers: VIN / mileage / price / repair-theme classification, and
robust parsing of dealer inventory pages.

VIN sources covered (all run, then merged by VIN — no short-circuit):
  1. JSON-LD Vehicle/Car/Product blocks (incl. @graph).
  2. data-vin / data-vehicle-vin attributes (SRP listing cards).
  3. ANY <script> contents (embedded inventory payloads, dataLayer pushes).
  4. Raw-HTML regex (VINs in attributes/links the selectors miss).
  5. VIN embedded in the page URL.
  6. Visible-text regex ("VIN: ...").

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
_JSON_VIN_RE = re.compile(r'["\']?vin["\']?\s*[:=]\s*["\']([A-HJ-NPR-Z0-9]{17})["\']', re.IGNORECASE)


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


def _merge(by_vin: dict, rec: dict) -> None:
    """Insert/merge a record by VIN, preferring richer (more populated) fields."""
    vin = rec.get("vin")
    if not vin:
        return
    cur = by_vin.get(vin)
    if cur is None:
        by_vin[vin] = rec
        return
    for k, val in rec.items():
        if val not in (None, "", []) and cur.get(k) in (None, "", []):
            cur[k] = val


def _walk_jsonld(node, url, by_vin) -> None:
    """Recurse JSON-LD (handles @graph and nested arrays/dicts)."""
    if isinstance(node, list):
        for n in node:
            _walk_jsonld(n, url, by_vin)
        return
    if not isinstance(node, dict):
        return
    if "@graph" in node:
        _walk_jsonld(node["@graph"], url, by_vin)
    typ = str(node.get("@type", "")).lower()
    vin_raw = node.get("vehicleIdentificationNumber") or node.get("vin")
    if vin_raw and (typ in ("vehicle", "car", "product", "motorvehicle") or typ == ""):
        v = validate_vin(vin_raw)
        if v.valid:
            offers = node.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            brand = node.get("brand")
            odo = node.get("mileageFromOdometer") or {}
            _merge(by_vin, {
                "vin": v.vin,
                "make": brand.get("name") if isinstance(brand, dict) else brand,
                "model": node.get("model"),
                "year": _coerce_int(node.get("vehicleModelDate") or node.get("modelDate")),
                "mileage": _coerce_int(odo.get("value") if isinstance(odo, dict) else odo),
                "price": _coerce_int(offers.get("price")) if isinstance(offers, dict) else None,
                "listing_url": node.get("url") or url,
                "source_url": url, "source": "jsonld",
            })
    # recurse into nested values that may hold vehicles
    for val in node.values():
        if isinstance(val, (list, dict)):
            _walk_jsonld(val, url, by_vin)


def parse_vehicle_listings_from_html(html: str, url: str) -> list[dict]:
    """Run all extraction strategies and merge by VIN. Never short-circuits."""
    by_vin: dict[str, dict] = {}
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")

    # 1) JSON-LD (incl. @graph)
    for tag in soup.find_all("script", type=lambda t: t and "ld+json" in t):
        try:
            _walk_jsonld(json.loads(tag.string or tag.get_text() or ""), url, by_vin)
        except (json.JSONDecodeError, TypeError):
            continue

    # 2) data-vin / data-vehicle-vin attributes (listing cards)
    for el in soup.select("[data-vin], [data-vehicle-vin]"):
        v = validate_vin(el.get("data-vin") or el.get("data-vehicle-vin") or "")
        if v.valid:
            txt = el.get_text(" ", strip=True)
            _merge(by_vin, {"vin": v.vin, "mileage": extract_mileage(txt),
                            "price": extract_price(txt), "listing_url": url, "source_url": url,
                            "listing_text": txt[:500], "source": "data-vin"})

    # 3) ANY <script> contents: explicit "vin": "..." keys, then raw VIN tokens
    for tag in soup.find_all("script"):
        content = tag.string or tag.get_text() or ""
        if not content:
            continue
        for m in _JSON_VIN_RE.findall(content):
            v = validate_vin(m)
            if v.valid:
                _merge(by_vin, {"vin": v.vin, "listing_url": url, "source_url": url, "source": "script-json"})
        for vin in extract_vins(content):
            _merge(by_vin, {"vin": vin, "listing_url": url, "source_url": url, "source": "script-text"})

    # 4) raw-HTML regex (attributes/links the selectors miss)
    for vin in extract_vins(html):
        _merge(by_vin, {"vin": vin, "listing_url": url, "source_url": url, "source": "raw-html"})

    # 5) VIN embedded in the URL
    for vin in extract_vins(url or ""):
        _merge(by_vin, {"vin": vin, "listing_url": url, "source_url": url, "source": "url"})

    # 6) visible text (e.g., "VIN: ...") + mileage/price context
    text = soup.get_text(" ", strip=True)
    for vin in extract_vins(text):
        _merge(by_vin, {"vin": vin, "mileage": extract_mileage(text), "price": extract_price(text),
                        "listing_url": url, "source_url": url, "source": "text"})

    return list(by_vin.values())


def vins_from_any(item: dict) -> list[str]:
    """Last-resort: collect VINs from every string value in an Apify item."""
    parts: list[str] = []

    def _collect(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                _collect(x)
        elif isinstance(v, list):
            for x in v:
                _collect(x)

    _collect(item)
    return extract_vins(" ".join(parts))


def parse_apify_item(item: dict) -> list[dict]:
    """Map one Apify crawler item (any common shape) into vehicle records."""
    url = (item.get("url") or item.get("loadedUrl")
           or (item.get("crawl") or {}).get("loadedUrl") or "")
    html = item.get("html") or item.get("body") or ""
    records = parse_vehicle_listings_from_html(html, url) if html else []
    have = {r["vin"] for r in records}

    # text/markdown/url fallback (when html absent or thin)
    blob = " ".join(str(item.get(k) or "") for k in
                    ("text", "markdown", "title", "description", "url", "loadedUrl"))
    for vin in extract_vins(f"{blob} {url}"):
        if vin not in have:
            records.append({"vin": vin, "listing_url": url, "source_url": url, "source": "item-text"})
            have.add(vin)

    # absolute last resort: scan the whole item
    if not records:
        for vin in vins_from_any(item):
            records.append({"vin": vin, "listing_url": url, "source_url": url, "source": "item-any"})
    return records
