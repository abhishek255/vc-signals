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
import sys
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

from radar_models import Candidate, RejectedSignal, SectorCoverage
from radar_company_discovery import collect_company_discovery
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
from radar_oss import enrich_oss_candidate


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

    candidate = Candidate(
        name=name,
        domain=_candidate_domain_from_item(item),
        sector=SECTOR_LABELS.get(signal.sector, signal.sector),
        theme=infer_theme(f"{signal.title} {signal.text}"),
        source=source,
        sources=[source] if source else [],
        source_count=1,
        candidate_type=signal.role,
        why_on_radar=why,
        why_this_may_be_noise="Needs verification across stronger company/founder/customer evidence.",
        company_linkedin=_profile_url(item, "company_linkedin", "linkedin_url", "linkedin"),
        company_x=_profile_url(item, "company_x", "x_url", "twitter_url", "twitter"),
        founder_profiles=_founder_profiles_from_item(item),
        engagement=item.get("engagement", {}),
        action="watch" if signal.role == "oss_project" else "assign owner",
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


def _merge_candidate_model(existing: Candidate, candidate: Candidate) -> None:
    existing.source_count += 1
    if candidate.source and candidate.source not in existing.sources:
        existing.sources.append(candidate.source)
    if not existing.domain and candidate.domain:
        existing.domain = candidate.domain
    if not existing.company_linkedin and candidate.company_linkedin:
        existing.company_linkedin = candidate.company_linkedin
    if not existing.company_x and candidate.company_x:
        existing.company_x = candidate.company_x
    seen = {(profile.get("name"), profile.get("linkedin"), profile.get("x"), profile.get("github")) for profile in existing.founder_profiles}
    for profile in candidate.founder_profiles:
        key = (profile.get("name"), profile.get("linkedin"), profile.get("x"), profile.get("github"))
        if key not in seen:
            existing.founder_profiles.append(profile)
            seen.add(key)


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
    progress: bool = False,
) -> dict:
    """Collect raw last30days and GitHub evidence for the weekly radar."""
    evidence = {"last30days": {}, "github": [], "warnings": []}
    sector_config = load_sector_config()
    grounded_available = _grounded_search_available()
    social_available = _social_search_available()

    if run_query:
        for sector in sectors:
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

    if run_trending:
        if progress:
            print("[vc-signals] github: collecting trending repos", file=sys.stderr, flush=True)
        github = run_trending("all", limit=github_limit)
        evidence["github"] = filter_repos(github.get("repos", []))
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
    progress: bool = False,
) -> dict:
    """Collect evidence and render a weekly partner preview in one command."""
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = collect_live_evidence(
        sectors=sectors,
        github_limit=github_limit,
        max_queries_per_sector=max_queries_per_sector,
        query_timeout_seconds=query_timeout_seconds,
        progress=progress,
    )
    signal_result = build_signals_from_evidence(evidence)
    theme_signals = build_theme_signals(signal_result["signals"], sectors=sectors)
    company_discovery = collect_company_discovery(
        theme_signals,
        query_runner=run_query,
        grounded_available=_grounded_search_available(),
        social_available=_social_search_available(),
        max_queries_per_theme=3,
    )
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
    scored_candidates = _apply_attio_to_candidates(scored_candidates, _attio_client_from_env())
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
    company_discovery_path = output_dir / "company-discovery.json"
    signals_path.write_text(json.dumps([signal.to_dict() for signal in signal_result["signals"]], indent=2))
    candidates_path.write_text(json.dumps([candidate.to_dict() for candidate in scored_candidates], indent=2))
    theme_signals_path.write_text(json.dumps([item.to_dict() for item in theme_signals], indent=2))
    sector_intelligence_path.write_text(json.dumps([item.to_dict() for item in sector_intelligence], indent=2))
    company_discovery_path.write_text(json.dumps(company_discovery, indent=2))
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
    result = {
        "raw_evidence": str(raw_path),
        "signals": str(signals_path),
        "candidates": str(candidates_path),
        "theme_signals": str(theme_signals_path),
        "sector_intelligence": str(sector_intelligence_path),
        "company_discovery": str(company_discovery_path),
        "preview": str(preview_path),
        "companies": len(scored_candidates),
        "sectors": list(sectors),
    }
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


def _attio_client_from_env():
    token = os.environ.get("ATTIO_ACCESS_TOKEN")
    if not token and get_access_token:
        token, _source = get_access_token()
    if not token or not AttioClient:
        return None
    return AttioClient(token)


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
            progress=bool(args.get("progress", True)),
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
