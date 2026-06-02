#!/usr/bin/env python3
"""LLM-guided signal investigation with deterministic safety rails."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from radar_models import Candidate

try:
    import requests

    HAS_REQUESTS = True
except ImportError:  # pragma: no cover - damaged local installs
    requests = None
    HAS_REQUESTS = False

try:
    from last30days_adapter import DEFAULT_CONFIG_PATH
except ImportError:  # pragma: no cover - damaged local installs
    DEFAULT_CONFIG_PATH = Path.home() / ".config" / "last30days" / ".env"


DEFAULT_MODEL = "gpt-4o-mini"
GEMINI_MODEL = "gemini-2.0-flash"
XAI_MODEL = "grok-4.3"
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_GENERATE_CONTENT_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
XAI_CHAT_COMPLETIONS_URL = "https://api.x.ai/v1/chat/completions"
PLACEHOLDER_VALUES = {"", "...", "TODO", "YOUR_KEY", "YOUR_API_KEY", "<YOUR_API_KEY>"}

SOCIAL_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "threads.net",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}
REPO_DOMAINS = {"github.com", "gitlab.com", "bitbucket.org"}
PRODUCT_HUNT_DOMAINS = {"producthunt.com", "www.producthunt.com"}
LOCAL_OR_REFERENCE_DOMAINS = {
    "0.0.0.0",
    "127.0.0.1",
    "cloud.google.com",
    "developer.mozilla.org",
    "developers.google.com",
    "docs.github.com",
    "fandom.com",
    "google.com",
    "localhost",
    "learn.microsoft.com",
    "management.azure.com",
    "meet.google.com",
    "npmjs.com",
    "pypi.org",
    "readthedocs.io",
    "support.google.com",
    "wikipedia.org",
}
DIRECTORY_DOMAINS = {
    "alternativeto.net",
    "apkpure.com",
    "apps.apple.com",
    "betalist.com",
    "capterra.com",
    "chromewebstore.google.com",
    "crx4chrome.com",
    "crunchbase.com",
    "dealroom.co",
    "cbinsights.com",
    "figma.com",
    "filecr.com",
    "g2.com",
    "itch.io",
    "pitchbook.com",
    "rocketreach.co",
    "saasworthy.com",
    "softonic.com",
    "tracxn.com",
    "uptodown.com",
}
ARTICLE_DOMAINS = {
    "businesswire.com",
    "forbes.com",
    "infoq.com",
    "medium.com",
    "securityjournalamericas.com",
    "substack.com",
    "techcrunch.com",
    "thenextweb.com",
    "theguardian.com",
    "venturebeat.com",
    "wired.com",
}
BLOCKED_OFFICIAL_DOMAINS = (
    SOCIAL_DOMAINS
    | REPO_DOMAINS
    | PRODUCT_HUNT_DOMAINS
    | LOCAL_OR_REFERENCE_DOMAINS
    | DIRECTORY_DOMAINS
    | ARTICLE_DOMAINS
    | {"news.ycombinator.com", "reddit.com", "discord.gg", "discord.com", "notion.site"}
)


def _configured(value: object) -> bool:
    normalized = str(value or "").strip().strip("\"'")
    return normalized not in PLACEHOLDER_VALUES


def _load_env_file(path: Path | str = DEFAULT_CONFIG_PATH) -> dict[str, str]:
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


def _merged_env() -> dict[str, str]:
    merged = _load_env_file()
    merged.update(os.environ)
    return merged


def _domain_from_url(url: str) -> str:
    url = str(url or "").strip().strip("`'\"")
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host


def _path_from_url(url: str) -> str:
    return (urlparse(url or "").path or "").lower()


def _domain_allowed_as_official(domain: str) -> bool:
    normalized = (domain or "").lower().removeprefix("www.").strip()
    if not normalized:
        return False
    return not any(normalized == blocked or normalized.endswith(f".{blocked}") for blocked in BLOCKED_OFFICIAL_DOMAINS)


def _name_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _text_tokens(value: str) -> set[str]:
    stop = {
        "about",
        "agent",
        "company",
        "developer",
        "founder",
        "launch",
        "launched",
        "official",
        "product",
        "startup",
        "website",
    }
    return {token for token in re.findall(r"[a-z0-9]{3,}", (value or "").lower()) if token not in stop}


def _dedupe(items: list[str]) -> list[str]:
    return [item for item in dict.fromkeys(str(value).strip() for value in items) if item]


def classify_url_role(url: str, *, title: str = "", snippet: str = "") -> dict:
    """Classify what a URL represents before it can affect identity."""

    domain = _domain_from_url(url)
    path = _path_from_url(url)
    text = f"{title} {snippet} {url}".lower()
    role = "unknown"
    if not domain:
        role = "unknown"
    elif domain in PRODUCT_HUNT_DOMAINS or domain.endswith(".producthunt.com"):
        role = "product_hunt"
    elif any(domain == item or domain.endswith(f".{item}") for item in SOCIAL_DOMAINS):
        role = "social"
    elif any(domain == item or domain.endswith(f".{item}") for item in REPO_DOMAINS):
        role = "repo"
    elif any(domain == item or domain.endswith(f".{item}") for item in LOCAL_OR_REFERENCE_DOMAINS):
        role = "reference"
    elif any(domain == item or domain.endswith(f".{item}") for item in DIRECTORY_DOMAINS):
        role = "directory"
    elif any(domain == item or domain.endswith(f".{item}") for item in ARTICLE_DOMAINS):
        role = "article"
    elif domain.startswith("docs.") or any(marker in path for marker in ("/docs", "/documentation", "/developers", "/api")):
        role = "docs"
    elif any(marker in path for marker in ("/pricing", "/plans")):
        role = "pricing"
    elif any(marker in path for marker in ("/careers", "/jobs", "/hiring")):
        role = "careers"
    elif any(term in text for term in ("press release", "launches", "announces", "reported by")) and not _domain_allowed_as_official(domain):
        role = "article"
    elif _domain_allowed_as_official(domain):
        role = "official_site"
    return {"url": url, "domain": domain, "role": role, "official_eligible": role in {"official_site", "docs", "pricing", "careers"}}


def build_investigation_packet(candidate_or_item: Candidate | dict) -> dict:
    if isinstance(candidate_or_item, Candidate):
        row = candidate_or_item.to_dict()
    else:
        row = dict(candidate_or_item)
    name = str(row.get("display_name") or row.get("canonical_name") or row.get("company_name") or row.get("name") or "").strip()
    urls = _dedupe(
        [
            str(row.get(key) or "")
            for key in ("source", "url", "website", "homepage", "outbound_url", "product_hunt_url", "company_x")
        ]
        + [str(value or "") for value in row.get("sources") or []]
        + [str(value or "") for value in row.get("source_outbound_urls") or []]
    )
    text = " ".join(
        str(row.get(key) or "")
        for key in ("title", "source_headline", "tagline", "description", "snippet", "why_on_radar", "why_this_may_be_noise")
    ).strip()
    return {
        "name": name,
        "source_lane": row.get("source_lane", ""),
        "candidate_type": row.get("candidate_type", row.get("source", "")),
        "theme": row.get("theme", row.get("movement", "")),
        "market_sector": row.get("market_sector", row.get("sector", "")),
        "text": text,
        "urls": urls,
        "maker_name": row.get("maker_name", ""),
        "maker_profiles": row.get("maker_profiles", []),
        "author": row.get("author", ""),
        "domain": row.get("domain", ""),
    }


def _provider_prompt(packet: dict) -> str:
    return (
        "You are a skeptical VC signal investigator. Convert this weak signal into JSON only. "
        "Do not invent official domains. Produce search queries that can verify identity.\n\n"
        "Required JSON keys: signal_type, company_hypotheses, domain_hypotheses, search_plan, "
        "evidence_needed, risk_flags. search_plan items need query, purpose, sources.\n\n"
        f"Signal packet:\n{json.dumps(packet, ensure_ascii=False, indent=2)}"
    )


def _parse_json_content(content: str) -> dict:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def _safe_provider_error(exc: Exception) -> str:
    message = str(exc)
    message = re.sub(r"([?&]key=)[^&\s]+", r"\1<redacted>", message)
    message = re.sub(r"(Authorization:\s*Bearer\s+)[^\s,]+", r"\1<redacted>", message, flags=re.IGNORECASE)
    return f"{type(exc).__name__}: {message}"


def default_llm_provider(packet: dict) -> dict | None:
    env = _merged_env()
    live_enabled = (env.get("VC_SIGNALS_INVESTIGATOR_ENABLE_LIVE") or "").strip().lower() in {"1", "true", "yes"}
    if not live_enabled:
        return None
    provider = (env.get("VC_SIGNALS_INVESTIGATOR_PROVIDER") or "auto").lower()
    openai_key = env.get("OPENAI_API_KEY", "")
    gemini_key = env.get("GEMINI_API_KEY") or env.get("GOOGLE_API_KEY") or ""
    xai_key = env.get("XAI_API_KEY", "")
    if provider == "auto":
        provider = "xai" if _configured(xai_key) else "openai" if _configured(openai_key) else "gemini" if _configured(gemini_key) else ""
    if not HAS_REQUESTS or not provider:
        return None
    prompt = _provider_prompt(packet)
    if provider == "openai" and _configured(openai_key):
        model = env.get("VC_SIGNALS_INVESTIGATOR_MODEL") or DEFAULT_MODEL
        response = requests.post(
            OPENAI_CHAT_COMPLETIONS_URL,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            },
            headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return _parse_json_content(content)
    if provider == "gemini" and _configured(gemini_key):
        model = env.get("VC_SIGNALS_INVESTIGATOR_MODEL") or GEMINI_MODEL
        response = requests.post(
            GEMINI_GENERATE_CONTENT_URL.format(model=model),
            params={"key": gemini_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
            },
            timeout=30,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return _parse_json_content(text)
    if provider == "xai" and _configured(xai_key):
        model = env.get("VC_SIGNALS_INVESTIGATOR_MODEL") or env.get("XAI_MODEL") or XAI_MODEL
        response = requests.post(
            XAI_CHAT_COMPLETIONS_URL,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "stream": False,
            },
            headers={"Authorization": f"Bearer {xai_key}", "Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return _parse_json_content(content)
    return None


def _sanitize_search_item(item: dict) -> dict | None:
    query = str(item.get("query") or "").strip()
    if not query:
        return None
    return {
        "query": query,
        "purpose": str(item.get("purpose") or "identity").strip(),
        "sources": str(item.get("sources") or "grounding").strip(),
    }


def _search_name(packet: dict) -> str:
    name = str(packet.get("name") or "").strip()
    if packet.get("candidate_type") == "oss_project" and "/" in name:
        return name.split("/", 1)[1]
    return name


def _fallback_search_plan(packet: dict) -> dict:
    name = _search_name(packet)
    full_name = str(packet.get("name") or "").strip()
    text = str(packet.get("text") or "").strip()
    author = str(packet.get("author") or packet.get("maker_name") or "").strip()
    queries: list[dict] = []
    if name:
        if packet.get("candidate_type") == "oss_project" and full_name != name:
            queries.append(
                {
                    "query": f'"{name}" "{full_name}" official website founder company',
                    "purpose": "official_domain",
                    "sources": "grounding",
                }
            )
        else:
            core = f'"{name}"'
            if text:
                tokens = " ".join(list(_text_tokens(text))[:5])
                core = f'{core} "{tokens}"' if tokens else core
            queries.append({"query": f"{core} official website company", "purpose": "official_domain", "sources": "grounding"})
        if author:
            queries.append({"query": f'"{name}" "{author}" founder maker official', "purpose": "founder", "sources": "grounding"})
        queries.append({"query": f'"{name}" pricing docs customers careers', "purpose": "commercial_evidence", "sources": "grounding"})
        queries.append({"query": f'"{name}" seed funding headcount founders LinkedIn', "purpose": "stage_or_team", "sources": "grounding"})
    return {
        "mode": "heuristic_fallback",
        "signal_type": _infer_signal_type(packet),
        "company_hypotheses": [full_name] if full_name else [],
        "domain_hypotheses": [],
        "search_plan": queries[:4],
        "evidence_needed": ["official_domain", "founder_team", "stage_or_size", "commercial_proof"],
        "risk_flags": ["llm_provider_unavailable"],
    }


def _infer_signal_type(packet: dict) -> str:
    lane = str(packet.get("source_lane") or "").lower()
    candidate_type = str(packet.get("candidate_type") or "").lower()
    if "product" in lane or candidate_type == "producthunt_launch":
        return "product_launch"
    if "oss" in lane or candidate_type == "oss_project":
        return "oss_project"
    if lane == "x" or candidate_type == "social_launch":
        return "product_launch"
    if "hacker" in lane:
        return "product_launch"
    return "market_signal"


GENERIC_BRAND_TERMS = {
    "ai",
    "api",
    "app",
    "assistant",
    "bot",
    "client",
    "cloud",
    "club",
    "data",
    "developer",
    "dev",
    "docs",
    "engine",
    "extension",
    "figma",
    "file",
    "hq",
    "json",
    "labs",
    "manager",
    "meeting",
    "meetings",
    "mcp",
    "open",
    "platform",
    "project",
    "search",
    "server",
    "service",
    "studio",
    "system",
    "systems",
    "tool",
    "tools",
    "web",
}
GENERIC_CONTEXT_TERMS = GENERIC_BRAND_TERMS | {
    "anywhere",
    "during",
    "from",
    "into",
    "local",
    "long",
    "multi",
    "natural",
    "now",
    "step",
    "using",
    "with",
    "work",
    "world",
    "your",
}


def _domain_root(domain: str) -> str:
    host = (domain or "").lower().strip().removeprefix("www.")
    parts = [part for part in host.split(".") if part]
    if len(parts) >= 2:
        return _name_slug(parts[-2])
    return _name_slug(parts[0]) if parts else ""


def _brand_tokens(packet: dict) -> list[str]:
    names = [str(packet.get("name") or ""), _search_name(packet)]
    names.extend(str(value) for value in packet.get("company_hypotheses") or [])
    tokens: list[str] = []
    for name in names:
        for token in _text_tokens(name):
            if token not in GENERIC_BRAND_TERMS:
                tokens.append(token)
        compact = _name_slug(name)
        if compact:
            tokens.append(compact)
    deduped = _dedupe(tokens)
    if deduped:
        return deduped
    return _dedupe([token for name in names for token in _text_tokens(name)])


def _context_tokens(text: str) -> set[str]:
    return {token for token in _text_tokens(text) if token not in GENERIC_CONTEXT_TERMS}


def _packet_context_tokens(packet: dict) -> set[str]:
    return _context_tokens(str(packet.get("text") or ""))


def _item_text(item: dict, url: str = "") -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "snippet", "description", "body", "text")
    ) + f" {url}"


def _score_domain_match(domain: str, packet: dict, item: dict, url: str) -> tuple[int, list[str]]:
    root = _domain_root(domain)
    generic_roots = {"app", "apps", "beta", "blog", "docs", "launch", "launches", "pricing", "www"}
    if root in generic_roots:
        return 0, ["generic_domain_root"]
    tokens = _brand_tokens(packet)
    if not root or not tokens:
        return 0, ["missing_domain_or_brand_tokens"]
    item_text = _item_text(item, url).lower()
    name = str(packet.get("name") or "").strip().lower()
    compact_name = _name_slug(name)
    hypothesis_domains = {
        _domain_from_url(str(value))
        or str(value).strip().lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").split("/", 1)[0]
        for value in packet.get("domain_hypotheses") or []
    }
    score = 0
    basis: list[str] = []
    if (domain or "").lower().removeprefix("www.") in hypothesis_domains:
        score += 90
        basis.append("llm_domain_hypothesis")
    if compact_name and root == compact_name:
        score += 85
        basis.append("domain_matches_full_name")
    for index, token in enumerate(tokens):
        if token == root:
            score += 80
            basis.append("domain_matches_brand_token")
            break
        if len(token) >= 5 and len(root) >= 5 and (root.startswith(token) or token in root or root in token):
            score += 70 if index == 0 else 55
            basis.append("domain_contains_brand_token")
            break
        if index == 0 and len(token) == 4 and len(root) >= 5 and root.startswith(token):
            score += 40
            basis.append("domain_weakly_contains_short_brand_token")
            break
    if name and re.search(rf"\b{re.escape(name)}\b", item_text):
        score += 20
        basis.append("item_mentions_full_name")
    packet_context = _packet_context_tokens(packet)
    item_context = _context_tokens(item_text)
    context_overlap = packet_context & item_context
    if context_overlap:
        score += min(30, 10 * len(context_overlap))
        basis.append("item_matches_launch_context")
    elif packet_context and len(tokens) <= 2:
        score -= 35
        basis.append("domain_context_mismatch")
    if item.get("source") == "signal_seed_url":
        score += 15
        basis.append("seed_url")
    return max(0, score), basis


def build_search_plan(packet: dict, *, provider=None) -> dict:
    fallback = _fallback_search_plan(packet)
    provider = provider or default_llm_provider
    raw = None
    if provider:
        try:
            raw = provider(packet)
        except Exception as exc:
            fallback["provider_error"] = _safe_provider_error(exc)
            return fallback
    if not isinstance(raw, dict):
        return fallback
    search_plan = []
    for item in raw.get("search_plan") or []:
        if isinstance(item, dict):
            sanitized = _sanitize_search_item(item)
            if sanitized:
                search_plan.append(sanitized)
    if not search_plan:
        return fallback
    return {
        "mode": "llm",
        "signal_type": str(raw.get("signal_type") or fallback["signal_type"]),
        "company_hypotheses": _dedupe([str(value) for value in raw.get("company_hypotheses") or fallback["company_hypotheses"]]),
        "domain_hypotheses": _dedupe([str(value) for value in raw.get("domain_hypotheses") or []]),
        "search_plan": search_plan[:6],
        "evidence_needed": _dedupe([str(value) for value in raw.get("evidence_needed") or fallback["evidence_needed"]]),
        "risk_flags": _dedupe([str(value) for value in raw.get("risk_flags") or []]),
    }


def _domain_matches_packet(domain: str, packet: dict, item: dict) -> bool:
    score, basis = _score_domain_match(domain, packet, item, str(item.get("url") or item.get("website") or ""))
    return score >= 70 and "domain_context_mismatch" not in basis


def _urls_from_item(item: dict) -> list[str]:
    urls = []
    for key in ("url", "website", "homepage", "resolved_url", "outbound_url", "source_url"):
        value = str(item.get(key) or "").strip()
        if _domain_from_url(value):
            urls.append(value)
    for match in re.findall(r"https?://[^\s<>)\\\"']+", " ".join(str(item.get(key) or "") for key in ("title", "snippet", "description", "body", "text"))):
        urls.append(match.rstrip(".,;:!?]})"))
    return _dedupe(urls)


def _seed_url_items(packet: dict) -> list[dict]:
    items = []
    for url in packet.get("urls") or []:
        if _domain_from_url(url):
            items.append(
                {
                    "title": packet.get("name", ""),
                    "snippet": packet.get("text", ""),
                    "url": url,
                    "source": "signal_seed_url",
                }
            )
    return items


def reconcile_search_evidence(packet: dict, search_items: list[dict], *, provider=None) -> dict:
    url_roles = []
    evidence_urls = []
    official_url = ""
    official_domain = ""
    unsafe_blocked = 0
    founder_hints: list[str] = []
    stage_hints: list[str] = []
    commercial_hints: list[str] = []
    official_candidates: list[dict] = []
    identity_risk_flags: list[str] = []
    for item in search_items:
        if not isinstance(item, dict):
            continue
        for url in _urls_from_item(item):
            role = classify_url_role(url, title=str(item.get("title") or ""), snippet=str(item.get("snippet") or item.get("description") or ""))
            url_roles.append(role)
            evidence_urls.append(url)
            if role["official_eligible"]:
                score, basis = _score_domain_match(role["domain"], packet, item, url)
                if score >= 70 and "domain_context_mismatch" not in basis:
                    official_candidates.append(
                        {
                            "domain": role["domain"],
                            "url": url,
                            "score": score,
                            "basis": basis,
                        }
                    )
                elif "domain_context_mismatch" in basis:
                    identity_risk_flags.append("domain_context_mismatch")
                    unsafe_blocked += 1
                else:
                    unsafe_blocked += 1
            elif role["role"] in {"article", "directory", "social", "repo", "product_hunt", "reference"}:
                unsafe_blocked += 1
        text = " ".join(str(item.get(key) or "") for key in ("title", "snippet", "description")).strip()
        if re.search(r"\b(founder|co-founder|ceo|cto|maker)\b", text, flags=re.IGNORECASE):
            founder_hints.append(item.get("url") or item.get("source_url") or text[:180])
        if re.search(r"\b(seed|series a|series b|funding|raised|employees|headcount)\b", text, flags=re.IGNORECASE):
            stage_hints.append(item.get("url") or item.get("source_url") or text[:180])
        if re.search(r"\b(pricing|customers|case studies|docs|careers|jobs|hiring)\b", text, flags=re.IGNORECASE):
            commercial_hints.append(item.get("url") or item.get("source_url") or text[:180])
    best_candidates: list[dict] = []
    for candidate in official_candidates:
        domain = candidate.get("domain", "")
        existing = next((item for item in best_candidates if item.get("domain") == domain), None)
        if existing is None:
            best_candidates.append(candidate)
        elif int(candidate.get("score") or 0) > int(existing.get("score") or 0):
            existing.update(candidate)
    best_candidates = sorted(best_candidates, key=lambda item: int(item.get("score") or 0), reverse=True)
    if best_candidates:
        top = best_candidates[0]
        close = [item for item in best_candidates[1:] if int(top.get("score") or 0) - int(item.get("score") or 0) <= 15]
        if close:
            identity_risk_flags.append("ambiguous_official_domain_candidates")
        else:
            official_url = str(top.get("url") or "")
            official_domain = str(top.get("domain") or "")
    return {
        "mode": "evidence_reconciliation",
        "signal_type": _infer_signal_type(packet),
        "official_domain": official_domain,
        "official_url": official_url,
        "official_domain_confidence": 85 if official_domain else 0,
        "official_domain_candidates": best_candidates[:5],
        "identity_risk_flags": _dedupe(identity_risk_flags),
        "url_roles": url_roles,
        "evidence_urls": _dedupe(evidence_urls),
        "founder_hints": _dedupe(founder_hints),
        "stage_hints": _dedupe(stage_hints),
        "commercial_hints": _dedupe(commercial_hints),
        "evidence_needed": [
            gap
            for gap, present in (
                ("official_domain", bool(official_domain)),
                ("founder_team", bool(founder_hints)),
                ("stage_or_size", bool(stage_hints)),
                ("commercial_proof", bool(commercial_hints)),
            )
            if not present
        ],
        "route": "evidence_gap" if official_domain else "watch",
        "unsafe_domain_attempts_blocked": unsafe_blocked,
    }


def apply_investigation_to_candidate(candidate: Candidate, investigation: dict) -> Candidate:
    out = Candidate.from_dict(candidate.to_dict())
    official_domain = str(investigation.get("official_domain") or "").strip().lower().removeprefix("www.")
    official_url = str(investigation.get("official_url") or "").strip() or (f"https://{official_domain}" if official_domain else "")
    confidence = int(investigation.get("official_domain_confidence") or 0)
    backed_by_official_role = any(
        role.get("domain") == official_domain and role.get("role") in {"official_site", "docs", "pricing", "careers"}
        for role in investigation.get("url_roles") or []
        if isinstance(role, dict)
    )
    if official_domain and confidence >= 70 and backed_by_official_role and _domain_allowed_as_official(official_domain):
        out.domain = official_domain
        if official_url and official_url not in out.sources:
            out.sources.append(official_url)
        out.source_outbound_urls = _dedupe(list(out.source_outbound_urls or []) + [official_url])
        if "signal_investigator_official_evidence" not in out.verified_domain_basis:
            out.verified_domain_basis.append("signal_investigator_official_evidence")
        if "signal_investigator" not in out.identity_resolved_from:
            out.identity_resolved_from.append("signal_investigator")
        out.missing_identity_evidence = [
            gap
            for gap in out.missing_identity_evidence
            if "domain" not in gap.lower() and "company identity" not in gap.lower() and "verified" not in gap.lower()
        ]
    out.weak_founder_team_hints = _dedupe(list(out.weak_founder_team_hints or []) + [str(value) for value in investigation.get("founder_hints") or []])
    out.weak_stage_funding_hints = _dedupe(list(out.weak_stage_funding_hints or []) + [str(value) for value in investigation.get("stage_hints") or []])
    out.customer_buyer_evidence = _dedupe(list(out.customer_buyer_evidence or []) + [str(value) for value in investigation.get("commercial_hints") or []])
    if investigation.get("evidence_needed"):
        out.recommended_next_validation_step = "Resolve " + ", ".join(str(value) for value in investigation.get("evidence_needed")[:3])
    out.evidence_metadata.append(
        {
            "source": "signal_investigator",
            "source_url": official_url,
            "url": official_url,
            "domain": official_domain,
            "title": f"Signal investigation for {out.name}",
            "description": "LLM-guided investigation with deterministic official-domain safety gate.",
            "query_kind": "signal_investigation",
            "query_family": "llm_guided_identity",
            "mode": investigation.get("mode", ""),
            "signal_type": investigation.get("signal_type", ""),
            "evidence_urls": _dedupe([str(value) for value in investigation.get("evidence_urls") or []]),
            "url_roles": deepcopy(investigation.get("url_roles") or []),
        }
    )
    out.owner_readiness_score = 0
    out.owner_readiness_basis = []
    out.missing_owner_evidence = []
    out.recommended_owner_action = ""
    return out


def _eligible_candidate(candidate: Candidate) -> bool:
    lane = (candidate.source_lane or "").strip().lower()
    ctype = (candidate.candidate_type or "").strip().lower()
    if candidate.category_anchor or candidate.lead_route in {"category_context", "monitor_only"}:
        return False
    return lane in {"product hunt", "x", "oss", "hacker news"} or ctype in {"producthunt_launch", "social_launch", "oss_project", "hn_launch"}


def investigate_candidates(
    candidates: list[Candidate],
    *,
    query_runner=None,
    provider=None,
    max_candidates: int = 15,
    max_queries_per_candidate: int = 2,
) -> tuple[list[Candidate], dict]:
    investigated: list[Candidate] = []
    items: list[dict] = []
    summary = {
        "enabled": True,
        "provider_mode": "disabled",
        "rows_considered": len(candidates),
        "rows_investigated": 0,
        "search_queries_planned": 0,
        "search_queries_run": 0,
        "official_domains_resolved": 0,
        "url_roles_classified": 0,
        "unsafe_domain_attempts_blocked": 0,
    }
    eligible_indices = [index for index, candidate in enumerate(candidates) if _eligible_candidate(candidate)][:max_candidates]
    for index, candidate in enumerate(candidates):
        if index not in eligible_indices:
            investigated.append(Candidate.from_dict(candidate.to_dict()))
            continue
        packet = build_investigation_packet(candidate)
        plan = build_search_plan(packet, provider=provider)
        summary["provider_mode"] = "llm" if plan.get("mode") == "llm" else summary["provider_mode"] or "heuristic_fallback"
        search_items: list[dict] = []
        queries_run = []
        for query in (plan.get("search_plan") or [])[:max_queries_per_candidate]:
            summary["search_queries_planned"] += 1
            if not query_runner:
                continue
            try:
                payload = query_runner(
                    query["query"],
                    sources=query.get("sources") or "grounding",
                    lookback_days=30,
                    auto_resolve=True,
                    store=True,
                    web_backend="auto",
                )
            except TypeError:
                payload = query_runner(
                    topic=query["query"],
                    sources=query.get("sources") or "grounding",
                    lookback_days=30,
                    auto_resolve=True,
                    store=True,
                    web_backend="auto",
                )
            summary["search_queries_run"] += 1
            queries_run.append(query)
            if isinstance(payload, dict):
                search_items.extend(item for item in payload.get("items", []) or [] if isinstance(item, dict))
        investigation = reconcile_search_evidence({**packet, **plan}, _seed_url_items(packet) + search_items)
        updated = apply_investigation_to_candidate(candidate, investigation)
        investigated.append(updated)
        summary["rows_investigated"] += 1
        if investigation.get("official_domain"):
            summary["official_domains_resolved"] += 1
        summary["url_roles_classified"] += len(investigation.get("url_roles") or [])
        summary["unsafe_domain_attempts_blocked"] += int(investigation.get("unsafe_domain_attempts_blocked") or 0)
        items.append(
            {
                "candidate_key": candidate.stable_key or candidate.domain or candidate.name,
                "name": candidate.name,
                "source_lane": candidate.source_lane,
                "candidate_type": candidate.candidate_type,
                "plan": plan,
                "queries_run": queries_run,
                "investigation": investigation,
                "resolved_domain": investigation.get("official_domain", ""),
            }
        )
    if summary["provider_mode"] == "disabled" and eligible_indices:
        summary["provider_mode"] = "heuristic_fallback"
    return investigated, {"summary": summary, "items": items}


def _source_lane_from_row(row: dict) -> str:
    lane = str(row.get("source_lane") or "").strip()
    if lane:
        return lane
    source = str(row.get("source") or "").strip().lower()
    if source in {"producthunt", "product_hunt"}:
        return "Product Hunt"
    if source == "x":
        return "X"
    if source in {"github", "oss"} or row.get("full_name"):
        return "OSS"
    if source in {"hackernews", "hn"}:
        return "Hacker News"
    return lane


def _source_row_packet(row: dict, lane: str) -> dict:
    payload = dict(row)
    if lane == "OSS":
        payload.setdefault("name", payload.get("full_name") or payload.get("repo") or payload.get("title"))
        payload.setdefault("candidate_type", "oss_project")
        payload.setdefault("source_lane", "OSS")
        payload.setdefault("why_on_radar", payload.get("description") or "")
    elif lane == "Product Hunt":
        payload.setdefault("candidate_type", "producthunt_launch")
        payload.setdefault("source_lane", "Product Hunt")
        payload.setdefault("why_on_radar", payload.get("tagline") or payload.get("description") or "")
    elif lane == "X":
        payload.setdefault("candidate_type", "social_launch")
        payload.setdefault("source_lane", "X")
        payload.setdefault("why_on_radar", payload.get("snippet") or payload.get("description") or "")
    elif lane == "Hacker News":
        payload.setdefault("name", payload.get("title") or payload.get("headline") or "Hacker News signal")
        payload.setdefault("candidate_type", "hn_launch")
        payload.setdefault("source_lane", "Hacker News")
        payload.setdefault("why_on_radar", payload.get("title") or payload.get("snippet") or "")
    return build_investigation_packet(payload)


def investigate_source_rows(
    source_rows: list[dict],
    *,
    query_runner=None,
    provider=None,
    max_rows_per_lane: int = 3,
    max_queries_per_row: int = 1,
) -> dict:
    """Investigate weak source rows before candidate ranking drops them."""

    lanes_seen: dict[str, int] = {}
    items: list[dict] = []
    summary = {
        "enabled": True,
        "provider_mode": "disabled",
        "rows_considered": len(source_rows),
        "rows_investigated": 0,
        "search_queries_planned": 0,
        "search_queries_run": 0,
        "official_domains_resolved": 0,
        "url_roles_classified": 0,
        "unsafe_domain_attempts_blocked": 0,
    }
    for row in source_rows:
        if not isinstance(row, dict):
            continue
        lane = _source_lane_from_row(row)
        if lane not in {"Product Hunt", "X", "OSS", "Hacker News"}:
            continue
        lanes_seen[lane] = lanes_seen.get(lane, 0)
        if lanes_seen[lane] >= max_rows_per_lane:
            continue
        lanes_seen[lane] += 1
        packet = _source_row_packet(row, lane)
        if not packet.get("name"):
            continue
        plan = build_search_plan(packet, provider=provider)
        if plan.get("mode") == "llm":
            summary["provider_mode"] = "llm"
        elif summary["provider_mode"] == "disabled":
            summary["provider_mode"] = "heuristic_fallback"
        search_items: list[dict] = []
        queries_run = []
        for query in (plan.get("search_plan") or [])[:max_queries_per_row]:
            summary["search_queries_planned"] += 1
            if not query_runner:
                continue
            try:
                payload = query_runner(
                    query["query"],
                    sources=query.get("sources") or "grounding",
                    lookback_days=30,
                    auto_resolve=True,
                    store=True,
                    web_backend="auto",
                )
            except TypeError:
                payload = query_runner(
                    topic=query["query"],
                    sources=query.get("sources") or "grounding",
                    lookback_days=30,
                    auto_resolve=True,
                    store=True,
                    web_backend="auto",
                )
            summary["search_queries_run"] += 1
            queries_run.append(query)
            if isinstance(payload, dict):
                search_items.extend(item for item in payload.get("items", []) or [] if isinstance(item, dict))
        investigation = reconcile_search_evidence({**packet, **plan}, _seed_url_items(packet) + search_items)
        summary["rows_investigated"] += 1
        if investigation.get("official_domain"):
            summary["official_domains_resolved"] += 1
        summary["url_roles_classified"] += len(investigation.get("url_roles") or [])
        summary["unsafe_domain_attempts_blocked"] += int(investigation.get("unsafe_domain_attempts_blocked") or 0)
        items.append(
            {
                "item_type": "source_row",
                "source_lane": lane,
                "candidate_type": packet.get("candidate_type", ""),
                "name": packet.get("name", ""),
                "plan": plan,
                "queries_run": queries_run,
                "investigation": investigation,
                "resolved_domain": investigation.get("official_domain", ""),
            }
        )
    return {"summary": summary, "items": items}
