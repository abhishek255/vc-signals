#!/usr/bin/env python3
"""Product Hunt launch/API adapter for company-formation signals."""

from __future__ import annotations

import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests

    HAS_REQUESTS = True
except ImportError:  # pragma: no cover - damaged local installs
    requests = None
    HAS_REQUESTS = False


PRODUCT_HUNT_FEED_URL = "https://www.producthunt.com/feed"
PRODUCT_HUNT_API_URL = "https://api.producthunt.com/v2/api/graphql"
PRODUCT_HUNT_HOSTS = {"producthunt.com", "www.producthunt.com"}
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_WEB_RESOLVER_TIMEOUT_SECONDS = 8
MAX_WEB_RESOLVER_QUERIES = 4
PLACEHOLDER_VALUES = {"", "...", "TODO", "YOUR_KEY", "YOUR_API_KEY", "<YOUR_API_KEY>"}

try:
    from last30days_adapter import DEFAULT_CONFIG_PATH
    from last30days_adapter import run_query as run_last30days_query
except ImportError:  # pragma: no cover - damaged local installs
    DEFAULT_CONFIG_PATH = Path.home() / ".config" / "last30days" / ".env"
    run_last30days_query = None

try:
    from signal_investigator import build_investigation_packet, build_search_plan, classify_url_role
except ImportError:  # pragma: no cover - damaged local installs
    build_investigation_packet = None
    build_search_plan = None
    classify_url_role = None

try:
    from discovery_search_providers import load_provider_env_files, provider_available, run_provider_query
except ImportError:  # pragma: no cover - damaged local installs
    load_provider_env_files = None
    provider_available = None
    run_provider_query = None


class _ContentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._current_link = ""
        self._current_paragraph: list[str] = []
        self._in_paragraph = False
        self.paragraphs: list[str] = []
        self.links: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self._in_paragraph = True
            self._current_paragraph = []
        if tag == "a":
            href = dict(attrs).get("href") or ""
            self._current_link = href

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._in_paragraph:
            text = _clean_text(" ".join(self._current_paragraph))
            if text:
                self.paragraphs.append(text)
            self._current_paragraph = []
            self._in_paragraph = False
        if tag == "a":
            self._current_link = ""

    def handle_data(self, data: str) -> None:
        text = _clean_text(data)
        if self._in_paragraph and text:
            self._current_paragraph.append(text)
        if self._current_link and text:
            self.links.append({"text": text, "href": html.unescape(self._current_link)})


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def _host(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _normalize_domain(value: str) -> str:
    if not value:
        return ""
    if "://" in value:
        return _host(value)
    value = value.lower().strip().strip("/")
    return value[4:] if value.startswith("www.") else value


DOMAIN_BLOCKLIST = PRODUCT_HUNT_HOSTS | {
    "apps.apple.com",
    "chromewebstore.google.com",
    "discord.gg",
    "discord.com",
    "docs.google.com",
    "github.com",
    "g2.com",
    "instagram.com",
    "linkedin.com",
    "medium.com",
    "notion.site",
    "apkpure.com",
    "alternativeto.net",
    "capterra.com",
    "reddit.com",
    "saasworthy.com",
    "softonic.com",
    "substack.com",
    "techcrunch.com",
    "theguardian.com",
    "tracxn.com",
    "tiktok.com",
    "twitter.com",
    "uptodown.com",
    "venturebeat.com",
    "wired.com",
    "x.com",
    "youtube.com",
}


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


def product_hunt_token(
    env: dict[str, str] | None = None,
    *,
    config_path: Path | str = DEFAULT_CONFIG_PATH,
) -> str:
    merged = load_env_file(config_path)
    merged.update(os.environ)
    if env is not None:
        merged.update(env)
    for key in ("PRODUCT_HUNT_TOKEN", "PRODUCTHUNT_API_TOKEN", "PRODUCT_HUNT_API_TOKEN"):
        value = merged.get(key)
        if _configured(value):
            return str(value).strip().strip("\"'")
    return ""


def _split_title_and_maker(title: str) -> tuple[str, str]:
    match = re.match(r"^(?P<name>.+?)\s+by\s+(?P<maker>.+)$", title or "", flags=re.IGNORECASE)
    if not match:
        return _clean_text(title), ""
    return _clean_text(match.group("name")), _clean_text(match.group("maker"))


def _parse_content(content: str) -> tuple[str, list[dict]]:
    parser = _ContentParser()
    parser.feed(html.unescape(content or ""))
    tagline = ""
    for paragraph in parser.paragraphs:
        if "Discussion" not in paragraph and "Link" not in paragraph:
            tagline = paragraph
            break
    return tagline, parser.links


def _launch_date(published_at: str) -> str:
    return (published_at or "").split("T", 1)[0]


def _external_link_from_links(links: list[dict]) -> str:
    for link in links:
        if (link.get("text") or "").lower() == "link" and link.get("href"):
            return link["href"]
    for link in links:
        href = link.get("href") or ""
        if href and _host(href) not in PRODUCT_HUNT_HOSTS:
            return href
    return ""


def _domain_allowed(domain: str) -> bool:
    normalized = _normalize_domain(domain)
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
    stop = {
        "and",
        "app",
        "better",
        "company",
        "for",
        "from",
        "into",
        "launch",
        "launched",
        "over",
        "ring",
        "smallest",
        "startup",
        "over",
        "that",
        "the",
        "this",
        "world",
        "with",
        "your",
    }
    return {token for token in re.findall(r"[a-z0-9]{3,}", (value or "").lower()) if token not in stop}


def _candidate_url_from_item(item: dict) -> str:
    urls = _candidate_urls_from_item(item)
    return urls[0] if urls else ""


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
        domain = _normalize_domain(candidate)
        if domain and _domain_allowed(domain):
            urls.append(candidate if "://" in candidate else f"https://{candidate}")
    return urls


def _text_extracted_urls_from_item(item: dict) -> list[str]:
    urls = []
    for key in ("title", "snippet", "description", "body", "text", "container"):
        urls.extend(_urls_from_text(str(item.get(key) or "")))
    return list(dict.fromkeys(urls))


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


def _candidate_text(item: dict) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "snippet", "description", "body", "container", "url", "website", "homepage")
    )


