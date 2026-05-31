#!/usr/bin/env python3
"""Public YC company directory adapter for official identity evidence."""

from __future__ import annotations

import json
import sys
import html
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests

    HAS_REQUESTS = True
except ImportError:  # pragma: no cover - damaged local installs
    requests = None
    HAS_REQUESTS = False


YC_COMPANIES_URL = "https://yc-oss.github.io/api/companies/all.json"
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_RECENT_BATCHES = (
    "Winter 2027",
    "Fall 2026",
    "Summer 2026",
    "Spring 2026",
    "Winter 2026",
    "Fall 2025",
    "Summer 2025",
    "Spring 2025",
    "Winter 2025",
    "Fall 2024",
    "Summer 2024",
)
DEFAULT_TERMS = (
    "ai",
    "agent",
    "developer",
    "devtools",
    "security",
    "cybersecurity",
    "infrastructure",
    "data",
    "automation",
    "analytics",
)


def parse_yc_company_page(html_text: str) -> dict:
    """Extract public company/founder detail from YC's Inertia data payload."""
    for match in re.finditer(r'data-page="(?P<payload>[^"]+)"', html_text or ""):
        raw_payload = html.unescape(match.group("payload"))
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            continue
        company = ((payload.get("props") or {}).get("company") or {})
        if not isinstance(company, dict) or not company:
            continue
        founder_profiles = []
        for founder in company.get("founders") or []:
            if not isinstance(founder, dict):
                continue
            name = _clean_text(founder.get("full_name") or founder.get("name"))
            role = _clean_text(founder.get("title") or founder.get("role"))
            linkedin = _clean_text(founder.get("linkedin_url") or founder.get("linkedin"))
            x_url = _clean_text(founder.get("twitter_url") or founder.get("x_url") or founder.get("x"))
            if name or linkedin or x_url:
                founder_profiles.append({"name": name, "role": role, "linkedin": linkedin, "x": x_url})
        return {
            "company_linkedin": _clean_text(company.get("linkedin_url")),
            "company_x": _clean_text(company.get("twitter_url")),
            "founding_year": _clean_text(company.get("year_founded")),
            "founder_profiles": founder_profiles,
        }
    return {}


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _launch_date(timestamp: object) -> str:
    if not timestamp:
        return ""
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _founder_profiles(row: dict) -> list[dict]:
    founders = row.get("founders") or row.get("founder_profiles") or []
    profiles: list[dict] = []
    if not isinstance(founders, list):
        return profiles
    for founder in founders:
        if isinstance(founder, str) and founder.strip():
            profiles.append({"name": founder.strip(), "linkedin": "", "x": ""})
        elif isinstance(founder, dict):
            name = _clean_text(founder.get("name") or founder.get("full_name"))
            role = _clean_text(founder.get("role") or founder.get("title"))
            linkedin = _clean_text(founder.get("linkedin") or founder.get("linkedin_url"))
            x_url = _clean_text(founder.get("x") or founder.get("x_url") or founder.get("twitter_url"))
            if name or linkedin or x_url:
                profiles.append({"name": name, "role": role, "linkedin": linkedin, "x": x_url})
    return profiles


def normalize_yc_company(row: dict) -> dict:
    """Normalize a YC public directory row into radar source evidence."""
    name = _clean_text(row.get("name"))
    yc_url = _clean_text(row.get("url")) or (
        f"https://www.ycombinator.com/companies/{row.get('slug')}" if row.get("slug") else ""
    )
    website = _clean_text(row.get("website"))
    domain = _domain_from_url(website)
    one_liner = _clean_text(row.get("one_liner"))
    description = _clean_text(row.get("long_description")) or one_liner
    team_size = row.get("team_size")
    stage = _clean_text(row.get("stage"))
    founders = _founder_profiles(row)
    evidence = {}
    if stage and yc_url:
        evidence["stage"] = yc_url
    if team_size not in ("", None) and yc_url:
        evidence["headcount"] = yc_url
    if founders and yc_url:
        evidence["founders"] = yc_url

    missing_evidence = []
    if not domain:
        missing_evidence.append("yc_official_website_missing")
    if not founders:
        missing_evidence.append("founder_team_missing_from_yc_public_api")
    missing_evidence.append("funding_round_missing_from_yc_public_api")

    company = {
        "source": "yc_directory",
        "source_lane": "YC Directory",
        "name": name,
        "company_name": name,
        "title": f"{name} | Y Combinator" if name else "Y Combinator company",
        "url": yc_url,
        "yc_url": yc_url,
        "website": website,
        "domain": domain,
        "tagline": one_liner,
        "description": description,
        "snippet": description,
        "batch": _clean_text(row.get("batch")),
        "stage": stage,
        "headcount": "" if team_size in ("", None) else str(team_size),
        "status": _clean_text(row.get("status")),
        "industry": _clean_text(row.get("industry")),
        "subindustry": _clean_text(row.get("subindustry")),
        "tags": list(row.get("tags") or []),
        "launched_at": row.get("launched_at") or "",
        "launch_date": _launch_date(row.get("launched_at")),
        "founder_profiles": founders,
        "founders": [profile["name"] for profile in founders if profile.get("name")],
        "founding_year": _clean_text(row.get("founding_year") or row.get("year_founded")),
        "company_linkedin": _clean_text(row.get("company_linkedin") or row.get("linkedin_url")),
        "company_x": _clean_text(row.get("company_x") or row.get("twitter_url")),
        "evidence": evidence,
        "action": "research deeper",
        "lead_route": "research_deeper",
        "missing_evidence": missing_evidence,
        "why_this_may_be_noise": (
            "YC public directory row; verify current activity, founders, funding, customers, "
            "and Marathon context before owner routing."
        ),
    }
    return company


