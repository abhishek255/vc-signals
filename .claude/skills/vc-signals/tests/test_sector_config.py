"""Tests for the VC Signals sector taxonomy."""

from __future__ import annotations

import json
from pathlib import Path


def _load_sectors() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "sectors.json"
    return json.loads(config_path.read_text())


def test_marathon_priority_sectors_are_configured():
    sectors = _load_sectors()

    assert {"devtools", "cybersecurity", "ai-infra", "vertical-ai", "data-infra", "oss"} <= set(sectors)


def test_each_sector_has_required_discovery_fields():
    sectors = _load_sectors()

    for slug, sector in sectors.items():
        assert sector["display_name"], slug
        assert sector["subreddits"], slug
        assert sector["hn_queries"], slug
        assert sector["subcategories"], slug
        assert sector["discovery_queries"], slug
        assert "negative_terms" in sector, slug


def test_oss_sector_has_oss_specific_signal_rules():
    sectors = _load_sectors()

    oss = sectors["oss"]
    assert "star_velocity" in oss["ranking_signals"]
    assert "contributor_quality" in oss["ranking_signals"]
    assert "company_formation_probability" in oss["ranking_signals"]
    assert oss["actions"] == [
        "watch",
        "contact maintainer",
        "map ecosystem",
        "track company formation",
        "ignore",
    ]
