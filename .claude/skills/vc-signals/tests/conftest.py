"""Shared fixtures for vc-signals tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add scripts/ to import path
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory matching the expected structure."""
    for subdir in ("briefings", "themes", "companies", "github", "history"):
        (tmp_path / subdir).mkdir()
    return tmp_path


@pytest.fixture
def sample_themes() -> list[dict]:
    """Sample theme list for testing."""
    return [
        {
            "name": "AI-Powered Code Review",
            "momentum": 8,
            "confidence": "high",
            "timing": "mid",
            "hype_vs_durable": "durable",
            "companies": [
                {"name": "CodeRabbit", "role": "direct_solver", "confidence": "confirmed"}
            ],
            "evidence_summary": "Multiple HN threads, Reddit discussions, and blog posts about AI code review tools.",
        },
        {
            "name": "Rust-Based Build Tools",
            "momentum": 5,
            "confidence": "medium",
            "timing": "early",
            "hype_vs_durable": "durable",
            "companies": [
                {"name": "Turbopack", "role": "direct_solver", "confidence": "likely"}
            ],
            "evidence_summary": "Growing discussion about Rust rewrites of JS toolchain.",
        },
    ]


@pytest.fixture
def sample_companies() -> list[dict]:
    """Sample company list (post-flip schema) for testing."""
    return [
        {
            "name": "MintMCP",
            "primary_theme": "MCP Agent Infrastructure",
            "secondary_themes": [],
            "tag": None,
            "why_on_radar": "First SOC2-compliant MCP gateway",
            "evidence_url": "https://example.com/mintmcp",
            "stage": None,
            "raised": None,
            "headcount": None,
            "founders": None,
        },
        {
            "name": "CodeRabbit",
            "primary_theme": "AI-Powered Code Review",
            "secondary_themes": ["Agentic Coding Tools"],
            "tag": None,
            "why_on_radar": "2M repos, 13M PRs reviewed",
            "evidence_url": "https://example.com/coderabbit",
            "stage": None,
            "raised": None,
            "headcount": None,
            "founders": None,
        },
    ]


@pytest.fixture
def sample_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory with sectors.json."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    sectors = {
        "devtools": {
            "display_name": "Developer Tools",
            "subcategories": {
                "ci_cd": {
                    "name": "CI/CD & Build Systems",
                    "aliases": ["continuous integration", "build pipelines", "GitHub Actions"],
                    "seed_queries": ["new CI/CD tools developers switching to"],
                }
            },
            "discovery_queries": ["emerging developer tools 2026"],
            "negative_terms": ["tutorial", "beginner guide"],
        }
    }
    (config_dir / "sectors.json").write_text(json.dumps(sectors, indent=2))
    return config_dir