def fetch_yc_companies(
    *,
    api_url: str = YC_COMPANIES_URL,
    timeout_seconds: int | None = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict]:
    if not HAS_REQUESTS:
        raise RuntimeError("requests unavailable")
    response = requests.get(
        api_url,
        timeout=timeout_seconds or DEFAULT_TIMEOUT_SECONDS,
        headers={"User-Agent": "vc-signals-yc-directory-adapter/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("YC directory response was not a list")
    return payload


def fetch_yc_company_detail(
    url: str,
    *,
    timeout_seconds: int | None = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    if not url or not HAS_REQUESTS:
        return {}
    response = requests.get(
        url,
        timeout=timeout_seconds or DEFAULT_TIMEOUT_SECONDS,
        headers={"User-Agent": "vc-signals-yc-directory-detail/1.0"},
    )
    response.raise_for_status()
    return parse_yc_company_page(response.text)


def _merge_yc_detail(row: dict, detail: dict) -> dict:
    if not detail:
        return row
    merged = dict(row)
    for key in ("company_linkedin", "company_x", "founding_year"):
        if detail.get(key):
            merged[key] = detail[key]
    if detail.get("founder_profiles"):
        merged["founder_profiles"] = detail["founder_profiles"]
        merged["founders"] = detail["founder_profiles"]
    return merged


def _matches_terms(row: dict, terms: tuple[str, ...]) -> bool:
    if not terms:
        return True
    haystack = " ".join(
        [
            _clean_text(row.get("name")),
            _clean_text(row.get("one_liner")),
            _clean_text(row.get("long_description")),
            _clean_text(row.get("industry")),
            _clean_text(row.get("subindustry")),
            " ".join(str(tag) for tag in row.get("tags") or []),
        ]
    ).lower()
    return any(term.lower() in haystack for term in terms)


def _matches_batches(row: dict, batches: tuple[str, ...]) -> bool:
    if not batches:
        return True
    return _clean_text(row.get("batch")) in set(batches)


def run_yc_directory(
    *,
    limit: int = 25,
    terms: tuple[str, ...] | None = DEFAULT_TERMS,
    batches: tuple[str, ...] | None = DEFAULT_RECENT_BATCHES,
    timeout_seconds: int | None = DEFAULT_TIMEOUT_SECONDS,
    api_url: str = YC_COMPANIES_URL,
    fetcher=fetch_yc_companies,
    detail_fetcher=fetch_yc_company_detail,
    detail_limit: int | None = None,
) -> dict:
    """Fetch and normalize YC public companies without scraping YC pages."""
    warnings: list[str] = []
    try:
        rows = fetcher(api_url=api_url, timeout_seconds=timeout_seconds)
        matched_rows = [
            row
            for row in rows
            if _matches_batches(row, tuple(batches or ())) and _matches_terms(row, tuple(terms or ()))
        ]
        enriched_rows = []
        max_details = limit if detail_limit is None else detail_limit
        for row in matched_rows[:limit]:
            detail = {}
            if detail_fetcher and max_details and len(enriched_rows) < max_details:
                try:
                    detail = detail_fetcher(row.get("url", ""), timeout_seconds=timeout_seconds)
                except Exception as exc:
                    warnings.append(f"{row.get('name', 'unknown')}: YC detail unavailable: {exc}")
            enriched_rows.append(_merge_yc_detail(row, detail))
        selected = [normalize_yc_company(row) for row in enriched_rows]
        selected = [
            company
            for company in selected
            if company.get("name") and company.get("status", "").lower() not in {"inactive", "acquired"}
        ][:limit]
        return {
            "companies": selected,
            "warnings": warnings,
            "source_meta": {
                "provider": "yc-oss public API",
                "endpoint": api_url,
                "official_source": "Y Combinator public company pages via yc-oss API",
                "terms": list(terms or ()),
                "batches": list(batches or ()),
            },
        }
    except Exception as exc:
        return {
            "companies": [],
            "warnings": [f"YC directory unavailable: {exc}"],
            "error": str(exc),
            "source_meta": {"provider": "yc-oss public API", "endpoint": api_url},
        }


def _parse_args(argv: list[str]) -> dict:
    args = {}
    index = 0
    while index < len(argv):
        if argv[index].startswith("--"):
            key = argv[index][2:].replace("-", "_")
            if index + 1 < len(argv) and not argv[index + 1].startswith("--"):
                args[key] = argv[index + 1]
                index += 2
            else:
                args[key] = True
                index += 1
        else:
            index += 1
    return args


def main() -> None:
    args = _parse_args(sys.argv[1:])
    terms = tuple(item.strip() for item in str(args.get("terms", ",".join(DEFAULT_TERMS))).split(",") if item.strip())
    batches = tuple(item.strip() for item in str(args.get("batches", ",".join(DEFAULT_RECENT_BATCHES))).split(",") if item.strip())
    result = run_yc_directory(
        limit=int(args.get("limit", 25)),
        terms=terms,
        batches=batches,
        timeout_seconds=int(args.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
