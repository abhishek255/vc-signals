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
    assert velocity["acceleration_ratio"] == pytest.approx(50 / 5000, abs=0.001)


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


def test_build_search_queries_all_sector(sample_config_dir):
    """`all` should aggregate queries across every sector in the config."""
    from github_trending import build_search_queries

    cfg = json.loads((sample_config_dir / "sectors.json").read_text())
    cfg["cybersecurity"] = {
        "display_name": "Cybersecurity",
        "subcategories": {
            "appsec": {
                "name": "AppSec",
                "aliases": ["SAST", "DAST"],
                "seed_queries": ["application security tools"],
            }
        },
        "discovery_queries": [],
        "negative_terms": [],
    }
    (sample_config_dir / "sectors.json").write_text(json.dumps(cfg))

    queries = build_search_queries("all", sample_config_dir / "sectors.json")
    combined = " ".join(queries).lower()
    assert "continuous integration" in combined or "github actions" in combined
    assert "sast" in combined or "dast" in combined


def test_run_trending_all_sector_dedupes(monkeypatch, sample_config_dir):
    """When repos appear in queries across sectors, the final list must dedupe."""
    from github_trending import run_trending, parse_repo_data

    fake_repo = {
        "full_name": "shared/repo",
        "description": "",
        "stargazers_count": 100,
        "forks_count": 0,
        "language": "Go",
        "created_at": "2025-01-01T00:00:00Z",
        "pushed_at": "2026-04-01T00:00:00Z",
        "html_url": "https://github.com/shared/repo",
        "owner": {"login": "shared", "type": "Organization"},
        "topics": [],
    }

    def fake_search(queries, token=None, limit=30):
        return [parse_repo_data(fake_repo)]

    def fake_timestamps(*a, **kw):
        return []

    monkeypatch.setattr("github_trending.search_repos", fake_search)
    monkeypatch.setattr("github_trending.fetch_star_timestamps", fake_timestamps)

    result = run_trending("all", config_path=sample_config_dir / "sectors.json", token="x", limit=10)
    assert result["sector"] == "all"
    full_names = [r["full_name"] for r in result["repos"]]
    assert full_names.count("shared/repo") == 1


def _raise_filenotfound(*a, **kw):
    raise FileNotFoundError("gh")


def test_get_token_falls_back_to_env_file(tmp_path, monkeypatch):
    """When gh CLI and GITHUB_TOKEN env var are both absent, read .env."""
    from github_trending import _get_token

    env_file = tmp_path / ".env"
    env_file.write_text("SETUP_COMPLETE=true\nGITHUB_TOKEN=ghp_fromenvfile\n")

    monkeypatch.setattr("github_trending.subprocess.run", _raise_filenotfound)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    assert _get_token(env_path=env_file) == "ghp_fromenvfile"


def test_get_token_prefers_env_var_over_env_file(tmp_path, monkeypatch):
    from github_trending import _get_token

    env_file = tmp_path / ".env"
    env_file.write_text("GITHUB_TOKEN=ghp_fromfile\n")

    monkeypatch.setattr("github_trending.subprocess.run", _raise_filenotfound)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fromenvvar")

    assert _get_token(env_path=env_file) == "ghp_fromenvvar"


def test_get_token_returns_none_when_no_source(tmp_path, monkeypatch):
    from github_trending import _get_token

    monkeypatch.setattr("github_trending.subprocess.run", _raise_filenotfound)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert _get_token(env_path=tmp_path / "nonexistent") is None


def test_get_token_handles_quoted_value(tmp_path, monkeypatch):
    """Setup wizard may write quoted values; parser must strip quotes."""
    from github_trending import _get_token

    env_file = tmp_path / ".env"
    env_file.write_text('GITHUB_TOKEN="ghp_quoted"\n')
    monkeypatch.setattr("github_trending.subprocess.run", _raise_filenotfound)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    assert _get_token(env_path=env_file) == "ghp_quoted"


# --- fetch_star_timestamps ---

