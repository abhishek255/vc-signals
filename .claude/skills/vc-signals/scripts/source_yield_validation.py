#!/usr/bin/env python3
"""Build a source-yield validation report and strict decision packet."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REVIEW_WORTHY_ACTIONS = {"research deeper", "contact maintainer", "watch"}
DEFAULT_ASSIGN_OWNER_ALLOWLIST = ("Voker",)
MARKET_SIGNAL_LIMIT = 5
EVIDENCE_GAP_LIMIT = 12
WATCHLIST_LIMIT = 12
DEFAULT_SOURCE_YIELD_TARGETS = {
    "assign_owner": {"min": 1, "max": 3, "allow_above_max": False},
    "review_worthy_companies": {"min": 5, "max": 15, "allow_above_max": True},
    "review_worthy_market_signals": {"min": 5, "max": 10, "allow_above_max": True},
    "evidence_gap_queue": {"min": 10, "max": 15, "allow_above_max": True},
    "unsafe_promotions": {"max": 0, "allow_above_max": False},
}


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _normalized_action(row: dict) -> str:
    return str(row.get("action") or row.get("recommended_action") or "").strip().lower()


def _row_name(row: dict) -> str:
    return str(row.get("name") or row.get("canonical_name") or row.get("display_name") or "").strip()


def _row_domain(row: dict) -> str:
    return str(row.get("domain") or row.get("company_domain") or row.get("candidate_domain") or "").strip()


def _has_founder_evidence(row: dict) -> bool:
    return _has_value(row.get("founders")) or _has_value(row.get("founder_profiles"))


def _has_founder_or_operator_evidence(row: dict) -> bool:
    return (
        _has_founder_evidence(row)
        or _has_value(row.get("founder_team_evidence"))
        or _has_value(row.get("maker_profiles"))
        or _has_value(row.get("maker_name"))
        or _has_value(row.get("maintainer_profiles"))
    )


def _has_stage_or_size_evidence(row: dict) -> bool:
    return (
        _has_value(row.get("stage"))
        or _has_value(row.get("raised"))
        or _has_value(row.get("raised_amount"))
        or _has_value(row.get("headcount"))
    )


def is_net_new_review_worthy_candidate(row: dict) -> bool:
    """Conservative review-worthy bar used for the source-yield sprint."""

    return (
        str(row.get("weekly_tag") or "").upper() == "NEW"
        and bool(_row_domain(row))
        and _has_founder_evidence(row)
        and _has_stage_or_size_evidence(row)
        and _normalized_action(row) in REVIEW_WORTHY_ACTIONS
    )


def _review_worthy_summary(row: dict) -> dict:
    return {
        "name": _row_name(row),
        "domain": _row_domain(row),
        "action": row.get("action", ""),
        "tier": row.get("tier", ""),
        "source_lane": row.get("source_lane", ""),
        "founders": _as_list(row.get("founders")),
        "stage": row.get("stage", ""),
        "raised": row.get("raised", row.get("raised_amount", "")),
        "headcount": row.get("headcount", ""),
        "company_linkedin": row.get("company_linkedin", ""),
        "company_x": row.get("company_x", ""),
        "evidence_urls": sorted(
            {
                str(url)
                for url in (
                    _as_list(row.get("founder_team_evidence"))
                    + _as_list(row.get("stage_funding_evidence"))
                    + _as_list(row.get("customer_buyer_evidence"))
                    + _as_list(row.get("source_outbound_urls"))
                )
                if str(url).strip()
            }
        ),
    }


def _row_project_url(row: dict) -> str:
    candidates = (
        _as_list(row.get("sources"))
        + _as_list(row.get("source_outbound_urls"))
        + _as_list(row.get("evidence_urls"))
        + [row.get("source"), row.get("url"), row.get("project_url")]
    )
    for url in candidates:
        value = str(url or "").strip()
        if "github.com/" in value:
            return value
    for url in candidates:
        value = str(url or "").strip()
        if value.startswith(("http://", "https://")):
            return value
    return ""


def _row_evidence_urls(row: dict) -> list[str]:
    urls = []
    for value in (
        _as_list(row.get("sources"))
        + _as_list(row.get("source_outbound_urls"))
        + _as_list(row.get("evidence_urls"))
        + _as_list(row.get("founder_team_evidence"))
        + _as_list(row.get("stage_funding_evidence"))
        + _as_list(row.get("customer_buyer_evidence"))
        + [row.get("source"), row.get("url"), row.get("project_url")]
    ):
        url = str(value or "").strip()
        if url.startswith(("http://", "https://")) and url not in urls:
            urls.append(url)
    return urls


def _row_market_sector(row: dict) -> str:
    return str(row.get("market_sector") or row.get("sector") or "").strip()


def _inferred_market_theme(row: dict) -> str:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("name", "source_headline", "tagline", "why_on_radar", "description", "theme")
    ).lower()
    if "agent" in text and any(term in text for term in ("security", "vulnerab", "permission", "mcp")):
        return "AI agent security"
    if any(term in text for term in ("github action", "github actions", "ci/cd", "continuous integration", "pipeline")):
        if "security" in text or "red team" in text:
            return "CI/CD security"
        return "Devtools workflow automation"
    if any(term in text for term in ("pull request", "pr", "code review")) and any(term in text for term in ("ai", "slop", "agent")):
        return "AI code quality control"
    if any(term in text for term in ("kubernetes", "deployment", "continuous delivery")):
        return "Kubernetes delivery automation"
    if any(term in text for term in ("eval", "benchmark", "swe")) and "agent" in text:
        return "Agent reliability and evals"
    return ""


def _row_theme(row: dict) -> str:
    theme = str(row.get("theme") or row.get("market_movement") or "").strip()
    if theme and theme != "Emerging technical signal":
        return theme
    return _inferred_market_theme(row) or theme


def _is_github_or_oss_row(row: dict) -> bool:
    return _row_source_bucket(row) == "github"


def _market_signal_score(row: dict) -> tuple[int, list[str]]:
    score = 0
    basis = []
    if str(row.get("weekly_tag") or "").upper() == "NEW":
        score += 15
        basis.append("new_this_week")
    stars_30d = int(row.get("stars_30d") or 0)
    stars = int(row.get("stars") or 0)
    if stars_30d >= 100:
        score += 30
        basis.append("very_high_star_velocity")
    elif stars_30d >= 50:
        score += 25
        basis.append("high_star_velocity")
    elif stars_30d >= 10:
        score += 10
        basis.append("some_star_velocity")
    if stars >= 500:
        score += 15
        basis.append("large_existing_interest")
    elif stars >= 100:
        score += 10
        basis.append("meaningful_existing_interest")
    theme = _row_theme(row)
    if theme and theme != "Emerging technical signal":
        score += 20
        basis.append("specific_market_theme")
    elif theme:
        score += 5
        basis.append("generic_theme_needs_clustering")
    if _row_market_sector(row):
        score += 10
        basis.append("market_sector_classified")
    action = _normalized_action(row)
    if action == "contact maintainer":
        score += 10
        basis.append("maintainer_outreach_worthy")
    elif action in REVIEW_WORTHY_ACTIONS:
        score += 5
        basis.append("research_actionable")
    if int(row.get("evidence_confidence_score") or 0) >= 40:
        score += 10
        basis.append("evidence_confidence_medium")
    if _row_domain(row):
        score += 5
        basis.append("project_or_company_domain_present")
    if int(row.get("source_count") or 0) > 1:
        score += 10
        basis.append("multi_source_echo")
    text = " ".join(str(row.get(key) or "") for key in ("name", "why_on_radar", "why_this_may_be_noise", "theme")).lower()
    if any(term in text for term in ("free titles", "gaming freebies", "captcha")):
        score -= 30
        basis.append("consumer_or_low_fit_noise")
    if any(term in text for term in ("daily news", "news brief", "newsletter", "market analysis", "行情")):
        score -= 25
        basis.append("content_aggregation_less_company_formation")
    return max(0, min(100, score)), basis


def _market_signal_summary(row: dict) -> dict:
    score, basis = _market_signal_score(row)
    project_url = _row_project_url(row)
    theme = _row_theme(row) or "Emerging technical signal"
    missing = list(dict.fromkeys(_as_list(row.get("missing_owner_evidence")) + _as_list(row.get("missing_identity_evidence"))))
    if not missing:
        missing = ["company formation evidence not yet complete"]
    return {
        "name": _row_name(row),
        "project_url": project_url,
        "domain": _row_domain(row),
        "source_lane": row.get("source_lane", ""),
        "market_sector": _row_market_sector(row),
        "theme": theme,
        "market_signal_score": score,
        "score_basis": basis,
        "stars": row.get("stars", 0),
        "stars_30d": row.get("stars_30d", 0),
        "repo_age_days": row.get("repo_age_days", 0),
        "action": row.get("action", ""),
        "why_it_matters": row.get("why_on_radar", ""),
        "why_not_company_yet": "; ".join(str(item) for item in missing),
        "suggested_company_search": f"{theme} startups founder pricing customers funding",
        "evidence_urls": _row_evidence_urls(row)[:5],
        "promotion_path": "Review-Worthy Market Signal -> company search theme -> Review-Worthy Company when identity/founder/stage evidence clears.",
    }


def build_review_worthy_market_signals(candidate_rows: list[dict], *, limit: int = MARKET_SIGNAL_LIMIT) -> list[dict]:
    rows = []
    seen = set()
    for row in candidate_rows:
        if not _is_github_or_oss_row(row):
            continue
        if not _row_project_url(row):
            continue
        score, _basis = _market_signal_score(row)
        if score < 55:
            continue
        key = _row_project_url(row) or _row_name(row)
        if key in seen:
            continue
        seen.add(key)
        rows.append(_market_signal_summary(row))
    return sorted(rows, key=lambda item: (item["market_signal_score"], int(item.get("stars_30d") or 0)), reverse=True)[:limit]


def _company_evidence_gaps(row: dict) -> list[str]:
    gaps = []
    if not _row_domain(row):
        gaps.append("official_domain_missing")
    if not _has_founder_or_operator_evidence(row):
        gaps.append("founder_team_missing")
    if not _has_stage_or_size_evidence(row):
        gaps.append("stage_funding_or_headcount_missing")
    if not (_has_value(row.get("company_linkedin")) or _has_value(row.get("company_x"))):
        gaps.append("company_linkedin_or_social_missing")
    if not (_has_value(row.get("customer_buyer_evidence")) or _has_value(row.get("customer_buyer_evidence_types"))):
        gaps.append("commercial_or_customer_signal_missing")
    if not (
        _has_value(row.get("pricing_evidence"))
        or _has_value(row.get("docs_evidence"))
        or _has_value(row.get("careers_evidence"))
        or any(
            term in str(url).lower()
            for url in _row_evidence_urls(row)
            for term in ("/pricing", "/docs", "/customers", "/careers", "/jobs")
        )
    ):
        gaps.append("pricing_docs_or_careers_missing")
    for gap in (
        _as_list(row.get("missing_owner_evidence"))
        + _as_list(row.get("missing_identity_evidence"))
        + _as_list(row.get("missing_evidence"))
    ):
        normalized = str(gap or "").strip()
        if normalized and normalized not in gaps:
            gaps.append(normalized)
    return gaps


def _gap_next_step(gaps: list[str], row: dict) -> str:
    if "official_domain_missing" in gaps or "no verified domain" in gaps:
        return "Resolve official domain from launch text, project docs, founder profile, or web search."
    if "founder_team_missing" in gaps or "founder_or_maintainer_missing" in gaps:
        return "Find founder or maintainer identity from website, GitHub org, LinkedIn, HN, or X."
    if "stage_funding_or_headcount_missing" in gaps:
        return "Find stage, funding, headcount, careers, or company profile evidence."
    if "commercial_or_customer_signal_missing" in gaps:
        return "Check pricing, docs, customers, case studies, waitlist, careers, or deployment evidence."
    source = _row_source_bucket(row)
    if source == "github":
        return "Use this as a market signal and search for companies building around the theme."
    return "Run one focused evidence check before promoting."


def _gap_bucket_status(is_missing: bool, missing_key: str) -> dict:
    return {
        "status": "missing" if is_missing else "present",
        "missing_evidence": missing_key if is_missing else "",
    }


def _gap_buckets(row: dict, gaps: list[str]) -> dict:
    gap_set = set(gaps)
    return {
        "official_domain": _gap_bucket_status("official_domain_missing" in gap_set, "official_domain_missing"),
        "founder_team": _gap_bucket_status(
            "founder_team_missing" in gap_set or "founder_or_maintainer_missing" in gap_set,
            "founder_team_missing",
        ),
        "stage_funding_headcount": _gap_bucket_status(
            "stage_funding_or_headcount_missing" in gap_set,
            "stage_funding_or_headcount_missing",
        ),
        "commercial_customer_signal": _gap_bucket_status(
            "commercial_or_customer_signal_missing" in gap_set,
            "commercial_or_customer_signal_missing",
        ),
        "pricing_docs_careers": _gap_bucket_status(
            "pricing_docs_or_careers_missing" in gap_set,
            "pricing_docs_or_careers_missing",
        ),
        "linkedin_manual_check": _gap_bucket_status(
            "company_linkedin_or_social_missing" in gap_set or "company_social_or_linkedin_missing" in gap_set,
            "company_linkedin_or_social_missing",
        ),
    }


def _manual_check_sources(gaps: list[str], row: dict) -> list[str]:
    sources = []
    gap_set = set(gaps)
    if "official_domain_missing" in gap_set:
        sources.append("Manual web resolver")
    if "founder_team_missing" in gap_set or "founder_or_maintainer_missing" in gap_set:
        sources.extend(["LinkedIn", "Product Hunt maker page", "GitHub/X founder profile"])
    if "stage_funding_or_headcount_missing" in gap_set:
        sources.extend(["Crunchbase-style web search", "company careers page"])
    if "commercial_or_customer_signal_missing" in gap_set:
        sources.append("company website/docs/customers")
    if "pricing_docs_or_careers_missing" in gap_set:
        sources.append("pricing/docs/careers pages")
    if "company_linkedin_or_social_missing" in gap_set or "company_social_or_linkedin_missing" in gap_set:
        sources.append("LinkedIn")
    return list(dict.fromkeys(sources))


def _evidence_gap_score(row: dict) -> int:
    score = int(row.get("investment_interest_score") or 0) + int(row.get("evidence_confidence_score") or 0)
    if _row_source_bucket(row) in {"product_hunt", "x", "github", "manual_web"}:
        score += 25
    if _normalized_action(row) in {"contact maintainer", "research deeper"}:
        score += 15
    score += min(30, int(row.get("stars_30d") or 0) // 5)
    text = " ".join(str(row.get(key) or "") for key in ("name", "why_on_radar", "theme")).lower()
    if any(term in text for term in ("daily news", "news brief", "newsletter", "market analysis", "行情")):
        score -= 25
    return score


def _evidence_gap_row(row: dict) -> dict:
    gaps = _company_evidence_gaps(row)
    return {
        "name": _row_name(row),
        "domain": _row_domain(row),
        "project_url": _row_project_url(row),
        "source_lane": row.get("source_lane", ""),
        "market_sector": _row_market_sector(row),
        "theme": _row_theme(row),
        "action": row.get("action", ""),
        "tier": row.get("tier", ""),
        "gap_priority_score": _evidence_gap_score(row),
        "missing_evidence": gaps,
        "gap_buckets": _gap_buckets(row, gaps),
        "manual_check_sources": _manual_check_sources(gaps, row),
        "next_step": _gap_next_step(gaps, row),
        "promotion_target": "Review-Worthy Company" if _row_source_bucket(row) != "github" else "Review-Worthy Company or supporting Market Signal",
        "evidence_urls": _row_evidence_urls(row)[:5],
    }


def build_evidence_gap_queue(
    candidate_rows: list[dict],
    review_worthy_rows: list[dict],
    *,
    limit: int = EVIDENCE_GAP_LIMIT,
) -> list[dict]:
    review_keys = {_row_domain(row) or _row_name(row) for row in review_worthy_rows}
    rows = []
    seen = set()
    for row in candidate_rows:
        bucket = _row_source_bucket(row)
        if bucket == "yc_directory":
            continue
        key = _row_domain(row) or _row_project_url(row) or _row_name(row)
        if not key or key in seen or key in review_keys:
            continue
        gaps = _company_evidence_gaps(row)
        if not gaps:
            continue
        seen.add(key)
        rows.append(_evidence_gap_row(row))
    return sorted(rows, key=lambda item: item["gap_priority_score"], reverse=True)[:limit]


def build_launch_and_oss_watch(candidate_rows: list[dict], market_signals: list[dict], gap_queue: list[dict]) -> list[dict]:
    promoted = {item.get("project_url") or item.get("domain") or item.get("name") for item in market_signals + gap_queue}
    rows = []
    for row in candidate_rows:
        bucket = _row_source_bucket(row)
        if bucket not in {"product_hunt", "x", "github"}:
            continue
        key = _row_project_url(row) or _row_domain(row) or _row_name(row)
        if key in promoted:
            continue
        rows.append(
            {
                "name": _row_name(row),
                "source_lane": row.get("source_lane", ""),
                "domain": _row_domain(row),
                "project_url": _row_project_url(row),
                "theme": _row_theme(row),
                "action": row.get("action", ""),
                "why_keep": row.get("why_on_radar", ""),
                "why_not_promoted": row.get("why_this_may_be_noise", "") or "Not enough evidence for company or market-signal promotion yet.",
                "evidence_urls": _row_evidence_urls(row)[:3],
            }
        )
    return rows[:WATCHLIST_LIMIT]


def _workflow_assign_owner_rows(weekly_focus: dict) -> list[dict]:
    workflow = weekly_focus.get("workflow_view") or {}
    rows = workflow.get("Assign owner") or workflow.get("Assign Owner") or []
    return rows if isinstance(rows, list) else []


def _assign_owner_names(rows: list[dict]) -> list[str]:
    names = []
    for row in rows:
        name = _row_name(row)
        if name:
            names.append(name)
    return names


def _hn_launch_trial_summary(run_dir: Path) -> dict:
    payload = _read_json(run_dir / "hn-launch-trial" / "hn-trial-row-review.json", {})
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    return summary if isinstance(summary, dict) else {}


def _source_counts(raw_evidence: dict, run_dir: Path) -> dict:
    counts = {}
    for source in ("github", "product_hunt", "yc_directory", "x_launches"):
        value = raw_evidence.get(source)
        counts[source] = len(value) if isinstance(value, list) else 0
    last30days = raw_evidence.get("last30days")
    counts["last30days_queries"] = len(last30days) if isinstance(last30days, dict) else 0
    hn_summary = _hn_launch_trial_summary(run_dir)
    counts["hn_launch_trial_rows"] = hn_summary.get("rows", 0)
    counts["hn_launch_assign_owner"] = (hn_summary.get("action_split") or {}).get("Assign owner", 0)
    counts["hn_launch_unsafe_promotions"] = hn_summary.get("unsafe_promotions", 0)
    return counts


def _latest_raw_evidence_path(run_path: Path) -> Path:
    matches = sorted(
        run_path.glob("*-raw-evidence.json"),
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    if matches:
        return matches[0]
    return run_path / "2026-05-31-raw-evidence.json"


def _domain_from_url(url: str) -> str:
    if not url or "://" not in url:
        return ""
    try:
        from urllib.parse import urlparse

        host = urlparse(url).netloc.lower().removeprefix("www.")
        return host
    except Exception:
        return ""


def _looks_like_source_or_directory_domain(domain: str) -> bool:
    normalized = (domain or "").lower().strip().removeprefix("www.")
    blocked = {
        "apps.apple.com",
        "github.com",
        "linkedin.com",
        "news.ycombinator.com",
        "producthunt.com",
        "reddit.com",
        "twitter.com",
        "x.com",
        "youtube.com",
    }
    return any(normalized == item or normalized.endswith(f".{item}") for item in blocked)


def _official_domain_hint(item: dict) -> str:
    domain = _row_domain(item)
    if domain and not _looks_like_source_or_directory_domain(domain):
        return domain
    for key in ("website", "homepage", "resolved_url"):
        candidate = _domain_from_url(str(item.get(key) or ""))
        if candidate and not _looks_like_source_or_directory_domain(candidate):
            return candidate
    return ""


def _row_source_bucket(row: dict) -> str:
    text = " ".join(
        str(value or "")
        for value in (
            row.get("source_lane"),
            row.get("candidate_type"),
            row.get("evidence_role"),
            row.get("source"),
            row.get("url"),
        )
    ).lower()
    if "producthunt" in text or "product hunt" in text:
        return "product_hunt"
    if "yc directory" in text or "ycombinator.com/companies" in text or "yc_company" in text:
        return "yc_directory"
    if "news.ycombinator.com" in text or "hackernews" in text or "hacker news" in text:
        return "hn"
    if "github.com" in text or "oss_project" in text or row.get("source_lane") == "OSS":
        return "github"
    if "x.com" in text or "twitter.com" in text or row.get("source_lane") == "X":
        return "x"
    if "grounded web" in text or "company_discovery" in text or "official_company_page" in text:
        return "manual_web"
    return "other"


def _count_by_source_bucket(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        bucket = _row_source_bucket(row)
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts


def _raw_domain_resolution_summary(raw_evidence: dict) -> dict:
    product_hunt = raw_evidence.get("product_hunt") if isinstance(raw_evidence, dict) else []
    x_launches = raw_evidence.get("x_launches") if isinstance(raw_evidence, dict) else []
    product_hunt = product_hunt if isinstance(product_hunt, list) else []
    x_launches = x_launches if isinstance(x_launches, list) else []
    ph_resolved = [
        item
        for item in product_hunt
        if _official_domain_hint(item)
    ]
    x_resolved = [
        item
        for item in x_launches
        if _official_domain_hint(item)
    ]
    return {
        "product_hunt": {
            "launches": len(product_hunt),
            "resolved_domains": len(ph_resolved),
            "unresolved_domains": max(0, len(product_hunt) - len(ph_resolved)),
        },
        "x": {
            "launches": len(x_launches),
            "resolved_domains": len(x_resolved),
            "unresolved_domains": max(0, len(x_launches) - len(x_resolved)),
        },
    }


def _raw_source_launch_rows(raw_evidence: dict) -> list[dict]:
    rows = []
    product_hunt = raw_evidence.get("product_hunt") if isinstance(raw_evidence, dict) else []
    x_launches = raw_evidence.get("x_launches") if isinstance(raw_evidence, dict) else []
    for item in product_hunt if isinstance(product_hunt, list) else []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "name": item.get("name") or item.get("company_name") or item.get("title") or "",
                "domain": item.get("domain") or "",
                "source_lane": "Product Hunt",
                "source": item.get("product_hunt_url") or item.get("url") or "",
                "url": item.get("product_hunt_url") or item.get("url") or "",
                "website": item.get("website") or "",
                "tagline": item.get("tagline") or item.get("description") or "",
                "weekly_tag": "NEW",
                "action": item.get("action") or "research deeper",
                "tier": "Evidence Gap",
                "market_sector": item.get("market_sector") or "Company Formation",
                "why_on_radar": item.get("tagline") or item.get("description") or "Product Hunt launch.",
                "why_this_may_be_noise": item.get("why_this_may_be_noise") or "Raw Product Hunt launch; needs company evidence before promotion.",
                "missing_evidence": item.get("missing_evidence") or [],
                "founder_profiles": item.get("maker_profiles") or item.get("founder_profiles") or [],
                "founders": item.get("founders") or [],
                "founder_team_evidence": item.get("founder_team_evidence") or [],
                "source_outbound_urls": [url for url in (item.get("website"), item.get("product_hunt_url"), item.get("url")) if url],
                "investment_interest_score": 35,
                "evidence_confidence_score": 25 if item.get("domain") else 15,
            }
        )
    for item in x_launches if isinstance(x_launches, list) else []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "name": item.get("company_name") or item.get("name") or item.get("title") or "",
                "domain": item.get("domain") or "",
                "source_lane": "X",
                "source": item.get("company_x") or item.get("url") or "",
                "url": item.get("company_x") or item.get("url") or "",
                "website": item.get("website") or "",
                "tagline": item.get("snippet") or item.get("description") or "",
                "weekly_tag": "NEW",
                "action": item.get("action") or "watch",
                "tier": "Evidence Gap",
                "market_sector": item.get("market_sector") or "Company Formation",
                "why_on_radar": item.get("snippet") or item.get("description") or "X launch/social-confidence signal.",
                "why_this_may_be_noise": item.get("why_this_may_be_noise") or "Raw X launch signal; needs official identity and durable company evidence.",
                "missing_evidence": item.get("missing_evidence") or [],
                "company_x": item.get("company_x") or item.get("url") or "",
                "source_outbound_urls": [url for url in (item.get("website"), item.get("company_x"), item.get("url")) if url],
                "investment_interest_score": 30,
                "evidence_confidence_score": min(45, int(item.get("launch_intent_score") or 0)),
            }
        )
    return [row for row in rows if _row_name(row)]


def _source_diversity_summary(
    *,
    candidate_rows: list[dict],
    review_worthy_rows: list[dict],
    raw_evidence: dict,
    run_dir: Path,
) -> dict:
    review_counts = _count_by_source_bucket(review_worthy_rows)
    candidate_counts = _count_by_source_bucket(candidate_rows)
    hn_summary = _hn_launch_trial_summary(run_dir)
    hn_assign_owner_count = (hn_summary.get("action_split") or {}).get("Assign owner", 0)
    if hn_assign_owner_count:
        review_counts["hn"] = review_counts.get("hn", 0) + hn_assign_owner_count
    desired = ("hn", "github", "product_hunt", "x", "manual_web", "yc_directory")
    non_yc_review_worthy = sum(
        count for bucket, count in review_counts.items() if bucket != "yc_directory"
    )
    review_lanes = [bucket for bucket in desired if review_counts.get(bucket, 0)]
    return {
        "desired_source_lanes": list(desired),
        "candidate_rows_by_source_lane": {bucket: candidate_counts.get(bucket, 0) for bucket in desired},
        "review_worthy_rows_by_source_lane": {bucket: review_counts.get(bucket, 0) for bucket in desired},
        "review_worthy_source_lanes": review_lanes,
        "non_yc_review_worthy_count": non_yc_review_worthy,
        "yc_review_worthy_count": review_counts.get("yc_directory", 0),
        "raw_domain_resolution": _raw_domain_resolution_summary(raw_evidence),
        "hn_launch_trial_rows": hn_summary.get("rows", 0),
        "hn_launch_trial_assign_owner": hn_assign_owner_count,
        "source_diversity_proven": non_yc_review_worthy > 0 and len(review_lanes) >= 2,
        "interpretation": (
            "Source diversity is proven when at least one non-YC lane produces a partner-grade row. "
            "HN Assign Owner rows count here; raw Product Hunt/X/GitHub/manual-web rows are discovery coverage until they clear the same evidence bar."
        ),
    }


def _ledger_packet_warning(run_dir: Path, strict_assign_owner_names: list[str]) -> dict:
    packet = _read_json(run_dir / "final-partner-packet" / "partner-decision-packet.json", {})
    sections = packet.get("sections") if isinstance(packet, dict) else {}
    owner_rows = sections.get("owner_follow_up") if isinstance(sections, dict) else []
    if not isinstance(owner_rows, list):
        owner_rows = []
    generated_names = [str(row.get("entity_name") or "").strip() for row in owner_rows if str(row.get("entity_name") or "").strip()]
    generated_count = packet.get("summary", {}).get("owner_follow_up", len(owner_rows)) if isinstance(packet, dict) else len(owner_rows)
    strict_names = set(strict_assign_owner_names)
    generated_name_set = set(generated_names)
    unsafe_for_blessed_decision = bool(generated_count and (generated_count > len(strict_names) or not generated_name_set <= strict_names))
    return {
        "generated_partner_packet_owner_follow_up_count": generated_count,
        "generated_partner_packet_owner_follow_up_names": generated_names,
        "strict_weekly_assign_owner_names": strict_assign_owner_names,
        "unsafe_for_blessed_decision": unsafe_for_blessed_decision,
        "warning": (
            "The generated historical ledger partner packet has more owner follow-up rows than the strict weekly workflow. "
            "Use the source-yield decision packet for this sprint until the ledger packet respects the weekly action gate."
            if unsafe_for_blessed_decision
            else ""
        ),
    }


def _manual_mode_summary(runtime_ledger: dict) -> dict:
    source_access = runtime_ledger.get("source_access") or {}
    summary = source_access.get("summary") or {}
    return {
        "configured": summary.get("configured", []),
        "manual_mode": summary.get("manual_mode", []),
        "missing": summary.get("missing", []),
        "recommendation": summary.get("recommendation", ""),
    }


def _source_yield_targets(target_review_worthy_count: int) -> dict:
    targets = json.loads(json.dumps(DEFAULT_SOURCE_YIELD_TARGETS))
    targets["review_worthy_companies"]["min"] = target_review_worthy_count
    return targets


def _target_result(count: int, bounds: dict) -> dict:
    minimum = bounds.get("min")
    maximum = bounds.get("max")
    allow_above_max = bool(bounds.get("allow_above_max"))
    meets_min = minimum is None or count >= int(minimum)
    meets_max = maximum is None or count <= int(maximum) or allow_above_max
    status = "met" if meets_min and meets_max else "below_min" if not meets_min else "above_max"
    return {
        "count": count,
        "min": minimum,
        "max": maximum,
        "met": meets_min and meets_max,
        "status": status,
    }


def _target_status(targets: dict, counts: dict) -> dict:
    return {
        key: _target_result(int(counts.get(key, 0)), bounds)
        for key, bounds in targets.items()
    }


def _structured_provider_decision(
    *,
    target_status: dict,
    source_diversity: dict,
    targeted_manual_enrichment: dict,
) -> dict:
    reasons = []
    if not target_status.get("review_worthy_companies", {}).get("met", False):
        reasons.append("Review-Worthy Company target missed")
    raw_resolution = source_diversity.get("raw_domain_resolution") or {}
    unresolved = sum(int(item.get("unresolved_domains") or 0) for item in raw_resolution.values())
    if unresolved:
        reasons.append(f"{unresolved} Product Hunt/X launch domains still unresolved")
    manual_summary = targeted_manual_enrichment.get("summary") if isinstance(targeted_manual_enrichment, dict) else {}
    if manual_summary and int(manual_summary.get("targets_enriched") or 0) and int(manual_summary.get("items_seen") or 0) == 0:
        reasons.append("Targeted public manual enrichment found no usable snippets")
    status = "recommend_structured_provider_trial" if reasons and "Review-Worthy Company target missed" in reasons else "public_sources_still_sufficient_for_next_pass"
    return {
        "status": status,
        "best_unlock": "Coresignal or Crunchbase-style company metadata" if status == "recommend_structured_provider_trial" else "",
        "reasons": reasons,
        "policy": (
            "Only consider paid structured data after public discovery/manual enrichment misses the company-yield target. "
            "Keep LinkedIn/Crunchbase-style checks manual for top rows unless compliant provider access is configured."
        ),
    }


def build_source_yield_validation_report(
    run_dir: Path | str,
    *,
    target_review_worthy_count: int = 5,
    assign_owner_allowlist: tuple[str, ...] = DEFAULT_ASSIGN_OWNER_ALLOWLIST,
    generated_at: str | None = None,
) -> dict:
    run_path = Path(run_dir)
    candidates = _read_json(run_path / "candidates.json", [])
    weekly_focus = _read_json(run_path / "weekly-focus.json", {})
    runtime_ledger = _read_json(run_path / "runtime-ledger.json", {})
    raw_evidence = _read_json(_latest_raw_evidence_path(run_path), {})
    company_discovery = _read_json(run_path / "company-discovery.json", {})
    manual_targets = _read_json(run_path / "manual-enrichment-targets.json", {})
    targeted_manual_enrichment = _read_json(run_path / "targeted-manual-enrichment.json", {})
    structured_provider_trial = _read_json(run_path / "structured-provider-trial.json", {})

    candidate_rows = candidates if isinstance(candidates, list) else []
    raw_source_rows = _raw_source_launch_rows(raw_evidence if isinstance(raw_evidence, dict) else {})
    source_yield_rows = candidate_rows + raw_source_rows
    assign_owner_rows = _workflow_assign_owner_rows(weekly_focus if isinstance(weekly_focus, dict) else {})
    assign_owner_names = _assign_owner_names(assign_owner_rows)
    candidate_assign_owner_names = [_row_name(row) for row in candidate_rows if _normalized_action(row) == "assign owner"]
    review_worthy_rows = [_review_worthy_summary(row) for row in candidate_rows if is_net_new_review_worthy_candidate(row)]
    market_signals = build_review_worthy_market_signals(source_yield_rows)
    evidence_gap_queue = build_evidence_gap_queue(source_yield_rows, review_worthy_rows)
    launch_watch = build_launch_and_oss_watch(source_yield_rows, market_signals, evidence_gap_queue)

    allowlist = {name.lower() for name in assign_owner_allowlist}
    weekly_owner_set = {name.lower() for name in assign_owner_names}
    candidate_owner_set = {name.lower() for name in candidate_assign_owner_names if name}
    voker_present = "voker" in weekly_owner_set
    unexpected_weekly_owners = sorted(weekly_owner_set - allowlist)
    unexpected_candidate_owners = sorted(candidate_owner_set - allowlist)
    assign_owner_bar_preserved = (
        voker_present
        and len(assign_owner_names) == 1
        and not unexpected_weekly_owners
        and not unexpected_candidate_owners
    )

    source_health = runtime_ledger.get("source_health", []) if isinstance(runtime_ledger, dict) else []
    source_health_summary = [
        {
            "source": item.get("source", ""),
            "status": item.get("status", ""),
            "fresh_items": item.get("fresh_items", 0),
            "duration_seconds": item.get("duration_seconds", 0),
            "warnings": item.get("warnings", []),
        }
        for item in source_health
        if isinstance(item, dict)
    ]
    hn_summary = _hn_launch_trial_summary(run_path)
    if hn_summary:
        source_health_summary.append(
            {
                "source": "hn_launch_trial",
                "status": "complete",
                "fresh_items": hn_summary.get("rows", 0),
                "duration_seconds": 0,
                "warnings": [],
            }
        )
    caveats = []
    unhealthy_last30days = [
        item
        for item in source_health_summary
        if str(item.get("source", "")).startswith("last30days:") and item.get("status") in {"error", "degraded"}
    ]
    if unhealthy_last30days:
        caveats.append("last30days sector queries were degraded or errored, mostly from Safari cookie permissions and timeouts.")
    ph_warnings = [item for item in source_health_summary if item.get("source") == "product_hunt" and item.get("warnings")]
    if ph_warnings:
        caveats.append("Product Hunt API worked, but several launch redirects still needed fallback domain resolution or stayed unresolved.")
    x_warnings = [item for item in source_health_summary if item.get("source") == "x_launches" and item.get("warnings")]
    if x_warnings:
        caveats.append("X worked as a launch signal, but evidence was thin and still needs domain enrichment for some rows.")

    ledger_warning = _ledger_packet_warning(run_path, assign_owner_names)
    if ledger_warning["warning"]:
        caveats.append(ledger_warning["warning"])

    net_new_count = len(review_worthy_rows)
    goal_reached = assign_owner_bar_preserved and net_new_count >= target_review_worthy_count
    unsafe_promotions = 0 if assign_owner_bar_preserved else 1
    targets = _source_yield_targets(target_review_worthy_count)
    target_status = _target_status(
        targets,
        {
            "assign_owner": len(assign_owner_names),
            "review_worthy_companies": net_new_count,
            "review_worthy_market_signals": len(market_signals),
            "evidence_gap_queue": len(evidence_gap_queue),
            "unsafe_promotions": unsafe_promotions,
        },
    )
    source_diversity = _source_diversity_summary(
        candidate_rows=source_yield_rows,
        review_worthy_rows=review_worthy_rows,
        raw_evidence=raw_evidence if isinstance(raw_evidence, dict) else {},
        run_dir=run_path,
    )
    structured_decision = _structured_provider_decision(
        target_status=target_status,
        source_diversity=source_diversity,
        targeted_manual_enrichment=targeted_manual_enrichment if isinstance(targeted_manual_enrichment, dict) else {},
    )
    return {
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_path),
        "goal_assessment": {
            "goal_reached": goal_reached,
            "target_assign_owner": list(assign_owner_allowlist),
            "assign_owner_names": assign_owner_names,
            "candidate_assign_owner_names": candidate_assign_owner_names,
            "voker_assign_owner_present": voker_present,
            "assign_owner_bar_preserved": assign_owner_bar_preserved,
            "unexpected_weekly_assign_owner_names": unexpected_weekly_owners,
            "unexpected_candidate_assign_owner_names": unexpected_candidate_owners,
            "target_net_new_review_worthy_count": target_review_worthy_count,
            "net_new_review_worthy_count": net_new_count,
            "review_worthy_target_met": net_new_count >= target_review_worthy_count,
        },
        "source_yield_targets": targets,
        "target_status": target_status,
        "review_worthy_rows": review_worthy_rows,
        "review_worthy_market_signals": market_signals,
        "evidence_gap_queue": evidence_gap_queue,
        "launch_and_oss_watch": launch_watch,
        "two_track_summary": {
            "review_worthy_companies": len(review_worthy_rows),
            "review_worthy_market_signals": len(market_signals),
            "evidence_gap_queue": len(evidence_gap_queue),
            "launch_and_oss_watch": len(launch_watch),
            "raw_launch_rows_preserved": len(raw_source_rows),
            "interpretation": (
                "Companies need official identity plus founder/stage/size evidence. "
                "Market signals can be review-worthy when OSS/theme momentum is strong even before a company exists."
            ),
        },
        "source_counts": _source_counts(raw_evidence if isinstance(raw_evidence, dict) else {}, run_path),
        "source_diversity": source_diversity,
        "structured_provider_decision": structured_decision,
        "source_health": source_health_summary,
        "source_access": _manual_mode_summary(runtime_ledger if isinstance(runtime_ledger, dict) else {}),
        "manual_enrichment_summary": manual_targets.get("summary", {}) if isinstance(manual_targets, dict) else {},
        "targeted_manual_enrichment_summary": (
            targeted_manual_enrichment.get("summary", {}) if isinstance(targeted_manual_enrichment, dict) else {}
        ),
        "structured_provider_trial_summary": (
            structured_provider_trial.get("summary", {}) if isinstance(structured_provider_trial, dict) else {}
        ),
        "company_discovery_summary": company_discovery.get("summary", {}) if isinstance(company_discovery, dict) else {},
        "ledger_partner_packet_warning": ledger_warning,
        "caveats": caveats,
    }


def build_repeatability_validation_report(
    run_dirs: list[Path | str],
    *,
    target_review_worthy_count: int = 5,
    assign_owner_allowlist: tuple[str, ...] = DEFAULT_ASSIGN_OWNER_ALLOWLIST,
    generated_at: str | None = None,
) -> dict:
    runs = []
    lane_totals: dict[str, dict[str, int]] = {}
    unsafe_total = 0
    for run_dir in run_dirs:
        report = build_source_yield_validation_report(
            run_dir,
            target_review_worthy_count=target_review_worthy_count,
            assign_owner_allowlist=assign_owner_allowlist,
        )
        assessment = report["goal_assessment"]
        unsafe = 0 if assessment["assign_owner_bar_preserved"] else 1
        unsafe_total += unsafe
        diversity = report.get("source_diversity", {})
        raw_resolution = diversity.get("raw_domain_resolution") or {}
        for lane, item in raw_resolution.items():
            totals = lane_totals.setdefault(lane, {"raw_launches": 0, "resolved_domains": 0, "unresolved_domains": 0})
            totals["raw_launches"] += int(item.get("launches") or 0)
            totals["resolved_domains"] += int(item.get("resolved_domains") or 0)
            totals["unresolved_domains"] += int(item.get("unresolved_domains") or 0)
        runs.append(
            {
                "run_dir": str(run_dir),
                "goal_reached": assessment["goal_reached"],
                "assign_owner": len(assessment["assign_owner_names"]),
                "assign_owner_bar_preserved": assessment["assign_owner_bar_preserved"],
                "review_worthy_companies": assessment["net_new_review_worthy_count"],
                "review_worthy_market_signals": len(report.get("review_worthy_market_signals", [])),
                "evidence_gap_queue": len(report.get("evidence_gap_queue", [])),
                "unsafe_promotions": unsafe,
                "review_worthy_source_lanes": diversity.get("review_worthy_source_lanes", []),
                "source_diversity_proven": diversity.get("source_diversity_proven", False),
                "target_status": report.get("target_status", {}),
            }
        )
    compared = len(runs)
    repeatability_proven = (
        compared >= 2
        and unsafe_total == 0
        and all(run["assign_owner_bar_preserved"] for run in runs)
        and all(run["review_worthy_companies"] >= target_review_worthy_count for run in runs)
    )
    return {
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "summary": {
            "runs_compared": compared,
            "repeatability_proven": repeatability_proven,
            "unsafe_promotions_total": unsafe_total,
            "all_runs_preserved_assign_owner_bar": all(run["assign_owner_bar_preserved"] for run in runs),
            "min_review_worthy_companies": min((run["review_worthy_companies"] for run in runs), default=0),
            "min_market_signals": min((run["review_worthy_market_signals"] for run in runs), default=0),
            "min_evidence_gap_queue": min((run["evidence_gap_queue"] for run in runs), default=0),
            "interpretation": (
                "Repeatability is proven when multiple validation runs preserve the strict Assign Owner gate, "
                "keep unsafe promotions at zero, and hit the Review-Worthy Company floor."
            ),
        },
        "source_lane_totals": lane_totals,
        "runs": runs,
    }


def render_repeatability_markdown(report: dict) -> str:
    lines = [
        "# Source Yield Repeatability",
        "",
        f"- Runs compared: {report['summary']['runs_compared']}",
        f"- Repeatability proven: {'yes' if report['summary']['repeatability_proven'] else 'no'}",
        f"- Unsafe promotions total: {report['summary']['unsafe_promotions_total']}",
        "",
        "| Run | Assign Owner | Review-Worthy Companies | Market Signals | Evidence Gaps | Unsafe |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for run in report.get("runs", []):
        lines.append(
            "| {run_dir} | {owner} | {companies} | {signals} | {gaps} | {unsafe} |".format(
                run_dir=str(run.get("run_dir", "")).replace("|", "/"),
                owner=run.get("assign_owner", 0),
                companies=run.get("review_worthy_companies", 0),
                signals=run.get("review_worthy_market_signals", 0),
                gaps=run.get("evidence_gap_queue", 0),
                unsafe=run.get("unsafe_promotions", 0),
            )
        )
    return "\n".join(lines) + "\n"


def build_source_yield_decision_packet(report: dict, weekly_focus: dict) -> dict:
    assign_owner_rows = _workflow_assign_owner_rows(weekly_focus)
    owner_follow_up = [
        {
            "name": _row_name(row),
            "domain": row.get("company_domain") or row.get("domain", ""),
            "recommended_action": "Assign owner",
            "lead_route": row.get("lead_route", ""),
            "owner_readiness_score": row.get("owner_readiness_score", ""),
            "evidence_urls": row.get("evidence_urls", []),
            "why_system_call": "Only row clearing the strict weekly Assign Owner gate.",
        }
        for row in assign_owner_rows
    ]
    review_rows = report["review_worthy_rows"]
    market_signals = report.get("review_worthy_market_signals", [])
    evidence_gap_queue = report.get("evidence_gap_queue", [])
    launch_watch = report.get("launch_and_oss_watch", [])
    return {
        "generated_at": report["generated_at"],
        "packet_type": "source_yield_two_track_decision_packet",
        "source_run_dir": report["run_dir"],
        "summary": {
            "goal_reached": report["goal_assessment"]["goal_reached"],
            "owner_follow_up": len(owner_follow_up),
            "review_worthy_companies": len(review_rows),
            "review_worthy_market_signals": len(market_signals),
            "evidence_gap_queue": len(evidence_gap_queue),
            "launch_and_oss_watch": len(launch_watch),
            "review_worthy_research": len(review_rows),
            "continue_research": len(review_rows),
            "unsafe_promotions": 0 if report["goal_assessment"]["assign_owner_bar_preserved"] else 1,
            "assign_owner_bar_preserved": report["goal_assessment"]["assign_owner_bar_preserved"],
            "source_yield_target_status": report.get("target_status", {}),
        },
        "sections": {
            "owner_follow_up": owner_follow_up,
            "review_worthy_companies": review_rows,
            "review_worthy_research": review_rows,
            "review_worthy_market_signals": market_signals,
            "evidence_gap_queue": evidence_gap_queue,
            "continue_research": review_rows,
            "launch_and_oss_watch": launch_watch,
            "source_caveats": report["caveats"],
        },
    }


def build_source_yield_ledger_action_report(report: dict) -> dict:
    return {
        "generated_at": report["generated_at"],
        "report_type": "source_yield_strict_action_report",
        "source_run_dir": report["run_dir"],
        "summary": {
            "goal_reached": report["goal_assessment"]["goal_reached"],
            "assign_owner_entities": len(report["goal_assessment"]["assign_owner_names"]),
            "review_worthy_company_entities": report["goal_assessment"]["net_new_review_worthy_count"],
            "review_worthy_market_signal_entities": len(report.get("review_worthy_market_signals", [])),
            "evidence_gap_entities": len(report.get("evidence_gap_queue", [])),
            "review_worthy_research_entities": report["goal_assessment"]["net_new_review_worthy_count"],
            "unsafe_promotions": 0 if report["goal_assessment"]["assign_owner_bar_preserved"] else 1,
        },
        "actions": [
            {
                "action": "Assign owner",
                "count": len(report["goal_assessment"]["assign_owner_names"]),
                "names": report["goal_assessment"]["assign_owner_names"],
            },
            {
                "action": "Review worthy - research deeper",
                "count": report["goal_assessment"]["net_new_review_worthy_count"],
                "names": [row["name"] for row in report["review_worthy_rows"]],
            },
            {
                "action": "Review worthy - market signal",
                "count": len(report.get("review_worthy_market_signals", [])),
                "names": [row["name"] for row in report.get("review_worthy_market_signals", [])],
            },
            {
                "action": "Evidence gap queue",
                "count": len(report.get("evidence_gap_queue", [])),
                "names": [row["name"] for row in report.get("evidence_gap_queue", [])],
            },
        ],
        "caveats": report["caveats"],
    }


def render_source_yield_markdown(report: dict) -> str:
    assessment = report["goal_assessment"]
    status = "yes" if assessment["goal_reached"] else "no"
    lines = [
        "# Source Yield Validation",
        "",
        f"- Goal reached: {status}",
        f"- Assign Owner rows: {', '.join(assessment['assign_owner_names']) or 'none'}",
        f"- Assign Owner bar preserved: {'yes' if assessment['assign_owner_bar_preserved'] else 'no'}",
        f"- Net-new credible Review-Worthy rows: {assessment['net_new_review_worthy_count']} / {assessment['target_net_new_review_worthy_count']}",
        f"- Review-Worthy Market Signals: {len(report.get('review_worthy_market_signals', []))}",
        f"- Evidence Gap Queue rows: {len(report.get('evidence_gap_queue', []))}",
        "",
        "## Source-Yield Targets",
        "",
        "| Metric | Count | Target | Status |",
        "| --- | --- | --- | --- |",
    ]
    for metric, status_row in report.get("target_status", {}).items():
        target_parts = []
        if status_row.get("min") is not None:
            target_parts.append(f"min {status_row['min']}")
        if status_row.get("max") is not None:
            target_parts.append(f"max {status_row['max']}")
        lines.append(
            "| {metric} | {count} | {target} | {status} |".format(
                metric=metric.replace("_", " ").title(),
                count=status_row.get("count", 0),
                target=", ".join(target_parts) or "n/a",
                status=status_row.get("status", ""),
            )
        )
    lines.extend(
        [
            "",
        "## Review-Worthy Companies",
        "",
        "| Company | Domain | Action | Stage | Raised | Headcount | Source |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report["review_worthy_rows"]:
        lines.append(
            "| {name} | {domain} | {action} | {stage} | {raised} | {headcount} | {source_lane} |".format(
                name=str(row["name"]).replace("|", "/"),
                domain=str(row["domain"]).replace("|", "/"),
                action=str(row["action"]).replace("|", "/"),
                stage=str(row["stage"]).replace("|", "/"),
                raised=str(row["raised"]).replace("|", "/"),
                headcount=str(row["headcount"]).replace("|", "/"),
                source_lane=str(row["source_lane"]).replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Review-Worthy Market Signals",
            "",
            "| Signal | Theme | Sector | Score | 30d Stars | Why It Matters | Next Search |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("review_worthy_market_signals", []):
        lines.append(
            "| {name} | {theme} | {sector} | {score} | {stars_30d} | {why} | {search} |".format(
                name=str(row.get("name", "")).replace("|", "/"),
                theme=str(row.get("theme", "")).replace("|", "/"),
                sector=str(row.get("market_sector", "")).replace("|", "/"),
                score=str(row.get("market_signal_score", "")).replace("|", "/"),
                stars_30d=str(row.get("stars_30d", "")).replace("|", "/"),
                why=str(row.get("why_it_matters", "")).replace("|", "/"),
                search=str(row.get("suggested_company_search", "")).replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Evidence Gap Queue",
            "",
            "| Row | Source | Missing Evidence | Next Step | Promotion Target |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("evidence_gap_queue", []):
        lines.append(
            "| {name} | {source} | {gaps} | {next_step} | {target} |".format(
                name=str(row.get("name", "")).replace("|", "/"),
                source=str(row.get("source_lane", "")).replace("|", "/"),
                gaps=", ".join(str(gap).replace("|", "/") for gap in row.get("missing_evidence", [])[:4]),
                next_step=str(row.get("next_step", "")).replace("|", "/"),
                target=str(row.get("promotion_target", "")).replace("|", "/"),
            )
        )
    diversity = report.get("source_diversity", {})
    lines.extend(["", "## Source Diversity", ""])
    lines.append(
        "- Non-YC review-worthy rows: {non_yc}".format(
            non_yc=diversity.get("non_yc_review_worthy_count", 0)
        )
    )
    lines.append(
        "- Review-worthy lanes: {lanes}".format(
            lanes=", ".join(diversity.get("review_worthy_source_lanes", [])) or "none"
        )
    )
    for source, item in (diversity.get("raw_domain_resolution") or {}).items():
        lines.append(
            "- {source}: launches={launches}, resolved_domains={resolved}, unresolved_domains={unresolved}".format(
                source=source,
                launches=item.get("launches", 0),
                resolved=item.get("resolved_domains", 0),
                unresolved=item.get("unresolved_domains", 0),
            )
        )
    provider_decision = report.get("structured_provider_decision", {})
    lines.extend(["", "## Structured Provider Decision", ""])
    lines.append(f"- Status: {provider_decision.get('status', 'unknown')}")
    if provider_decision.get("best_unlock"):
        lines.append(f"- Best unlock: {provider_decision['best_unlock']}")
    for reason in provider_decision.get("reasons", []):
        lines.append(f"- Reason: {reason}")
    provider_trial = report.get("structured_provider_trial_summary", {})
    if provider_trial:
        lines.append(
            "- Trial: targets={targets}, hints={hints}, direct_access={direct}, manual_mode={manual}".format(
                targets=provider_trial.get("targets_enriched", 0),
                hints=provider_trial.get("targets_with_structured_hints", 0),
                direct=", ".join(provider_trial.get("direct_provider_access", [])) or "none",
                manual=", ".join(provider_trial.get("manual_mode_providers", [])) or "none",
            )
        )
    lines.extend(["", "## Source Health", ""])
    for item in report["source_health"]:
        lines.append(
            f"- {item['source']}: {item['status']}, fresh_items={item['fresh_items']}, duration_seconds={item['duration_seconds']}"
        )
    lines.extend(["", "## Caveats", ""])
    if report["caveats"]:
        lines.extend(f"- {caveat}" for caveat in report["caveats"])
    else:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def write_source_yield_outputs(
    run_dir: Path | str,
    *,
    target_review_worthy_count: int = 5,
    assign_owner_allowlist: tuple[str, ...] = DEFAULT_ASSIGN_OWNER_ALLOWLIST,
    packet_dir: Path | str | None = None,
    repeatability_run_dirs: list[Path | str] | None = None,
) -> dict:
    run_path = Path(run_dir)
    report = build_source_yield_validation_report(
        run_path,
        target_review_worthy_count=target_review_worthy_count,
        assign_owner_allowlist=assign_owner_allowlist,
    )
    weekly_focus = _read_json(run_path / "weekly-focus.json", {})
    packet = build_source_yield_decision_packet(report, weekly_focus if isinstance(weekly_focus, dict) else {})
    ledger_report = build_source_yield_ledger_action_report(report)
    packet_path = Path(packet_dir) if packet_dir is not None else run_path / "source-yield-decision-packet"

    report_json_path = run_path / "source-yield-validation-report.json"
    report_md_path = run_path / "source-yield-validation-report.md"
    _write_json(report_json_path, report)
    report_md_path.write_text(render_source_yield_markdown(report))
    _write_json(packet_path / "partner-decision-packet.json", packet)
    _write_json(packet_path / "ledger-action-report.json", ledger_report)
    (packet_path / "README.md").write_text(
        "# Source Yield Decision Packet\n\n"
        "This packet is the strict source-yield sprint decision view. It keeps Assign Owner limited to rows that cleared the weekly workflow gate.\n"
    )
    result = {
        "report_json": str(report_json_path),
        "report_markdown": str(report_md_path),
        "partner_decision_packet": str(packet_path / "partner-decision-packet.json"),
        "ledger_action_report": str(packet_path / "ledger-action-report.json"),
        "goal_reached": report["goal_assessment"]["goal_reached"],
    }
    if repeatability_run_dirs:
        repeatability = build_repeatability_validation_report(
            repeatability_run_dirs,
            target_review_worthy_count=target_review_worthy_count,
            assign_owner_allowlist=assign_owner_allowlist,
        )
        repeat_json_path = run_path / "source-yield-repeatability-report.json"
        repeat_md_path = run_path / "source-yield-repeatability-report.md"
        _write_json(repeat_json_path, repeatability)
        repeat_md_path.write_text(render_repeatability_markdown(repeatability))
        result["repeatability_report_json"] = str(repeat_json_path)
        result["repeatability_report_markdown"] = str(repeat_md_path)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--target-review-worthy-count", type=int, default=5)
    parser.add_argument("--assign-owner-allowlist", default=",".join(DEFAULT_ASSIGN_OWNER_ALLOWLIST))
    parser.add_argument("--packet-dir", default="")
    parser.add_argument("--repeatability-run-dir", action="append", default=[])
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    allowlist = tuple(name.strip() for name in args.assign_owner_allowlist.split(",") if name.strip())
    result = write_source_yield_outputs(
        args.run_dir,
        target_review_worthy_count=args.target_review_worthy_count,
        assign_owner_allowlist=allowlist or DEFAULT_ASSIGN_OWNER_ALLOWLIST,
        packet_dir=args.packet_dir or None,
        repeatability_run_dirs=args.repeatability_run_dir,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
