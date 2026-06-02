from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from radar_company_discovery import classify_discovery_source


DURABLE_SOURCE_TYPES = {
    "funding_press_release",
    "investor_page",
    "publisher_article",
}


@dataclass(frozen=True)
class EvidenceSourceQuality:
    quality: str
    source_type: str
    reason: str


def _normalize_domain(value: str) -> str:
    value = (value or "").strip().lower()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    domain = parsed.netloc or parsed.path
    return domain.removeprefix("www.").split("/", 1)[0]


def _domain_from_url(url: str) -> str:
    return _normalize_domain(urlparse(url or "").netloc)


def _same_domain(url: str, candidate_domain: str = "") -> bool:
    source_domain = _domain_from_url(url)
    target_domain = _normalize_domain(candidate_domain)
    return bool(source_domain and target_domain and source_domain == target_domain)


def classify_evidence_source(url: str, *, candidate_domain: str = "", item: dict | None = None) -> EvidenceSourceQuality:
    """Classify whether a URL is durable enough to count as owner-ready evidence."""
    if not url:
        return EvidenceSourceQuality("weak", "missing_url", "evidence_url_required")
    if _same_domain(url, candidate_domain):
        return EvidenceSourceQuality("durable", "official_company_domain", "official_company_domain")
    lowered = url.lower()
    if "ycombinator.com/companies/" in lowered:
        return EvidenceSourceQuality("durable", "accelerator_company_profile", "accelerator_company_profile")
    source_item = {"url": url, "title": ""}
    if item:
        source_item.update(item)
        source_item["url"] = url
    source_type = classify_discovery_source(source_item)
    if source_type in DURABLE_SOURCE_TYPES:
        return EvidenceSourceQuality("durable", source_type, source_type)
    return EvidenceSourceQuality("weak", source_type, f"weak_source:{source_type}")


def split_durable_and_weak_urls(
    urls: list[str],
    *,
    candidate_domain: str = "",
    item: dict | None = None,
) -> tuple[list[str], list[str]]:
    durable: list[str] = []
    weak: list[str] = []
    for url in dict.fromkeys(url for url in urls if url):
        quality = classify_evidence_source(url, candidate_domain=candidate_domain, item=item)
        if quality.quality == "durable":
            durable.append(url)
        else:
            weak.append(url)
    return durable, weak

