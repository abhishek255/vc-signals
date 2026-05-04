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
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))

try:
    from attio import AttioClient, enrich_companies
except ImportError:  # pragma: no cover - only for damaged installs
    AttioClient = None
    enrich_companies = None

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


DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "radar_runs"
DEFAULT_SECTORS = ("devtools", "cybersecurity", "ai-infra", "vertical-ai", "data-infra", "oss")
SECTOR_CONFIG_PATH = Path(__file__).parent.parent / "config" / "sectors.json"

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


def build_sector_collection_queries(
    sector_slug: str,
    sector_config: dict,
    *,
    grounded_available: bool = False,
    lookback_days: int = 30,
    max_queries: int = 3,
) -> list[dict]:
    """Build a small, Marathon-focused query set for one sector."""
    config = sector_config.get(sector_slug, {}) if sector_slug in sector_config else sector_config
    display_name = config.get("display_name", SECTOR_LABELS.get(sector_slug, sector_slug))
    if not grounded_available:
        if sector_slug == "oss":
            return [
                {
                    "kind": "oss_show",
                    "topic": "Show HN open source AI agent MCP security developer tool",
                    "sources": "hackernews,github",
                    "lookback_days": lookback_days,
                },
                {
                    "kind": "oss_github",
                    "topic": "open source AI agent infrastructure GitHub stars MCP security",
                    "sources": "github,hackernews",
                    "lookback_days": lookback_days,
                },
                {
                    "kind": "oss_security",
                    "topic": "open source AI security scanner MCP agent tool GitHub",
                    "sources": "github,hackernews",
                    "lookback_days": lookback_days,
                },
            ][:max_queries]
        return [
            {
                "kind": "conversation",
                "topic": f"Show HN {display_name} AI startup developer tool open source",
                "sources": "hackernews,github",
                "lookback_days": lookback_days,
            },
            {
                "kind": "hn_show",
                "topic": f"Launch HN Show HN {display_name} startup AI infrastructure",
                "sources": "hackernews,github",
                "lookback_days": lookback_days,
            },
            {
                "kind": "github_signal",
                "topic": f"{display_name} AI agent infrastructure open source GitHub stars",
                "sources": "github,hackernews",
                "lookback_days": lookback_days,
            },
        ][:max_queries]

    seed_queries = _flatten_seed_queries(config)
    conversation_topic = (
        seed_queries[0]
        if seed_queries
        else f"{display_name} startups Seed Series A Series B emerging traction"
    )
    queries = [{
        "kind": "conversation",
        "topic": f"{conversation_topic} Seed Series A Series B founder customer traction",
        "sources": "reddit,hackernews,github",
        "lookback_days": lookback_days,
    }]

    if grounded_available:
        queries.extend([
            {
                "kind": "yc_company",
                "topic": f"site:ycombinator.com/companies {display_name} AI startups Seed Series A Series B",
                "sources": "grounding,hackernews,github",
                "web_backend": "auto",
                "lookback_days": lookback_days,
            },
            {
                "kind": "company_discovery",
                "topic": f"{display_name} startups Seed Series A Series B emerging companies funding founder traction",
                "sources": "grounding,reddit,hackernews,github",
                "web_backend": "auto",
                "lookback_days": lookback_days,
            },
        ])

    return queries[:max_queries]


def _grounded_search_available() -> bool:
    if not check_last30days_availability:
        return False
    try:
        availability = check_last30days_availability()
    except Exception:
        return False
    return bool((availability.get("source_capabilities") or {}).get("grounded"))


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


def _merge_candidate(existing: dict, candidate: dict) -> None:
    existing["source_count"] = int(existing.get("source_count") or 1) + 1
    source = candidate.get("source", "")
    if source:
        sources = existing.setdefault("sources", [existing.get("source", "")])
        if source not in sources:
            sources.append(source)
    if not existing.get("domain") and candidate.get("domain"):
        existing["domain"] = candidate["domain"]
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
    if not attio_client or not enrich_companies:
        return [
            {
                **company,
                "attio_status": company.get("attio_status", "unknown"),
                "action": company.get("action", company.get("attio_action", "monitor only")),
            }
            for company in companies
        ]

    enriched = enrich_companies(companies, attio_client)
    for company in enriched:
        existing_action = company.get("action")
        sector = (company.get("sector") or "").lower()
        preserve_oss_action = existing_action and "oss" in sector
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
        "| Company | Sector | Theme | Interest | Evidence | Attio | Action | Why On Radar | Why This May Be Noise | Source |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ])
    for company in companies:
        lines.append(
            "| {name} | {sector} | {theme} | {interest} | {evidence} | {attio} | {action} | {why} | {noise} | {source} |".format(
                name=company.get("name", ""),
                sector=company.get("sector", ""),
                theme=company.get("theme") or company.get("primary_theme", ""),
                interest=company.get("investment_interest", ""),
                evidence=company.get("evidence_confidence", ""),
                attio=company.get("attio_status", "unknown"),
                action=company.get("action") or company.get("attio_action", ""),
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
) -> dict:
    """Collect raw last30days and GitHub evidence for the weekly radar."""
    evidence = {"last30days": {}, "github": [], "warnings": []}
    sector_config = load_sector_config()
    grounded_available = _grounded_search_available()

    if run_query:
        for sector in sectors:
            query_specs = build_sector_collection_queries(
                sector,
                sector_config,
                grounded_available=grounded_available,
                lookback_days=lookback_days,
                max_queries=max_queries_per_sector,
            )
            items = []
            clusters = []
            warnings = []
            errors = []
            for query_spec in query_specs:
                result = run_query(
                    query_spec["topic"],
                    sources=query_spec["sources"],
                    lookback_days=query_spec["lookback_days"],
                    auto_resolve=True,
                    store=True,
                    web_backend=query_spec.get("web_backend"),
                )
                for item in result.get("items", []):
                    item.setdefault("query_kind", query_spec["kind"])
                    item.setdefault("query_topic", query_spec["topic"])
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
        github = run_trending("all", limit=github_limit)
        evidence["github"] = filter_repos(github.get("repos", []))
        evidence["warnings"].extend(github.get("warnings", []))
        if github.get("error"):
            evidence["warnings"].append(github["error"])

    return evidence


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


def _attio_client_from_env():
    token = os.environ.get("ATTIO_ACCESS_TOKEN")
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
        evidence = collect_live_evidence(
            sectors=parse_sectors_arg(args.get("sectors")),
            github_limit=int(args.get("github_limit", 40)),
            max_queries_per_sector=int(args.get("max_queries_per_sector", 3)),
        )
        path = save_raw_evidence(evidence, output_dir=output_dir)
        print(json.dumps({"saved": str(path), "github_count": len(evidence.get("github", []))}))
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
