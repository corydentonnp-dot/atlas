"""Aggregate analysis over the sanitized dataset.

Usage:
    python -m research.replica_catalog_study.analyze

Reads data/dataset/products.jsonl and writes per-dimension CSVs plus a
markdown research report under data/analysis/. All outputs are aggregates
about design representation — no listings, URLs, or seller information.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from .config import ANALYSIS_DIR, DATASET_DIR

log = logging.getLogger("replica_study.analyze")

DIAMETER_BUCKETS = [(0, 34), (34, 36), (36, 38), (38, 40), (40, 42), (42, 44),
                    (44, 46), (46, 60)]


def load_records(dataset_dir: Path = DATASET_DIR) -> list[dict]:
    path = dataset_dir / "products.jsonl"
    if not path.exists():
        raise SystemExit(f"{path} not found; run the parse step first")
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_counter_csv(path: Path, counter: Counter, key_name: str, total: int) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([key_name, "count", "share_pct"])
        for key, count in counter.most_common():
            writer.writerow([key, count, round(100 * count / total, 2) if total else 0])


def bucket_label(lo: int, hi: int) -> str:
    if lo == 0:
        return f"<{hi}mm"
    if hi >= 60:
        return f">={lo}mm"
    return f"{lo}-{hi}mm"


def summarize(records: list[dict], out_dir: Path = ANALYSIS_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(records)

    brand_counts = Counter(r["brand"] or "(unidentified)" for r in records)
    family_counts = Counter(
        f"{r['brand']} {r['model_family']}"
        for r in records if r["brand"] and r["model_family"]
    )
    shape_counts = Counter(r["case_shape"] for r in records if r["case_shape"])
    material_counts = Counter(r["case_material"] for r in records if r["case_material"])
    dial_color_counts = Counter(r["dial_color"] for r in records if r["dial_color"])
    dial_char_counts = Counter(c for r in records for c in r["dial_characteristics"])
    complication_counts = Counter(c for r in records for c in r["complications"])
    movement_counts = Counter(r["movement_category"] for r in records if r["movement_category"])
    movement_base_counts = Counter(r["movement_base"] for r in records if r["movement_base"])
    bracelet_counts = Counter(r["bracelet_type"] for r in records if r["bracelet_type"])
    year_counts = Counter(r["listed_year"] for r in records if r["listed_year"])

    diameters = [r["case_diameter_mm"] for r in records if r["case_diameter_mm"]]
    diameter_buckets = Counter()
    for d in diameters:
        for lo, hi in DIAMETER_BUCKETS:
            if lo <= d < hi:
                diameter_buckets[bucket_label(lo, hi)] += 1
                break

    prices = [r["price_usd"] for r in records if r["price_usd"]]

    write_counter_csv(out_dir / "brands.csv", brand_counts, "brand", total)
    write_counter_csv(out_dir / "model_families.csv", family_counts, "model_family",
                      sum(family_counts.values()))
    write_counter_csv(out_dir / "case_shapes.csv", shape_counts, "case_shape",
                      sum(shape_counts.values()))
    write_counter_csv(out_dir / "case_materials.csv", material_counts, "case_material",
                      sum(material_counts.values()))
    write_counter_csv(out_dir / "dial_colors.csv", dial_color_counts, "dial_color",
                      sum(dial_color_counts.values()))
    write_counter_csv(out_dir / "dial_characteristics.csv", dial_char_counts,
                      "dial_characteristic", total)
    write_counter_csv(out_dir / "complications.csv", complication_counts, "complication", total)
    write_counter_csv(out_dir / "movements.csv", movement_counts, "movement_category",
                      sum(movement_counts.values()))
    write_counter_csv(out_dir / "movement_bases.csv", movement_base_counts, "movement_base",
                      sum(movement_base_counts.values()))
    write_counter_csv(out_dir / "bracelets.csv", bracelet_counts, "bracelet_type",
                      sum(bracelet_counts.values()))
    write_counter_csv(out_dir / "diameter_buckets.csv", diameter_buckets, "diameter_bucket",
                      len(diameters))
    if year_counts:
        write_counter_csv(out_dir / "listed_years.csv", year_counts, "listed_year",
                          sum(year_counts.values()))

    # Per-brand diameter medians (design-preference signal by brand).
    by_brand_diam: dict[str, list[float]] = defaultdict(list)
    for r in records:
        if r["brand"] and r["case_diameter_mm"]:
            by_brand_diam[r["brand"]].append(r["case_diameter_mm"])
    with (out_dir / "diameter_by_brand.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["brand", "n", "median_mm", "min_mm", "max_mm"])
        for brand, vals in sorted(by_brand_diam.items(), key=lambda kv: -len(kv[1])):
            writer.writerow([brand, len(vals), round(statistics.median(vals), 1),
                             min(vals), max(vals)])

    summary = {
        "total_listings": total,
        "identified_brand_pct": round(
            100 * sum(1 for r in records if r["brand"]) / total, 1) if total else 0,
        "with_diameter_pct": round(100 * len(diameters) / total, 1) if total else 0,
        "with_detail_page_pct": round(
            100 * sum(1 for r in records if r["has_detail_page"]) / total, 1) if total else 0,
        "diameter_median_mm": round(statistics.median(diameters), 1) if diameters else None,
        "price_median_usd": round(statistics.median(prices), 2) if prices else None,
        "price_quartiles_usd": (
            [round(q, 2) for q in statistics.quantiles(prices, n=4)] if len(prices) >= 4 else None
        ),
        "top_brands": brand_counts.most_common(15),
        "top_families": family_counts.most_common(20),
        "shapes": shape_counts.most_common(),
        "movements": movement_counts.most_common(),
        "top_complications": complication_counts.most_common(10),
        "top_dial_colors": dial_color_counts.most_common(10),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_report(summary, out_dir / "report.md")
    log.info("analysis written to %s", out_dir)
    return summary


def _table(rows: list[tuple], headers: tuple[str, ...], total: int | None = None) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    for key, count in rows:
        share = f" | {100 * count / total:.1f}%" if total else ""
        lines.append(f"| {key} | {count}{share} |")
    return "\n".join(lines)


def write_report(summary: dict, path: Path) -> None:
    total = summary["total_listings"]
    parts = [
        "# Replica-Market Design Representation: Catalog Analysis",
        "",
        "Aggregate analysis of a public replica-watch catalog. This report describes",
        "*which genuine designs the replica market chooses to copy* — brand and model",
        "representation, case geometry, dial and complication trends. It contains no",
        "listings, links, sellers, or purchasing information.",
        "",
        f"- Listings analyzed: **{total}**",
        f"- Brand identified: {summary['identified_brand_pct']}%",
        f"- Case diameter extracted: {summary['with_diameter_pct']}%"
        f" (median {summary['diameter_median_mm']} mm)",
        "",
        "## Brand representation",
        _table(summary["top_brands"], ("Brand", "Listings", "Share"), total),
        "",
        "## Most-replicated model families",
        _table(summary["top_families"], ("Model family", "Listings")),
        "",
        "## Case shapes",
        _table(summary["shapes"], ("Shape", "Listings")),
        "",
        "## Movement categories",
        _table(summary["movements"], ("Movement", "Listings")),
        "",
        "## Complications",
        _table(summary["top_complications"], ("Complication", "Listings"), total),
        "",
        "## Dial colors",
        _table(summary["top_dial_colors"], ("Dial color", "Listings")),
        "",
        "_See the CSV files in this directory for full distributions, including",
        "diameter buckets, per-brand diameter medians, materials, bracelet types,",
        "and dial characteristics._",
    ]
    path.write_text("\n".join(parts), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    summarize(load_records())


if __name__ == "__main__":
    main()
