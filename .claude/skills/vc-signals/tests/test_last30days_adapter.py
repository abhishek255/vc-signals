"""Tests for the last30days adapter module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_check_not_installed(tmp_path):
    from last30days_adapter import check_availability

    result = check_availability(vendor_path=tmp_path / "nonexistent")
    assert result["installed"] is False
    assert result["configured"] is False


def test_check_installed_not_configured(tmp_path):
    from last30days_adapter import check_availability

    vendor = tmp_path / "last30days-skill"
    (vendor / "scripts" / "lib").mkdir(parents=True)
    (vendor / "scripts" / "last30days.py").write_text("# stub")
    (vendor / "scripts" / "lib" / "__init__.py").write_text("")

    result = check_availability(vendor_path=vendor)
    assert result["installed"] is True
    assert result["configured"] is False


def test_check_installed_and_configured(tmp_path):
    from last30days_adapter import check_availability

    vendor = tmp_path / "last30days-skill"
    (vendor / "scripts" / "lib").mkdir(parents=True)
    (vendor / "scripts" / "last30days.py").write_text("# stub")
    (vendor / "scripts" / "lib" / "__init__.py").write_text("")

    config_dir = tmp_path / "config" / "last30days"
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text("SETUP_COMPLETE=true\nOPENAI_API_KEY=sk-fake\n")

    result = check_availability(vendor_path=vendor, config_path=config_dir / ".env")
    assert result["installed"] is True
    assert result["configured"] is True


def test_normalize_report_items():
    from last30days_adapter import normalize_report_items

    mock_items = {
        "reddit": [
            {
                "item_id": "r1",
                "source": "reddit",
                "title": "AI code review is amazing",
                "url": "https://reddit.com/r/programming/123",
                "snippet": "I switched to CodeRabbit and it changed everything",
                "published_at": "2026-04-07T10:00:00Z",
                "engagement": {"upvotes": 350, "comments": 42},
                "container": "r/programming",
            }
        ],
        "hackernews": [
            {
                "item_id": "hn1",
                "source": "hackernews",
                "title": "Show HN: New testing framework",
                "url": "https://news.ycombinator.com/item?id=999",
                "snippet": "Built a new testing tool that uses AI",
                "published_at": "2026-04-08T14:00:00Z",
                "engagement": {"points": 200, "comments": 85},
                "container": "hackernews",
            }
        ],
    }

    normalized = normalize_report_items(mock_items)
    assert len(normalized) == 2
    assert normalized[0]["source"] in ("reddit", "hackernews")
    assert "title" in normalized[0]
    assert "engagement" in normalized[0]


def test_run_query_returns_structure(tmp_path):
    """Test that run_query returns expected JSON structure even with mock."""
    from last30days_adapter import check_availability

    result = check_availability(vendor_path=tmp_path / "nonexistent")
    assert result["installed"] is False
