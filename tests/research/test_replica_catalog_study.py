"""Tests for the replica-catalog study pipeline (fixtures only, no network)."""

from __future__ import annotations

import gzip
import json

import pytest

from research.replica_catalog_study import analyze, parse
from research.replica_catalog_study import attributes as attr
from research.replica_catalog_study.crawl import (
    catalog_url,
    discover_last_page,
    extract_product_links,
)
from research.replica_catalog_study.sanitize import contains_excluded_content, scrub_text

LISTING_HTML = """
<html><body>
<div id="productsListingTopNumber">Displaying <strong>1</strong> to <strong>10</strong>
 (of <strong>17,842</strong> products)</div>
<table class="productListing">
 <tr class="productListing-odd">
  <td><a href="index.php?main_page=product_info&products_id=101"><img src="x.jpg"></a></td>
  <td><a href="index.php?main_page=product_info&products_id=101">Rolex Submariner Date
   116610LN 40mm Black Dial Ceramic Bezel 904L SS Oyster Bracelet A3135 Automatic</a></td>
  <td class="productListing-data">$438.00</td>
 </tr>
 <tr class="productListing-even">
  <td><a href="index.php?main_page=product_info&products_id=102">Patek Philippe Nautilus
   5711/1A 40mm Blue Dial SS Bracelet Cal.324SC Super Clone</a></td>
  <td class="productListing-data">$668.00</td>
 </tr>
 <tr class="productListing-odd">
  <td><a href="index.php?main_page=product_info&products_id=103">Cartier Tank Must
   Quartz White Roman Dial Leather Strap Ladies 29mm</a></td>
  <td class="productListing-data">$258.00</td>
 </tr>
</table>
<div id="productsListingListingBottomLinks">
 <a href="index.php?main_page=products_all&page=2">2</a>
 <a href="index.php?main_page=products_all&page=3">3</a>
 <a href="index.php?main_page=products_all&page=1785">1785</a>
 <a href="index.php?main_page=products_all&page=2">[Next&nbsp;&gt;&gt;]</a>
</div>
</body></html>
"""

DETAIL_HTML = """
<html><body>
<h1 id="productName">Audemars Piguet Royal Oak 15500ST 41mm Blue Tapisserie Dial
 SS Bracelet Clone Cal.4302 Automatic</h1>
<div id="productPrices">US$758.00</div>
<div id="productDescription">
Case size: 41mm x 10.4mm thick. Stainless steel case, octagonal bezel.
Blue "Grande Tapisserie" dial with luminous baton markers, date at 3.
Contact us on WhatsApp +86 1234 567 8901 or sales@example.com for stock alerts.
Payment methods: Western Union, USDT. Free shipping via DHL within 7 days.
</div>
</body></html>
"""


# ---------------------------------------------------------------- crawl bits
def test_discover_last_page_from_links_and_count():
    assert discover_last_page(LISTING_HTML) == 1785


def test_discover_last_page_from_count_only():
    html = LISTING_HTML.replace("main_page=products_all&page", "main_page=nope&page")
    # 17842 products / 10 per page -> 1785 pages
    assert discover_last_page(html) == 1785


def test_catalog_url_page1_has_no_page_param():
    assert "&page=" not in catalog_url("https://example.test", 1)
    assert catalog_url("https://example.test", 7).endswith("page=7")


def test_extract_product_links():
    links = extract_product_links(LISTING_HTML, "https://example.test")
    assert set(links) == {"101", "102", "103"}
    assert links["101"].startswith("https://example.test/")


# ---------------------------------------------------------------- parsing
def test_parse_listing_page_entries():
    entries = parse.parse_listing_page(LISTING_HTML, page_number=1)
    by_id = {e["listing_id"]: e for e in entries}
    assert len(by_id) == 3
    assert "Submariner" in by_id["101"]["title"]
    assert "$438.00" in by_id["101"]["price_text"]
    assert by_id["103"]["source_page"] == 1


def test_parse_detail_page():
    detail = parse.parse_detail_page(DETAIL_HTML)
    assert "Royal Oak" in detail["title"]
    assert "758.00" in detail["price_text"]
    assert "Case size: 41mm" in detail["description"]


def test_build_record_full_pipeline():
    listing = {"listing_id": "104", "title": "", "price_text": "", "source_page": 42}
    detail = parse.parse_detail_page(DETAIL_HTML)
    rec = parse.build_record(listing, detail)
    assert rec.brand == "Audemars Piguet"
    assert rec.model_family == "Royal Oak"
    assert rec.case_diameter_mm == 41.0
    assert rec.case_thickness_mm == 10.4
    assert rec.case_shape == "octagonal"
    assert rec.case_material == "stainless steel"
    assert rec.dial_color == "blue"
    assert "tapisserie" in rec.dial_characteristics
    assert rec.movement_category == "automatic"
    assert "date" in rec.complications
    assert rec.price_usd == 758.00
    assert rec.source_page == 42
    # sanitization: no contact/payment/shipping content anywhere in the record
    dumped = json.dumps(rec.__dict__)
    for banned in ("WhatsApp", "example.com", "Western Union", "USDT", "DHL", "8901"):
        assert banned not in dumped


