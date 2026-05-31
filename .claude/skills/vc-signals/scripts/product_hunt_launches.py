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
PLACEHOLDER_VALUES = {"", "...", "TODO", "YOUR_KEY", "YOUR_API_KEY", "<YOUR_API_KEY>"}

try:
    from last30days_adapter import DEFAULT_CONFIG_PATH
    from last30days_adapter import run_query as run_last30days_query
except ImportError:  # pragma: no cover - damaged local installs
    DEFAULT_CONFIG_PATH = Path.home() / ".config" / "last30days" / ".env"
    run_last30days_query = None


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
    return list(dict.fromkeys(urls))


def _candidate_text(item: dict) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "snippet", "description", "body", "container", "url", "website", "homepage")
    )


def _verify_domain_candidate(launch: dict, item: dict) -> tuple[bool, list[str]]:
    url = _candidate_url_from_item(item)
    domain = _normalize_domain(url or item.get("domain", ""))
    if not _domain_allowed(domain):
        return False, []

    name = str(launch.get("name") or launch.get("company_name") or "")
    tagline = str(launch.get("tagline") or launch.get("description") or "")
    name_slug = _name_slug(name)
    domain_slug = _name_slug(domain.split(".", 1)[0])
    text = _candidate_text(item)
    text_blob = text.lower()
    tagline_hits = _text_tokens(tagline) & _text_tokens(text)
    name_tokens = _text_tokens(name)
    domain_name_match = bool(
        (name_slug and len(name_slug) >= 4 and name_slug in domain_slug)
        or (domain_slug and len(domain_slug) >= 4 and domain_slug in name_slug)
        or any(token in domain_slug for token in name_tokens)
    )
    text_match = bool((name and name.lower() in text_blob) or len(tagline_hits) >= 2)
    reasons = []
    if domain_name_match:
        reasons.append("domain_matches_product_name")
    if name and name.lower() in text_blob:
        reasons.append("search_result_mentions_product_name")
    if len(tagline_hits) >= 2:
        reasons.append("search_result_matches_tagline")
    return domain_name_match and text_match, reasons


def _web_domain_query(launch: dict) -> str:
    name = str(launch.get("name") or launch.get("company_name") or "").strip()
    tagline = str(launch.get("tagline") or launch.get("description") or "").strip()
    quoted_name = f'"{name}"' if name else ""
    quoted_tagline = f'"{tagline}"' if tagline else ""
    return " ".join(part for part in (quoted_name, quoted_tagline, "official website company startup") if part)


def resolve_launch_domain_via_web(
    launch: dict,
    *,
    query_runner=run_last30days_query,
    timeout_seconds: int | None = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    if not query_runner:
        return {"url": "", "warning": "last30days query runner unavailable"}
    query = _web_domain_query(launch)
    if not query.strip():
        return {"url": "", "warning": "missing Product Hunt name/tagline for web resolver"}
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
        return {"url": "", "warning": f"web resolver failed: {exc}"}
    if payload.get("error"):
        return {"url": "", "warning": f"web resolver failed: {payload['error']}"}
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
                        "source": "web_fallback",
                        "query": query,
                        "domain": domain,
                        "url": candidate_url,
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "verification": reasons,
                    },
                }
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


def normalize_product_hunt_api_post(post: dict) -> dict:
    name = _clean_text(str(post.get("name") or ""))
    tagline = _clean_text(str(post.get("tagline") or post.get("description") or ""))
    created_at = _clean_text(str(post.get("featuredAt") or post.get("createdAt") or ""))
    maker_profiles = _maker_profiles(post)
    maker_name = ", ".join(profile["name"] for profile in maker_profiles if profile.get("name"))
    product_hunt_url = str(post.get("url") or "").strip()
    outbound_url = _first_website_link(post)
    return {
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
        "action": "research deeper",
        "lead_route": "research_deeper",
        "missing_evidence": ["official_domain_identity_not_confirmed"],
        "why_this_may_be_noise": (
            "Product Hunt API launch row; needs official domain, founder/team, stage, "
            "and customer evidence before owner routing."
        ),
    }


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
        if outbound_url:
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
