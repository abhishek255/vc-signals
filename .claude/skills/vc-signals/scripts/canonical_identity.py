from __future__ import annotations

import re
from urllib.parse import urlparse


TAGLINE_START_WORDS = {
    "automate",
    "build",
    "deploy",
    "discover",
    "find",
    "get",
    "make",
    "manage",
    "secure",
    "ship",
    "stop",
    "take",
    "turn",
}
TAGLINE_PHRASES = (
    " your ",
    " faster",
    " from day one",
    " in minutes",
    " in seconds",
    " into production",
    " built for ",
    " platform for ",
    " the future of ",
)


def normalize_domain(domain: str) -> str:
    value = (domain or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        value = parsed.netloc or parsed.path
    value = value.lower().strip("/")
    return value[4:] if value.startswith("www.") else value


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def domain_company_name(domain: str) -> str:
    normalized = normalize_domain(domain)
    if not normalized:
        return ""
    root = normalized.split(".")[0]
    parts = [part for part in re.split(r"[-_]+", root) if part]
    names = []
    for part in parts:
        if part.lower() == "ai":
            names.append("AI")
        elif part.lower().endswith("ai") and len(part) <= 4:
            names.append(part[:-2].capitalize() + "AI")
        elif any(char.isdigit() for char in part):
            names.append(part)
        else:
            names.append(part[:1].upper() + part[1:])
    return " ".join(names)


def is_oss_project_name(name: str, *, candidate_type: str = "", identity_type: str = "") -> bool:
    if candidate_type == "oss_project" or identity_type in {"oss_project_watch", "oss_with_commercial_intent"}:
        return True
    value = (name or "").strip()
    return bool("/" in value and " " not in value)


def is_tagline_like_name(name: str) -> bool:
    value = (name or "").strip()
    if not value or "/" in value:
        return False
    lowered = value.lower()
    words = re.findall(r"[a-z0-9]+", lowered)
    if len(words) > 5:
        return True
    if value.endswith((".", "!", "?")) and len(words) >= 3:
        return True
    if words and words[0] in TAGLINE_START_WORDS:
        return True
    return any(phrase in f" {lowered} " for phrase in TAGLINE_PHRASES)


def split_title_name(title: str) -> str:
    value = (title or "").strip()
    if not value:
        return ""
    for separator in (" | ", " - ", " – ", " — ", ": "):
        if separator in value:
            parts = [part.strip() for part in value.split(separator) if part.strip()]
            if parts and not is_tagline_like_name(parts[0]):
                return parts[0]
            if len(parts) > 1 and not is_tagline_like_name(parts[-1]):
                return parts[-1]
    return value


def canonicalize_identity(
    *,
    name: str = "",
    domain: str = "",
    candidate_type: str = "",
    identity_type: str = "",
    raw_title: str = "",
    source_headline: str = "",
) -> dict:
    original_name = (name or "").strip()
    headline = (source_headline or raw_title or "").strip()
    domain_name = domain_company_name(domain)

    if is_oss_project_name(original_name, candidate_type=candidate_type, identity_type=identity_type):
        return {
            "canonical_name": original_name,
            "display_name": original_name,
            "source_headline": headline,
            "tagline": "",
        }

    candidate_name = split_title_name(original_name)
    normalized_domain = normalize_domain(domain)
    domain_root = normalized_domain.split(".")[0] if normalized_domain else ""
    candidate_value = candidate_name.strip()
    candidate_is_domain_like = (
        "." in candidate_value
        or candidate_value == domain_root
        or normalize_domain(candidate_value) == normalized_domain
    )
    if domain_name and candidate_is_domain_like and _normalized(candidate_name) in {
        _normalized(normalized_domain),
        _normalized(domain_root),
    }:
        candidate_name = domain_name
    if is_tagline_like_name(candidate_name) and domain_name:
        canonical_name = domain_name
        tagline = original_name
    elif candidate_name:
        canonical_name = candidate_name
        tagline = headline if headline and is_tagline_like_name(headline) and headline != candidate_name else ""
    else:
        canonical_name = domain_name
        tagline = headline if is_tagline_like_name(headline) else ""

    if domain_name and is_tagline_like_name(canonical_name):
        tagline = original_name or headline
        canonical_name = domain_name

    return {
        "canonical_name": canonical_name or original_name or domain_name,
        "display_name": canonical_name or original_name or domain_name,
        "source_headline": headline,
        "tagline": tagline,
    }
