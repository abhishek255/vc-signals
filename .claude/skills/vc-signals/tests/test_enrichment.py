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
