from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


ARTICLE_PATH_HINTS = (
    "/blog",
    "/posts",
    "/news",
    "/article",
    "/articles",
    "/cyberpedia",
    "/tools/",
    "/resources",
    "/learn",
    "/think/",
    "/faqs",
    "/faq",
    "/guide",
    "/technical/",
    "/topics/",
)

GENERIC_TITLE_FRAGMENT_NAMES = {
    "after rsac",
    "about",
    "agentic ai operations",
    "agentic ai security",
    "ai agent testing",
    "ai data infrastructure",
    "ai workflow automation",
    "amazon bedrock agentcore",
    "application security",
    "best ai agent",
    "best ai coding",
    "data",
    "data lineage",
    "designing",
    "gemini enterprise agent",
    "how",
    "introducing agentic pipelines",
    "i tried this",
    "llm observability",
    "mcp security",
    "model context protocol",
    "preventing ai agent",
    "the",
    "tools",
    "top",
    "vertical farming companies",
    "what are vertical ai",
}

EDITORIAL_LEAD_WORDS = {
    "after",
    "about",
    "before",
    "best",
    "designing",
    "how",
    "introducing",
    "preventing",
    "the",
    "tools",
    "top",
    "what",
    "why",
}

CATEGORY_FRAGMENT_TERMS = {
    "agentic",
    "ai",
    "agent",
    "agents",
    "application",
    "automation",
    "architecture",
    "best",
    "challenges",
    "coding",
    "context",
    "data",
    "enterprise",
    "governance",
    "infrastructure",
    "lineage",
    "llm",
    "mcp",
    "model",
    "observability",
    "operations",
    "platform",
    "playbook",
    "process",
    "protocol",
    "security",
    "software",
    "strategy",
    "testing",
    "tools",
    "vertical",
    "workflow",
}

INCUMBENT_PLATFORM_STEMS = {
    "amazon",
    "aws",
    "github",
    "google",
    "ibm",
    "meta",
    "microsoft",
    "nvidia",
    "openai",
    "oracle",
    "salesforce",
}

INCUMBENT_PLATFORM_TERMS = {
    "azure",
    "bedrock",
    "cloud",
    "developer",
    "developers",
    "enterprise",
    "gemini",
    "platform",
}


@dataclass(frozen=True)
class CandidateNameQuality:
    usable: bool
    reason: str = ""
    basis: tuple[str, ...] = ()

    @property
    def rejection_code(self) -> str:
        return f"candidate_name_quality_failed:{self.reason}" if self.reason else "candidate_name_quality_failed"


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip()).strip(" .,:;|").lower()


def _urls_from_candidate(candidate) -> list[str]:
    urls = []
    source = getattr(candidate, "source", "") or ""
    if source:
        urls.append(source)
    for url in getattr(candidate, "sources", []) or []:
        if url:
            urls.append(url)
    for metadata in getattr(candidate, "evidence_metadata", []) or []:
        if not isinstance(metadata, dict):
            continue
        for key in ("source_url", "url", "outbound_url"):
            if metadata.get(key):
                urls.append(str(metadata[key]))
    return list(dict.fromkeys(urls))


