"""Parser must extract VINs from every common dealer-page pattern, merged."""
from coveragex.extract import parse_apify_item, parse_vehicle_listings_from_html

V_JSONLD = "1HGCM82633A004352"   # JSON-LD Vehicle
V_DATAVIN = "1FTFW1ET5DFC10312"  # data-vin card on the SRP
V_SCRIPT = "5YJ3E1EA7KF000316"   # embedded JS inventory payload  ("vin": "...")
V_URL = "WBA3A5C50CF000000"      # VIN in the page URL
V_TEXT = "JH4KA8270MC000000"     # visible "VIN: ..." text

HTML = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Vehicle",
 "vehicleIdentificationNumber":"1HGCM82633A004352","brand":{"name":"Honda"},
 "model":"Accord","vehicleModelDate":"2017",
 "mileageFromOdometer":{"value":"96000","unitCode":"SMI"},
 "offers":{"@type":"Offer","price":"24995","priceCurrency":"USD"}}
</script>
</head><body>
<section class="srp">
  <article data-vin="1FTFW1ET5DFC10312">2013 Ford F-150 - 88,000 miles - $31,500</article>
</section>
<script>window.__INVENTORY__ = {"results":[{"vin":"5YJ3E1EA7KF000316","price":28000}]};</script>
<p>Certified pre-owned. VIN: JH4KA8270MC000000 in stock now.</p>
</body></html>
"""
URL = "https://dealer.example/used/2014-bmw-3-series-WBA3A5C50CF000000/"


def test_all_patterns_extracted_and_merged():
    recs = parse_vehicle_listings_from_html(HTML, URL)
    vins = {r["vin"] for r in recs}
    assert {V_JSONLD, V_DATAVIN, V_SCRIPT, V_URL, V_TEXT} <= vins


def test_jsonld_fields_populated():
    recs = {r["vin"]: r for r in parse_vehicle_listings_from_html(HTML, URL)}
    j = recs[V_JSONLD]
    assert j["make"] == "Honda" and j["model"] == "Accord"
    assert j["year"] == 2017 and j["mileage"] == 96000 and j["price"] == 24995


def test_datavin_card_gets_mileage_price():
    recs = {r["vin"]: r for r in parse_vehicle_listings_from_html(HTML, URL)}
    card = recs[V_DATAVIN]
    assert card["mileage"] == 88000
    assert card["price"] == 31500


def test_jsonld_graph_form():
    html = ('<script type="application/ld+json">'
            '{"@graph":[{"@type":"Vehicle","vin":"5YJ3E1EA7KF000316","model":"Model 3"}]}'
            '</script>')
    vins = {r["vin"] for r in parse_vehicle_listings_from_html(html, "")}
    assert V_SCRIPT in vins


def test_parse_apify_item_html_shape():
    vins = {r["vin"] for r in parse_apify_item({"url": URL, "html": HTML})}
    assert {V_JSONLD, V_DATAVIN, V_SCRIPT, V_URL, V_TEXT} <= vins


def test_parse_apify_item_text_only_fallback():
    item = {"url": "https://d.example/x", "text": f"Great deal. VIN {V_SCRIPT} here.", "html": ""}
    vins = {r["vin"] for r in parse_apify_item(item)}
    assert V_SCRIPT in vins


def test_no_vin_yields_nothing():
    assert parse_vehicle_listings_from_html("<html><body>no vehicles</body></html>", "") == []
