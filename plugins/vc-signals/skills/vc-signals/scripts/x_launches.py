#!/usr/bin/env python3
"""Credential-gated X launch lane using last30days when access exists."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

try:
    from last30days_adapter import DEFAULT_CONFIG_PATH
except ImportError:  # pragma: no cover - damaged local installs
    DEFAULT_CONFIG_PATH = Path.home() / ".config" / "last30days" / ".env"

try:
    from signal_investigator import classify_url_role
except ImportError:  # pragma: no cover - damaged local installs
    classify_url_role = None


PLACEHOLDER_VALUES = {"", "...", "TODO", "YOUR_KEY", "YOUR_API_KEY", "<YOUR_API_KEY>"}
DEFAULT_LOOKBACK_DAYS = 14
DEFAULT_TIMEOUT_SECONDS = 45
DEFAULT_WEB_RESOLVER_TIMEOUT_SECONDS = 8
MAX_X_LAUNCH_QUERIES = 4
MAX_X_DOMAIN_RESOLUTIONS = 3
DOMAIN_BLOCKLIST = {
    "apps.apple.com",
    "bit.ly",
    "crunchbase.com",
    "facebook.com",
    "github.com",
    "instagram.com",
    "lnkd.in",
    "linktr.ee",
    "linkedin.com",
    "medium.com",
    "news.ycombinator.com",
    "producthunt.com",
    "reddit.com",
    "substack.com",
    "t.co",
    "techcrunch.com",
    "tiktok.com",
    "tinyurl.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}
GENERIC_COMPANY_NAMES = {"ai", "api", "app", "bot", "mcp", "saas", "startup"}


def _configured(value: object) -> bool:
    normalized = str(value or "").strip().strip("\"'")
    return normalized not in PLACEHOLDER_VALUES


def load_env_file(path: Path | str = DEFAULT_CONFIG_PATH) -> dict[str, str]:
    env: dict[str, str] = {}
    config_path = Path(path)
    if not config_path.exists():
        return env
    for line in config_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env[key.strip()] = value.strip().strip("\"'")
    return env


def merged_x_env(env: dict[str, str] | None = None, *, config_path: Path | str = DEFAULT_CONFIG_PATH) -> dict[str, str]:
    merged = load_env_file(config_path)
    merged.update({key: value for key, value in os.environ.items() if key in {"XAI_API_KEY", "AUTH_TOKEN", "CT0"}})
    if env is not None:
        merged.update(env)
    return merged


def x_credentials_available(env: dict[str, str] | None = None) -> bool:
    source = env if env is not None else merged_x_env()
    return _configured(source.get("XAI_API_KEY")) or (
        _configured(source.get("AUTH_TOKEN")) and _configured(source.get("CT0"))
    )


def build_x_launch_queries(
    movements: list[dict],
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[dict]:
    queries: list[dict] = []
    seen: set[str] = set()
    for row in movements:
        movement = str(row.get("movement") or row.get("theme") or row.get("market_sector") or "").strip()
        if not movement:
            continue
        variants = [
            f'("{movement}") (launching OR launched OR announcing OR shipped OR "we built") startup founder product',
            f'("{movement}") ("we launched" OR "just launched" OR "launching today" OR shipped) (founder OR cofounder OR startup OR product)',
            f'("{movement}") ("public beta" OR "private beta" OR "early access" OR waitlist) (founder OR startup OR product)',
            f'("{movement}") ("now live" OR "product launch" OR "I built" OR "we built") (try OR demo OR http OR website)',
            f'("{movement}") (announcing OR launched OR launching OR shipped) ("new product" OR SaaS OR tool)',
        ]
        for topic in variants:
            key = topic.lower()
            if key in seen:
                continue
            seen.add(key)
            queries.append(
                {
                    "id": f"x_launch:{len(queries) + 1}",
                    "movement": movement,
                    "market_sector": row.get("market_sector", ""),
                    "topic": topic,
                    "sources": "x",
                    "lookback_days": lookback_days,
                }
            )
    return queries


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _domain_allowed(domain: str) -> bool:
    normalized = (domain or "").lower().removeprefix("www.").strip()
    if not normalized:
        return False
    return not any(normalized == blocked or normalized.endswith(f".{blocked}") for blocked in DOMAIN_BLOCKLIST)


def _name_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _domain_identity_slug(domain: str) -> str:
    labels = [label for label in (domain or "").lower().split(".") if label]
    if len(labels) >= 3:
        labels = labels[:-1]
    elif len(labels) >= 2:
        labels = labels[:-1]
    return _name_slug(" ".join(labels))


def _text_tokens(value: str) -> set[str]:
    stop = {"and", "app", "for", "from", "launch", "launched", "startup", "the", "this", "with", "your"}
    return {token for token in re.findall(r"[a-z0-9]{3,}", (value or "").lower()) if token not in stop}


def _candidate_urls_from_item(item: dict) -> list[str]:
    urls = []
    for key in ("website", "homepage", "resolved_url", "outbound_url", "url"):
        value = str(item.get(key) or "").strip()
        if value:
            urls.append(value)
    for link in item.get("links") or item.get("outbound_links") or []:
        if isinstance(link, dict):
            value = str(link.get("url") or link.get("href") or "").strip()
        else:
            value = str(link or "").strip()
        if value:
            urls.append(value)
    for key in ("source_outbound_urls", "source_urls", "evidence_urls"):
        for raw_url in item.get(key) or []:
            value = str(raw_url or "").strip()
            if value:
                urls.append(value)
    urls.extend(_text_extracted_urls_from_item(item))
    return list(dict.fromkeys(urls))


def _urls_from_text(value: str) -> list[str]:
    urls = []
    for match in re.findall(r"https?://[^\s<>)\\\"']+", value or ""):
        urls.append(match.rstrip(".,;:!?]})"))
    bare_domain_pattern = re.compile(
        r"(?<![@/\w.-])((?:www\.)?[a-z0-9][a-z0-9-]{1,63}(?:\.[a-z0-9][a-z0-9-]{1,63})+(?:/[^\s<>)\\\"']*)?)",
        flags=re.IGNORECASE,
    )
    for match in bare_domain_pattern.findall(value or ""):
        candidate = match.rstrip(".,;:!?]})")
        domain = _domain_from_url(candidate if "://" in candidate else f"https://{candidate}")
        if _domain_allowed(domain):
            urls.append(candidate if "://" in candidate else f"https://{candidate}")
    return urls


def _text_extracted_urls_from_item(item: dict) -> list[str]:
    urls = []
    for key in ("title", "snippet", "description", "body", "text", "container"):
        urls.extend(_urls_from_text(str(item.get(key) or "")))
    return list(dict.fromkeys(urls))


def _candidate_text(item: dict) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "snippet", "description", "body", "text", "container", "url", "website", "homepage")
    )


def _company_name_from_title(title: str) -> str:
    title = str(title or "").strip()
    for pattern in (
        r"\blaunch(?:ing|ed)?\s+(?P<name>[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,2})\b",
        r"\bannouncing\s+(?P<name>[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,2})\b",
        r"\bshipped\s+(?P<name>[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,2})\b",
        r"\bintroducing\s+(?P<name>[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,2})\b",
        r"\bmeet\s+(?P<name>[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,2})\b",
        r"\bcalled\s+(?P<name>[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,2})\b",
    ):
        match = re.search(pattern, title)
        if match:
            return match.group("name").strip()
    return ""


def _clear_launch_language(item: dict) -> bool:
    text = _candidate_text(item).lower()
    return any(
        term in text
        for term in (
            "we launched",
            "i launched",
            "just launched",
            "launching today",
            "public beta",
            "private beta",
            "early access",
            "now live",
            "product launch",
        )
    )


def _company_name_from_domain(domain: str) -> str:
    label = (domain or "").split(".", 1)[0]
    parts = [part for part in re.split(r"[-_]+", label) if part]
    return " ".join(part.capitalize() for part in parts)


def _embedded_official_url_without_name(item: dict) -> str:
    if not _clear_launch_language(item):
        return ""
    for candidate_url in _structured_link_urls_from_item(item) + _text_extracted_urls_from_item(item):
        domain = _domain_from_url(candidate_url)
        if not _domain_allowed(domain):
            continue
        if classify_url_role:
            role = classify_url_role(
                candidate_url if "://" in candidate_url else f"https://{domain}",
                title=str(item.get("title") or ""),
                snippet=str(item.get("snippet") or item.get("description") or ""),
            )
            if not role.get("official_eligible"):
                continue
        return candidate_url if "://" in candidate_url else f"https://{domain}"
    return ""


def _resolvable_company_name(name: str) -> bool:
    normalized = _name_slug(name)
    return len(normalized) >= 4 and normalized not in GENERIC_COMPANY_NAMES


def _launch_intent_score(item: dict) -> tuple[int, list[str]]:
    text = " ".join(
        str(item.get(key) or "")
        for key in ("title", "snippet", "description", "body", "text", "container")
    ).lower()
    score = 0
    basis = []
    if any(term in text for term in ("we launched", "i launched", "just launched", "launching today")):
        score += 35
        basis.append("first_person_launch_language")
    elif any(term in text for term in ("launches", "launched", "launching", "announcing", "shipped")):
        score += 25
        basis.append("launch_language")
    if any(term in text for term in ("founder", "co-founder", "ceo", "cto")):
        score += 15
        basis.append("operator_context")
    if any(term in text for term in ("waitlist", "beta", "private beta", "early access")):
        score += 10
        basis.append("early_product_signal")
    if item.get("website") or item.get("homepage") or item.get("domain"):
        score += 20
        basis.append("identity_link_present")
    if item.get("author"):
        score += 5
        basis.append("author_present")
    if item.get("company_name") or item.get("name"):
        score += 10
        basis.append("company_name_present")
    return min(100, score), basis


def _x_source_outbound_urls(item: dict, *, website: str, article_urls: list[str], directory_urls: list[str], repo_urls: list[str]) -> list[str]:
    urls = []
    for value in (
        website,
        item.get("url"),
        item.get("x_url"),
        item.get("company_x"),
        *_structured_link_urls_from_item(item),
        *_text_extracted_urls_from_item(item),
        *article_urls,
        *directory_urls,
        *repo_urls,
    ):
        url = str(value or "").strip()
        if url:
            urls.append(url)
    return list(dict.fromkeys(urls))


def _x_plan_item(field: str, present: bool, why: str, where_to_check: list[str]) -> dict:
    return {
        "field": field,
        "status": "present" if present else "missing",
        "why_it_matters": why,
        "where_to_check": where_to_check,
        "promote_if_found": "Use the X signal as supporting launch evidence only after this field is verified elsewhere.",
        "discard_if_not_found": "Keep as launch watch or discard if X remains the only durable evidence.",
    }


def _x_evidence_completion_plan(row: dict) -> list[dict]:
    missing = set(row.get("missing_evidence") or [])
    domain = str(row.get("domain") or "").strip()
    official_site = f"https://{domain}" if domain else "official company website"
    return [
        _x_plan_item(
            "official_domain",
            "official_domain_identity_not_confirmed" not in missing and bool(domain),
            "X can show a launch happened, but the official website is the identity source.",
            ["embedded URL in X post", "founder X profile", "Product Hunt/HN/GitHub launch page", "web search official result"],
        ),
        _x_plan_item(
            "founder_team",
            bool(row.get("founder_profiles") or row.get("founders") or row.get("founder_team_evidence")),
            "Founder/operator proof turns social chatter into accountable company evidence.",
            ["founder X profile", f"{official_site}/about", f"{official_site}/team", "LinkedIn manual check"],
        ),
        _x_plan_item(
            "commercial",
            bool(row.get("customer_buyer_evidence") or row.get("pricing_evidence") or row.get("docs_evidence") or row.get("careers_evidence")),
            "Commercial proof shows the launch is becoming a real company/product surface.",
            [f"{official_site}/pricing", f"{official_site}/docs", f"{official_site}/customers", f"{official_site}/careers"],
        ),
        _x_plan_item(
            "stage_funding_headcount",
            bool(row.get("stage") or row.get("raised") or row.get("headcount") or row.get("stage_funding_evidence")),
            "Maturity metadata helps decide whether the row deserves partner time this week.",
            ["public funding snippets", "company careers page", "Crunchbase-style web result", "LinkedIn manual check"],
        ),
    ]


def _x_manual_review_checklist(row: dict) -> list[str]:
    checks = []
    for plan_item in _x_evidence_completion_plan(row):
        if plan_item["status"] != "missing":
            continue
        checks.append(f"Check {plan_item['field'].replace('_', ' ')}: {', '.join(plan_item['where_to_check'])}.")
    return checks or ["Do one focused contradiction check before promotion."]


def _decorate_x_launch_row(row: dict, item: dict) -> dict:
    article_urls = row.get("article_evidence_urls") or []
    directory_urls = row.get("directory_evidence_urls") or []
    repo_urls = row.get("repo_evidence_urls") or []
    row["launch_radar_role"] = "launch_signal_not_identity_truth"
    row["identity_resolution_policy"] = (
        "X can detect launch chatter and founder excitement; official identity must be verified through an official "
        "domain, company site, Product Hunt/HN/GitHub context, LinkedIn/manual checks, or structured metadata."
    )
    row["launch_signal"] = {
        "confidence_score": row.get("launch_intent_score", 0),
        "basis": row.get("launch_intent_basis", []),
        "x_url": row.get("company_x") or row.get("url") or "",
        "author": row.get("author", ""),
        "published_at": row.get("published_at", ""),
    }
    row["source_outbound_urls"] = _x_source_outbound_urls(
        item,
        website=row.get("website", ""),
        article_urls=article_urls,
        directory_urls=directory_urls,
        repo_urls=repo_urls,
    )
    row["evidence_completion_plan"] = _x_evidence_completion_plan(row)
    checklist = _x_manual_review_checklist(row)
    row["manual_review_checklist"] = checklist
    row["recommended_manual_check"] = checklist[0] if checklist else ""
    row["promote_if"] = (
        "Promote if the launch resolves to an official domain plus founder/operator and commercial or maturity proof."
    )
    row["discard_if"] = "Discard if evidence remains only an X post, article, directory, or unresolved product name."
    row["likely_payoff"] = "Medium: X is useful as launch radar, but payoff depends on official-domain and operator proof."
    return row


def _verify_domain_candidate(launch: dict, item: dict, candidate_url: str) -> tuple[bool, list[str]]:
    domain = _domain_from_url(candidate_url) or str(item.get("domain") or "").strip().lower().removeprefix("www.")
    if not _domain_allowed(domain):
        return False, []
    if classify_url_role:
        role = classify_url_role(candidate_url if "://" in candidate_url else f"https://{domain}", title=str(item.get("title") or ""), snippet=str(item.get("snippet") or item.get("description") or ""))
        if not role.get("official_eligible"):
            return False, []
    name = str(launch.get("company_name") or launch.get("name") or "").strip()
    if not _resolvable_company_name(name):
        return False, []
    name_slug = _name_slug(name)
    domain_slug = _domain_identity_slug(domain)
    text = _candidate_text(item)
    text_blob = text.lower()
    name_tokens = _text_tokens(name)
    description_tokens = _text_tokens(str(launch.get("description") or launch.get("snippet") or ""))
    domain_name_match = bool(
        name_slug in domain_slug
        or domain_slug in name_slug
        or any(token in domain_slug for token in name_tokens)
    )
    text_match = bool(name.lower() in text_blob or len(description_tokens & _text_tokens(text)) >= 2)
    reasons = []
    if domain_name_match:
        reasons.append("domain_matches_company_name")
    if name.lower() in text_blob:
        reasons.append("search_result_mentions_company_name")
    if len(description_tokens & _text_tokens(text)) >= 2:
        reasons.append("search_result_matches_launch_text")
    return domain_name_match and text_match, reasons


def _structured_link_urls_from_item(item: dict) -> list[str]:
    urls = []
    for link in item.get("links") or item.get("outbound_links") or []:
        if isinstance(link, dict):
            value = str(link.get("url") or link.get("href") or "").strip()
        else:
            value = str(link or "").strip()
        if value:
            urls.append(value)
    for key in ("source_outbound_urls", "source_urls", "evidence_urls"):
        for raw_url in item.get(key) or []:
            value = str(raw_url or "").strip()
            if value:
                urls.append(value)
    return list(dict.fromkeys(urls))


def resolve_embedded_launch_link_domain(item: dict, launch: dict) -> dict:
    for candidate_url in _structured_link_urls_from_item(item):
        verified, reasons = _verify_domain_candidate(launch, item, candidate_url)
        if not verified:
            continue
        domain = _domain_from_url(candidate_url) or str(item.get("domain") or "").strip().lower().removeprefix("www.")
        return {
            "url": candidate_url if "://" in candidate_url else f"https://{domain}",
            "warning": "",
            "evidence": {
                "source": "embedded_launch_link_url",
                "domain": domain,
                "url": candidate_url,
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "verification": reasons + ["url_extracted_from_structured_link"],
            },
        }
    return {"url": "", "warning": "no verified embedded launch link URL"}


def resolve_embedded_launch_text_domain(item: dict, launch: dict) -> dict:
    for candidate_url in _text_extracted_urls_from_item(item):
        verified, reasons = _verify_domain_candidate(launch, item, candidate_url)
        if not verified:
            continue
        domain = _domain_from_url(candidate_url)
        return {
            "url": candidate_url if "://" in candidate_url else f"https://{domain}",
            "warning": "",
            "evidence": {
                "source": "embedded_launch_text_url",
                "domain": domain,
                "url": candidate_url,
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "verification": reasons + ["url_extracted_from_text"],
            },
        }
    return {"url": "", "warning": "no verified embedded launch URL"}


def _web_domain_query(launch: dict) -> str:
    name = str(launch.get("company_name") or launch.get("name") or "").strip()
    description = str(launch.get("description") or launch.get("snippet") or launch.get("title") or "").strip()
    quoted_name = f'"{name}"' if name else ""
    quoted_description = f'"{description}"' if description else ""
    return " ".join(part for part in (quoted_name, quoted_description, "official website company startup") if part)


def resolve_x_launch_domain_via_web(
    launch: dict,
    *,
    query_runner,
    timeout_seconds: int | None = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    if not query_runner:
        return {"url": "", "warning": "X domain resolver skipped: last30days query runner unavailable"}
    if not _resolvable_company_name(str(launch.get("company_name") or launch.get("name") or "")):
        return {"url": "", "warning": "X domain resolver skipped: company name too generic"}
    query = _web_domain_query(launch)
    query_timeout = min(timeout_seconds or DEFAULT_TIMEOUT_SECONDS, DEFAULT_WEB_RESOLVER_TIMEOUT_SECONDS)
    try:
        payload = query_runner(
            topic=query,
            sources="web",
            lookback_days=30,
            auto_resolve=True,
            store=False,
            timeout_seconds=query_timeout,
        )
    except Exception as exc:
        return {"url": "", "warning": f"X domain resolver failed: {exc}"}
    if payload.get("error"):
        return {"url": "", "warning": f"X domain resolver failed: {payload['error']}"}
    for item in payload.get("items", []) or []:
        for candidate_url in _candidate_urls_from_item(item):
            verified, reasons = _verify_domain_candidate(launch, item, candidate_url)
            if verified:
                domain = _domain_from_url(candidate_url) or str(item.get("domain") or "").strip().lower().removeprefix("www.")
                return {
                    "url": candidate_url if "://" in candidate_url else f"https://{domain}",
                    "warning": "",
                    "evidence": {
                        "source": "web_fallback",
                        "query": query,
                        "domain": domain,
                        "url": candidate_url,
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "verification": reasons,
                    },
                }
    return {"url": "", "warning": "X domain resolver found no verified official domain"}


def normalize_x_launch_item(item: dict, query: dict) -> dict:
    website = item.get("website") or item.get("homepage") or item.get("outbound_url") or ""
    website_domain = _domain_from_url(website)
    raw_domain = website_domain or str(item.get("domain") or "").strip().lower().removeprefix("www.")
    url_role = {}
    article_evidence_urls = []
    directory_evidence_urls = []
    repo_evidence_urls = []
    if classify_url_role and (website or raw_domain):
        role_url = website if website else f"https://{raw_domain}"
        url_role = classify_url_role(
            role_url,
            title=str(item.get("title") or ""),
            snippet=str(item.get("snippet") or item.get("description") or item.get("text") or ""),
        )
    domain = raw_domain if _domain_allowed(raw_domain) else ""
    if url_role and not url_role.get("official_eligible"):
        if url_role.get("role") == "article" and website:
            article_evidence_urls.append(website)
        elif url_role.get("role") == "directory" and website:
            directory_evidence_urls.append(website)
        elif url_role.get("role") == "repo" and website:
            repo_evidence_urls.append(website)
        website = ""
        domain = ""
    if website and website_domain and not _domain_allowed(website_domain):
        website = ""
        domain = ""
    company_name = item.get("company_name") or item.get("name") or _company_name_from_title(item.get("title", ""))
    inferred_embedded_url = ""
    if not company_name:
        inferred_embedded_url = _embedded_official_url_without_name(item)
        inferred_domain = _domain_from_url(inferred_embedded_url)
        if inferred_domain:
            company_name = _company_name_from_domain(inferred_domain)
            website = website or inferred_embedded_url
            domain = domain or inferred_domain
    missing = []
    if not company_name:
        missing.append("company_name_missing")
    if not domain:
        missing.append("official_domain_identity_not_confirmed")
    domain_resolution_source = ""
    domain_resolution_evidence = {}
    if not domain and company_name:
        launch_identity = {"company_name": company_name, "description": item.get("snippet") or item.get("description") or item.get("text") or ""}
        embedded = resolve_embedded_launch_link_domain(item, launch_identity)
        if not str(embedded.get("url") or "").strip():
            embedded = resolve_embedded_launch_text_domain(item, launch_identity)
        resolved_url = str(embedded.get("url") or "").strip()
        if resolved_url:
            website = resolved_url
            domain = _domain_from_url(resolved_url)
            domain_resolution_source = str((embedded.get("evidence") or {}).get("source") or "embedded_launch_text_url")
            domain_resolution_evidence = embedded.get("evidence") or {}
            missing = [gap for gap in missing if gap != "official_domain_identity_not_confirmed"]
    launch_score, launch_basis = _launch_intent_score({**item, "company_name": company_name, "website": website, "domain": domain})
    action = "research deeper" if launch_score >= 65 else "watch"
    if launch_score < 65:
        missing.append("launch_intent_low")
    row = {
        "source": "x",
        "source_lane": "X",
        "name": company_name,
        "company_name": company_name,
        "title": item.get("title") or company_name,
        "url": item.get("url") or item.get("x_url") or "",
        "company_x": item.get("company_x") or item.get("x_url") or item.get("url") or "",
        "website": website,
        "domain": domain,
        "description": item.get("snippet") or item.get("description") or item.get("text") or "",
        "snippet": item.get("snippet") or item.get("description") or item.get("text") or "",
        "published_at": item.get("published_at", ""),
        "author": item.get("author", ""),
        "movement": query.get("movement", ""),
        "market_sector": query.get("market_sector", ""),
        "query_topic": query.get("topic", ""),
        "launch_intent_score": launch_score,
        "launch_intent_basis": launch_basis,
        "social_confidence_evidence": [
            {
                "source": "x",
                "url": item.get("url") or item.get("x_url") or "",
                "author": item.get("author", ""),
                "published_at": item.get("published_at", ""),
                "title": item.get("title") or company_name,
            }
        ],
        "article_evidence_urls": article_evidence_urls,
        "directory_evidence_urls": directory_evidence_urls,
        "repo_evidence_urls": repo_evidence_urls,
        "url_role": url_role,
        "action": action,
        "lead_route": "research_deeper" if action == "research deeper" else "watch",
        "missing_evidence": missing,
        "why_this_may_be_noise": (
            "X launch/social-confidence row; needs official identity, durable founder/team, "
            "stage/funding, customer, and Marathon context before owner routing."
        ),
    }
    if domain_resolution_source:
        row["domain_resolution_source"] = domain_resolution_source
    elif inferred_embedded_url:
        row["domain_resolution_source"] = "embedded_launch_text_url"
    if domain_resolution_evidence:
        row["domain_resolution_evidence"] = domain_resolution_evidence
    elif inferred_embedded_url:
        row["domain_resolution_evidence"] = {
            "source": "embedded_launch_text_url",
            "domain": domain,
            "url": inferred_embedded_url,
            "verification": ["company_name_inferred_from_embedded_domain", "clear_launch_language"],
        }
    return _decorate_x_launch_row(row, item)


def run_x_launches(
    *,
    movements: list[dict],
    query_runner,
    domain_resolver=resolve_x_launch_domain_via_web,
    env: dict[str, str] | None = None,
    limit: int = 25,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    timeout_seconds: int | None = DEFAULT_TIMEOUT_SECONDS,
    max_queries: int = MAX_X_LAUNCH_QUERIES,
    max_domain_resolutions: int = MAX_X_DOMAIN_RESOLUTIONS,
) -> dict:
    runtime_env = merged_x_env(env) if env is None else env
    if not x_credentials_available(runtime_env):
        return {
            "launches": [],
            "warnings": ["X launch lane skipped: configure XAI_API_KEY or X AUTH_TOKEN/CT0 in last30days config."],
            "status": "unavailable",
        }
    if not query_runner:
        return {
            "launches": [],
            "warnings": ["X launch lane skipped: last30days query runner unavailable."],
            "status": "unavailable",
        }

    warnings = []
    launches = []
    queries = build_x_launch_queries(movements, lookback_days=lookback_days)[:max_queries]
    domain_resolution_attempts = 0
    domain_resolution_cap_warned = False
    seen_launch_keys = set()
    for query in queries:
        if len(launches) >= limit:
            break
        try:
            payload = query_runner(
                topic=query["topic"],
                sources="x",
                lookback_days=query["lookback_days"],
                auto_resolve=True,
                store=True,
                web_backend="none",
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            warnings.append(f"{query['id']}: {exc}")
            continue
        warnings.extend(payload.get("warnings", []) or [])
        for source, error in (payload.get("errors_by_source", {}) or {}).items():
            warnings.append(f"{source}: {error}")
        for item in payload.get("items", []) or []:
            launch = normalize_x_launch_item(item, query)
            launch_key = launch.get("url") or launch.get("company_x") or launch.get("domain") or launch.get("company_name")
            if launch_key and launch_key in seen_launch_keys:
                continue
            if not launch["domain"] and not _resolvable_company_name(launch["company_name"]):
                if launch["company_name"]:
                    warnings.append(f"{launch['company_name']}: X launch skipped because company name is too generic")
                continue
            if not launch["domain"] and launch["company_name"] and domain_resolver and domain_resolution_attempts < max_domain_resolutions:
                domain_resolution_attempts += 1
                resolved = domain_resolver(launch, query_runner=query_runner, timeout_seconds=timeout_seconds)
                resolved_url = str(resolved.get("url") or "").strip() if isinstance(resolved, dict) else ""
                if resolved_url:
                    launch["website"] = resolved_url
                    launch["domain"] = _domain_from_url(resolved_url)
                    launch["domain_resolution_source"] = "web_fallback"
                    if resolved.get("evidence"):
                        launch["domain_resolution_evidence"] = resolved["evidence"]
                    launch["missing_evidence"] = [
                        gap for gap in launch.get("missing_evidence", []) if gap != "official_domain_identity_not_confirmed"
                    ]
                else:
                    warning = str(resolved.get("warning") or "").strip() if isinstance(resolved, dict) else ""
                    if warning:
                        warnings.append(f"{launch['company_name']}: {warning}")
            elif not launch["domain"] and launch["company_name"] and domain_resolver and domain_resolution_attempts >= max_domain_resolutions:
                if not domain_resolution_cap_warned:
                    warnings.append(f"X domain resolver capped after {max_domain_resolutions} attempts")
                    domain_resolution_cap_warned = True
            if launch["company_name"] or launch["domain"]:
                launches.append(launch)
                if launch_key:
                    seen_launch_keys.add(launch_key)
            if len(launches) >= limit:
                break

    return {
        "launches": launches[:limit],
        "warnings": warnings,
        "status": "complete" if launches else "unavailable" if any("403" in warning or "Forbidden" in warning for warning in warnings) else "empty",
        "queries": queries,
    }


def main() -> None:
    print(json.dumps({"error": "x_launches.py is used through radar_run.py so a query runner can be supplied."}, indent=2))


if __name__ == "__main__":
    main()
