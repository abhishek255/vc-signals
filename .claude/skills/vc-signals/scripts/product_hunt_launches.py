#!/usr/bin/env python3
"""Product Hunt launch feed adapter for company-formation signals."""

from __future__ import annotations

import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urlparse

try:
    import requests

    HAS_REQUESTS = True
except ImportError:  # pragma: no cover - damaged local installs
    requests = None
    HAS_REQUESTS = False


PRODUCT_HUNT_FEED_URL = "https://www.producthunt.com/feed"
PRODUCT_HUNT_HOSTS = {"producthunt.com", "www.producthunt.com"}
DEFAULT_TIMEOUT_SECONDS = 15


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


def enrich_launch_domains(launches: list[dict], *, resolver=resolve_product_hunt_redirect) -> list[dict]:
    enriched = []
    for launch in launches:
        item = dict(launch)
        outbound_url = item.get("outbound_url") or ""
        resolved_url = ""
        warning = ""
        if outbound_url:
            resolved_url, warning = resolver(outbound_url)
        domain = _normalize_domain(resolved_url)
        if domain and domain not in PRODUCT_HUNT_HOSTS:
            item["website"] = resolved_url
            item["domain"] = domain
            item["domain_resolution_status"] = "resolved"
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
    try:
        feed_xml = fetch_product_hunt_feed(timeout_seconds=timeout)
        launches = parse_product_hunt_feed(feed_xml, limit=limit)
        launches = enrich_launch_domains(launches)
        for launch in launches:
            warning = launch.get("domain_resolution_warning")
            if warning:
                warnings.append(f"{launch.get('name', 'unknown')}: {warning}")
        return {"launches": launches[:limit], "warnings": warnings}
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
