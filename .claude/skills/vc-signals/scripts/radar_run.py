#!/usr/bin/env python3
"""Weekly VC Signals radar orchestration helpers.

This script is intentionally deterministic: it gathers/filter evidence, merges
Attio context, and renders a partner-preview artifact. Claude still owns the
investor judgment and final synthesis.
"""

from __future__ import annotations

import json
import os
import re
import signal
import sys
import time
from inspect import Parameter, signature
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))

try:
    from attio import AttioClient, enrich_companies, get_access_token
except ImportError:  # pragma: no cover - only for damaged installs
    AttioClient = None
    enrich_companies = None
    get_access_token = None

try:
    from github_trending import run_trending
except ImportError:  # pragma: no cover - only for damaged installs
    run_trending = None

try:
    from last30days_adapter import check_availability as check_last30days_availability
    from last30days_adapter import run_query
except ImportError:  # pragma: no cover - only for damaged installs
    check_last30days_availability = None
    run_query = None

from radar_models import Candidate, EvidenceMetadata, FocusItem, RejectedSignal, SectorCoverage
from radar_company_discovery import (
    DiscoveryRunBudget,
    DiscoveryYieldTrialConfig,
    classify_discovery_source,
    collect_company_discovery,
)
from radar_scoring import score_and_tier
from radar_sources import classify_source_item
from radar_sector_intelligence import build_sector_intelligence
from radar_sector_classifier import classify_market_sector
from radar_partner_review import select_partner_review
from radar_render import render_weekly_brief
from radar_theme_signals import build_theme_signals
from radar_workbench import write_workbench_artifacts
from radar_history import apply_weekly_tags, load_candidate_history, save_candidate_history
from radar_enrichment import apply_candidate_enrichment, merge_source_enrichment
from identity_resolution import apply_identity_resolution
from metadata_loss import build_metadata_loss_report
from founder_team_verification import enrich_founder_team_verification, write_founder_team_verification_json
from owner_evidence import enrich_owner_evidence, write_owner_evidence_json
from owner_readiness import enrich_owner_readiness, write_owner_readiness_json
from hn_weekly_trial import HNLaunchTrialConfig, run_hn_launch_weekly_trial
from radar_oss import enrich_oss_candidate
from canonical_identity import canonicalize_identity
from radar_focus import (
    build_focus_item,
    build_weekly_focus_artifact,
    render_weekly_focus_markdown,
    write_feedback_scaffold,
    write_weekly_focus_json,
)


DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "radar_runs"
DEFAULT_SECTORS = ("devtools", "cybersecurity", "ai-infra", "vertical-ai", "data-infra", "oss")
SECTOR_CONFIG_PATH = Path(__file__).parent.parent / "config" / "sectors.json"
REDDIT_SOURCES_CONFIG_PATH = Path(__file__).parent.parent / "config" / "reddit_sources.json"

REPO_NOISE_TERMS = (
    "daily digest",
    "news radar",
    "ai ecosystem digest",
    "content aggregator",
    "beginner to pro",
    "course",
    "tutorial",
    "showcase",
    "example",
    "project configuration",
    "anthropics/",
    "claude-code-security-review",
    "macos",
    "installer iso",
    "paper recommendation",
    "arxiv",
    "gemini cli",
    "github/ai-moderator",
    "detects and tags spam",
    "curated suite",
    "esg data",
    "power bi dashboards",
    "azure data factory",
    "movie studio",
    "research fork",
    "adreno",
    "driver",
    "cloudflare worker",
    "awesome-",
    "readme stats",
    "yaml config",
    "clash yaml",
    "mihomo",
    "config files",
)

EVIDENCE_NOISE_TERMS = (
    "introducing claude",
    "most capable model",
    "[hiring]",
    "ugc creators",
    "digest",
    "content summary",
    "market research:",
    "competitive landscape",
    "moved source docs",
    "system prompts?",
    "statcast",
    "spam filter backend",
    "internal automation",
    "tech & ai news",
    "deepseek v4",
    "salesforce launches",
    "daily news rundown",
    "a complete guide on how to play",
    "black ops",
    "chemical families",
    "$200m+ funding",
    "emerges from stealth",
    "ask me anything",
    "dotadda wrote this",
    "github-actions[bot]",
    "auto-generated comment",
    "summarize by coderabbit",
)

GENERIC_EXTRACTED_NAMES = {
    "i",
    "ai",
    "tech",
    "market research",
    "deepseek v4",
    "salesforce",
    "add it support",
    "ai weekly news",
    "mozilla announces",
    "open source ai",
    "asserting american leadership",
    "free",
}

SECTOR_LABELS = {
    "devtools": "Devtools",
    "cybersecurity": "Cybersecurity",
    "ai-infra": "AI Infra",
    "vertical-ai": "Vertical AI",
    "data-infra": "Data Infra",
    "oss": "OSS",
}

THEME_KEYWORDS = (
    ("security", "AI agent security"),
    ("phishing", "AI agent security"),
    ("sre", "AI SRE"),
    ("on-call", "AI SRE"),
    ("runtime", "Agent runtime infrastructure"),
    ("mcp", "Agent runtime infrastructure"),
    ("workflow", "Vertical AI operations"),
    ("slack", "Vertical AI operations"),
    ("data", "AI data infrastructure"),
    ("eval", "Agent reliability and evals"),
    ("simulation", "Agent reliability and evals"),
)

INTEREST_KEYWORDS = (
    "agent",
    "security",
    "mcp",
    "sre",
    "on-call",
    "workflow",
    "regulated",
    "healthcare",
    "finance",
    "enterprise",
    "open source",
    "github",
)

CONSENSUS_TERMS = ("series c", "series d", "$1.5b", "$60b", "too late", "consensus")
DEFAULT_GITHUB_TIMEOUT_SECONDS = 5 * 60


class GithubCollectionTimeout(TimeoutError):
    pass


def _label(score: int) -> str:
    if score >= 70:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"


def run_synthesis(**kwargs):
    from radar_synthesis import run_synthesis as _run_synthesis

    return _run_synthesis(**kwargs)


def _blob(*parts: object) -> str:
    values = []
    for part in parts:
        if isinstance(part, list):
            values.extend(str(item) for item in part)
        elif part is not None:
            values.append(str(part))
    return " ".join(values).lower()


def is_repo_noise(repo: dict) -> bool:
    """True for repo results that should not enter the partner radar."""
    text = _blob(repo.get("full_name"), repo.get("description"), repo.get("topics", []))
    return any(term in text for term in REPO_NOISE_TERMS)


def is_evidence_noise(item: dict) -> bool:
    """True for evidence items that are likely social/model/news noise."""
    if (item.get("source") or "").lower() in {"grounding", "web"} and classify_discovery_source(item) in {
        "publisher_article",
        "directory_page",
        "content_platform",
    }:
        return True
    title = (item.get("title") or "").strip()
    if re.match(r"^(feat|fix|chore|docs|refactor|test|ci|build)(\\(.+\\))?:", title.lower()):
        return True
    if len(title.split()) <= 2 and not any(marker in title.lower() for marker in ("ai", "mcp", "llm", "sre")):
        return True
    text = _blob(title, item.get("snippet"), item.get("container"), item.get("author"))
    return any(term in text for term in EVIDENCE_NOISE_TERMS)


def filter_repos(repos: list[dict]) -> list[dict]:
    return [repo for repo in repos if not is_repo_noise(repo)]


def filter_evidence(items: list[dict]) -> list[dict]:
    return [item for item in items if not is_evidence_noise(item)]


def _source_health(source: str, status: str, *, fresh_items: int = 0, duration_seconds: float = 0.0, warnings: list[str] | None = None) -> dict:
    return {
        "source": source,
        "status": status,
        "fresh_items": fresh_items,
        "duration_seconds": round(duration_seconds, 2),
        "warnings": list(warnings or []),
    }


def _github_timeout_handler(signum, frame):  # pragma: no cover - exercised through alarm behavior
    raise GithubCollectionTimeout("github_collection_timeout")


def _run_github_trending_with_timeout(*, limit: int, timeout_seconds: int | None) -> tuple[dict, dict]:
    if not run_trending:
        return {"repos": [], "warnings": ["GitHub trending unavailable"]}, _source_health(
            "github",
            "skipped_unavailable",
            warnings=["GitHub trending unavailable"],
        )
    if limit <= 0:
        return {"repos": [], "warnings": ["GitHub collection skipped by github_limit=0"]}, _source_health(
            "github",
            "skipped_disabled",
            warnings=["GitHub collection skipped by github_limit=0"],
        )

    started = time.monotonic()
    previous_handler = None
    try:
        if timeout_seconds and hasattr(signal, "SIGALRM"):
            previous_handler = signal.getsignal(signal.SIGALRM)
            signal.signal(signal.SIGALRM, _github_timeout_handler)
            signal.alarm(max(1, int(timeout_seconds)))
        result = run_trending("all", limit=limit)
        duration = time.monotonic() - started
        return result, _source_health(
            "github",
            "complete",
            fresh_items=len(result.get("repos", [])),
            duration_seconds=duration,
            warnings=result.get("warnings", []),
        )
    except GithubCollectionTimeout:
        duration = time.monotonic() - started
        warning = f"GitHub collection timed out after {timeout_seconds}s"
        return {"repos": [], "warnings": [warning], "error": warning}, _source_health(
            "github",
            "partial_timeout",
            fresh_items=0,
            duration_seconds=duration,
            warnings=[warning],
        )
    finally:
        if timeout_seconds and hasattr(signal, "SIGALRM"):
            signal.alarm(0)
            if previous_handler is not None:
                signal.signal(signal.SIGALRM, previous_handler)


