# Replica-Watch Catalog Study

Research pipeline for studying **which genuine luxury-watch designs the replica
market replicates**, based on the publicly visible `products_all` listing
catalog of one replica marketplace (~18,000 listings, ~10 per paginated page).

## Research questions

- Which genuine brands and model families are replicated, and in what proportions?
- Case-size and case-shape distributions.
- Dial color / design-characteristic trends.
- Complication representation.
- Movement-category composition.
- Price distribution as a market-structure signal (aggregate only).

## Scope and exclusions (deliberate)

This is a design-representation study, **not** a shopping resource. The
pipeline does not collect, and the sanitizer (`sanitize.py`) actively scrubs:

- WhatsApp/phone numbers, email addresses, and any dealer contact information
- payment, checkout, and shipping instructions
- stock alerts and purchase calls-to-action
- product URLs (kept only inside the temporary raw corpus, for crawling detail
  pages; never written to the dataset or report)

The outputs contain no seller rankings, dealer comparisons, or purchasing
recommendations.

## Pipeline

```
1. Crawl    python -m research.replica_catalog_study.crawl listings
            python -m research.replica_catalog_study.crawl details [--sample N]
2. Parse    python -m research.replica_catalog_study.parse
3. Analyze  python -m research.replica_catalog_study.analyze
```

Dependencies: `pip install httpx beautifulsoup4 lxml` (or `pip install -e .[research]`).

### Crawl behavior

- **Polite**: ~1 request / 2.5 s with jitter (`--delay` can raise it; it cannot
  be set below 1 s), single connection, exponential-backoff retries, honors
  `Retry-After` on 429/503, checks `robots.txt` before starting.
- **Auto pagination discovery**: the final page is inferred from the site's own
  "Displaying X to Y (of Z products)" counter and the highest `page=` link, and
  re-checked on every fetched page rather than assumed. A `max_pages` safety
  valve prevents unbounded crawls.
- **Resumable**: raw pages are stored gzipped under `data/raw/` and re-runs skip
  what is already present.
- Listing pages alone (~1,800 requests, ≈ 1.5 h at the default rate) yield
  titles + prices, from which most schema fields parse. The optional detail
  crawl (~18,000 requests, ≈ 15 h) adds thickness and other spec-sheet fields;
  `--sample N` supports a statistically adequate random sample instead of a
  full detail crawl.

### Raw corpus is temporary

`data/` is gitignored. `data/raw/` is a temporary working corpus and can be
deleted once `data/dataset/` and `data/analysis/` are produced.

## Dataset schema (`data/dataset/products.jsonl` / `.csv`)

`listing_id` (internal numeric key for dedup), `source_page`, `title`
(sanitized), `brand`, `model_family`, `reference`, `listed_year`,
`case_diameter_mm`, `case_thickness_mm`, `case_shape`, `case_material`,
`dial_color`, `dial_characteristics[]`, `movement_category`, `movement_base`,
`complications[]`, `bracelet_type`, `price_usd`, `has_detail_page`.

Fields are extracted from listing titles and (when crawled) detail
descriptions by the rule lexicons in `attributes.py`. Extraction is
conservative: a field is `null` rather than guessed (e.g. a non-round case
shape requires positive evidence).

## Analysis outputs (`data/analysis/`)

Per-dimension distribution CSVs (brands, model families, shapes, materials,
dial colors and characteristics, complications, movements, bracelets, diameter
buckets, per-brand diameter medians, listed years when present), a
`summary.json`, and a human-readable `report.md`.

## Known limitations

- Attribute coverage depends on how much sellers pack into titles; the
  per-field coverage percentages in `summary.json` quantify this.
- "Historical change" can only be inferred from explicit year mentions
  (rare) or repeated crawls over time; a single crawl is a snapshot.
- Reference-number extraction is heuristic and should be treated as claimed,
  not verified.

## Note on network policy

Claude Code remote sessions run behind an egress allowlist; this marketplace
domain is blocked there, so the crawl step must run from an environment with
ordinary network access (e.g. locally). Parse/analyze steps run anywhere.
