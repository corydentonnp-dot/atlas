"""Polite crawler for the public products_all catalog pages.

Usage:
    python -m research.replica_catalog_study.crawl listings
    python -m research.replica_catalog_study.crawl details [--sample N]

Behavior:
- Rate-limited (default ~1 request / 2.5s with jitter) with exponential-backoff
  retries; single connection; identifies itself with a stable User-Agent.
- Discovers the final listing page automatically from the site's own
  pagination ("Displaying X to Y (of Z products)" and the highest page= link),
  re-checking as it goes rather than assuming a fixed page count.
- Resumable: already-downloaded pages are skipped, so an interrupted crawl
  continues where it left off.
- Stores raw HTML gzipped under data/raw/ (a temporary corpus, gitignored).
  Product URLs live only in the raw-corpus manifest for crawling detail pages;
  they are never copied into the research dataset.
- Checks robots.txt first and refuses paths disallowed for '*' unless
  --ignore-robots is passed explicitly.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import random
import re
import sys
import time
import urllib.parse
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from .config import CATALOG_QUERY, CrawlConfig

log = logging.getLogger("replica_study.crawl")

DISPLAYING_RE = re.compile(
    r"displaying\s+\d+\s+to\s+(\d+)\s+\(of\s+([\d,]+)\s+products?\)", re.IGNORECASE
)


class PoliteFetcher:
    def __init__(self, cfg: CrawlConfig):
        self.cfg = cfg
        self.client = httpx.Client(
            headers={"User-Agent": cfg.user_agent, "Accept-Language": "en"},
            timeout=cfg.timeout_seconds,
            follow_redirects=True,
        )
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        wait = self.cfg.delay_seconds + random.uniform(0, self.cfg.jitter_seconds)
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < wait:
            time.sleep(wait - elapsed)
        self._last_request_at = time.monotonic()

    def get(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(self.cfg.max_retries + 1):
            self._throttle()
            try:
                resp = self.client.get(url)
                if resp.status_code in (429, 503):
                    retry_after = float(resp.headers.get("Retry-After", 0) or 0)
                    delay = max(retry_after, self.cfg.backoff_base_seconds * 2**attempt)
                    log.warning("HTTP %s on %s; backing off %.0fs", resp.status_code, url, delay)
                    time.sleep(delay)
                    continue
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPError as exc:
                last_error = exc
                delay = self.cfg.backoff_base_seconds * 2**attempt
                log.warning("fetch failed (%s); retry in %.0fs", exc, delay)
                time.sleep(delay)
        raise RuntimeError(f"giving up on {url}: {last_error}")

    def close(self) -> None:
        self.client.close()


def robots_allows(fetcher: PoliteFetcher, base_url: str, path: str) -> bool:
    """Minimal robots.txt check for User-agent: * disallow rules."""
    try:
        text = fetcher.get(urllib.parse.urljoin(base_url, "/robots.txt"))
    except RuntimeError:
        return True  # no robots.txt reachable -> proceed politely
    applies = False
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            applies = value == "*"
        elif key == "disallow" and applies and value and path.startswith(value):
            return False
    return True


def catalog_url(base_url: str, page: int) -> str:
    query = dict(CATALOG_QUERY)
    if page > 1:
        query["page"] = str(page)
    return f"{base_url}/index.php?{urllib.parse.urlencode(query)}"


def discover_last_page(html: str, per_page_hint: int = 10) -> int | None:
    """Infer the final page number from pagination markup and result counts."""
    soup = BeautifulSoup(html, "lxml")
    best = 0
    for a in soup.find_all("a", href=True):
        parsed = urllib.parse.urlparse(a["href"])
        params = urllib.parse.parse_qs(parsed.query)
        if params.get("main_page", [""])[0] == "products_all" and "page" in params:
            try:
                best = max(best, int(params["page"][0]))
            except ValueError:
                continue
    m = DISPLAYING_RE.search(soup.get_text(" ", strip=True))
    if m:
        shown_to = int(m.group(1))
        total = int(m.group(2).replace(",", ""))
        per_page = shown_to if shown_to > 0 else per_page_hint
        best = max(best, -(-total // per_page))
    return best or None


def listing_path(raw_dir: Path, page: int) -> Path:
    return raw_dir / f"listing_p{page:05d}.html.gz"


def save_raw(path: Path, url: str, html: str, manifest: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(html)
    with manifest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"file": path.name, "url": url, "fetched_at": time.time()}) + "\n")


def crawl_listings(cfg: CrawlConfig, ignore_robots: bool = False) -> None:
    fetcher = PoliteFetcher(cfg)
    manifest = cfg.raw_dir / "manifest.jsonl"
    try:
        if not ignore_robots and not robots_allows(fetcher, cfg.base_url, "/index.php"):
            log.error("robots.txt disallows /index.php for '*'; aborting (see --ignore-robots)")
            sys.exit(2)

        page, last_page = 1, None
        while last_page is None or page <= min(last_page, cfg.max_pages):
            path = listing_path(cfg.raw_dir, page)
            if path.exists():
                if last_page is None:
                    with gzip.open(path, "rt", encoding="utf-8") as fh:
                        last_page = discover_last_page(fh.read())
            else:
                url = catalog_url(cfg.base_url, page)
                log.info("fetching listing page %d%s", page,
                         f" of {last_page}" if last_page else "")
                html = fetcher.get(url)
                save_raw(path, url, html, manifest)
                discovered = discover_last_page(html)
                if discovered:
                    last_page = discovered  # keep re-checking; catalogs shift under you
            page += 1
        log.info("listing crawl complete: %d pages", (last_page or page - 1))
    finally:
        fetcher.close()


PRODUCT_ID_RE = re.compile(r"products_id=(\d+)")


def extract_product_links(html: str, base_url: str) -> dict[str, str]:
    """Map products_id -> absolute product_info URL (raw corpus use only)."""
    soup = BeautifulSoup(html, "lxml")
    links: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        m = PRODUCT_ID_RE.search(a["href"])
        if m and "product_info" in a["href"]:
            links[m.group(1)] = urllib.parse.urljoin(base_url, a["href"])
    return links


def crawl_details(cfg: CrawlConfig, sample: int | None = None,
                  ignore_robots: bool = False) -> None:
    listing_files = sorted(cfg.raw_dir.glob("listing_p*.html.gz"))
    if not listing_files:
        log.error("no listing pages downloaded yet; run the 'listings' step first")
        sys.exit(2)

    all_links: dict[str, str] = {}
    for lf in listing_files:
        with gzip.open(lf, "rt", encoding="utf-8") as fh:
            all_links.update(extract_product_links(fh.read(), cfg.base_url))
    log.info("discovered %d unique products across %d listing pages",
             len(all_links), len(listing_files))

    items = sorted(all_links.items(), key=lambda kv: int(kv[0]))
    if sample:
        items = random.sample(items, min(sample, len(items)))

    fetcher = PoliteFetcher(cfg)
    manifest = cfg.raw_dir / "manifest.jsonl"
    try:
        if not ignore_robots and not robots_allows(fetcher, cfg.base_url, "/index.php"):
            log.error("robots.txt disallows /index.php for '*'; aborting")
            sys.exit(2)
        remaining = [(pid, url) for pid, url in items
                     if not (cfg.raw_dir / f"product_{pid}.html.gz").exists()]
        log.info("%d detail pages to fetch (%d already present)",
                 len(remaining), len(items) - len(remaining))
        for i, (pid, url) in enumerate(remaining, 1):
            html = fetcher.get(url)
            save_raw(cfg.raw_dir / f"product_{pid}.html.gz", url, html, manifest)
            if i % 100 == 0:
                log.info("detail progress: %d/%d", i, len(remaining))
    finally:
        fetcher.close()


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=["listings", "details"])
    parser.add_argument("--sample", type=int, default=None,
                        help="details: crawl a random sample of N products instead of all")
    parser.add_argument("--delay", type=float, default=None, help="seconds between requests")
    parser.add_argument("--ignore-robots", action="store_true")
    args = parser.parse_args(argv)

    cfg = CrawlConfig()
    if args.delay is not None:
        cfg.delay_seconds = max(args.delay, 1.0)  # never below 1s

    if args.step == "listings":
        crawl_listings(cfg, ignore_robots=args.ignore_robots)
    else:
        crawl_details(cfg, sample=args.sample, ignore_robots=args.ignore_robots)


if __name__ == "__main__":
    main()
