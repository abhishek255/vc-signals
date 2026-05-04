"""Tests for the enrichment cache module."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


# --- Task 1: load/save ---

def test_load_enrichment_cache_missing_returns_empty(data_dir):
    from enrichment import load_enrichment_cache
    assert load_enrichment_cache(data_dir) == {}


def test_load_enrichment_cache_malformed_returns_empty(data_dir, capsys):
    from enrichment import load_enrichment_cache
    cache_path = data_dir / "companies" / "enrichment_cache.json"
    cache_path.write_text("not json{")
    assert load_enrichment_cache(data_dir) == {}
    captured = capsys.readouterr()
    assert "malformed" in captured.err.lower() or "warning" in captured.err.lower()


def test_save_and_load_enrichment_cache_roundtrip(data_dir, enriched_company):
    from enrichment import load_enrichment_cache, save_enrichment_cache
    cache = {"jane-co": enriched_company}
    save_enrichment_cache(cache, data_dir)
    loaded = load_enrichment_cache(data_dir)
    assert loaded == cache


def test_save_enrichment_cache_creates_directory(tmp_path, enriched_company):
    """Cache dir should be auto-created if missing."""
    from enrichment import save_enrichment_cache
    save_enrichment_cache({"x": enriched_company}, tmp_path)
    assert (tmp_path / "companies" / "enrichment_cache.json").exists()


# --- Task 2: TTL check ---

def test_is_cache_fresh_within_ttl():
    from datetime import date
    from enrichment import is_cache_fresh
    entry = {"fetched_at": "2026-05-01"}
    assert is_cache_fresh(entry, ttl_days=14, now=date(2026, 5, 10)) is True


def test_is_cache_fresh_at_boundary_inclusive():
    """Boundary (age == ttl_days) counts as fresh."""
    from datetime import date
    from enrichment import is_cache_fresh
    entry = {"fetched_at": "2026-04-19"}
    assert is_cache_fresh(entry, ttl_days=14, now=date(2026, 5, 3)) is True


def test_is_cache_fresh_beyond_ttl():
    from datetime import date
    from enrichment import is_cache_fresh
    entry = {"fetched_at": "2026-04-18"}
    assert is_cache_fresh(entry, ttl_days=14, now=date(2026, 5, 3)) is False


def test_is_cache_fresh_missing_fetched_at():
    from enrichment import is_cache_fresh
    assert is_cache_fresh({"stage": "Series A"}) is False


def test_is_cache_fresh_malformed_date():
    from enrichment import is_cache_fresh
    assert is_cache_fresh({"fetched_at": "yesterday"}) is False