# ---------------------------------------------------------------- attributes
@pytest.mark.parametrize(
    ("title", "brand", "family"),
    [
        ("Omega Speedmaster Moonwatch 3861 42mm Hesalite", "Omega", "Speedmaster"),
        ("Richard Mille RM-011 Felipe Massa Flyback NTPT", "Richard Mille", "RM"),
        ("Tudor Black Bay 58 M79030N-0001 39mm", "Tudor", "Black Bay"),
        ("IWC Portugieser Chronograph IW371605 41mm Blue", "IWC", "Portugieser"),
        ("Panerai PAM01312 Luminor Marina 44mm", "Panerai", "Luminor"),
    ],
)
def test_brand_and_family(title, brand, family):
    got_brand = attr.extract_brand(title)
    assert got_brand == brand
    assert attr.extract_model_family(title, got_brand) == family


def test_rolex_1908_family_not_mistaken_for_year():
    text = "Rolex 1908 39mm White Dial Manual"
    brand = attr.extract_brand(text)
    assert attr.extract_model_family(text, brand) == "1908"
    assert attr.extract_listed_year(text) is None


def test_listed_year_requires_context():
    assert attr.extract_listed_year("Submariner 2020 release 41mm") == 2020
    assert attr.extract_listed_year("new 2023 model green dial") == 2023
    assert attr.extract_listed_year("ref 16610 no year here") is None


def test_diameter_and_thickness():
    assert attr.extract_diameter_mm("case size: 40mm") == 40.0
    assert attr.extract_diameter_mm("41 x 10.4mm") == 41.0
    assert attr.extract_diameter_mm("no size") is None
    assert attr.extract_diameter_mm("116610 90mm banner") is None  # implausible
    assert attr.extract_thickness_mm("thickness: 12.2mm") == 12.2
    assert attr.extract_thickness_mm("10.4mm thick") == 10.4


def test_case_shape_defaults():
    assert attr.extract_case_shape("Cartier Tank", "Cartier", "Tank") == "rectangular"
    assert attr.extract_case_shape("Rolex Submariner", "Rolex", "Submariner") == "round"
    assert attr.extract_case_shape("mystery watch", None, None) is None
    assert attr.extract_case_shape("tonneau shaped case", None, None) == "tonneau"


def test_movement_and_materials():
    cat, base = attr.extract_movement("SS case A3135 clone movement")
    assert (cat, base) == ("automatic", "clone of genuine caliber")
    cat, base = attr.extract_movement("quartz ladies watch")
    assert cat == "quartz"
    assert attr.extract_case_material("two-tone SS/gold wrapped") == "two-tone"
    assert attr.extract_case_material("904L stainless steel") == "stainless steel"
    assert attr.extract_case_material("Everose case") == "rose gold"


def test_complications_day_date_precedence():
    comps = attr.extract_complications("Day-Date 40 president")
    assert "day-date" in comps
    assert "date" not in comps


def test_price():
    assert attr.extract_price_usd("US$1,268.00 special") == 1268.0
    assert attr.extract_price_usd("no price") is None


# ---------------------------------------------------------------- sanitizer
def test_scrub_removes_contact_payment_shipping():
    dirty = (
        "Great watch. WhatsApp +86 138 0000 0000, email me at a@b.com. "
        "Payment methods: PayPal or bitcoin. Free shipping via EMS. Buy now! "
        "https://example.com/checkout"
    )
    clean = scrub_text(dirty)
    assert not contains_excluded_content(clean)
    for banned in ("WhatsApp", "a@b.com", "PayPal", "bitcoin", "EMS", "http", "0000"):
        assert banned not in clean
    assert "Great watch" in clean


def test_scrub_keeps_design_text():
    text = "Rolex Daytona 116500LN 40mm white panda dial ceramic bezel"
    assert scrub_text(text) == text


# ---------------------------------------------------------------- end-to-end
def test_parse_and_analyze_end_to_end(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    with gzip.open(raw / "listing_p00001.html.gz", "wt", encoding="utf-8") as fh:
        fh.write(LISTING_HTML)
    with gzip.open(raw / "product_101.html.gz", "wt", encoding="utf-8") as fh:
        fh.write(DETAIL_HTML)

    dataset_dir = tmp_path / "dataset"
    records = parse.run(raw_dir=raw, out_dir=dataset_dir)
    assert len(records) == 3
    assert (dataset_dir / "products.jsonl").exists()
    assert (dataset_dir / "products.csv").exists()

    # No URLs leak into the dataset.
    dataset_text = (dataset_dir / "products.jsonl").read_text(encoding="utf-8")
    assert "http" not in dataset_text
    assert "product_info" not in dataset_text

    loaded = analyze.load_records(dataset_dir)
    summary = analyze.summarize(loaded, out_dir=tmp_path / "analysis")
    assert summary["total_listings"] == 3
    assert (tmp_path / "analysis" / "report.md").exists()
    assert (tmp_path / "analysis" / "brands.csv").exists()
    report = (tmp_path / "analysis" / "report.md").read_text(encoding="utf-8")
    assert "Brand representation" in report
