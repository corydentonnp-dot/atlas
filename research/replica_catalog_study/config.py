"""Configuration for the replica-catalog study pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parent
DATA_DIR = STUDY_DIR / "data"
RAW_DIR = DATA_DIR / "raw"  # gitignored: raw HTML corpus (temporary, deletable)
DATASET_DIR = DATA_DIR / "dataset"  # sanitized research dataset (no URLs, no contact info)
ANALYSIS_DIR = DATA_DIR / "analysis"  # aggregate outputs + report

BASE_URL = "https://trustytime168.io"
CATALOG_PATH = "/index.php"
CATALOG_QUERY = {"main_page": "products_all"}

# Politeness settings. One request roughly every DELAY_SECONDS (+/- JITTER).
DELAY_SECONDS = 2.5
JITTER_SECONDS = 1.0
TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 4
BACKOFF_BASE_SECONDS = 2.0  # 2s, 4s, 8s, 16s

USER_AGENT = (
    "Mozilla/5.0 (compatible; academic-catalog-research/0.1; polite crawl, rate-limited)"
)


@dataclass
class CrawlConfig:
    base_url: str = BASE_URL
    delay_seconds: float = DELAY_SECONDS
    jitter_seconds: float = JITTER_SECONDS
    timeout_seconds: float = TIMEOUT_SECONDS
    max_retries: int = MAX_RETRIES
    backoff_base_seconds: float = BACKOFF_BASE_SECONDS
    user_agent: str = USER_AGENT
    raw_dir: Path = field(default_factory=lambda: RAW_DIR)
    # Safety valve so a bad pagination parse can never turn into an unbounded crawl.
    max_pages: int = 5000
