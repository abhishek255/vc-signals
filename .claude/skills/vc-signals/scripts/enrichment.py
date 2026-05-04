#!/usr/bin/env python3
"""Enrichment cache for VC Signals — funding, headcount, founders, etc.

The cache is keyed by `_normalize_company_name` so display variants
("Anysphere (Cursor)" vs "anysphere") resolve to the same entry. Each
entry has a flat schema with `fetched_at` (ISO date) and the enriched
fields. Field absence = "researched, not found" (or never researched).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Re-use the existing normalizer from persistence
sys.path.insert(0, str(Path(__file__).parent))
from persistence import _normalize_company_name  # noqa: E402

DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_TTL_DAYS = 14
ENRICHED_FIELDS = (
    "stage",
    "raised",
    "headcount",
    "founders",
    "founding_year",
    "lead_investor",
    "founder_github_activity",
)


def _cache_path(data_dir: Path) -> Path:
    return data_dir / "companies" / "enrichment_cache.json"


def load_enrichment_cache(data_dir: Path | None = None) -> dict:
    """Load the enrichment cache. Returns {} if missing or malformed."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    path = _cache_path(data_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        print(f"Warning: malformed JSON in {path}, starting empty", file=sys.stderr)
        return {}


def save_enrichment_cache(cache: dict, data_dir: Path | None = None) -> None:
    """Persist the enrichment cache to disk, creating dirs as needed."""
    data_dir = data_dir or DEFAULT_DATA_DIR
    path = _cache_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2))
