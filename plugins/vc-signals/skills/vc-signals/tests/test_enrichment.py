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


# --- Task 3: update_enrichment ---

def test_update_enrichment_creates_entry_with_fetched_at():
    from datetime import date
    from enrichment import update_enrichment
    cache = {}
    update_enrichment(cache, "Acme", {"stage": "Seed"}, now=date(2026, 5, 3))
    assert cache == {"acme": {"fetched_at": "2026-05-03", "stage": "Seed"}}


def test_update_enrichment_merges_preserving_old_fields():
    from datetime import date
    from enrichment import update_enrichment
    cache = {"acme": {"fetched_at": "2026-04-01", "stage": "Seed", "raised": "$2M"}}
    update_enrichment(cache, "Acme", {"headcount": "12"}, now=date(2026, 5, 3))
    assert cache["acme"] == {
        "fetched_at": "2026-05-03",
        "stage": "Seed",
        "raised": "$2M",
        "headcount": "12",
    }


def test_update_enrichment_normalized_name_dedup():
    """Display variants resolve to one cache key."""
    from datetime import date
    from enrichment import update_enrichment
    cache = {}
    update_enrichment(cache, "Anysphere (Cursor)", {"stage": "Series A"}, now=date(2026, 5, 3))
    update_enrichment(cache, "Anysphere", {"raised": "$60M"}, now=date(2026, 5, 3))
    assert list(cache.keys()) == ["anysphere"]
    assert cache["anysphere"]["stage"] == "Series A"
    assert cache["anysphere"]["raised"] == "$60M"


def test_update_enrichment_rejects_unknown_fields():
    from enrichment import update_enrichment
    with pytest.raises(ValueError, match="unknown"):
        update_enrichment({}, "Acme", {"ceo_pet": "dog"})


def test_update_enrichment_overwrites_existing_field():
    from datetime import date
    from enrichment import update_enrichment
    cache = {"acme": {"fetched_at": "2026-04-01", "stage": "Seed"}}
    update_enrichment(cache, "Acme", {"stage": "Series A"}, now=date(2026, 5, 3))
    assert cache["acme"]["stage"] == "Series A"


# --- Task 4: merge_into_company ---

def test_merge_into_company_applies_cached_fields():
    from enrichment import merge_into_company
    cache = {"acme": {"fetched_at": "2026-05-03", "stage": "Series A", "raised": "$15M"}}
    company = {"name": "Acme", "stage": None, "raised": None, "headcount": None}
    out = merge_into_company(company, cache)
    assert out["stage"] == "Series A"
    assert out["raised"] == "$15M"


def test_merge_into_company_uses_normalized_lookup():
    from enrichment import merge_into_company
    cache = {"anysphere": {"fetched_at": "2026-05-03", "stage": "Series C"}}
    company = {"name": "Anysphere (Cursor)", "stage": None}
    out = merge_into_company(company, cache)
    assert out["stage"] == "Series C"


def test_merge_into_company_does_not_overwrite_truthy():
    """Claude's inferences (truthy existing values) win over cache."""
    from enrichment import merge_into_company
    cache = {"acme": {"fetched_at": "2026-05-03", "stage": "Series A", "raised": "$15M"}}
    company = {"name": "Acme", "stage": "Seed", "raised": None}
    out = merge_into_company(company, cache)
    assert out["stage"] == "Seed"  # preserved
    assert out["raised"] == "$15M"  # filled from cache


def test_merge_into_company_no_cache_entry_keeps_nulls():
    from enrichment import merge_into_company
    company = {"name": "Unknown", "stage": None, "raised": None}
    out = merge_into_company(company, {})
    assert out == company


def test_merge_into_company_does_not_mutate_input():
    from enrichment import merge_into_company
    cache = {"acme": {"fetched_at": "2026-05-03", "stage": "Series A"}}
    company = {"name": "Acme", "stage": None}
    merge_into_company(company, cache)
    assert company["stage"] is None


def test_update_enrichment_merges_evidence_dict():
    from datetime import date
    from enrichment import update_enrichment
    cache = {"acme": {
        "fetched_at": "2026-04-01",
        "stage": "Seed",
        "evidence": {"stage": "https://old.example.com"},
    }}
    update_enrichment(
        cache, "Acme", {"raised": "$10M"},
        evidence={"raised": "https://tc.example.com"},
        now=date(2026, 5, 3),
    )
    assert cache["acme"]["evidence"] == {
        "stage": "https://old.example.com",
        "raised": "https://tc.example.com",
    }


# --- Task 5: CLI commands ---

def _run_enrichment_cli(args, *, stdin: str | None = None):
    script = Path(__file__).parent.parent / "scripts" / "enrichment.py"
    return subprocess.run(
        ["python3", str(script), *args],
        input=stdin,
        capture_output=True,
        text=True,
    )


def test_cli_load_cache_empty(data_dir):
    result = _run_enrichment_cli(["load-cache", "--data-dir", str(data_dir)])
    assert result.returncode == 0
    assert json.loads(result.stdout) == {}


def test_cli_update_creates_entry(data_dir):
    payload = {"name": "Acme", "fields": {"stage": "Seed"}}
    result = _run_enrichment_cli(
        ["update", "--date", "2026-05-03", "--data-dir", str(data_dir)],
        stdin=json.dumps(payload),
    )
    assert result.returncode == 0
    body = json.loads(result.stdout)
    assert body["updated"] == "acme"
    assert body["entry"]["stage"] == "Seed"
    assert body["entry"]["fetched_at"] == "2026-05-03"


def test_cli_update_with_evidence(data_dir):
    payload = {
        "name": "Acme",
        "fields": {"raised": "$10M"},
        "evidence": {"raised": "https://techcrunch.com/acme"},
    }
    result = _run_enrichment_cli(
        ["update", "--date", "2026-05-03", "--data-dir", str(data_dir)],
        stdin=json.dumps(payload),
    )
    assert result.returncode == 0
    body = json.loads(result.stdout)
    assert body["entry"]["evidence"]["raised"] == "https://techcrunch.com/acme"


def test_cli_update_rejects_unknown_field(data_dir):
    payload = {"name": "Acme", "fields": {"ceo_pet": "dog"}}
    result = _run_enrichment_cli(
        ["update", "--data-dir", str(data_dir)],
        stdin=json.dumps(payload),
    )
    assert result.returncode == 0
    assert "unknown" in json.loads(result.stdout)["error"]


def test_cli_merge_applies_fields(data_dir):
    update_payload = {"name": "Acme", "fields": {"stage": "Series A"}}
    _run_enrichment_cli(
        ["update", "--date", "2026-05-03", "--data-dir", str(data_dir)],
        stdin=json.dumps(update_payload),
    )

    merge_payload = {"companies": [{"name": "Acme", "stage": None}]}
    result = _run_enrichment_cli(
        ["merge", "--data-dir", str(data_dir)],
        stdin=json.dumps(merge_payload),
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["companies"][0]["stage"] == "Series A"


def test_cli_malformed_stdin_returns_structured_error(data_dir):
    result = _run_enrichment_cli(
        ["merge", "--data-dir", str(data_dir)],
        stdin="not json{",
    )
    assert result.returncode == 0
    assert "error" in json.loads(result.stdout)


def test_cli_unknown_command_returns_error(data_dir):
    result = _run_enrichment_cli(["bogus", "--data-dir", str(data_dir)])
    assert result.returncode == 0
    assert json.loads(result.stdout)["error"] == "Unknown command: bogus"