def load_sector_config(path: Path = SECTOR_CONFIG_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def load_reddit_sources_config(path: Path = REDDIT_SOURCES_CONFIG_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _flatten_seed_queries(sector_config: dict) -> list[str]:
    queries = list(sector_config.get("discovery_queries", []))
    for subcategory in sector_config.get("subcategories", {}).values():
        queries.extend(subcategory.get("seed_queries", []))
    return queries


def _dedupe_items(items: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for item in items:
        key = item.get("url") or item.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _sources(*base: str, social_available: bool = False, vertical_social: bool = False) -> str:
    sources = list(base)
    if social_available:
        sources.append("youtube")
        if vertical_social:
            sources.extend(["tiktok", "instagram", "threads"])
    return ",".join(dict.fromkeys(sources))


def _reddit_pain_query(sector_slug: str, reddit_config: dict, *, lookback_days: int) -> dict | None:
    config = reddit_config.get(sector_slug, {})
    primary = config.get("primary", [])
    secondary = config.get("secondary", [])
    pain_queries = config.get("pain_queries", [])
    if not primary and not pain_queries:
        return None
    topic = " OR ".join(pain_queries[:3]) if pain_queries else f"{sector_slug} practitioner pain"
    return {
        "kind": "reddit_pain",
        "topic": topic,
        "sources": "reddit",
        "subreddits": ",".join(dict.fromkeys(primary + secondary)),
        "lookback_days": lookback_days,
        "candidate_eligible": False,
    }


def build_sector_collection_queries(
    sector_slug: str,
    sector_config: dict,
    *,
    grounded_available: bool = False,
    social_available: bool = False,
    lookback_days: int = 30,
    max_queries: int = 3,
) -> list[dict]:
    """Build a small, Marathon-focused query set for one sector."""
    config = sector_config.get(sector_slug, {}) if sector_slug in sector_config else sector_config
    display_name = config.get("display_name", SECTOR_LABELS.get(sector_slug, sector_slug))
    reddit_pain = _reddit_pain_query(sector_slug, load_reddit_sources_config(), lookback_days=lookback_days)
    queries: list[dict] = []
    if reddit_pain:
        queries.append(reddit_pain)
    if not grounded_available:
        if sector_slug == "vertical-ai":
            queries.extend([
                {
                    "kind": "vertical_workflow_social",
                    "topic": f"{display_name} AI workflow demos operator pain SMB automation founder product demo",
                    "sources": _sources("reddit", "hackernews", social_available=social_available, vertical_social=True),
                    "lookback_days": lookback_days,
                },
                {
                    "kind": "vertical_hn",
                    "topic": f"Show HN {display_name} AI agent workflow startup",
                    "sources": _sources("hackernews", "github", social_available=social_available),
                    "lookback_days": lookback_days,
                },
                {
                    "kind": "vertical_github",
                    "topic": f"{display_name} AI workflow automation GitHub agent",
                    "sources": _sources("github", "hackernews", social_available=social_available),
                    "lookback_days": lookback_days,
                },
            ])
            return queries[:max_queries]
        if sector_slug == "oss":
            queries.extend([
                {
                    "kind": "oss_show",
                    "topic": "Show HN open source AI agent MCP security developer tool",
                    "sources": _sources("hackernews", "github", social_available=social_available),
                    "lookback_days": lookback_days,
                },
                {
                    "kind": "oss_github",
                    "topic": "open source AI agent infrastructure GitHub stars MCP security",
                    "sources": _sources("github", "hackernews", social_available=social_available),
                    "lookback_days": lookback_days,
                },
                {
                    "kind": "oss_security",
                    "topic": "open source AI security scanner MCP agent tool GitHub",
                    "sources": _sources("github", "hackernews", social_available=social_available),
                    "lookback_days": lookback_days,
                },
            ])
            return queries[:max_queries]
        queries.extend([
            {
                "kind": "conversation",
                "topic": f"Show HN {display_name} AI startup developer tool open source",
                "sources": _sources("hackernews", "github", social_available=social_available),
                "lookback_days": lookback_days,
            },
            {
                "kind": "hn_show",
                "topic": f"Launch HN Show HN {display_name} startup AI infrastructure",
                "sources": _sources("hackernews", "github", social_available=social_available),
                "lookback_days": lookback_days,
            },
            {
                "kind": "github_signal",
                "topic": f"{display_name} AI agent infrastructure open source GitHub stars",
                "sources": _sources("github", "hackernews", social_available=social_available),
                "lookback_days": lookback_days,
            },
        ])
        return queries[:max_queries]

    seed_queries = _flatten_seed_queries(config)
    conversation_topic = (
        seed_queries[0]
        if seed_queries
        else f"{display_name} startups Seed Series A Series B emerging traction"
    )
    company_queries = config.get("company_discovery_queries", {})
    if grounded_available and company_queries:
        for kind, key in (
            ("yc_company", "yc_queries"),
            ("funding_company", "funding_queries"),
            ("company_launch", "company_launch_queries"),
            ("founder_company", "founder_queries"),
            ("technical_blog_company", "technical_blog_queries"),
        ):
            if len(queries) >= max_queries:
                break
            for topic in company_queries.get(key, []):
                if len(queries) >= max_queries:
                    break
                queries.append({
                    "kind": kind,
                    "topic": topic,
                    "sources": _sources("grounding", "hackernews", "github", social_available=social_available),
                    "web_backend": "auto",
                    "lookback_days": lookback_days,
                })
    elif grounded_available:
        queries.extend([
            {
                "kind": "yc_company",
                "topic": f"site:ycombinator.com/companies {display_name} AI startups Seed Series A Series B",
                "sources": _sources("grounding", "hackernews", "github", social_available=social_available),
                "web_backend": "auto",
                "lookback_days": lookback_days,
            },
            {
                "kind": "company_discovery",
                "topic": f"{display_name} startups Seed Series A Series B emerging companies funding founder traction",
                "sources": _sources("grounding", "reddit", "hackernews", "github", social_available=social_available, vertical_social=(sector_slug == "vertical-ai")),
                "web_backend": "auto",
                "lookback_days": lookback_days,
            },
        ])

    if len(queries) < max_queries:
        queries.append({
            "kind": "conversation",
            "topic": f"{conversation_topic} Seed Series A Series B founder customer traction",
            "sources": _sources("reddit", "hackernews", "github", social_available=social_available),
            "lookback_days": lookback_days,
        })

    return queries[:max_queries]


def _grounded_search_available() -> bool:
    if not check_last30days_availability:
        return False
    try:
        availability = check_last30days_availability()
    except Exception:
        return False
    return bool((availability.get("source_capabilities") or {}).get("grounded"))


def _social_search_available() -> bool:
    if not check_last30days_availability:
        return False
    try:
        availability = check_last30days_availability()
    except Exception:
        return False
    return bool((availability.get("source_capabilities") or {}).get("social"))


def parse_sectors_arg(value: str | None) -> tuple[str, ...]:
    if not value or value.strip().lower() == "all":
        return DEFAULT_SECTORS
    sectors = tuple(sector.strip() for sector in value.split(",") if sector.strip())
    return sectors or DEFAULT_SECTORS


def infer_theme(text: str) -> str:
    lower = text.lower()
    for keyword, theme in THEME_KEYWORDS:
        if keyword in lower:
            return theme
    return "Emerging technical signal"


def _extract_name_from_title(title: str) -> str | None:
    cleaned = title.strip()
    for prefix in ("Show HN:", "Launch HN:", "Ask HN:"):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()

    stop_words = (" stops ", " is ", " for ", " – ", " - ", ":", " with ", " raises ", " builds ")
    for stop in stop_words:
        if stop in cleaned:
            cleaned = cleaned.split(stop, 1)[0].strip()
            break

    match = re.search(r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,2}(?:\s+AI)?)\b", cleaned)
    if not match:
        return None
    name = match.group(1).strip()
    if name.lower() in GENERIC_EXTRACTED_NAMES:
        return None
    return name


def _normalize_candidate_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if not host:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def _yc_slug_from_url(url: str) -> str | None:
    parsed = urlparse(url or "")
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host != "ycombinator.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "companies":
        return parts[1]
    return None


def _name_from_slug(slug: str) -> str:
    words = [word for word in re.split(r"[-_]+", slug) if word]
    return " ".join("AI" if word.lower() == "ai" else word.capitalize() for word in words)


def _candidate_name_from_item(item: dict) -> str | None:
    structured_name = (item.get("company_name") or item.get("name") or "").strip()
    if structured_name and structured_name.lower() not in GENERIC_EXTRACTED_NAMES:
        return structured_name

    slug = _yc_slug_from_url(item.get("url", ""))
    if slug:
        return _name_from_slug(slug)

    return _extract_name_from_title(item.get("title", ""))


def _is_github_issue_or_pr(item: dict) -> bool:
    if (item.get("source") or "").lower() != "github":
        return False
    url = item.get("url") or ""
    return "/issues/" in url or "/pull/" in url


def _candidate_domain_from_item(item: dict) -> str:
    domain = (item.get("domain") or "").strip().lower()
    if domain:
        return domain.removeprefix("www.")

    url = item.get("url", "")
    slug = _yc_slug_from_url(url)
    if slug:
        return f"{slug}.com"

    domain = _domain_from_url(url)
    if domain in {"news.ycombinator.com", "reddit.com", "github.com", "medium.com", "substack.com"}:
        return ""
    return domain


def _profile_url(item: dict, *keys: str) -> str:
    for key in keys:
        value = (item.get(key) or "").strip()
        if value:
            return value
    return ""


def _founder_profiles_from_item(item: dict) -> list[dict]:
    founders = item.get("founders") or item.get("founder_profiles") or []
    profiles = []
    if isinstance(founders, list):
        for founder in founders:
            if not isinstance(founder, dict):
                continue
            name = (founder.get("name") or "").strip()
            linkedin = _profile_url(founder, "linkedin", "linkedin_url")
            x_url = _profile_url(founder, "x", "x_url", "twitter", "twitter_url")
            if name or linkedin or x_url:
                profiles.append({"name": name, "linkedin": linkedin, "x": x_url})
    return profiles


def _merge_candidate(existing: dict, candidate: dict) -> None:
    existing["source_count"] = int(existing.get("source_count") or 1) + 1
    source = candidate.get("source", "")
    if source:
        sources = existing.setdefault("sources", [existing.get("source", "")])
        if source not in sources:
            sources.append(source)
    if not existing.get("domain") and candidate.get("domain"):
        existing["domain"] = candidate["domain"]
    for key in ("company_linkedin", "company_x"):
        if not existing.get(key) and candidate.get(key):
            existing[key] = candidate[key]
    if candidate.get("founder_profiles"):
        profiles = existing.setdefault("founder_profiles", [])
        seen_profiles = {(profile.get("name"), profile.get("linkedin"), profile.get("x")) for profile in profiles}
        for profile in candidate["founder_profiles"]:
            key = (profile.get("name"), profile.get("linkedin"), profile.get("x"))
            if key not in seen_profiles:
                profiles.append(profile)
                seen_profiles.add(key)
    existing_engagement = existing.setdefault("engagement", {})
    for key, value in (candidate.get("engagement") or {}).items():
        if isinstance(value, int):
            existing_engagement[key] = int(existing_engagement.get(key) or 0) + value
        elif key not in existing_engagement:
            existing_engagement[key] = value


def extract_company_candidates(evidence: dict) -> list[dict]:
    """Extract rough company candidates from raw evidence items."""
    candidates_by_key: dict[str, dict] = {}
    for sector_slug, sector_payload in evidence.get("last30days", {}).items():
        sector = SECTOR_LABELS.get(sector_slug, sector_slug)
        for item in filter_evidence(sector_payload.get("items", [])):
            if _is_github_issue_or_pr(item) and not item.get("company_name"):
                continue
            title = item.get("title", "")
            name = _candidate_name_from_item(item)
            key = _normalize_candidate_key(name or "")
            if not name or name.lower() in GENERIC_EXTRACTED_NAMES or not key:
                continue
            text = _blob(title, item.get("snippet"))
            source = item.get("url", "")
            candidate = {
                "name": name,
                "domain": _candidate_domain_from_item(item),
                "sector": sector,
                "theme": infer_theme(text),
                "why_on_radar": title,
                "why_this_may_be_noise": "Extracted from public chatter; verify company, customer pull, and funding stage.",
                "source": source,
                "sources": [source] if source else [],
                "source_count": 1,
                "engagement": item.get("engagement", {}),
                "action": "assign owner",
            }
            company_linkedin = _profile_url(item, "company_linkedin", "linkedin_url", "linkedin")
            company_x = _profile_url(item, "company_x", "x_url", "twitter_url", "twitter")
            founder_profiles = _founder_profiles_from_item(item)
            if company_linkedin:
                candidate["company_linkedin"] = company_linkedin
            if company_x:
                candidate["company_x"] = company_x
            if founder_profiles:
                candidate["founder_profiles"] = founder_profiles
            if key in candidates_by_key:
                _merge_candidate(candidates_by_key[key], candidate)
            else:
                candidates_by_key[key] = candidate
    return list(candidates_by_key.values())


def score_candidate(candidate: dict) -> dict:
    """Apply an explainable first-pass VC scoring rubric."""
    text = _blob(
        candidate.get("name"),
        candidate.get("sector"),
        candidate.get("theme"),
        candidate.get("why_on_radar"),
        candidate.get("why_this_may_be_noise"),
    )
    interest = 35
    evidence = 25

    interest += min(30, sum(5 for keyword in INTEREST_KEYWORDS if keyword in text))
    source_count = int(candidate.get("source_count") or 0)
    evidence += min(25, source_count * 10)

    stars_30d = int(candidate.get("github_stars_30d") or 0)
    if stars_30d >= 150:
        interest += 15
        evidence += 15
    elif stars_30d >= 50:
        interest += 10
        evidence += 10

    engagement = candidate.get("engagement") or {}
    discussion = (
        engagement.get("comments", 0)
        or engagement.get("num_comments", 0)
        or engagement.get("points", 0)
        or engagement.get("score", 0)
    )
    if discussion:
        evidence += min(15, int(discussion) // 5)

    if candidate.get("attio_status") == "no_match":
        interest += 5
    if candidate.get("attio_status") in {"active", "passed"}:
        interest -= 5
    if any(term in text for term in CONSENSUS_TERMS):
        interest -= 25

    interest = max(0, min(100, interest))
    evidence = max(0, min(100, evidence))
    out = candidate.copy()
    out["investment_interest_score"] = interest
    out["evidence_confidence_score"] = evidence
    out["investment_interest"] = _label(interest)
    out["evidence_confidence"] = _label(evidence)
    return out


def rank_candidates(candidates: list[dict]) -> list[dict]:
    return sorted(
        candidates,
        key=lambda c: (c.get("investment_interest_score", 0), c.get("evidence_confidence_score", 0)),
        reverse=True,
    )


def merge_attio_context(companies: list[dict], attio_client=None) -> list[dict]:
    """Merge Attio match fields into companies, preserving existing fields."""
    def is_oss_project(company: dict) -> bool:
        sector = (company.get("sector") or "").lower()
        source_lane = (company.get("source_lane") or "").lower()
        candidate_type = (company.get("candidate_type") or "").lower()
        evidence_role = (company.get("evidence_role") or "").lower()
        return (
            "oss" in sector
            or source_lane == "oss"
            or candidate_type == "oss_project"
            or evidence_role == "oss_project"
        )

    def should_skip_attio(company: dict) -> bool:
        name = company.get("name") or ""
        return is_oss_project(company) and "/" in name and not company.get("domain")

    def skipped(company: dict) -> dict:
        return {
            **company,
            "attio_status": company.get("attio_status", "no_match"),
            "action": company.get("action", "watch"),
        }

    if not attio_client or not enrich_companies:
        return [
            skipped(company) if should_skip_attio(company) else {
                **company,
                "attio_status": company.get("attio_status", "unknown"),
                "action": company.get("action", company.get("attio_action", "monitor only")),
            }
            for company in companies
        ]

    enriched = []
    for company in companies:
        if should_skip_attio(company):
            enriched.append(skipped(company))
        else:
            enriched.extend(enrich_companies([company], attio_client))

    for company in enriched:
        existing_action = company.get("action")
        preserve_oss_action = existing_action and is_oss_project(company)
        preserve_late_label = existing_action == "likely too late"
        if preserve_oss_action or preserve_late_label:
            company["action"] = existing_action
        elif company.get("attio_action"):
            company["action"] = company["attio_action"]
        else:
            company.setdefault("action", "monitor only")
    return enriched


def build_partner_candidates(
    *,
    company_seeds: list[dict],
    repos: list[dict] | None = None,
    limit: int = 15,
) -> list[dict]:
    """Combine hand/LLM company candidates with high-quality OSS candidates."""
    candidates = []
    seen = set()

    for company in company_seeds:
        name = company.get("name")
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        candidates.append(company.copy())

    for repo in filter_repos(repos or []):
        name = repo.get("full_name")
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        velocity = repo.get("velocity", {})
        why = repo.get("description") or "Fast-growing OSS project."
        if velocity.get("stars_last_30d") is not None:
            why = f"{why} +{velocity.get('stars_last_30d')} stars in 30d."
        candidates.append({
            "name": name,
            "domain": "",
            "sector": "OSS",
            "theme": "OSS signal",
            "investment_interest": "Medium",
            "evidence_confidence": "Medium",
            "why_on_radar": why,
            "why_this_may_be_noise": "Repo traction may not map to company formation or buyer urgency.",
            "source": repo.get("url", ""),
            "founder_profiles": [{"name": name.split("/", 1)[0], "github": repo.get("url", "").rsplit("/", 1)[0]}],
            "action": "watch",
        })

    return candidates[:limit]


def build_scored_preview_from_evidence(
    evidence: dict,
    *,
    attio_client=None,
    limit: int = 15,
) -> list[dict]:
    """Extract, enrich, score, and rank preview candidates from raw evidence."""
    extracted = extract_company_candidates(evidence)
    repo_candidates = build_partner_candidates(company_seeds=[], repos=evidence.get("github", []), limit=limit)
    candidates = extracted + repo_candidates
    candidates = merge_attio_context(candidates, attio_client)
    scored = [score_candidate(candidate) for candidate in candidates]
    scored = [candidate for candidate in scored if candidate.get("investment_interest_score", 0) >= 45]
    return rank_candidates(scored)[:limit]


def render_partner_preview(
    companies: list[dict],
    themes: list[str],
    *,
    output_path: Path | None = None,
    run_date: str | None = None,
) -> str:
    """Render a compact Marathon partner preview and optionally save it."""
    run_date = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "# VC Signals Radar",
        "",
        f"**Run date:** {run_date}",
        "**Artifact:** Marathon Partner Preview",
        "",
        "## Marathon Partner Preview",
        "",
    ]
    if themes:
        lines.append("### Themes")
        lines.extend(f"- **{theme}**" for theme in themes)
        lines.append("")

    lines.extend([
        "### Top Candidates",
        "",
        "| Company | Sector | Theme | Interest | Evidence | Attio | Action | LinkedIn | Founders | X | Why On Radar | Why This May Be Noise | Source |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ])
    for company in companies:
        lines.append(
            "| {name} | {sector} | {theme} | {interest} | {evidence} | {attio} | {action} | {linkedin} | {founders} | {x_url} | {why} | {noise} | {source} |".format(
                name=company.get("name", ""),
                sector=company.get("sector", ""),
                theme=company.get("theme") or company.get("primary_theme", ""),
                interest=company.get("investment_interest", ""),
                evidence=company.get("evidence_confidence", ""),
                attio=company.get("attio_status", "unknown"),
                action=company.get("action") or company.get("attio_action", ""),
                linkedin=company.get("company_linkedin", ""),
                founders=_format_founders(company.get("founder_profiles", [])),
                x_url=company.get("company_x", ""),
                why=company.get("why_on_radar", ""),
                noise=company.get("why_this_may_be_noise", ""),
                source=company.get("source") or company.get("evidence_url", ""),
            )
        )

    by_sector: dict[str, list[dict]] = {}
    for company in companies:
        by_sector.setdefault(company.get("sector", "Unknown"), []).append(company)

    lines.append("")
    lines.append("## Sector Notes")
    for sector, sector_companies in by_sector.items():
        lines.append("")
        lines.append(f"### {sector}")
        for company in sector_companies:
            lines.append(f"- **{company.get('name', '')}**: {company.get('why_on_radar', '')}")

    markdown = "\n".join(lines).rstrip() + "\n"
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown)
    return markdown


def _format_founders(founders: list[dict]) -> str:
    formatted = []
    for founder in founders or []:
        name = founder.get("name") or "Founder"
        links = [founder.get("linkedin"), founder.get("x"), founder.get("github")]
        links = [link for link in links if link]
        if links:
            formatted.append(f"{name}: {', '.join(links)}")
        else:
            formatted.append(name)
    return "; ".join(formatted)


def _compact_evidence_metadata(candidate_key: str, item: dict) -> dict:
    metadata = EvidenceMetadata(
        candidate_key=candidate_key,
        source_url=item.get("url", ""),
        source=item.get("source", ""),
        title=item.get("title") or item.get("full_name") or item.get("name") or "",
        author=item.get("author", ""),
        published_at=item.get("published_at", ""),
        container=item.get("container", ""),
        query_kind=item.get("query_kind", ""),
        query_topic=item.get("query_topic", ""),
        outbound_url=item.get("outbound_url") or item.get("resolved_url") or "",
        domain=item.get("domain") or item.get("website_domain") or "",
        owner_name=item.get("owner_name", ""),
        owner_type=item.get("owner_type", ""),
        topics=list(item.get("topics") or []),
        description=item.get("description") or item.get("snippet") or "",
        homepage=item.get("homepage") or item.get("website") or "",
    )
    return metadata.to_dict()


def _candidate_from_signal(signal) -> Candidate | None:
    item = signal.metadata or {}
    name = None
    if signal.role == "oss_project":
        parsed = urlparse(signal.url or "")
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and "github.com" in parsed.netloc:
            name = "/".join(path_parts[:2])
    if not name:
        name = _candidate_name_from_item(item)
    if not name:
        name = _extract_name_from_title(signal.title)
    if not name:
        return None

    source = signal.url or item.get("url", "")
    velocity = item.get("velocity", {}) if isinstance(item.get("velocity"), dict) else {}
    why = signal.title
    if velocity.get("stars_last_30d") is not None:
        why = f"{item.get('description') or signal.title} +{velocity.get('stars_last_30d')} stars in 30d."

    domain = _candidate_domain_from_item(item)
    source_headline = item.get("source_headline") or item.get("title") or signal.title
    identity = canonicalize_identity(
        name=item.get("display_name") or item.get("canonical_name") or name,
        domain=domain,
        candidate_type=signal.role,
        identity_type=item.get("identity_type", ""),
        raw_title=source_headline,
        source_headline=source_headline,
    )

    candidate = Candidate(
        name=identity["display_name"] or name,
        canonical_name=identity["canonical_name"],
        display_name=identity["display_name"],
        source_headline=identity["source_headline"],
        tagline=identity["tagline"],
        domain=domain,
        sector=SECTOR_LABELS.get(signal.sector, signal.sector),
        theme=infer_theme(f"{signal.title} {signal.text}"),
        source=source,
        sources=[source] if source else [],
        source_count=1,
        candidate_type=signal.role,
        why_on_radar=why,
        why_this_may_be_noise=item.get("why_this_may_be_noise") or "Needs verification across stronger company/founder/customer evidence.",
        company_linkedin=_profile_url(item, "company_linkedin", "linkedin_url", "linkedin"),
        company_x=_profile_url(item, "company_x", "x_url", "twitter_url", "twitter"),
        founder_profiles=_founder_profiles_from_item(item),
        engagement=item.get("engagement", {}),
        action=item.get("action") or ("watch" if signal.role == "oss_project" else "assign owner"),
        maturity_status=item.get("maturity_status") or "unknown",
        maturity_basis=list(item.get("maturity_basis") or []),
        maturity_evidence_urls=list(item.get("maturity_evidence_urls") or []),
        category_anchor=bool(item.get("category_anchor")),
        consensus_risk_reason=item.get("consensus_risk_reason", ""),
        lead_route=item.get("lead_route") or "research_deeper",
    )
    source_lane = item.get("source_lane") or ("OSS" if signal.role == "oss_project" else signal.source)
    sector_classification = classify_market_sector(
        title=name,
        text=_blob(signal.title, signal.text, item.get("description"), item.get("topics", [])),
        source_lane=source_lane,
    )
    candidate.market_sector = sector_classification.market_sector
    candidate.source_lane = source_lane
    candidate.evidence_role = signal.role
    candidate.sector_confidence = sector_classification.sector_confidence
    candidate.sector_reason = sector_classification.sector_reason
    candidate.evidence_metadata = [_compact_evidence_metadata(candidate.stable_key or candidate.name, item)]
    if candidate.market_sector != "Unclassified":
        candidate.sector = candidate.market_sector
    candidate = merge_source_enrichment(candidate, item)
    return enrich_oss_candidate(candidate, item)


def build_signals_from_evidence(evidence: dict) -> dict:
    signals = []
    coverage = {}

    for sector, payload in evidence.get("last30days", {}).items():
        sector_signals = []
        for item in filter_evidence(payload.get("items", [])):
            signal = classify_source_item(sector=sector, item=item)
            signals.append(signal)
            sector_signals.append(signal)
        coverage[sector] = SectorCoverage(
            sector=sector,
            raw_signals=len(sector_signals),
            reason="No candidate-eligible signals yet." if not any(signal.can_create_candidate for signal in sector_signals) else "",
        )

    github_signals = []
    for repo in filter_repos(evidence.get("github", [])):
        item = {
            **repo,
            "source": "github",
            "title": repo.get("full_name", ""),
            "url": repo.get("url", ""),
            "description": repo.get("description", ""),
        }
        signal = classify_source_item(sector="oss", item=item)
        signals.append(signal)
        github_signals.append(signal)
    if github_signals:
        existing = coverage.get("oss")
        if existing:
            existing.raw_signals += len(github_signals)
            if any(signal.can_create_candidate for signal in github_signals):
                existing.reason = ""
        else:
            coverage["oss"] = SectorCoverage(sector="oss", raw_signals=len(github_signals), reason="")

    discovery_signals = []
    for item in _filter_company_discovery_items(evidence.get("company_discovery", {}).get("items", [])):
        sector = item.get("sector") or _sector_slug_from_label(item.get("market_sector")) or "company-discovery"
        signal = classify_source_item(sector=sector, item=item)
        signals.append(signal)
        discovery_signals.append(signal)
    for sector in sorted({signal.sector for signal in discovery_signals if signal.sector}):
        sector_items = [signal for signal in discovery_signals if signal.sector == sector]
        existing = coverage.get(sector)
        if existing:
            existing.raw_signals += len(sector_items)
            if any(signal.can_create_candidate for signal in sector_items):
                existing.reason = ""
        else:
            coverage[sector] = SectorCoverage(sector=sector, raw_signals=len(sector_items), reason="")

    return {"signals": signals, "coverage": coverage}


def _sector_slug_from_label(label: str | None) -> str:
    normalized = (label or "").strip().lower()
    for slug, sector_label in SECTOR_LABELS.items():
        if normalized == sector_label.lower():
            return slug
    return normalized.replace(" ", "-") if normalized else ""


def _filter_company_discovery_items(items: list[dict]) -> list[dict]:
    kept = []
    for item in items:
        has_structured_company = bool((item.get("company_name") or item.get("name") or "").strip()) and bool(
            (item.get("domain") or item.get("website") or item.get("url") or "").strip()
        )
        if has_structured_company or not is_evidence_noise(item):
            kept.append(item)
    return kept


def _slug_id(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "unknown"


def _category_context_focus_items_from_company_discovery(company_discovery: dict) -> list[FocusItem]:
    items: list[FocusItem] = []
    seen: set[str] = set()
    for lead in company_discovery.get("accepted_leads", []) or []:
        if not isinstance(lead, dict):
            continue
        if not (lead.get("category_anchor") or lead.get("lead_route") in {"category_context", "monitor_only"}):
            continue
        domain = lead.get("domain") or _domain_from_url(lead.get("source_url", ""))
        identity = canonicalize_identity(
            name=lead.get("display_name") or lead.get("canonical_name") or lead.get("name") or lead.get("company_name") or lead.get("raw_title") or "Unknown",
            domain=domain,
            candidate_type=lead.get("candidate_type") or "",
            raw_title=lead.get("raw_title") or "",
            source_headline=lead.get("source_headline") or lead.get("raw_title") or "",
        )
        name = identity["display_name"] or "Unknown"
        key = domain or name
        item_id = _slug_id(f"category-context-{key}")
        if item_id in seen:
            continue
        seen.add(item_id)
        source_url = lead.get("source_url") or ""
        evidence_urls = [
            source_url,
            *(lead.get("supporting_evidence_urls") or []),
            lead.get("official_domain_verification_url") or "",
            *(lead.get("maturity_evidence_urls") or []),
        ]
        evidence_urls = list(dict.fromkeys(url for url in evidence_urls if url))
        movement = lead.get("movement") or lead.get("query_theme") or "Category context"
        sector = lead.get("market_sector") or "Company Discovery"
        items.append(
            FocusItem(
                id=item_id,
                name=name,
                canonical_name=identity["canonical_name"],
                display_name=identity["display_name"],
                source_headline=identity["source_headline"],
                tagline=identity["tagline"],
                company_domain=domain,
                market_movement_id=_slug_id(f"{sector}-{movement}"),
                market_movement=movement,
                market_sector=sector,
                why_focus_this_week=lead.get("why_on_radar") or lead.get("raw_snippet") or lead.get("raw_title") or "",
                who_is_talking=["Grounded web evidence"],
                talker_types=["unknown"],
                talker_type_confidence="Low",
                evidence_snapshot=[lead.get("why_on_radar") or lead.get("raw_snippet") or lead.get("raw_title") or ""],
                evidence_urls=evidence_urls,
                attio_status="unknown",
                identity_type=lead.get("candidate_type") or "verified_company",
                recommended_action="Monitor only",
                evidence_confidence_score=70 if domain else 45,
                company_identity_quality_score=90 if domain else 45,
                company_identity_quality_basis=list(lead.get("verification_basis") or []),
                focus_priority_basis=["category_context_from_company_discovery"],
                actionability_basis=["category_context_not_owner_action"],
                market_movement_basis=list(lead.get("movement_assignment_basis") or []),
                noise_risk_score=60,
                consensus_risk_score=90 if lead.get("likely_too_late") or lead.get("category_anchor") else 55,
                consensus_risk_basis=list(lead.get("maturity_basis") or []),
                movement_assignment_method="backtrace",
                movement_assignment_confidence="Medium",
                movement_assignment_evidence_url=evidence_urls[0] if evidence_urls else "",
                why_this_may_be_noise=lead.get("why_this_may_be_noise") or lead.get("consensus_risk_reason") or "",
                skepticism_events=[lead.get("why_this_may_be_noise") or lead.get("consensus_risk_reason") or ""],
                source_candidate_id=lead.get("query_id") or item_id,
                maturity_status=lead.get("maturity_status") or "unknown",
                maturity_basis=list(lead.get("maturity_basis") or []),
                maturity_evidence_urls=list(lead.get("maturity_evidence_urls") or []),
                category_anchor=bool(lead.get("category_anchor")),
                consensus_risk_reason=lead.get("consensus_risk_reason") or "",
                lead_route=lead.get("lead_route") or "category_context",
            )
        )
    return items


def _merge_candidate_model(existing: Candidate, candidate: Candidate) -> None:
    existing.source_count += 1
    if candidate.source and candidate.source not in existing.sources:
        existing.sources.append(candidate.source)
    existing_metadata_keys = {
        (metadata.get("source_url"), metadata.get("title"), metadata.get("outbound_url"))
        for metadata in existing.evidence_metadata
        if isinstance(metadata, dict)
    }
    for metadata in candidate.evidence_metadata:
        if not isinstance(metadata, dict):
            continue
        key = (metadata.get("source_url"), metadata.get("title"), metadata.get("outbound_url"))
        if key not in existing_metadata_keys:
            existing.evidence_metadata.append(metadata)
            existing_metadata_keys.add(key)
    if not existing.domain and candidate.domain:
        existing.domain = candidate.domain
    if not existing.company_linkedin and candidate.company_linkedin:
        existing.company_linkedin = candidate.company_linkedin
    if not existing.company_x and candidate.company_x:
        existing.company_x = candidate.company_x
    if candidate.category_anchor or candidate.lead_route in {"category_context", "monitor_only"}:
        existing.maturity_status = candidate.maturity_status
        existing.maturity_basis = list(candidate.maturity_basis)
        existing.maturity_evidence_urls = list(candidate.maturity_evidence_urls)
        existing.category_anchor = candidate.category_anchor
        existing.consensus_risk_reason = candidate.consensus_risk_reason
        existing.lead_route = candidate.lead_route
    elif existing.lead_route == "research_deeper" and candidate.lead_route:
        existing.maturity_status = candidate.maturity_status
        existing.maturity_basis = list(candidate.maturity_basis)
        existing.maturity_evidence_urls = list(candidate.maturity_evidence_urls)
        existing.consensus_risk_reason = candidate.consensus_risk_reason
        existing.lead_route = candidate.lead_route
    seen = {(profile.get("name"), profile.get("linkedin"), profile.get("x"), profile.get("github")) for profile in existing.founder_profiles}
    for profile in candidate.founder_profiles:
        key = (profile.get("name"), profile.get("linkedin"), profile.get("x"), profile.get("github"))
        if key not in seen:
            existing.founder_profiles.append(profile)
            seen.add(key)
    if not existing.canonical_name and candidate.canonical_name:
        existing.canonical_name = candidate.canonical_name
    if not existing.display_name and candidate.display_name:
        existing.display_name = candidate.display_name
    if not existing.source_headline and candidate.source_headline:
        existing.source_headline = candidate.source_headline
    if not existing.tagline and candidate.tagline:
        existing.tagline = candidate.tagline


def promote_signals_to_candidates(signals: list) -> dict:
    candidates_by_key: dict[str, Candidate] = {}
    rejected = []

    for signal in signals:
        if not signal.can_create_candidate:
            rejected.append(RejectedSignal(
                sector=signal.sector,
                source=signal.source,
                title=signal.title,
                url=signal.url,
                reason="source_not_candidate_eligible",
            ))
            continue

        candidate = _candidate_from_signal(signal)
        if not candidate:
            rejected.append(RejectedSignal(
                sector=signal.sector,
                source=signal.source,
                title=signal.title,
                url=signal.url,
                reason="candidate_name_not_extractable",
            ))
            continue

        key = _normalize_candidate_key(candidate.domain or candidate.name)
        if key in candidates_by_key:
            _merge_candidate_model(candidates_by_key[key], candidate)
        else:
            candidates_by_key[key] = candidate

    return {"candidates": list(candidates_by_key.values()), "rejected": rejected}


def _score_sort_limit_candidates(candidates: list[Candidate], candidate_limit: int) -> list[Candidate]:
    scored = [
        candidate if candidate.tier and candidate.investment_interest_score else score_and_tier(candidate)
        for candidate in candidates
    ]
    visible = [candidate for candidate in scored if candidate.tier != "Filtered"]
    return sorted(
        visible,
        key=lambda c: (c.tier == "Partner Review", c.investment_interest_score, c.evidence_confidence_score),
        reverse=True,
    )[:candidate_limit]


def _apply_attio_to_candidates(candidates: list[Candidate], attio_client=None) -> list[Candidate]:
    enriched = merge_attio_context([candidate.to_dict() for candidate in candidates], attio_client)
    return [Candidate.from_dict(candidate) for candidate in enriched]


def prepare_candidates_for_weekly_focus(candidates: list[Candidate], attio_client=None) -> tuple[list[Candidate], list]:
    resolved_candidates, identity_resolutions = apply_identity_resolution(candidates)
    resolved_candidates = _apply_attio_to_candidates(resolved_candidates, attio_client)
    return resolved_candidates, identity_resolutions


def _update_sector_coverage(
    coverage: dict[str, SectorCoverage],
    sectors: tuple[str, ...],
    candidates: list[Candidate],
    rejected: list[RejectedSignal],
) -> None:
    for sector in sectors:
        coverage.setdefault(sector, SectorCoverage(sector=sector, status="no signal found", reason="No relevant source evidence returned for this sector."))

    for sector, item in coverage.items():
        sector_label = SECTOR_LABELS.get(sector, sector).lower()
        sector_candidates = [
            candidate for candidate in candidates
            if candidate.sector.lower() == sector_label or candidate.sector.lower().replace(" ", "-") == sector
        ]
        sector_rejections = [rejection for rejection in rejected if rejection.sector == sector]
        item.candidates = len(sector_candidates)
        item.rejected = len(sector_rejections)
        if sector_candidates:
            item.status = "qualified candidates found"
            item.reason = ""
        elif item.raw_signals:
            item.status = "no qualified candidates"
            item.reason = item.reason or "Signals found, but none met candidate eligibility or evidence quality."
        else:
            item.status = "no signal found"
            item.reason = "No relevant source evidence returned for this sector."


def _source_errors_from_evidence(evidence: dict) -> dict[str, list[str]]:
    return {
        sector: payload.get("errors", [])
        for sector, payload in evidence.get("last30days", {}).items()
        if payload.get("errors")
    }


def _render_weekly_brief(
    candidates: list[Candidate],
    coverage: dict[str, SectorCoverage],
    rejected: list[RejectedSignal],
    *,
    faded: list[dict],
    theme_signals: list,
    sector_intelligence: list,
    partner_review: list[Candidate],
    synthesis=None,
    company_discovery=None,
) -> str:
    kwargs = {"faded": faded}
    accepted = signature(render_weekly_brief).parameters
    accepts_kwargs = any(parameter.kind == Parameter.VAR_KEYWORD for parameter in accepted.values())
    if "theme_signals" in accepted or accepts_kwargs:
        kwargs["theme_signals"] = theme_signals
    if "sector_intelligence" in accepted or accepts_kwargs:
        kwargs["sector_intelligence"] = sector_intelligence
    if "partner_review" in accepted or accepts_kwargs:
        kwargs["partner_review"] = partner_review
    if "synthesis" in accepted or accepts_kwargs:
        kwargs["synthesis"] = synthesis
    if "company_discovery" in accepted or accepts_kwargs:
        kwargs["company_discovery"] = company_discovery
    return render_weekly_brief(candidates, coverage, rejected, **kwargs)


def save_raw_evidence(evidence: dict, *, output_dir: Path = DEFAULT_OUTPUT_DIR, run_date: str | None = None) -> Path:
    run_date = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_date}-raw-evidence.json"
    path.write_text(json.dumps(evidence, indent=2))
    return path


def collect_live_evidence(
    *,
    sectors: tuple[str, ...] = DEFAULT_SECTORS,
    lookback_days: int = 30,
    github_limit: int = 40,
    max_queries_per_sector: int = 3,
    query_timeout_seconds: int | None = None,
    github_timeout_seconds: int | None = DEFAULT_GITHUB_TIMEOUT_SECONDS,
    progress: bool = False,
) -> dict:
    """Collect raw last30days and GitHub evidence for the weekly radar."""
    evidence = {"last30days": {}, "github": [], "warnings": [], "source_health": []}
    sector_config = load_sector_config()
    grounded_available = _grounded_search_available()
    social_available = _social_search_available()

    if run_query:
        for sector in sectors:
            started = time.monotonic()
            query_specs = build_sector_collection_queries(
                sector,
                sector_config,
                grounded_available=grounded_available,
                social_available=social_available,
                lookback_days=lookback_days,
                max_queries=max_queries_per_sector,
            )
            items = []
            clusters = []
            warnings = []
            errors = []
            for index, query_spec in enumerate(query_specs, start=1):
                if progress:
                    print(
                        f"[vc-signals] {sector}: query {index}/{len(query_specs)} "
                        f"({query_spec['kind']})",
                        file=sys.stderr,
                        flush=True,
                    )
                result = run_query(
                    query_spec["topic"],
                    sources=query_spec["sources"],
                    subreddits=query_spec.get("subreddits"),
                    lookback_days=query_spec["lookback_days"],
                    auto_resolve=True,
                    store=True,
                    web_backend=query_spec.get("web_backend"),
                    timeout_seconds=query_timeout_seconds,
                )
                for item in result.get("items", []):
                    item.setdefault("query_kind", query_spec["kind"])
                    item.setdefault("query_topic", query_spec["topic"])
                    item.setdefault("candidate_eligible", query_spec.get("candidate_eligible", True))
                items.extend(result.get("items", []))
                clusters.extend(result.get("clusters", []))
                warnings.extend(result.get("warnings", []))
                if result.get("error"):
                    errors.append(result["error"])
                    evidence["warnings"].append(f"{sector}: {result['error']}")
            items = filter_evidence(_dedupe_items(items))
            evidence["last30days"][sector] = {
                "queries": query_specs,
                "query_count": len(query_specs),
                "items": items,
                "clusters": clusters,
                "warnings": warnings,
                "errors": errors,
            }
            evidence["source_health"].append(
                _source_health(
                    f"last30days:{sector}",
                    "error" if errors else "complete",
                    fresh_items=len(items),
                    duration_seconds=time.monotonic() - started,
                    warnings=errors or warnings,
                )
            )

    if progress:
        print("[vc-signals] github: collecting trending repos", file=sys.stderr, flush=True)
    github, github_health = _run_github_trending_with_timeout(
        limit=github_limit,
        timeout_seconds=github_timeout_seconds,
    )
    evidence["github"] = filter_repos(github.get("repos", []))
    evidence["source_health"].append(github_health)
    evidence["warnings"].extend(github.get("warnings", []))
    if github.get("error"):
        evidence["warnings"].append(github["error"])

    return evidence


def run_weekly_artifacts(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    sectors: tuple[str, ...] = DEFAULT_SECTORS,
    github_limit: int = 40,
    max_queries_per_sector: int = 3,
    candidate_limit: int = 15,
    with_synthesis: bool = False,
    query_timeout_seconds: int | None = None,
    github_timeout_seconds: int | None = DEFAULT_GITHUB_TIMEOUT_SECONDS,
    progress: bool = False,
    discovery_budget: DiscoveryRunBudget | None = None,
    discovery_budget_mode: str = "weekly",
    discovery_cache_dir: Path | None = None,
    discovery_yield_trial_config: DiscoveryYieldTrialConfig | None = None,
    hn_launch_trial_config: HNLaunchTrialConfig | None = None,
) -> dict:
    """Collect evidence and render a weekly partner preview in one command."""
    output_dir.mkdir(parents=True, exist_ok=True)
    company_discovery_path = output_dir / "company-discovery.json"
    runtime_ledger_path = output_dir / "runtime-ledger.json"
    coverage_report_path = output_dir / "coverage-report.json"
    evidence = collect_live_evidence(
        sectors=sectors,
        github_limit=github_limit,
        max_queries_per_sector=max_queries_per_sector,
        query_timeout_seconds=query_timeout_seconds,
        github_timeout_seconds=github_timeout_seconds,
        progress=progress,
    )
    signal_result = build_signals_from_evidence(evidence)
    theme_signals = build_theme_signals(signal_result["signals"], sectors=sectors)
    initial_promotion = promote_signals_to_candidates(signal_result["signals"])
    provisional_candidates = _score_sort_limit_candidates(initial_promotion["candidates"], candidate_limit)
    provisional_focus_items = [build_focus_item(candidate) for candidate in provisional_candidates]
    resolved_discovery_budget = discovery_budget or DiscoveryRunBudget.for_mode(discovery_budget_mode)
    company_discovery = collect_company_discovery(
        theme_signals,
        focus_items=provisional_focus_items,
        unresolved_candidates=provisional_candidates,
        query_runner=run_query,
        grounded_available=_grounded_search_available(),
        social_available=_social_search_available(),
        max_queries_per_theme=3,
        run_budget=resolved_discovery_budget,
        partial_output_path=company_discovery_path,
        query_cache_dir=discovery_cache_dir or output_dir / "provider-query-cache",
        trial_config=discovery_yield_trial_config,
    )
    company_discovery["source_health"] = list(evidence.get("source_health", []))
    evidence["company_discovery"] = company_discovery
    for error in company_discovery.get("errors", []):
        evidence.setdefault("warnings", []).append(f"company-discovery: {error}")
    signal_result = build_signals_from_evidence(evidence)
    promotion = promote_signals_to_candidates(signal_result["signals"])
    theme_signals = build_theme_signals(signal_result["signals"], sectors=sectors)
    raw_path = save_raw_evidence(evidence, output_dir=output_dir)
    source_errors = _source_errors_from_evidence(evidence)
    scored_candidates = _score_sort_limit_candidates(promotion["candidates"], candidate_limit)
    scored_candidates = apply_candidate_enrichment(scored_candidates)
    scored_candidates, identity_resolutions = prepare_candidates_for_weekly_focus(
        scored_candidates,
        _attio_client_from_env(),
    )
    scored_candidates = _score_sort_limit_candidates(scored_candidates, candidate_limit)
    grounded_available = _grounded_search_available()
    scored_candidates, owner_evidence_report = enrich_owner_evidence(
        scored_candidates,
        query_runner=run_query if grounded_available else None,
        cache_dir=output_dir / "owner-evidence-cache",
        max_candidates=5,
    )
    scored_candidates = _score_sort_limit_candidates(scored_candidates, candidate_limit)
    scored_candidates, founder_team_verification_report = enrich_founder_team_verification(
        scored_candidates,
        query_runner=run_query if grounded_available else None,
        cache_dir=output_dir / "founder-team-verification-cache",
        max_candidates=5,
    )
    scored_candidates = _score_sort_limit_candidates(scored_candidates, candidate_limit)
    scored_candidates, owner_readiness_report = enrich_owner_readiness(
        scored_candidates,
        query_runner=None,
        cache_dir=output_dir / "owner-readiness-cache",
        max_queries=0,
    )
    scored_candidates = _score_sort_limit_candidates(scored_candidates, candidate_limit)
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    history_result = apply_weekly_tags(scored_candidates, load_candidate_history(), run_date=run_date)
    scored_candidates = history_result.candidates
    partner_review = select_partner_review(scored_candidates)
    save_candidate_history(history_result.history)
    _update_sector_coverage(signal_result["coverage"], sectors, scored_candidates, promotion["rejected"])
    sector_intelligence = build_sector_intelligence(
        sectors=sectors,
        coverage=signal_result["coverage"],
        candidates=scored_candidates,
        rejected=promotion["rejected"],
        theme_signals=theme_signals,
        source_errors=source_errors,
        grounded_available=_grounded_search_available(),
    )
    signals_path = output_dir / "signals.json"
    candidates_path = output_dir / "candidates.json"
    theme_signals_path = output_dir / "theme-signals.json"
    sector_intelligence_path = output_dir / "sector-intelligence.json"
    identity_resolution_path = output_dir / "identity-resolution.json"
    metadata_loss_report_path = output_dir / "metadata-loss-report.json"
    owner_evidence_path = output_dir / "owner-evidence.json"
    founder_team_verification_path = output_dir / "founder-team-verification.json"
    owner_readiness_path = output_dir / "owner-readiness.json"
    signals_path.write_text(json.dumps([signal.to_dict() for signal in signal_result["signals"]], indent=2))
    candidates_path.write_text(json.dumps([candidate.to_dict() for candidate in scored_candidates], indent=2))
    theme_signals_path.write_text(json.dumps([item.to_dict() for item in theme_signals], indent=2))
    sector_intelligence_path.write_text(json.dumps([item.to_dict() for item in sector_intelligence], indent=2))
    company_discovery_path.write_text(json.dumps(company_discovery, indent=2))
    runtime_ledger = dict(company_discovery.get("runtime_ledger", {}))
    runtime_ledger["source_health"] = list(evidence.get("source_health", []))
    runtime_ledger_path.write_text(json.dumps(runtime_ledger, indent=2))
    coverage_report_path.write_text(json.dumps(company_discovery.get("coverage_report", {}), indent=2))
    identity_resolution_path.write_text(json.dumps([item.to_dict() for item in identity_resolutions], indent=2, sort_keys=True))
    metadata_loss_report = build_metadata_loss_report(
        evidence=evidence,
        signals=signal_result["signals"],
        candidates=scored_candidates,
        identity_resolutions=identity_resolutions,
    )
    metadata_loss_report_path.write_text(json.dumps([item.to_dict() for item in metadata_loss_report], indent=2, sort_keys=True))
    write_owner_evidence_json(owner_evidence_report, owner_evidence_path)
    write_founder_team_verification_json(founder_team_verification_report, founder_team_verification_path)
    write_owner_readiness_json(owner_readiness_report, owner_readiness_path)
    synthesis = None
    synthesis_path = None
    if with_synthesis:
        synthesis = run_synthesis(
            evidence=evidence,
            signals=signal_result["signals"],
            candidates=scored_candidates,
            sector_intelligence=sector_intelligence,
            theme_signals=theme_signals,
        )
        synthesis_path = output_dir / "synthesis.json"
        synthesis_path.write_text(json.dumps(synthesis.to_dict(), indent=2))
    hn_launch_trial = {"enabled": False}
    if hn_launch_trial_config and hn_launch_trial_config.enabled:
        hn_launch_trial = run_hn_launch_weekly_trial(
            movements=_hn_launch_trial_movements(theme_signals, scored_candidates),
            run_query_fn=run_query,
            query_runner=run_query if grounded_available else None,
            page_fetcher=None,
            attio_matcher=_hn_attio_matcher_from_env(),
            output_dir=output_dir / "hn-launch-trial",
            cache_dir=output_dir / "hn-launch-trial" / "cache",
            config=hn_launch_trial_config,
        )
    preview_path = output_dir / "weekly-preview.md"
    preview_path.write_text(
        _render_weekly_brief(
            scored_candidates,
            signal_result["coverage"],
            promotion["rejected"],
            faded=history_result.faded,
            theme_signals=theme_signals,
            sector_intelligence=sector_intelligence,
            partner_review=partner_review,
            synthesis=synthesis,
            company_discovery=company_discovery,
        )
    )
    weekly_focus = build_weekly_focus_artifact(
        candidates=scored_candidates,
        category_context_items=_category_context_focus_items_from_company_discovery(company_discovery),
        theme_signals=theme_signals,
        sector_intelligence=sector_intelligence,
        source_gap_context="bounded_validation" if query_timeout_seconds is not None else "",
        source_health=evidence.get("source_health", []),
        run_id=run_date,
        discovery_yield_trial=company_discovery.get("discovery_yield_trial", {"enabled": False}),
        hn_launch_trial=hn_launch_trial,
    )
    weekly_focus_json_path = output_dir / "weekly-focus.json"
    weekly_focus_path = output_dir / "weekly-focus.md"
    feedback_path = output_dir / "feedback.json"
    write_weekly_focus_json(weekly_focus, weekly_focus_json_path)
    weekly_focus_path.write_text(render_weekly_focus_markdown(weekly_focus))
    write_feedback_scaffold(run_date, weekly_focus.partner_focus, feedback_path)
    result = {
        "raw_evidence": str(raw_path),
        "signals": str(signals_path),
        "candidates": str(candidates_path),
        "theme_signals": str(theme_signals_path),
        "sector_intelligence": str(sector_intelligence_path),
        "company_discovery": str(company_discovery_path),
        "runtime_ledger": str(runtime_ledger_path),
        "coverage_report": str(coverage_report_path),
        "identity_resolution_json": str(identity_resolution_path),
        "metadata_loss_report": str(metadata_loss_report_path),
        "owner_evidence_json": str(owner_evidence_path),
        "founder_team_verification_json": str(founder_team_verification_path),
        "owner_readiness_json": str(owner_readiness_path),
        "preview": str(preview_path),
        "weekly_focus_json": str(weekly_focus_json_path),
        "weekly_focus": str(weekly_focus_path),
        "feedback": str(feedback_path),
        "companies": len(scored_candidates),
        "sectors": list(sectors),
    }
    if hn_launch_trial.get("enabled"):
        result["hn_launch_trial"] = str(output_dir / "hn-launch-trial")
    if synthesis_path:
        result["synthesis"] = str(synthesis_path)
    return result


def _read_json_stdin():
    raw = sys.stdin.read()
    if not raw.strip():
        return None, {"error": "No data piped to stdin."}
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as exc:
        return None, {"error": f"Invalid JSON on stdin: {exc.msg}"}


def _parse_args(argv: list[str]) -> dict:
    args = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i][2:].replace("-", "_")
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                args[key] = argv[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            i += 1
    return args


def _get_bool_arg(args: dict, *names: str) -> bool:
    return any(args.get(name) is True for name in names)


def _get_int_arg(args: dict, *names: str, default: int | None = None) -> int | None:
    for name in names:
        if name in args:
            return int(args[name])
    return default


def _discovery_budget_from_args(args: dict, *, first_pass: bool) -> DiscoveryRunBudget:
    mode = args.get("discovery_budget_mode") or args.get("budget_mode") or ("smoke" if first_pass else "weekly")
    overrides = {}
    for arg_name, field_name in (
        ("max_runtime_seconds", "max_runtime_seconds"),
        ("max_company_discovery_queries", "max_company_discovery_queries"),
        ("max_maturity_queries", "max_maturity_queries"),
        ("max_article_fetches", "max_article_fetches"),
        ("max_results_per_query", "max_results_per_query"),
        ("per_movement_query_cap", "per_movement_query_cap"),
        ("query_cache_ttl_seconds", "query_cache_ttl_seconds"),
    ):
        if arg_name in args:
            overrides[field_name] = int(args[arg_name])
    if "allow_stale_cache" in args:
        overrides["allow_stale_cache"] = _get_bool_arg(args, "allow_stale_cache")
    return DiscoveryRunBudget.for_mode(mode, **overrides)


def _discovery_yield_trial_config_from_args(args: dict) -> DiscoveryYieldTrialConfig | None:
    if not _get_bool_arg(args, "discovery_yield_trial", "discoveryYieldTrial"):
        return None
    raw_families = args.get("discovery_trial_families", "")
    families = tuple(
        family.strip()
        for family in str(raw_families).split(",")
        if family.strip()
    ) or ("official_company_page", "founder_company_pages", "movement_platform")
    movement_platform_cap = int(args.get("discovery_trial_movement_platform_cap", 1))
    return DiscoveryYieldTrialConfig(
        enabled=True,
        families=families,
        movement_platform_cap_per_movement=movement_platform_cap,
    )


def _hn_launch_trial_config_from_args(args: dict) -> HNLaunchTrialConfig | None:
    if not _get_bool_arg(args, "hn_launch_trial", "hnLaunchTrial"):
        return None
    return HNLaunchTrialConfig(
        enabled=True,
        lookback_days=int(args.get("hn_launch_lookback_days", 30)),
        timeout_seconds=int(args.get("hn_launch_timeout_seconds", 120)),
        max_candidates=int(args.get("hn_launch_max_candidates", 10)),
        max_runtime_seconds=float(args.get("hn_launch_max_runtime_seconds", 90)),
        max_attio_checks=int(args.get("hn_launch_max_attio_checks", 10)),
        max_live_queries=int(args.get("hn_launch_max_live_queries", 25)),
        per_candidate_timeout_seconds=float(args.get("hn_launch_per_candidate_timeout_seconds", 8)),
    )


def _hn_launch_trial_movements(theme_signals, candidates) -> list[dict]:
    movements: list[dict] = []
    seen: set[str] = set()
    for signal in theme_signals or []:
        movement = (getattr(signal, "theme", "") or "").strip()
        if not movement or movement in seen:
            continue
        seen.add(movement)
        movements.append(
            {
                "movement": movement,
                "market_sector": getattr(signal, "market_sector", ""),
                "origin_row_ids": [],
            }
        )
    for candidate in candidates or []:
        movement = (getattr(candidate, "theme", "") or "").strip()
        if not movement or movement in seen:
            continue
        seen.add(movement)
        movements.append(
            {
                "movement": movement,
                "market_sector": getattr(candidate, "market_sector", "") or getattr(candidate, "sector", ""),
                "origin_row_ids": [getattr(candidate, "stable_key", "")] if getattr(candidate, "stable_key", "") else [],
            }
        )
    return movements


def _attio_client_from_env():
    token = os.environ.get("ATTIO_ACCESS_TOKEN")
    if not token and get_access_token:
        token, _source = get_access_token()
    if not token or not AttioClient:
        return None
    return AttioClient(token)


def _hn_attio_matcher_from_env():
    client = _attio_client_from_env()
    if not client:
        return None

    def match(candidate):
        return client.match_company({"name": candidate.name, "domain": candidate.domain})

    return match


def _cli_main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: radar_run.py <collect|preview> [args]"}))
        return

    command = sys.argv[1]
    args = _parse_args(sys.argv[2:])

    if command == "collect":
        output_dir = Path(args.get("output_dir", DEFAULT_OUTPUT_DIR))
        first_pass = _get_bool_arg(args, "first_pass", "firstPass")
        evidence = collect_live_evidence(
            sectors=parse_sectors_arg(args.get("sectors")),
            github_limit=int(args.get("github_limit", 40)),
            max_queries_per_sector=_get_int_arg(
                args,
                "max_queries_per_sector",
                default=1 if first_pass else 3,
            ),
            query_timeout_seconds=_get_int_arg(
                args,
                "query_timeout",
                "query_timeout_seconds",
                default=45 if first_pass else None,
            ),
            github_timeout_seconds=_get_int_arg(
                args,
                "github_timeout",
                "github_timeout_seconds",
                default=60 if first_pass else DEFAULT_GITHUB_TIMEOUT_SECONDS,
            ),
            progress=bool(args.get("progress", False)),
        )
        path = save_raw_evidence(evidence, output_dir=output_dir)
        print(json.dumps({"saved": str(path), "github_count": len(evidence.get("github", []))}))
        return

    if command == "weekly":
        output_dir = Path(args.get("output_dir", DEFAULT_OUTPUT_DIR))
        first_pass = _get_bool_arg(args, "first_pass", "firstPass")
        result = run_weekly_artifacts(
            output_dir=output_dir,
            sectors=parse_sectors_arg(args.get("sectors")),
            github_limit=int(args.get("github_limit", 40)),
            max_queries_per_sector=_get_int_arg(
                args,
                "max_queries_per_sector",
                default=1 if first_pass else 3,
            ),
            candidate_limit=int(args.get("limit", 15)),
            with_synthesis=bool(args.get("with_synthesis", False)),
            query_timeout_seconds=_get_int_arg(
                args,
                "query_timeout",
                "query_timeout_seconds",
                default=45 if first_pass else None,
            ),
            github_timeout_seconds=_get_int_arg(
                args,
                "github_timeout",
                "github_timeout_seconds",
                default=60 if first_pass else DEFAULT_GITHUB_TIMEOUT_SECONDS,
            ),
            progress=bool(args.get("progress", True)),
            discovery_budget=_discovery_budget_from_args(args, first_pass=first_pass),
            discovery_yield_trial_config=_discovery_yield_trial_config_from_args(args),
            hn_launch_trial_config=_hn_launch_trial_config_from_args(args),
        )
        print(json.dumps(result))
        return

    if command == "workbench":
        run_dir = Path(args.get("from_run", args.get("run_dir", DEFAULT_OUTPUT_DIR)))
        output_dir = Path(args.get("output_dir", run_dir))
        result = write_workbench_artifacts(run_dir=run_dir, output_dir=output_dir)
        print(json.dumps(result))
        return

    if command == "preview":
        if "from_evidence" in args:
            evidence = json.loads(Path(args["from_evidence"]).read_text())
            companies = build_scored_preview_from_evidence(evidence, attio_client=_attio_client_from_env())
            themes = sorted({company.get("theme", "") for company in companies if company.get("theme")})
            output = Path(args["output"]) if "output" in args else DEFAULT_OUTPUT_DIR / "partner-preview.md"
            render_partner_preview(companies, themes, output_path=output)
            print(json.dumps({"saved": str(output), "companies": len(companies)}))
            return

        payload, error = _read_json_stdin()
        if error:
            print(json.dumps(error))
            return
        companies = payload.get("companies", []) if isinstance(payload, dict) else []
        themes = payload.get("themes", []) if isinstance(payload, dict) else []
        companies = merge_attio_context(companies, _attio_client_from_env())
        output = Path(args["output"]) if "output" in args else DEFAULT_OUTPUT_DIR / "partner-preview.md"
        render_partner_preview(companies, themes, output_path=output)
        print(json.dumps({"saved": str(output), "companies": len(companies)}))
        return

    print(json.dumps({"error": f"Unknown command: {command}"}))


if __name__ == "__main__":
    _cli_main()