def _host(url: str) -> str:
    parsed = urlparse(url or "")
    host = (parsed.netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def _domain_stem(domain: str) -> str:
    host = (domain or "").lower().strip().removeprefix("www.")
    if host.startswith("blog."):
        host = host[5:]
    parts = [part for part in host.split(".") if part]
    if len(parts) >= 2:
        return parts[-2]
    return parts[0] if parts else ""


def _article_like_url(url: str) -> bool:
    parsed = urlparse(url or "")
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()
    return host.startswith("blog.") or any(hint in path for hint in ARTICLE_PATH_HINTS)


def _article_like_context(urls: list[str], source_headline: str, why_on_radar: str) -> bool:
    if any(_article_like_url(url) for url in urls):
        return True
    text = f"{source_headline or ''} {why_on_radar or ''}".lower()
    return any(marker in text for marker in (" | ", " - ", " — ", "top ", "best ", "how to "))


def _token_set(text: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", (text or "").lower()) if token}


def _domain_matches_name(name: str, domain: str) -> bool:
    stem = _domain_stem(domain)
    if not stem:
        return False
    tokens = _token_set(name)
    normalized = _normalize_name(name).replace(" ", "")
    return stem in tokens or stem == normalized


def candidate_name_quality(
    *,
    name: str,
    domain: str = "",
    urls: list[str] | tuple[str, ...] | None = None,
    source_headline: str = "",
    why_on_radar: str = "",
    candidate_type: str = "",
) -> CandidateNameQuality:
    normalized = _normalize_name(name)
    if not normalized:
        return CandidateNameQuality(False, "missing_name", ("missing_name",))
    if candidate_type == "oss_project" or "/" in (name or ""):
        return CandidateNameQuality(True, basis=("project_style_name",))

    urls = list(urls or [])
    article_like = _article_like_context(urls, source_headline, why_on_radar)
    domain_matched = _domain_matches_name(name, domain or (_host(urls[0]) if urls else ""))
    tokens = _token_set(normalized)
    stem = _domain_stem(domain or (_host(urls[0]) if urls else ""))
    if stem in INCUMBENT_PLATFORM_STEMS and (tokens & INCUMBENT_PLATFORM_TERMS):
        return CandidateNameQuality(False, "incumbent_platform_context", ("known_incumbent_platform_namespace",))
    if domain_matched and normalized not in GENERIC_TITLE_FRAGMENT_NAMES:
        return CandidateNameQuality(True, basis=("name_matches_domain",))

    if normalized in GENERIC_TITLE_FRAGMENT_NAMES:
        return CandidateNameQuality(False, "article_title_fragment", ("generic_title_fragment_name",))

    first_token = next(iter(normalized.split()), "")
    if article_like and first_token in EDITORIAL_LEAD_WORDS:
        return CandidateNameQuality(False, "article_title_fragment", ("editorial_leading_word",))

    if article_like and tokens and tokens.issubset(CATEGORY_FRAGMENT_TERMS):
        return CandidateNameQuality(False, "article_title_fragment", ("category_phrase_not_company_name",))

    if article_like and len(normalized.split()) >= 5:
        return CandidateNameQuality(False, "article_title_fragment", ("long_article_title_fragment",))

    return CandidateNameQuality(True, basis=("candidate_name_quality_ok",))


def candidate_quality_from_candidate(candidate) -> CandidateNameQuality:
    return candidate_name_quality(
        name=getattr(candidate, "name", "") or "",
        domain=getattr(candidate, "domain", "") or getattr(candidate, "candidate_domain", "") or "",
        urls=_urls_from_candidate(candidate),
        source_headline=getattr(candidate, "source_headline", "") or "",
        why_on_radar=getattr(candidate, "why_on_radar", "") or "",
        candidate_type=getattr(candidate, "candidate_type", "") or "",
    )


def apply_candidate_name_quality_failure(candidate, quality: CandidateNameQuality | None = None):
    quality = quality or candidate_quality_from_candidate(candidate)
    reason = quality.rejection_code
    candidate.identity_type = "article_context"
    candidate.domain = ""
    candidate.attio_safe_to_match = False
    candidate.recommended_identity_action = "Research deeper"
    candidate.recommended_owner_action = "Research deeper"
    candidate.owner_readiness_score = 0
    candidate.owner_readiness_basis = []
    candidate.missing_owner_evidence = list(dict.fromkeys(list(candidate.missing_owner_evidence) + ["no verified Attio-safe company identity"]))
    candidate.missing_identity_evidence = list(
        dict.fromkeys(list(candidate.missing_identity_evidence) + ["candidate name appears to be an article/title fragment"])
    )
    candidate.identity_confidence = "Low"
    candidate.identity_confidence_score = min(int(candidate.identity_confidence_score or 0), 30)
    candidate.verified_domain_basis = list(dict.fromkeys(list(candidate.verified_domain_basis) + [reason]))
    candidate.action = "research deeper"
    candidate.lead_route = "research_deeper"
    if "candidate name appears to be an article/title fragment" not in (candidate.why_this_may_be_noise or ""):
        suffix = "Candidate name appears to be an article/title fragment, not a company identity."
        candidate.why_this_may_be_noise = f"{candidate.why_this_may_be_noise} {suffix}".strip()
    return candidate
