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


PLACEHOLDER_VALUES = {"", "...", "TODO", "YOUR_KEY", "YOUR_API_KEY", "<YOUR_API_KEY>"}
DEFAULT_LOOKBACK_DAYS = 14
DEFAULT_TIMEOUT_SECONDS = 45
DOMAIN_BLOCKLIST = {
    "apps.apple.com",
    "crunchbase.com",
    "facebook.com",
    "github.com",
    "instagram.com",
    "linkedin.com",
    "medium.com",
    "news.ycombinator.com",
    "producthunt.com",
    "reddit.com",
    "substack.com",
    "techcrunch.com",
    "tiktok.com",
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
        topic = f'("{movement}") (launching OR launched OR announcing OR shipped OR "we built") startup founder product'
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
    urls.extend(_text_extracted_urls_from_item(item))
    return list(dict.fromkeys(urls))


def _urls_from_text(value: str) -> list[str]:
    urls = []
    for match in re.findall(r"https?://[^\s<>)\\\"']+", value or ""):
        urls.append(match.rstrip(".,;:!?]})"))
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
    ):
        match = re.search(pattern, title)
        if match:
            return match.group("name").strip()
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


def _verify_domain_candidate(launch: dict, item: dict, candidate_url: str) -> tuple[bool, list[str]]:
    domain = _domain_from_url(candidate_url) or str(item.get("domain") or "").strip().lower().removeprefix("www.")
    if not _domain_allowed(domain):
        return False, []
    name = str(launch.get("company_name") or launch.get("name") or "").strip()
    if not _resolvable_company_name(name):
        return False, []
    name_slug = _name_slug(name)
    domain_slug = _name_slug(domain.split(".", 1)[0])
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
    try:
        payload = query_runner(
            topic=query,
            sources="web",
            lookback_days=30,
            auto_resolve=True,
            store=False,
            timeout_seconds=timeout_seconds,
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
    domain = raw_domain if _domain_allowed(raw_domain) else ""
    if website and website_domain and not _domain_allowed(website_domain):
        website = ""
    company_name = item.get("company_name") or item.get("name") or _company_name_from_title(item.get("title", ""))
    missing = []
    if not company_name:
        missing.append("company_name_missing")
    if not domain:
        missing.append("official_domain_identity_not_confirmed")
    domain_resolution_source = ""
    domain_resolution_evidence = {}
    if not domain and company_name:
        embedded = resolve_embedded_launch_text_domain(item, {"company_name": company_name, "description": item.get("snippet") or item.get("description") or item.get("text") or ""})
        resolved_url = str(embedded.get("url") or "").strip()
        if resolved_url:
            website = resolved_url
            domain = _domain_from_url(resolved_url)
            domain_resolution_source = "embedded_launch_text_url"
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
    if domain_resolution_evidence:
        row["domain_resolution_evidence"] = domain_resolution_evidence
    return row


def run_x_launches(
    *,
    movements: list[dict],
    query_runner,
    domain_resolver=resolve_x_launch_domain_via_web,
    env: dict[str, str] | None = None,
    limit: int = 25,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    timeout_seconds: int | None = DEFAULT_TIMEOUT_SECONDS,
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
    queries = build_x_launch_queries(movements, lookback_days=lookback_days)
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
            if not launch["domain"] and not _resolvable_company_name(launch["company_name"]):
                if launch["company_name"]:
                    warnings.append(f"{launch['company_name']}: X launch skipped because company name is too generic")
                continue
            if not launch["domain"] and launch["company_name"] and domain_resolver:
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
            if launch["company_name"] or launch["domain"]:
                launches.append(launch)
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
