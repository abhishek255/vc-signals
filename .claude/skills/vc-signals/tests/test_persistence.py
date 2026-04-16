"""Tests for the persistence module."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


def test_save_briefing_creates_json(data_dir, sample_themes):
    from persistence import save_briefing

    result = save_briefing(
        sector="devtools",
        themes=sample_themes,
        retrieval_path="websearch",
        date="2026-04-09",
        data_dir=data_dir,
    )
    json_path = data_dir / "briefings" / "2026-04-09-devtools.json"
    assert json_path.exists()
    briefing = json.loads(json_path.read_text())
    assert briefing["date"] == "2026-04-09"
    assert briefing["sector"] == "devtools"
    assert briefing["retrieval_path"] == "websearch"
    assert len(briefing["themes"]) == 2
    assert result["saved"] == str(json_path)


def test_load_briefing_returns_data(data_dir, sample_themes):
    from persistence import load_briefing, save_briefing

    save_briefing("devtools", sample_themes, "websearch", "2026-04-09", data_dir)
    result = load_briefing("devtools", "2026-04-09", data_dir)
    assert result is not None
    assert result["sector"] == "devtools"
    assert len(result["themes"]) == 2


def test_load_briefing_missing_returns_none(data_dir):
    from persistence import load_briefing

    result = load_briefing("devtools", "2099-01-01", data_dir)
    assert result is None


def test_load_previous_finds_earlier(data_dir, sample_themes):
    from persistence import load_previous_briefing, save_briefing

    save_briefing("devtools", sample_themes, "websearch", "2026-04-02", data_dir)
    save_briefing("devtools", sample_themes, "websearch", "2026-04-09", data_dir)
    result = load_previous_briefing("devtools", before_date="2026-04-09", data_dir=data_dir)
    assert result is not None
    assert result["date"] == "2026-04-02"


def test_load_previous_no_earlier_returns_none(data_dir, sample_themes):
    from persistence import load_previous_briefing, save_briefing

    save_briefing("devtools", sample_themes, "websearch", "2026-04-09", data_dir)
    result = load_previous_briefing("devtools", before_date="2026-04-01", data_dir=data_dir)
    assert result is None


def test_compute_diff_new_themes(data_dir):
    from persistence import compute_diff

    previous = {
        "date": "2026-04-02",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 6},
        ],
    }
    current = {
        "date": "2026-04-09",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 7},
            {"name": "Rust Build Tools", "momentum": 5},
        ],
    }
    diff = compute_diff(current, previous)
    assert diff["previous_date"] == "2026-04-02"
    new_names = [t["name"] for t in diff["new_themes"]]
    assert "Rust Build Tools" in new_names


def test_compute_diff_fading_themes():
    from persistence import compute_diff

    previous = {
        "date": "2026-04-02",
        "sector": "devtools",
        "themes": [
            {"name": "WebAssembly Runtimes", "momentum": 7},
            {"name": "AI Code Review", "momentum": 6},
        ],
    }
    current = {
        "date": "2026-04-09",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 7},
        ],
    }
    diff = compute_diff(current, previous)
    fading_names = [t["name"] for t in diff["fading_themes"]]
    assert "WebAssembly Runtimes" in fading_names


def test_compute_diff_accelerating_themes():
    from persistence import compute_diff

    previous = {
        "date": "2026-04-02",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 5},
        ],
    }
    current = {
        "date": "2026-04-09",
        "sector": "devtools",
        "themes": [
            {"name": "AI Code Review", "momentum": 8},
        ],
    }
    diff = compute_diff(current, previous)
    accel_names = [t["name"] for t in diff["accelerating_themes"]]
    assert "AI Code Review" in accel_names


def test_update_theme_index_new_theme(data_dir, sample_themes):
    from persistence import update_theme_index

    index = update_theme_index(sample_themes, "devtools", "2026-04-09", data_dir)
    assert "AI-Powered Code Review" in index
    entry = index["AI-Powered Code Review"]
    assert entry["first_seen"] == "2026-04-09"
    assert entry["last_seen"] == "2026-04-09"
    assert entry["appearances"] == 1
    assert entry["momentum_history"] == [8]
    assert entry["peak_momentum"] == 8


def test_update_theme_index_existing_theme(data_dir, sample_themes):
    from persistence import update_theme_index

    update_theme_index(sample_themes, "devtools", "2026-04-02", data_dir)
    updated_themes = [{"name": "AI-Powered Code Review", "momentum": 9}]
    index = update_theme_index(updated_themes, "devtools", "2026-04-09", data_dir)
    entry = index["AI-Powered Code Review"]
    assert entry["first_seen"] == "2026-04-02"
    assert entry["last_seen"] == "2026-04-09"
    assert entry["appearances"] == 2
    assert entry["momentum_history"] == [8, 9]
    assert entry["peak_momentum"] == 9


def test_save_markdown(data_dir):
    from persistence import save_markdown

    content = "# Test Briefing\n\nSome content here."
    result = save_markdown("themes", "agent-evals", content, "2026-04-09", data_dir)
    md_path = data_dir / "themes" / "2026-04-09-agent-evals.md"
    assert md_path.exists()
    assert md_path.read_text() == content
    assert result["saved"] == str(md_path)


def test_validate_date_accepts_iso_date():
    from persistence import _validate_date
    _validate_date("2026-04-16", "date")  # should not raise


def test_validate_date_rejects_path_traversal():
    from persistence import _validate_date

    with pytest.raises(SystemExit):
        _validate_date("../../etc/passwd", "date")


def test_validate_date_rejects_wrong_format():
    from persistence import _validate_date

    for bad in ["2026/04/16", "20260416", "April 16", ""]:
        with pytest.raises(SystemExit):
            _validate_date(bad, "date")


def test_cli_load_briefing_rejects_traversal_date(data_dir):
    script = Path(__file__).parent.parent / "scripts" / "persistence.py"
    result = subprocess.run(
        ["python3", str(script), "load-briefing",
         "--sector", "devtools",
         "--date", "../../etc/passwd",
         "--data-dir", str(data_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Invalid date" in result.stdout


def test_normalize_company_name_lowercases():
    from persistence import _normalize_company_name
    assert _normalize_company_name("MintMCP") == "mintmcp"


def test_normalize_company_name_strips_legal_suffix():
    from persistence import _normalize_company_name
    assert _normalize_company_name("Anthropic, Inc.") == "anthropic"
    assert _normalize_company_name("Datadog Inc") == "datadog"
    assert _normalize_company_name("Acme Corp.") == "acme"
    assert _normalize_company_name("Foo LLC") == "foo"


def test_normalize_company_name_strips_parenthetical():
    from persistence import _normalize_company_name
    assert _normalize_company_name("Anysphere (Cursor)") == "anysphere"


def test_normalize_company_name_strips_domain_suffix():
    from persistence import _normalize_company_name
    assert _normalize_company_name("Vercel.com") == "vercel"
    assert _normalize_company_name("baserock.ai") == "baserock"


def test_normalize_company_name_collapses_whitespace():
    from persistence import _normalize_company_name
    assert _normalize_company_name("  Grafana   Labs  ") == "grafana labs"