def _product_alias_slugs(name: str) -> set[str]:
    cleaned = re.sub(r"\b(?:v?\d+(?:\.\d+)+|beta|alpha)\b", " ", name or "", flags=re.IGNORECASE)
    pieces = [cleaned]
    pieces.extend(re.split(r"\s+(?:by|from)\s+", cleaned, flags=re.IGNORECASE))
    pieces.extend(re.split(r"[|/•:–—-]+", cleaned))
    tokens = [token for token in _text_tokens(cleaned) if len(token) >= 4]
    if tokens:
        pieces.append(tokens[0])
        if len(tokens) >= 2:
            pieces.append(" ".join(tokens[:2]))
    aliases = {_name_slug(piece) for piece in pieces if _name_slug(piece)}
    return {alias for alias in aliases if len(alias) >= 4}


def _verify_domain_candidate(launch: dict, item: dict) -> tuple[bool, list[str]]:
    url = _candidate_url_from_item(item)
    domain = _normalize_domain(url or item.get("domain", ""))
    if not _domain_allowed(domain):
        return False, []
    if classify_url_role:
        role = classify_url_role(url or f"https://{domain}", title=str(item.get("title") or ""), snippet=_candidate_text(item))
        if not role.get("official_eligible"):
            return False, []

    name = str(launch.get("name") or launch.get("company_name") or "")
    tagline = str(launch.get("tagline") or launch.get("description") or "")
    name_slug = _name_slug(name)
    domain_slug = _domain_identity_slug(domain)
    text = _candidate_text(item)
    text_blob = text.lower()
    tagline_hits = _text_tokens(tagline) & _text_tokens(text)
    name_tokens = _text_tokens(name)
    alias_slugs = _product_alias_slugs(name)
    domain_alias_match = bool(
        (domain_slug and any(alias in domain_slug or domain_slug in alias for alias in alias_slugs))
        or any(token in domain_slug for token in name_tokens)
    )
    domain_name_match = bool(
        (name_slug and len(name_slug) >= 4 and name_slug in domain_slug)
        or (domain_slug and len(domain_slug) >= 4 and domain_slug in name_slug)
    )
    text_match = bool((name and name.lower() in text_blob) or len(tagline_hits) >= 2)
    strong_launch_text_match = bool((name and name.lower() in text_blob and len(tagline_hits) >= 2) or len(tagline_hits) >= 3)
    reasons = []
    if domain_name_match:
        reasons.append("domain_matches_product_name")
    if domain_alias_match:
        reasons.append("domain_matches_product_alias")
    if name and name.lower() in text_blob:
        reasons.append("search_result_mentions_product_name")
    if len(tagline_hits) >= 2:
        reasons.append("search_result_matches_tagline")
    if url in _text_extracted_urls_from_item(item):
        reasons.append("url_extracted_from_text")
    if strong_launch_text_match:
        reasons.append("strong_launch_text_match")
    tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
    name_only_match = bool(name and name.lower() in text_blob and len(tagline_hits) < 1)
    if len(name_tokens) <= 1:
        if name_only_match and len(tagline_hits) < 2:
            return False, []
        if len(tagline_hits) < 2:
            return False, []
    return (domain_name_match or domain_alias_match) and text_match, reasons


def _absolute_url(candidate_url: str, domain: str) -> str:
    return candidate_url if "://" in candidate_url else f"https://{domain}"


