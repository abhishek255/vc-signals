from __future__ import annotations

from urllib.parse import urlparse


MARKETPLACE_PROJECT_DOMAINS = {
    "pcbway.com",
    "hackster.io",
    "instructables.com",
    "tindie.com",
}

MARKETPLACE_PROJECT_PATH_HINTS = (
    "/project/",
    "/projects/",
    "/shareproject/",
    "/shareproject",
)

MARKETPLACE_PROJECT_TITLE_TERMS = (
    " share project ",
    " open source ",
)


def normalize_domain(value: str) -> str:
    raw = (value or "").strip()
    if raw.startswith(("http://", "https://")):
        parsed = urlparse(raw)
        raw = parsed.netloc
    raw = raw.lower().strip("/")
    return raw[4:] if raw.startswith("www.") else raw


def domain_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    return normalize_domain(parsed.netloc)


def is_marketplace_project_page(*, url: str = "", domain: str = "", title: str = "") -> bool:
    normalized_domain = normalize_domain(domain) or domain_from_url(url)
    if not any(
        normalized_domain == blocked or normalized_domain.endswith(f".{blocked}")
        for blocked in MARKETPLACE_PROJECT_DOMAINS
    ):
        return False

    path = (urlparse(url or "").path or "").lower()
    title_lower = f" {(title or '').lower()} "
    if any(hint in path for hint in MARKETPLACE_PROJECT_PATH_HINTS):
        return True
    return any(term in title_lower for term in MARKETPLACE_PROJECT_TITLE_TERMS)
