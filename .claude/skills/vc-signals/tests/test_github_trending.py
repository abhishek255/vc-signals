"""Tests for the GitHub trending module."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_build_search_queries_from_taxonomy(sample_config_dir):
    from github_trending import build_search_queries

    queries = build_search_queries("devtools", sample_config_dir / "sectors.json")
    assert len(queries) > 0
    combined = " ".join(queries)
    assert "continuous integration" in combined.lower() or "ci/cd" in combined.lower() or "build pipelines" in combined.lower()


def test_build_search_queries_unknown_sector(sample_config_dir):
    from github_trending import build_search_queries

    queries = build_search_queries("nonexistent", sample_config_dir / "sectors.json")
    assert queries == []


def test_parse_repo_data():
    from github_trending import parse_repo_data

    raw = {
        "full_name": "vercel/turbo",
        "description": "Incremental bundler and build system",
        "stargazers_count": 25000,
        "forks_count": 1700,
        "language": "Rust",
        "created_at": "2021-06-15T00:00:00Z",
        "pushed_at": "2026-04-08T12:00:00Z",
        "html_url": "https://github.com/vercel/turbo",
        "owner": {"login": "vercel", "type": "Organization"},
        "topics": ["build-tool", "monorepo"],
    }
    parsed = parse_repo_data(raw)
    assert parsed["full_name"] == "vercel/turbo"
    assert parsed["stars"] == 25000
    assert parsed["language"] == "Rust"
    assert parsed["owner_name"] == "vercel"
    assert parsed["owner_type"] == "Organization"
    assert "age_days" in parsed
    assert parsed["age_days"] > 0


def test_calculate_velocity_with_timestamps():
    from github_trending import calculate_velocity

    now = datetime.now(timezone.utc)
    timestamps = []
    for i in range(50):
        timestamps.append((now - timedelta(days=i % 7)).isoformat())
    for i in range(30):
        timestamps.append((now - timedelta(days=8 + i % 22)).isoformat())

    velocity = calculate_velocity(timestamps, total_stars=5000)
    assert velocity["stars_last_7d"] == 50
    assert velocity["stars_last_30d"] == 80
    assert velocity["weekly_velocity"] == pytest.approx(50 / 5000, abs=0.001)


def test_calculate_velocity_empty():
    from github_trending import calculate_velocity

    velocity = calculate_velocity([], total_stars=100)
    assert velocity["stars_last_7d"] == 0
    assert velocity["stars_last_30d"] == 0


def test_estimate_velocity_fallback():
    from github_trending import estimate_velocity_fallback

    result = estimate_velocity_fallback(total_stars=3650, age_days=365)
    assert result["estimated_daily_avg"] == pytest.approx(10.0, abs=0.1)
    assert result["estimated_weekly_avg"] == pytest.approx(70.0, abs=1.0)
    assert result["method"] == "fallback"


@patch("github_trending.requests.get")
def test_search_repos_success(mock_get, sample_config_dir):
    from github_trending import search_repos

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {
                "full_name": "test/repo",
                "description": "A test repo",
                "stargazers_count": 1000,
                "forks_count": 100,
                "language": "Python",
                "created_at": "2025-01-01T00:00:00Z",
                "pushed_at": "2026-04-08T00:00:00Z",
                "html_url": "https://github.com/test/repo",
                "owner": {"login": "test", "type": "User"},
                "topics": [],
            }
        ]
    }
    mock_response.headers = {"X-RateLimit-Remaining": "29"}
    mock_get.return_value = mock_response

    repos = search_repos(["test query"], token="fake-token", limit=10)
    assert len(repos) == 1
    assert repos[0]["full_name"] == "test/repo"


@patch("github_trending.requests.get")
def test_search_repos_rate_limited(mock_get, sample_config_dir):
    from github_trending import search_repos

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"message": "API rate limit exceeded"}
    mock_response.headers = {"X-RateLimit-Remaining": "0"}
    mock_get.return_value = mock_response

    repos = search_repos(["test query"], token="fake-token", limit=10)
    assert repos == []
