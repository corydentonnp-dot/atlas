"""Parse the raw HTML corpus into the sanitized research dataset.

Usage:
    python -m research.replica_catalog_study.parse

Reads data/raw/listing_p*.html.gz (and product_*.html.gz detail pages when
present), extracts the research schema, scrubs any contact/commerce text, and
writes data/dataset/products.jsonl + products.csv. Product URLs are never
written to the dataset; the internal numeric listing id is kept only as a
deduplication key.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup

from . import attributes as attr
from .config import DATASET_DIR, RAW_DIR
from .sanitize import scrub_text

log = logging.getLogger("replica_study.parse")

PRODUCT_ID_RE = re.compile(r"products_id=(\d+)")


@dataclass
class ProductRecord:
    listing_id: str
    source_page: int | None = None
    title: str = ""
    brand: str | None = None
    model_family: str | None = None
    reference: str | None = None
    listed_year: int | None = None
    case_diameter_mm: float | None = None
    case_thickness_mm: float | None = None
    case_shape: str | None = None
    case_material: str | None = None
    dial_color: str | None = None
    dial_characteristics: list[str] = field(default_factory=list)
    movement_category: str | None = None
    movement_base: str | None = None
    complications: list[str] = field(default_factory=list)
    bracelet_type: str | None = None
    price_usd: float | None = None
    has_detail_page: bool = False


def parse_listing_page(html: str, page_number: int) -> list[dict]:
    """Extract (listing_id, title, price_text) entries from one listing page."""
    soup = BeautifulSoup(html, "lxml")
    entries: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        if "product_info" not in a["href"]:
            continue
        m = PRODUCT_ID_RE.search(a["href"])
        if not m:
            continue
        pid = m.group(1)
        title = a.get_text(" ", strip=True)
        if not title:  # image-only anchor
            continue
        entry = entries.setdefault(pid, {"listing_id": pid, "title": title,
                                         "price_text": "", "source_page": page_number})
        if len(title) > len(entry["title"]):
            entry["title"] = title
        container = a.find_parent(["tr", "li"]) or a.find_parent("div")
        if container and not entry["price_text"]:
            text = container.get_text(" ", strip=True)
            if attr.PRICE_RE.search(text):
                entry["price_text"] = text
    return list(entries.values())


def parse_detail_page(html: str) -> dict:
    """Extract title/description/price text from a product_info page."""
    soup = BeautifulSoup(html, "lxml")
    for selector in ("script", "style", "form"):
        for tag in soup.find_all(selector):
            tag.decompose()

    title = ""
    for candidate in (soup.find(id="productName"), soup.find("h1"), soup.find("h2")):
        if candidate and candidate.get_text(strip=True):
            title = candidate.get_text(" ", strip=True)
            break

    desc_node = soup.find(id="productDescription") or soup.find(class_="description")
    description = desc_node.get_text("\n", strip=True) if desc_node else ""
    if not description:
        # Fallback: main content text minus obvious navigation.
        main = soup.find(id="productGeneral") or soup.body or soup
        description = main.get_text("\n", strip=True)[:4000]

    price_node = soup.find(id="productPrices") or soup.find(class_="productGeneral")
    price_text = price_node.get_text(" ", strip=True) if price_node else ""
    if not attr.PRICE_RE.search(price_text):
        m = attr.PRICE_RE.search(soup.get_text(" ", strip=True))
        price_text = m.group(0) if m else ""

    return {"title": title, "description": description, "price_text": price_text}


def build_record(listing: dict, detail: dict | None) -> ProductRecord:
    title = (detail or {}).get("title") or listing.get("title", "")
    description = (detail or {}).get("description", "")
    combined = f"{title}\n{description}"

    brand = attr.extract_brand(combined)
    family = attr.extract_model_family(combined, brand)
    movement_category, movement_base = attr.extract_movement(combined)
    price_text = (detail or {}).get("price_text") or listing.get("price_text", "")

    return ProductRecord(
        listing_id=listing["listing_id"],
        source_page=listing.get("source_page"),
        title=scrub_text(title),
        brand=brand,
        model_family=family,
        reference=attr.extract_reference(combined),
        listed_year=attr.extract_listed_year(combined),
        case_diameter_mm=attr.extract_diameter_mm(combined),
        case_thickness_mm=attr.extract_thickness_mm(combined),
        case_shape=attr.extract_case_shape(combined, brand, family),
        case_material=attr.extract_case_material(combined),
        dial_color=attr.extract_dial_color(combined),
        dial_characteristics=attr.extract_dial_characteristics(combined),
        movement_category=movement_category,
        movement_base=movement_base,
        complications=attr.extract_complications(combined),
        bracelet_type=attr.extract_bracelet_type(combined),
        price_usd=attr.extract_price_usd(price_text) or attr.extract_price_usd(combined),
        has_detail_page=detail is not None,
    )


def _page_number(path: Path) -> int:
    m = re.search(r"listing_p(\d+)", path.name)
    return int(m.group(1)) if m else 0


def run(raw_dir: Path = RAW_DIR, out_dir: Path = DATASET_DIR) -> list[ProductRecord]:
    listing_files = sorted(raw_dir.glob("listing_p*.html.gz"))
    if not listing_files:
        raise SystemExit(f"no raw listing pages found under {raw_dir}; crawl first")

    listings: dict[str, dict] = {}
    for lf in listing_files:
        with gzip.open(lf, "rt", encoding="utf-8") as fh:
            for entry in parse_listing_page(fh.read(), _page_number(lf)):
                listings.setdefault(entry["listing_id"], entry)
    log.info("parsed %d unique listings from %d pages", len(listings), len(listing_files))

    records: list[ProductRecord] = []
    for pid, listing in sorted(listings.items(), key=lambda kv: int(kv[0])):
        detail_file = raw_dir / f"product_{pid}.html.gz"
        detail = None
        if detail_file.exists():
            with gzip.open(detail_file, "rt", encoding="utf-8") as fh:
                detail = parse_detail_page(fh.read())
        records.append(build_record(listing, detail))

    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "products.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")

    csv_path = out_dir / "products.csv"
    fields = [f for f in asdict(records[0])] if records else []
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for rec in records:
            row = asdict(rec)
            row["dial_characteristics"] = "; ".join(row["dial_characteristics"])
            row["complications"] = "; ".join(row["complications"])
            writer.writerow(row)

    log.info("wrote %d records -> %s, %s", len(records), jsonl_path, csv_path)
    return records


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    run()


if __name__ == "__main__":
    main()
