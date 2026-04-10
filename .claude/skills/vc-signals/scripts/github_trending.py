#!/usr/bin/env python3
"""GitHub trending repos — search by sector keywords, compute star velocity."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "sectors.json"
GITHUB_API = "https://api.github.com"


def build_search_queries(sector: str, config_path: Path | None = None) -> list[str]:
    """Build GitHub search queries from sector taxonomy."""
    config_path = config_path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return []

    sectors = json.loads(config_path.read_text())
    if sector not in sectors:
        return []

    sector_data = sectors[sector]
    queries = []

    for _key, subcat in sector_data.get("subcategories", {}).items():
        aliases = subcat.get("aliases", [])
        for i in range(0, len(aliases), 2):
            chunk = aliases[i : i + 2]
            query_terms = " OR ".join(f'"{a}"' for a in chunk)
            queries.append(query_terms)

    return queries


def parse_repo_data(raw: dict) -> dict:
    """Parse a GitHub API repo object into our normalized format."""
    created = raw.get("created_at", "")
    age_days = 0
    if created:
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - created_dt).days
        except ValueError:
            pass

    return {
        "full_name": raw.get("full_name", ""),
        "description": raw.get("description", ""),
        "stars": raw.get("stargazers_count", 0),
        "forks": raw.get("forks_count", 0),
        "language": raw.get("language", ""),
        "created_at": created,
        "pushed_at": raw.get("pushed_at", ""),
        "url": raw.get("html_url", ""),
        "owner_name": raw.get("owner", {}).get("login", ""),
        "owner_type": raw.get("owner", {}).get("type", ""),
        "topics": raw.get("topics", []),
        "age_days": age_days,
    }


def calculate_velocity(
    star_timestamps: list[str], total_stars: int
) -> dict:
    """Calculate star velocity from timestamped stargazer data."""
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    stars_7d = 0
    stars_30d = 0

    for ts in star_timestamps:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt >= seven_days_ago:
                stars_7d += 1
            if dt >= thirty_days_ago:
                stars_30d += 1
        except ValueError:
            continue

    # stars_last_7d / total_stars — higher = faster relative growth
    acceleration_ratio = stars_7d / total_stars if total_stars > 0 else 0.0

    return {
        "stars_last_7d": stars_7d,
        "stars_last_30d": stars_30d,
        "acceleration_ratio": acceleration_ratio,
        "method": "stargazer_timestamps",
    }


def estimate_velocity_fallback(total_stars: int, age_days: int) -> dict:
    """Estimate velocity from total stars and repo age when timestamps unavailable."""
    if age_days <= 0:
        age_days = 1
    daily_avg = total_stars / age_days
    return {
        "estimated_daily_avg": round(daily_avg, 2),
        "estimated_weekly_avg": round(daily_avg * 7, 2),
        "method": "fallback",
    }


def _get_token() -> str | None:
    """Resolve GitHub token: gh CLI first (keychain-backed), env var as fallback."""
    # Prefer gh CLI — uses system keychain, more secure
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # Fallback to env var
    return os.environ.get("GITHUB_TOKEN")


def search_repos(
    queries: list[str],
    token: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """Search GitHub repos using the search API. Returns parsed repo dicts."""
    if not HAS_REQUESTS:
        return []
    token = token or _get_token()
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    seen = set()
    results = []

    for query in queries:
        if len(results) >= limit:
            break

        six_months_ago = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%d")
        one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
        # Filter for repos created in the last year AND recently active — surfaces emerging projects
        full_query = f"{query} created:>{one_year_ago} pushed:>{six_months_ago} stars:>20"

        try:
            resp = requests.get(
                f"{GITHUB_API}/search/repositories",
                params={
                    "q": full_query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": min(30, limit - len(results)),
                },
                headers=headers,
                timeout=15,
            )
        except requests.RequestException as e:
            print(json.dumps({"warning": f"GitHub API error: {e}"}), file=sys.stderr)
            continue

        if resp.status_code == 403:
            remaining = resp.headers.get("X-RateLimit-Remaining", "?")
            print(
                json.dumps({"warning": f"GitHub rate limited. Remaining: {remaining}"}),
                file=sys.stderr,
            )
            break

        if resp.status_code != 200:
            continue

        for item in resp.json().get("items", []):
            name = item.get("full_name", "")
            if name not in seen:
                seen.add(name)
                results.append(parse_repo_data(item))

    return results[:limit]


def fetch_star_timestamps(
    full_name: str,
    token: str | None = None,
    sample_pages: int = 2,
) -> list[str]:
    """Fetch recent stargazer timestamps for a repo. Samples last N pages."""
    if not HAS_REQUESTS:
        return []
    token = token or _get_token()
    headers = {
        "Accept": "application/vnd.github.v3.star+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    timestamps = []

    try:
        resp = requests.get(
            f"{GITHUB_API}/repos/{full_name}/stargazers",
            params={"per_page": 1},
            headers=headers,
            timeout=10,
        )
    except requests.RequestException:
        return []

    if resp.status_code != 200:
        return []

    link_header = resp.headers.get("Link", "")
    last_page = 1
    parsed_last_page = False
    if 'rel="last"' in link_header:
        for part in link_header.split(","):
            if 'rel="last"' in part:
                try:
                    last_page = int(part.split("page=")[-1].split(">")[0])
                    parsed_last_page = True
                except (ValueError, IndexError):
                    pass
        # Only warn if Link header contained rel="last" but we failed to parse it
        if not parsed_last_page:
            print(
                json.dumps({"warning": f"Could not parse Link header for {full_name}; velocity data may be incomplete"}),
                file=sys.stderr,
            )

    # Convert last_page from per_page=1 pagination to per_page=100 pagination
    last_page_100 = math.ceil(last_page / 100)

    for page_num in range(max(1, last_page_100 - sample_pages + 1), last_page_100 + 1):
        try:
            page_resp = requests.get(
                f"{GITHUB_API}/repos/{full_name}/stargazers",
                params={"per_page": 100, "page": page_num},
                headers=headers,
                timeout=10,
            )
        except requests.RequestException:
            continue

        if page_resp.status_code != 200:
            continue

        for item in page_resp.json():
            if isinstance(item, dict) and "starred_at" in item:
                timestamps.append(item["starred_at"])

    return timestamps


def run_trending(
    sector: str,
    config_path: Path | None = None,
    token: str | None = None,
    limit: int = 15,
) -> dict:
    """Full pipeline: search repos for a sector, compute velocity, return ranked results."""
    if not HAS_REQUESTS:
        return {"error": "GitHub trending requires the 'requests' library. Run: pip install requests", "repos": [], "warnings": ["requests library not installed"]}
    config_path = config_path or DEFAULT_CONFIG_PATH
    queries = build_search_queries(sector, config_path)

    if not queries:
        return {"error": f"No queries for sector '{sector}'", "repos": []}

    repos = search_repos(queries, token=token, limit=limit * 2)
    warnings = []

    for repo in repos:
        timestamps = fetch_star_timestamps(repo["full_name"], token=token)
        if timestamps:
            repo["velocity"] = calculate_velocity(timestamps, repo["stars"])
        else:
            repo["velocity"] = estimate_velocity_fallback(repo["stars"], repo["age_days"])
            if repo["velocity"]["method"] == "fallback":
                warnings.append(f"Used fallback velocity for {repo['full_name']}")

    def sort_key(r):
        v = r.get("velocity", {})
        if v.get("method") == "stargazer_timestamps":
            return (v.get("stars_last_7d", 0), r.get("stars", 0))
        return (v.get("estimated_weekly_avg", 0), r.get("stars", 0))

    repos.sort(key=sort_key, reverse=True)

    return {
        "sector": sector,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repos": repos[:limit],
        "warnings": warnings,
    }


def _cli_main() -> None:
    """CLI entry point."""
    if not HAS_REQUESTS:
        print(json.dumps({"error": "GitHub trending requires the 'requests' library. Run: pip install requests", "repos": []}))
        sys.exit(0)  # exit cleanly, not with error code
    args = _parse_cli_args(sys.argv[1:])

    sector = args.get("sector", "")
    config_path = Path(args["config"]) if "config" in args else None
    token = None
    try:
        limit = int(args.get("limit", "15"))
        if limit <= 0:
            limit = 15
    except ValueError:
        limit = 15

    if not sector:
        print(json.dumps({"error": "Usage: github_trending.py --sector <sector> [--config <path>] [--limit N]"}))
        sys.exit(1)

    result = run_trending(sector, config_path, token, limit)
    print(json.dumps(result, indent=2))


def _parse_cli_args(argv: list[str]) -> dict:
    """Parse --key value pairs."""
    result = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i][2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                result[key] = argv[i + 1]
                i += 2
            else:
                result[key] = "true"
                i += 1
        else:
            i += 1
    return result


if __name__ == "__main__":
    _cli_main()