def _structured_row_candidate_urls(item: dict) -> list[tuple[str, str]]:
    urls: list[tuple[str, str]] = []
    for key in ("website", "homepage", "resolved_url"):
        value = str(item.get(key) or "").strip()
        if value:
            urls.append((value, key))
    for key in ("source_outbound_urls", "source_urls", "evidence_urls"):
        for raw_url in item.get(key) or []:
            value = str(raw_url or "").strip()
            if value:
                urls.append((value, key))
    for link in item.get("links") or item.get("outbound_links") or []:
        if isinstance(link, dict):
            value = str(link.get("url") or link.get("href") or "").strip()
        else:
            value = str(link or "").strip()
        if value:
            urls.append((value, "links"))
    for value in _text_extracted_urls_from_item(item):
        urls.append((value, "text"))
    deduped: list[tuple[str, str]] = []
    seen = set()
    for value, source in urls:
        if value in seen:
            continue
        seen.add(value)
        deduped.append((value, source))
    return deduped


def resolve_row_level_launch_domain(launch: dict) -> dict:
    for candidate_url, source_key in _structured_row_candidate_urls(launch):
        domain = _normalize_domain(candidate_url)
        if not _domain_allowed(domain):
            continue
        absolute_url = _absolute_url(candidate_url, domain)
        if classify_url_role:
            role = classify_url_role(
                absolute_url,
                title=str(launch.get("title") or launch.get("name") or ""),
                snippet=str(launch.get("tagline") or launch.get("description") or ""),
            )
            if not role.get("official_eligible"):
                continue
        if source_key == "text":
            verified, reasons = _verify_domain_candidate(launch, {**launch, "url": absolute_url})
            if not verified:
                continue
        else:
            reasons = ["structured_launch_url_present"]
        return {
            "url": absolute_url,
            "warning": "",
            "evidence": {
                "source": "row_level_official_url",
                "source_key": source_key,
                "domain": domain,
                "url": absolute_url,
                "verification": reasons,
            },
        }
    return {"url": "", "warning": "no row-level official URL"}


def _web_domain_query(launch: dict) -> str:
    name = str(launch.get("name") or launch.get("company_name") or "").strip()
    tagline = str(launch.get("tagline") or launch.get("description") or "").strip()
    quoted_name = f'"{name}"' if name else ""
    quoted_tagline = f'"{tagline}"' if tagline else ""
    return " ".join(part for part in (quoted_name, quoted_tagline, "official website company startup") if part)


def _fixed_web_domain_queries(launch: dict) -> list[dict]:
    name = str(launch.get("name") or launch.get("company_name") or "").strip()
    tagline = str(launch.get("tagline") or launch.get("description") or "").strip()
    queries = []
    if name:
        queries.append({"query": f'"{name}" official website', "sources": "web", "search_plan_source": "fixed_short_name"})
    if name and tagline:
        compact_tagline = " ".join(sorted(_text_tokens(tagline))[:5])
        if compact_tagline:
            queries.append(
                {
                    "query": f'"{name}" {compact_tagline} official',
                    "sources": "web",
                    "search_plan_source": "fixed_compact_tagline",
                }
            )
    fallback_query = _web_domain_query(launch)
    if fallback_query:
        queries.append({"query": fallback_query, "sources": "web", "search_plan_source": "fixed_fallback"})
    return queries