def _stargazer_response(stars: list[str], headers: dict | None = None, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = [{"starred_at": s} for s in stars]
    resp.headers = headers or {}
    return resp


@patch("github_trending.requests.get")
def test_fetch_star_timestamps_no_link_header_uses_page_one(mock_get):
    """When the Link header is absent, the function uses last_page=1 (single page)."""
    from github_trending import fetch_star_timestamps

    probe = _stargazer_response(["2026-04-01T00:00:00Z"])  # per_page=1 probe
    page = _stargazer_response(["2026-04-01T00:00:00Z", "2026-04-02T00:00:00Z"])
    mock_get.side_effect = [probe, page]

    timestamps = fetch_star_timestamps("owner/repo", token="x")
    assert timestamps == ["2026-04-01T00:00:00Z", "2026-04-02T00:00:00Z"]


@patch("github_trending.requests.get")
def test_fetch_star_timestamps_with_last_link_paginates(mock_get):
    """A Link header with rel=\"last\" should drive pagination by 100s."""
    from github_trending import fetch_star_timestamps

    # Probe response says last per_page=1 page is 250 → last per_page=100 page is 3.
    # With sample_pages=2, we fetch pages 2 and 3.
    link = '<https://api.github.com/repos/o/r/stargazers?page=2>; rel="next", <https://api.github.com/repos/o/r/stargazers?page=250>; rel="last"'
    probe = _stargazer_response(["2026-01-01T00:00:00Z"], headers={"Link": link})
    page2 = _stargazer_response(["2026-03-01T00:00:00Z"])
    page3 = _stargazer_response(["2026-04-01T00:00:00Z"])
    mock_get.side_effect = [probe, page2, page3]

    timestamps = fetch_star_timestamps("o/r", token="x")
    assert "2026-03-01T00:00:00Z" in timestamps
    assert "2026-04-01T00:00:00Z" in timestamps
    # Probe stargazer is NOT in the result (sampled pages don't include page 1
    # when last_page > sample_pages).


@patch("github_trending.requests.get")
def test_fetch_star_timestamps_unparseable_link_warns(mock_get, capsys):
    """Malformed Link header should still proceed (not crash) and emit a warning."""
    from github_trending import fetch_star_timestamps

    probe = _stargazer_response(
        ["2026-04-01T00:00:00Z"],
        headers={"Link": '<bogus>; rel="last"'},  # no page= parameter
    )
    page = _stargazer_response(["2026-04-01T00:00:00Z"])
    mock_get.side_effect = [probe, page]

    timestamps = fetch_star_timestamps("o/r", token="x")
    assert timestamps == ["2026-04-01T00:00:00Z"]
    captured = capsys.readouterr()
    assert "Could not parse" in captured.err or '"warning"' in captured.err


@patch("github_trending.requests.get")
def test_fetch_star_timestamps_404_returns_empty(mock_get):
    from github_trending import fetch_star_timestamps

    resp = MagicMock(status_code=404, headers={})
    resp.json.return_value = []
    mock_get.return_value = resp

    assert fetch_star_timestamps("o/missing", token="x") == []


@patch("github_trending.requests.get")
def test_fetch_star_timestamps_request_exception_returns_empty(mock_get):
    """Network errors must not propagate; return [] silently."""
    import requests
    from github_trending import fetch_star_timestamps

    mock_get.side_effect = requests.RequestException("boom")
    assert fetch_star_timestamps("o/r", token="x") == []


@patch("github_trending.requests.get")
def test_fetch_star_timestamps_skips_non_dict_items(mock_get):
    """Defensive: non-dict items in JSON response are silently skipped."""
    from github_trending import fetch_star_timestamps

    probe = _stargazer_response([])
    page_resp = MagicMock(status_code=200)
    page_resp.json.return_value = [
        "not_a_dict",
        {"starred_at": "2026-04-01T00:00:00Z"},
        {"no_starred_at": True},
    ]
    page_resp.headers = {}
    mock_get.side_effect = [probe, page_resp]

    timestamps = fetch_star_timestamps("o/r", token="x")
    assert timestamps == ["2026-04-01T00:00:00Z"]