def _web_domain_queries(launch: dict, *, max_queries: int = MAX_WEB_RESOLVER_QUERIES) -> list[dict]:
    queries: list[dict] = []
    queries.extend(_fixed_web_domain_queries(launch))
    if build_investigation_packet and build_search_plan:
        packet = build_investigation_packet(
            {
                **launch,
                "source_lane": "Product Hunt",
                "candidate_type": "producthunt_launch",
                "why_on_radar": launch.get("tagline") or launch.get("description") or "",
            }
        )
        plan = build_search_plan(packet, provider=lambda _packet: None)
        for item in plan.get("search_plan") or []:
            query = str(item.get("query") or "").strip()
            if query:
                queries.append(
                    {
                        "query": query,
                        "sources": item.get("sources") or "grounding",
                        "search_plan_source": "signal_investigator",
                    }
                )
    seen = set()
    out = []
    for item in queries:
        key = item["query"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out[:max_queries]


def _provider_names(provider: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(provider, str):
        raw_names = provider.split(",")
    else:
        raw_names = list(provider or [])
    names = []
    seen = set()
    for raw_name in raw_names:
        name = str(raw_name or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _available_provider_fallbacks(provider: str | list[str] | tuple[str, ...]) -> list[str]:
    if not (load_provider_env_files and provider_available and run_provider_query):
        return []
    load_provider_env_files()
    return [name for name in _provider_names(provider) if provider_available(name)]


def _provider_fallback_available(provider: str | list[str] | tuple[str, ...]) -> bool:
    return bool(_available_provider_fallbacks(provider))


def _run_provider_fallback_query(
    query_item: dict,
    *,
    provider: str,
    timeout_seconds: int,
    max_results: int = 8,
) -> dict:
    if not run_provider_query:
        return {"items": [], "error": "provider query runner unavailable"}
    return run_provider_query(
        provider,
        {"query": query_item["query"], "query_family": "product_hunt_domain_resolver"},
        max_results=max_results,
        timeout_seconds=timeout_seconds,
    )


def _resolve_from_payload_items(launch: dict, payload: dict, query_item: dict, *, evidence_source: str) -> dict:
    for item in payload.get("items", []) or []:
        for candidate_url in _candidate_urls_from_item(item):
            candidate_item = dict(item)
            candidate_item["url"] = candidate_url
            domain = _normalize_domain(candidate_url or item.get("domain", ""))
            verified, reasons = _verify_domain_candidate(launch, candidate_item)
            if verified:
                return {
                    "url": candidate_url if "://" in candidate_url else f"https://{domain}",
                    "warning": "",
                    "evidence": {
                        "source": evidence_source,
                        "search_plan_source": query_item.get("search_plan_source", "fixed_fallback"),
                        "query": query_item["query"],
                        "domain": domain,
                        "url": candidate_url,
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "verification": reasons,
                    },
                }
    return {"url": "", "warning": ""}


def resolve_launch_domain_via_web(
    launch: dict,
    *,
    query_runner=run_last30days_query,
    timeout_seconds: int | None = DEFAULT_TIMEOUT_SECONDS,
    max_queries: int = MAX_WEB_RESOLVER_QUERIES,
    provider_fallback: bool | None = None,
    provider: str | list[str] | tuple[str, ...] = "exa,brave",
) -> dict:
    if not query_runner:
        return {"url": "", "warning": "last30days query runner unavailable"}
    queries = _web_domain_queries(launch, max_queries=max_queries)
    if not queries:
        return {"url": "", "warning": "missing Product Hunt name/tagline for web resolver"}
    last_error = ""
    query_timeout = min(timeout_seconds or DEFAULT_TIMEOUT_SECONDS, DEFAULT_WEB_RESOLVER_TIMEOUT_SECONDS)
    if provider_fallback is None:
        provider_fallback = query_runner is run_last30days_query
    provider_fallbacks = _available_provider_fallbacks(provider) if provider_fallback else []
    for query_item in queries:
        query = query_item["query"]
        provider_returned_items = False
        for provider_name in provider_fallbacks:
            provider_payload = {}
            try:
                provider_payload = _run_provider_fallback_query(
                    query_item,
                    provider=provider_name,
                    timeout_seconds=query_timeout,
                )
            except Exception as exc:
                last_error = f"{provider_name} resolver failed: {exc}"
            if provider_payload.get("skipped"):
                last_error = f"{provider_name} resolver skipped: {provider_payload.get('skip_reason') or 'unknown'}"
            provider_resolved = _resolve_from_payload_items(
                launch,
                provider_payload,
                query_item,
                evidence_source=f"{provider_name}_fallback",
            )
            if provider_resolved.get("url"):
                return provider_resolved
            if provider_payload.get("items"):
                provider_returned_items = True
        if provider_returned_items:
            continue
        try:
            payload = query_runner(
                topic=query,
                sources=query_item.get("sources") or "web",
                lookback_days=30,
                auto_resolve=True,
                store=False,
                timeout_seconds=query_timeout,
            )
        except Exception as exc:
            last_error = f"web resolver failed: {exc}"
            payload = {}
        if payload.get("error"):
            last_error = f"web resolver failed: {payload['error']}"
        resolved = _resolve_from_payload_items(launch, payload, query_item, evidence_source="web_fallback")
        if resolved.get("url"):
            return resolved
    if last_error:
        return {"url": "", "warning": last_error}
    return {"url": "", "warning": "web resolver found no verified official domain"}


def _first_website_link(post: dict) -> str:
    candidates = []
    for link in post.get("productLinks") or []:
        if not isinstance(link, dict):
            continue
        link_type = str(link.get("type") or "").strip().lower()
        url = str(link.get("url") or "").strip()
        if url and (not link_type or link_type == "website"):
            candidates.append(url)
    if post.get("website"):
        candidates.append(str(post.get("website") or "").strip())
    for url in candidates:
        if _domain_allowed(_normalize_domain(url)):
            return url
    return candidates[0] if candidates else ""


def _maker_profiles(post: dict) -> list[dict]:
    profiles = []
    for maker in post.get("makers") or []:
        if not isinstance(maker, dict):
            continue
        name = _clean_text(str(maker.get("name") or ""))
        username = _clean_text(str(maker.get("username") or ""))
        url = str(maker.get("url") or "").strip()
        if name or username or url:
            profiles.append(
                {
                    "name": name,
                    "username": username,
                    "product_hunt_url": url,
                }
            )
    return profiles


def _maker_evidence_urls(profiles: list[dict]) -> list[str]:
    return [
        str(profile.get("product_hunt_url") or "").strip()
        for profile in profiles
        if str(profile.get("product_hunt_url") or "").strip()
    ]


def _is_product_hunt_launch(item: dict) -> bool:
    return (
        str(item.get("source_detail") or "").strip() == "api"
        or str(item.get("source_lane") or "").strip().lower() == "product hunt"
        or str(item.get("source") or "").strip().lower() in {"producthunt", "product_hunt"}
        or "producthunt.com/" in str(item.get("product_hunt_url") or item.get("url") or "").lower()
    )


def _product_hunt_missing_evidence(item: dict) -> list[str]:
    missing = []
    domain = _normalize_domain(str(item.get("domain") or item.get("website") or ""))
    if not domain or not _domain_allowed(domain):
        missing.append("official_domain_identity_not_confirmed")
    if not (item.get("maker_profiles") or item.get("maker_name") or item.get("founder_team_evidence")):
        missing.append("founder_team_missing")
    if not (item.get("stage") or item.get("raised") or item.get("headcount") or item.get("stage_funding_evidence")):
        missing.append("stage_funding_or_headcount_missing")
    if not (item.get("customer_buyer_evidence") or item.get("customer_buyer_evidence_types")):
        missing.append("commercial_or_customer_signal_missing")
    if not (item.get("pricing_evidence") or item.get("docs_evidence") or item.get("careers_evidence")):
        missing.append("pricing_docs_or_careers_missing")
    if not (item.get("company_linkedin") or item.get("company_x")):
        missing.append("company_linkedin_or_social_missing")
    return missing


def _maker_profile_urls_from_item(item: dict) -> list[str]:
    urls = []
    for profile in item.get("maker_profiles") or []:
        if isinstance(profile, dict):
            url = str(profile.get("product_hunt_url") or profile.get("url") or "").strip()
        else:
            url = str(profile or "").strip()
        if url:
            urls.append(url)
    return list(dict.fromkeys(urls))


def _product_hunt_source_urls(item: dict) -> list[str]:
    urls = []
    for value in (
        item.get("website"),
        item.get("outbound_url"),
        item.get("product_hunt_url"),
        item.get("url"),
        *(item.get("source_outbound_urls") or []),
        *_maker_profile_urls_from_item(item),
    ):
        url = str(value or "").strip()
        if url:
            urls.append(url)
    return list(dict.fromkeys(urls))


def _product_hunt_launch_context(item: dict) -> dict:
    return {
        "role": "launch_source",
        "identity_policy": (
            "Product Hunt proves launch context; official company identity must come from the outbound site, "
            "maker/operator proof, official pages, or manual/structured metadata."
        ),
        "product_hunt_url": item.get("product_hunt_url") or item.get("url") or "",
        "launch_date": item.get("launch_date", ""),
        "source_detail": item.get("source_detail", ""),
        "votes_count": item.get("votes_count", 0),
        "comments_count": item.get("comments_count", 0),
        "daily_rank": item.get("daily_rank", ""),
        "maker_name": item.get("maker_name", ""),
        "maker_profile_urls": _maker_profile_urls_from_item(item),
    }


def _ph_plan_item(field: str, present: bool, why: str, where_to_check: list[str]) -> dict:
    return {
        "field": field,
        "status": "present" if present else "missing",
        "why_it_matters": why,
        "where_to_check": where_to_check,
        "promote_if_found": (
            "Use this Product Hunt launch as a Partner Review candidate when this evidence matches the official company."
        ),
        "discard_if_not_found": "Keep as launch watch or discard if Product Hunt remains the only proof.",
    }


def _product_hunt_evidence_completion_plan(item: dict) -> list[dict]:
    missing = set(item.get("missing_evidence") or [])
    domain = _normalize_domain(str(item.get("domain") or item.get("website") or ""))
    official_site = f"https://{domain}" if domain and _domain_allowed(domain) else "official company website"
    return [
        _ph_plan_item(
            "official_domain",
            "official_domain_identity_not_confirmed" not in missing,
            "Product Hunt is a launch source, not the company identity source.",
            ["Product Hunt outbound link", "Company Info field", "maker profile", "web search official result"],
        ),
        _ph_plan_item(
            "founder_team",
            "founder_team_missing" not in missing,
            "Maker/founder evidence tells us there is a real operator behind the launch.",
            ["Product Hunt maker page", f"{official_site}/about", f"{official_site}/team", "LinkedIn manual check"],
        ),
        _ph_plan_item(
            "commercial",
            "commercial_or_customer_signal_missing" not in missing,
            "Commercial proof separates a real company surface from a launch announcement.",
            [f"{official_site}/pricing", f"{official_site}/docs", f"{official_site}/customers", f"{official_site}/case-studies"],
        ),
        _ph_plan_item(
            "pricing_docs_careers",
            "pricing_docs_or_careers_missing" not in missing,
            "Pricing, docs, or careers pages are fast public proof of product and company maturity.",
            [f"{official_site}/pricing", f"{official_site}/docs", f"{official_site}/careers", f"{official_site}/jobs"],
        ),
        _ph_plan_item(
            "stage_funding_headcount",
            "stage_funding_or_headcount_missing" not in missing,
            "Stage, funding, headcount, or hiring evidence helps decide whether this is partner-reviewable.",
            ["careers page", "public funding snippets", "Crunchbase-style web result", "LinkedIn manual check"],
        ),
        _ph_plan_item(
            "social",
            "company_linkedin_or_social_missing" not in missing,
            "Company social or LinkedIn metadata is supporting confidence, not identity truth by itself.",
            ["company LinkedIn page", "company X profile", "founder/operator profile"],
        ),
    ]


def _product_hunt_manual_review_checklist(item: dict) -> list[str]:
    checks = []
    for plan_item in _product_hunt_evidence_completion_plan(item):
        if plan_item["status"] != "missing":
            continue
        field = plan_item["field"].replace("_", " ")
        if plan_item["field"] == "commercial":
            checks.append(f"Check company website/docs/customers for commercial proof: {', '.join(plan_item['where_to_check'])}.")
            continue
        checks.append(f"Check {field}: {', '.join(plan_item['where_to_check'])}.")
    return checks or ["Do one focused contradiction check before promotion."]


def _refresh_product_hunt_conversion_fields(item: dict) -> None:
    if not _is_product_hunt_launch(item):
        return
    item["missing_evidence"] = _product_hunt_missing_evidence(item)
    item["product_hunt_role"] = "launch_source_not_identity_source"
    item["launch_context"] = _product_hunt_launch_context(item)
    item["source_outbound_urls"] = _product_hunt_source_urls(item)
    if item.get("domain"):
        item["product_hunt_conversion_status"] = (
            "domain_resolved_needs_company_evidence"
            if item["missing_evidence"]
            else "domain_resolved_company_evidence_complete"
        )
    else:
        item["product_hunt_conversion_status"] = "needs_official_domain"
    item["conversion_blockers"] = list(item["missing_evidence"])
    item["evidence_completion_plan"] = _product_hunt_evidence_completion_plan(item)
    checklist = _product_hunt_manual_review_checklist(item)
    item["manual_review_checklist"] = checklist
    item["recommended_manual_check"] = checklist[0] if checklist else ""
    item["promote_if"] = (
        "Promote if manual review confirms official identity plus founder/operator and commercial or maturity evidence."
    )
    item["discard_if"] = "Discard if evidence remains only a Product Hunt page, social chatter, or third-party directory."
    item["likely_payoff"] = (
        "High if the official site has pricing/docs/customers/careers; medium if only makers and launch context are visible."
    )


def normalize_product_hunt_api_post(post: dict) -> dict:
    name = _clean_text(str(post.get("name") or ""))
    tagline = _clean_text(str(post.get("tagline") or post.get("description") or ""))
    created_at = _clean_text(str(post.get("featuredAt") or post.get("createdAt") or ""))
    maker_profiles = _maker_profiles(post)
    maker_name = ", ".join(profile["name"] for profile in maker_profiles if profile.get("name"))
    product_hunt_url = str(post.get("url") or "").strip()
    outbound_url = _first_website_link(post)
    item = {
        "source": "producthunt",
        "source_lane": "Product Hunt",
        "source_detail": "api",
        "name": name,
        "company_name": name,
        "maker_name": maker_name,
        "maker_profiles": maker_profiles,
        "title": name,
        "tagline": tagline,
        "description": tagline,
        "published_at": created_at,
        "launch_date": _launch_date(created_at),
        "url": product_hunt_url,
        "product_hunt_url": product_hunt_url,
        "outbound_url": outbound_url,
        "domain": "",
        "website": "",
        "votes_count": post.get("votesCount") or 0,
        "comments_count": post.get("commentsCount") or 0,
        "daily_rank": post.get("dailyRank"),
        "launch_evidence": {
            "votes_count": post.get("votesCount") or 0,
            "comments_count": post.get("commentsCount") or 0,
            "daily_rank": post.get("dailyRank"),
            "product_hunt_url": product_hunt_url,
        },
        "founder_team_evidence": _maker_evidence_urls(maker_profiles),
        "action": "research deeper",
        "lead_route": "research_deeper",
        "missing_evidence": ["official_domain_identity_not_confirmed"],
        "why_this_may_be_noise": (
            "Product Hunt API launch row; needs official domain, founder/team, stage, "
            "and customer evidence before owner routing."
        ),
    }
    _refresh_product_hunt_conversion_fields(item)
    return item


PRODUCT_HUNT_POSTS_QUERY = """
query ProductHuntLaunches($first: Int!) {
  posts(first: $first) {
    edges {
      node {
        id
        name
        tagline
        description
        url
        website
        votesCount
        commentsCount
        createdAt
        featuredAt
        dailyRank
        makers {
          name
          username
          url
        }
        productLinks {
          type
          url
        }
      }
    }
  }
}
""".strip()


def fetch_product_hunt_api_posts(
    *,
    token: str,
    limit: int = 20,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    api_url: str = PRODUCT_HUNT_API_URL,
) -> list[dict]:
    if not HAS_REQUESTS:
        raise RuntimeError("requests unavailable")
    if not _configured(token):
        raise RuntimeError("Product Hunt API token missing")
    response = requests.post(
        api_url,
        json={"query": PRODUCT_HUNT_POSTS_QUERY, "variables": {"first": limit}},
        timeout=timeout_seconds,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "vc-signals-product-hunt-api/1.0",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        messages = "; ".join(str(error.get("message") or error) for error in payload["errors"][:3])
        raise RuntimeError(f"Product Hunt API returned errors: {messages}")
    edges = payload.get("data", {}).get("posts", {}).get("edges", []) or []
    posts = [edge.get("node", {}) for edge in edges if isinstance(edge, dict)]
    return [post for post in posts if isinstance(post, dict)]


def parse_product_hunt_api_posts(posts: list[dict], *, limit: int = 20) -> list[dict]:
    launches = []
    for post in posts:
        if len(launches) >= limit:
            break
        launch = normalize_product_hunt_api_post(post)
        if launch["name"]:
            launches.append(launch)
    return launches


def parse_product_hunt_feed(feed_xml: str, *, limit: int = 20) -> list[dict]:
    root = ET.fromstring(feed_xml)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    launches: list[dict] = []
    for entry in root.findall("atom:entry", namespace):
        if len(launches) >= limit:
            break
        title = _clean_text(entry.findtext("atom:title", default="", namespaces=namespace))
        if not title:
            continue
        product_name, maker_name = _split_title_and_maker(title)
        content = entry.findtext("atom:content", default="", namespaces=namespace) or ""
        tagline, content_links = _parse_content(content)
        alternate_url = ""
        for link in entry.findall("atom:link", namespace):
            if link.attrib.get("rel") == "alternate" and link.attrib.get("href"):
                alternate_url = html.unescape(link.attrib["href"])
                break
        published_at = _clean_text(entry.findtext("atom:published", default="", namespaces=namespace))
        outbound_url = _external_link_from_links(content_links)
        launches.append(
            {
                "source": "producthunt",
                "source_lane": "Product Hunt",
                "name": product_name,
                "company_name": product_name,
                "maker_name": maker_name,
                "title": title,
                "tagline": tagline,
                "description": tagline,
                "published_at": published_at,
                "launch_date": _launch_date(published_at),
                "url": alternate_url,
                "product_hunt_url": alternate_url,
                "outbound_url": outbound_url,
                "domain": "",
                "website": "",
                "action": "research deeper",
                "lead_route": "research_deeper",
                "missing_evidence": ["official_domain_identity_not_confirmed"],
                "why_this_may_be_noise": (
                    "Product Hunt launch feed row; needs official domain, founder/team, stage, "
                    "and customer evidence before owner routing."
                ),
            }
        )
    return launches


def resolve_product_hunt_redirect(url: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> tuple[str, str]:
    if not url or not HAS_REQUESTS:
        return "", "requests unavailable" if not HAS_REQUESTS else ""
    try:
        response = requests.get(
            url,
            allow_redirects=False,
            timeout=timeout_seconds,
            headers={"User-Agent": "vc-signals-product-hunt-adapter/1.0"},
        )
    except Exception as exc:  # pragma: no cover - network dependent
        return "", str(exc)
    if 300 <= response.status_code < 400 and response.headers.get("location"):
        return response.headers["location"], ""
    return "", f"{response.status_code} {response.reason}".strip()


def enrich_launch_domains(
    launches: list[dict],
    *,
    resolver=resolve_product_hunt_redirect,
    fallback_resolver=None,
    timeout_seconds: int | None = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict]:
    enriched = []
    for launch in launches:
        item = dict(launch)
        outbound_url = item.get("outbound_url") or ""
        resolved_url = ""
        warning = ""
        row_level = resolve_row_level_launch_domain(item)
        row_level_url = str(row_level.get("url") or "").strip()
        if row_level_url:
            resolved_url = row_level_url
            item["domain_resolution_source"] = "row_level_official_url"
            if row_level.get("evidence"):
                item["domain_resolution_evidence"] = row_level["evidence"]
        elif outbound_url:
            outbound_domain = _normalize_domain(outbound_url)
            if outbound_domain and _domain_allowed(outbound_domain):
                resolved_url = outbound_url
            elif outbound_domain and outbound_domain not in PRODUCT_HUNT_HOSTS:
                warning = f"direct Product Hunt link uses non-official host {outbound_domain}"
            else:
                resolved_url, warning = resolver(outbound_url)
        if not _domain_allowed(_normalize_domain(resolved_url)) and fallback_resolver:
            fallback = fallback_resolver(item, timeout_seconds=timeout_seconds)
            fallback_url = str(fallback.get("url") or "").strip() if isinstance(fallback, dict) else ""
            fallback_warning = str(fallback.get("warning") or "").strip() if isinstance(fallback, dict) else ""
            if fallback_url:
                if warning:
                    item["product_hunt_redirect_warning"] = warning
                resolved_url = fallback_url
                item["domain_resolution_source"] = "web_fallback"
                if fallback.get("evidence"):
                    item["domain_resolution_evidence"] = fallback["evidence"]
                warning = ""
            elif fallback_warning:
                warning = f"{warning}; {fallback_warning}" if warning else fallback_warning
        domain = _normalize_domain(resolved_url)
        if _domain_allowed(domain):
            item["website"] = resolved_url
            item["domain"] = domain
            item["domain_resolution_status"] = "resolved"
            item.setdefault("domain_resolution_source", "product_hunt_redirect_or_direct_link")
            item["missing_evidence"] = [gap for gap in item.get("missing_evidence", []) if gap != "official_domain_identity_not_confirmed"]
        else:
            item.setdefault("website", "")
            item.setdefault("domain", "")
            item["domain_resolution_status"] = "unresolved"
            if warning:
                item["domain_resolution_warning"] = warning
            missing = list(item.get("missing_evidence") or [])
            if "official_domain_identity_not_confirmed" not in missing:
                missing.append("official_domain_identity_not_confirmed")
            item["missing_evidence"] = missing
        _refresh_product_hunt_conversion_fields(item)
        enriched.append(item)
    return enriched


def fetch_product_hunt_feed(*, feed_url: str = PRODUCT_HUNT_FEED_URL, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    if not HAS_REQUESTS:
        raise RuntimeError("requests unavailable")
    response = requests.get(
        feed_url,
        timeout=timeout_seconds,
        headers={"User-Agent": "vc-signals-product-hunt-adapter/1.0"},
    )
    response.raise_for_status()
    return response.text


def run_product_hunt_launches(*, limit: int = 20, timeout_seconds: int | None = DEFAULT_TIMEOUT_SECONDS) -> dict:
    warnings = []
    timeout = timeout_seconds or DEFAULT_TIMEOUT_SECONDS
    token = product_hunt_token()
    if token:
        try:
            posts = fetch_product_hunt_api_posts(token=token, limit=limit, timeout_seconds=timeout)
            launches = parse_product_hunt_api_posts(posts, limit=limit)
            launches = enrich_launch_domains(launches, fallback_resolver=resolve_launch_domain_via_web, timeout_seconds=timeout)
            for launch in launches:
                warning = launch.get("domain_resolution_warning")
                if warning:
                    warnings.append(f"{launch.get('name', 'unknown')}: {warning}")
            return {
                "launches": launches[:limit],
                "warnings": warnings,
                "source_mode": "api",
                "source_meta": {"endpoint": PRODUCT_HUNT_API_URL},
            }
        except Exception as exc:
            warnings.append(f"Product Hunt API unavailable, falling back to feed: {exc}")
    try:
        feed_xml = fetch_product_hunt_feed(timeout_seconds=timeout)
        launches = parse_product_hunt_feed(feed_xml, limit=limit)
        launches = enrich_launch_domains(launches, fallback_resolver=resolve_launch_domain_via_web, timeout_seconds=timeout)
        for launch in launches:
            warning = launch.get("domain_resolution_warning")
            if warning:
                warnings.append(f"{launch.get('name', 'unknown')}: {warning}")
        return {
            "launches": launches[:limit],
            "warnings": warnings,
            "source_mode": "feed_fallback" if token else "feed",
            "source_meta": {"endpoint": PRODUCT_HUNT_FEED_URL},
        }
    except Exception as exc:
        return {"launches": [], "warnings": [f"Product Hunt feed unavailable: {exc}"], "error": str(exc)}


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
    result = run_product_hunt_launches(
        limit=int(args.get("limit", 20)),
        timeout_seconds=int(args.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
