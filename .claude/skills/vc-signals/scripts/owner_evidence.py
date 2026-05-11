from __future__ import annotations

import hashlib
import json
import re
from html import unescape
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from founder_team_verification import extract_named_founder_profiles_from_text
from radar_focus import (
    ACTION_ASSIGN_OWNER,
    ACTION_MONITOR_ONLY,
    ACTION_REFRESH_ATTIO,
    ACTION_RESEARCH_DEEPER,
    ATTIO_NEW_STATUSES,
    ATTIO_NO_OWNER_STATUSES,
    ATTIO_UNKNOWN_STATUSES,
    LEAD_ROUTE_CATEGORY_CONTEXT,
    LEAD_ROUTE_MONITOR_ONLY,
    OWNER_READY_THRESHOLD,
    _blocking_owner_missing,
    score_owner_readiness,
)
from radar_models import Candidate, OwnerEvidence


OFFICIAL_SITE_PATHS = ("", "/about", "/team", "/blog", "/customers", "/pricing", "/contact")
FOUNDER_ELIGIBLE_PATHS = {"", "/about", "/team", "/blog"}
LATE_OR_CONTEXT_STATUSES = {"likely_too_late", "acquired", "incumbent", "category_leader"}
FOUNDER_ROLE_PATTERN = r"(?:founder|co-founder|cofounder|ceo|cto|chief executive officer|chief technology officer)"
PERSON_NAME_PATTERN = r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+"
FUNDING_TERMS = ("pre-seed", "pre seed", "seed", "series a", "series b", "series c", "series d", "series e", "raised")
EARLY_STAGE_TERMS = ("pre-seed", "pre seed", "seed", "series a", "series b")
LATE_STAGE_TERMS = ("series c", "series d", "series e", "ipo", "acquired", "acquisition", "$100m", "$1b")
CUSTOMER_TERMS = (
    "customer",
    "customers",
    "trusted by",
    "used by",
    "case study",
    "design partner",
    "pilot",
    "pilots",
    "ciso",
)
STRONG_CUSTOMER_EVIDENCE_TYPES = {
    "named_customer_evidence",
    "early_customer_segment_evidence",
    "buyer_pain_evidence",
    "waitlist_or_demo_evidence",
    "commercial_intent_evidence",
}
DURABLE_EVIDENCE_URL_MARKERS = (
    "/blog-posts/",
    "businesswire.com/",
    "gunder.com/",
    "ycombinator.com/companies/",
)


def _stable_cache_name(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _cache_path(cache_dir: Path | None, namespace: str, key: str) -> Path | None:
    if not cache_dir:
        return None
    return cache_dir / namespace / f"{_stable_cache_name(key)}.json"


def _read_cache(cache_dir: Path | None, namespace: str, key: str):
    path = _cache_path(cache_dir, namespace, key)
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _write_cache(cache_dir: Path | None, namespace: str, key: str, payload) -> None:
    path = _cache_path(cache_dir, namespace, key)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _extract_durable_links_from_html(html: str, *, base_domain: str = "") -> list[str]:
    links = re.findall(r"href=[\"']([^\"']+)[\"']", html or "", flags=re.IGNORECASE)
    out: list[str] = []
    for link in links:
        lowered = link.lower()
        if not any(marker in lowered for marker in DURABLE_EVIDENCE_URL_MARKERS):
            continue
        if link.startswith("/") and base_domain:
            out.append(f"https://{base_domain}{link}")
        elif link.startswith("http"):
            out.append(link)
    return list(dict.fromkeys(out))


def _candidate_key(candidate: Candidate) -> str:
    return candidate.stable_key or candidate.domain or candidate.name


def _clean_company_name(candidate: Candidate) -> str:
    name = re.sub(r"\s+", " ", (candidate.name or "").strip())
    for separator in (" | ", " - ", " – ", " — ", ": "):
        if separator in name:
            parts = [part.strip() for part in name.split(separator) if part.strip()]
            if parts:
                name = parts[-1] if len(parts[-1]) >= 2 else parts[0]
                break
    return name[:80]


def _company_aliases(candidate: Candidate) -> list[str]:
    aliases: list[str] = []
    for value in (
        candidate.canonical_name,
        candidate.display_name,
        candidate.name,
        _clean_company_name(candidate),
    ):
        value = re.sub(r"\s+", " ", (value or "").strip())
        if value and value.lower() not in {alias.lower() for alias in aliases}:
            aliases.append(value)
    domain = _domain(candidate)
    root = domain.split(".", 1)[0] if domain else ""
    if root:
        root_title = root[:1].upper() + root[1:]
        for value in (root_title, f"{root_title} AI" if domain.endswith(".ai") else ""):
            if value and value.lower() not in {alias.lower() for alias in aliases}:
                aliases.append(value)
    return aliases[:6]


def _domain(candidate: Candidate) -> str:
    domain = (candidate.domain or candidate.candidate_domain or "").strip()
    if domain.startswith("http://") or domain.startswith("https://"):
        parsed = urlparse(domain)
        return parsed.netloc or parsed.path
    return domain.strip("/")


def funding_stage_query(candidate: Candidate) -> str:
    return f'"{_clean_company_name(candidate)}" "{_domain(candidate)}" funding seed series A series B'


def customer_buyer_query(candidate: Candidate) -> str:
    return f'"{_clean_company_name(candidate)}" "{_domain(candidate)}" customers users case study enterprise'


def _eligible_for_owner_evidence(candidate: Candidate) -> tuple[bool, str]:
    if candidate.category_anchor or candidate.lead_route in {LEAD_ROUTE_CATEGORY_CONTEXT, LEAD_ROUTE_MONITOR_ONLY}:
        return False, "category_context_or_monitor_only"
    if candidate.maturity_status in LATE_OR_CONTEXT_STATUSES:
        return False, candidate.maturity_status
    if candidate.identity_type in {"oss_project_watch", "oss_with_commercial_intent"}:
        return False, "oss_project_only"
    if candidate.candidate_type == "oss_project" and candidate.identity_type != "verified_company":
        return False, "oss_project_only"
    if candidate.identity_type != "verified_company" or not _domain(candidate):
        return False, "not_verified_company"
    return True, ""


def _official_url(domain: str, path: str) -> str:
    return f"https://{domain}{path}"


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _default_page_fetcher(url: str) -> str:
    request = Request(url, headers={"User-Agent": "vc-signals/owner-evidence"})
    try:
        with urlopen(request, timeout=5) as response:
            return response.read(60_000).decode("utf-8", errors="ignore")
    except (HTTPError, URLError, TimeoutError, OSError):
        return ""


def _page_text(payload) -> str:
    if isinstance(payload, dict):
        return _strip_html(" ".join(str(payload.get(key, "")) for key in ("title", "snippet", "description", "body", "html")))
    return _strip_html(str(payload or ""))


def _query_items(payload: dict | None) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    return [item for item in payload.get("items", []) if isinstance(item, dict)]


def _items_text(items: list[dict]) -> str:
    return " ".join(
        " ".join(str(item.get(key, "")) for key in ("title", "snippet", "description", "url"))
        for item in items
    )


def _item_urls(items: list[dict]) -> list[str]:
    return list(dict.fromkeys(item.get("url") or item.get("source_url") or "" for item in items if item.get("url") or item.get("source_url")))


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in terms)


def _has_founder_team_evidence(text: str, path: str) -> bool:
    if path not in FOUNDER_ELIGIBLE_PATHS:
        return False
    role = f"(?i:{FOUNDER_ROLE_PATTERN})"
    if re.search(rf"(?i:founded by)\s+{PERSON_NAME_PATTERN}", text or ""):
        return True
    if re.search(rf"{PERSON_NAME_PATTERN}\s*,\s*(?:[^.\n]{{0,80}})?{role}", text or ""):
        return True
    if re.search(rf"{role}\s+{PERSON_NAME_PATTERN}", text or ""):
        return True
    return False


def _has_stage_funding_evidence(text: str) -> bool:
    lowered = (text or "").lower()
    if any(term in lowered for term in EARLY_STAGE_TERMS + LATE_STAGE_TERMS):
        return True
    return bool(re.search(r"\braised\b[^.\n]{0,80}(?:\$|\d|round|financing|funding)", lowered))


def _has_customer_buyer_evidence(text: str) -> bool:
    return any(evidence_type in STRONG_CUSTOMER_EVIDENCE_TYPES for evidence_type in classify_customer_buyer_evidence(text))


def classify_customer_buyer_evidence(text: str) -> list[str]:
    """Classify customer/buyer evidence without overstating generic positioning."""
    lowered = (text or "").lower()
    labels: list[str] = []
    if not lowered:
        return labels
    named_customer_patterns = (
        r"\bcustomers?\s+include\s+[A-Z][A-Za-z0-9&.,\s-]{2,80}",
        r"\btrusted\s+by\s+[A-Z][A-Za-z0-9&.,\s-]{2,80}",
        r"\bused\s+by\s+[A-Z][A-Za-z0-9&.,\s-]{2,80}",
        r"\bcase\s+study\b",
    )
    if any(re.search(pattern, text or "") for pattern in named_customer_patterns):
        labels.append("named_customer_evidence")
    if any(term in lowered for term in ("design partner", "design partners", "pilot", "pilots", "early customer")):
        labels.append("early_customer_segment_evidence")
    if any(
        term in lowered
        for term in (
            "roi scrutiny",
            "policy constraint",
            "policy constraints",
            "production realities",
            "regulator",
            "regulators",
            "accuracy, cost",
            "latency sla",
            "reliability crisis",
            "ciso",
        )
    ):
        labels.append("buyer_pain_evidence")
    if any(term in lowered for term in ("book demo", "request demo", "schedule demo", "join waitlist", "get started", "contact sales")):
        labels.append("waitlist_or_demo_evidence")
    if any(
        term in lowered
        for term in (
            "enterprise teams",
            "enterprise security",
            "enterprise-grade",
            "enterprise customers",
            "soc 2",
            "marketplace",
            "production-ready",
            "self-serve",
            "customers use",
            "customer pilots",
            "customer pilot",
        )
    ):
        labels.append("commercial_intent_evidence")
    if _contains_any(text, CUSTOMER_TERMS) and not labels:
        labels.append("generic_positioning")
    return list(dict.fromkeys(labels))


def _attio_confidence(candidate: Candidate) -> tuple[str, list[str]]:
    status = (candidate.attio_status or "unknown").lower()
    basis: list[str] = []
    if status in ATTIO_UNKNOWN_STATUSES:
        return "Low", ["attio_unknown"]
    if not candidate.attio_safe_to_match:
        return "Low", ["attio_not_safe_to_match"]
    if not _domain(candidate):
        return "Low", ["no_domain_match_key"]
    basis.extend(["attio_safe_to_match", f"attio_status_{status}"])
    if candidate.attio_match_keys:
        basis.append("attio_match_keys_present")
    if status in ATTIO_NEW_STATUSES or status in ATTIO_NO_OWNER_STATUSES or status in {"stale", "passed"}:
        return "High", basis
    return "Medium", basis


def _recommended_action(candidate: Candidate, score: int, missing: list[str]) -> str:
    if candidate.category_anchor or candidate.maturity_status in LATE_OR_CONTEXT_STATUSES:
        return ACTION_MONITOR_ONLY
    if score < OWNER_READY_THRESHOLD or _blocking_owner_missing(missing):
        return ACTION_RESEARCH_DEEPER
    status = (candidate.attio_status or "unknown").lower()
    if status in {"stale", "passed"}:
        return ACTION_REFRESH_ATTIO
    if status in ATTIO_NEW_STATUSES or status in ATTIO_NO_OWNER_STATUSES:
        return ACTION_ASSIGN_OWNER
    return ACTION_RESEARCH_DEEPER


def _dedupe_founder_profiles(profiles: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen = set()
    for profile in profiles:
        name = str(profile.get("name", "")).strip()
        source = str(profile.get("source", "")).strip()
        if not name or name.lower() == "source-backed founder/team evidence":
            continue
        key = (name, str(profile.get("role", "")).strip(), source)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(profile))
    return deduped


def _dedupe_customer_evidence_types(items: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen = set()
    for item in items:
        url = str(item.get("url", "")).strip()
        evidence_types = list(dict.fromkeys(str(label) for label in item.get("evidence_types", []) if label))
        if not url or not evidence_types:
            continue
        key = (url, tuple(evidence_types))
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"url": url, "evidence_types": evidence_types})
    return deduped


def _profiles_from_text(candidate: Candidate, *, text: str, url: str) -> list[dict]:
    profiles, _rejected = extract_named_founder_profiles_from_text(
        company_names=_company_aliases(candidate),
        text=text,
        url=url,
    )
    return profiles


def _apply_evidence(candidate: Candidate, *, founder_urls: list[str], founder_profiles: list[dict], stage_urls: list[str], customer_urls: list[str], customer_evidence_types: list[dict], page_texts: list[str], query_texts: list[str]) -> Candidate:
    out = Candidate.from_dict(candidate.to_dict())
    combined_text = " ".join(page_texts + query_texts).lower()
    evidence_changed = False
    founder_profiles = _dedupe_founder_profiles(founder_profiles)
    if founder_profiles:
        evidence_changed = True
        existing_names = set(out.founders)
        for profile in founder_profiles:
            name = profile.get("name", "")
            if name and name not in existing_names:
                out.founders.append(name)
                existing_names.add(name)
        existing_profiles = {(profile.get("name"), profile.get("role"), profile.get("source")) for profile in out.founder_profiles}
        for profile in founder_profiles:
            key = (profile.get("name"), profile.get("role"), profile.get("source"))
            if key not in existing_profiles:
                out.founder_profiles.append(dict(profile))
                existing_profiles.add(key)
        profile_urls = [profile.get("source", "") for profile in founder_profiles if profile.get("source")]
        founder_urls = list(dict.fromkeys(founder_urls + profile_urls))
        out.founder_team_evidence = list(dict.fromkeys(out.founder_team_evidence + founder_urls))[:5]
    if stage_urls:
        evidence_changed = True
        out.stage_funding_evidence = list(dict.fromkeys(out.stage_funding_evidence + stage_urls))[:5]
        out.maturity_evidence_urls = list(dict.fromkeys(out.maturity_evidence_urls + stage_urls))[:5]
        early_stage_evidence = any(term in combined_text for term in EARLY_STAGE_TERMS)
        late_stage_evidence = any(term in combined_text for term in LATE_STAGE_TERMS)
        if out.maturity_status == "unknown" and early_stage_evidence and not late_stage_evidence:
            out.maturity_status = "seed_to_series_b"
            out.maturity_basis = list(dict.fromkeys(out.maturity_basis + ["owner_evidence_stage_funding_signal"]))
            if out.lead_route == "research_deeper":
                out.lead_route = "sourcing_candidate"
    if customer_urls:
        evidence_changed = True
        out.customer_buyer_evidence = list(dict.fromkeys(out.customer_buyer_evidence + customer_urls))[:5]
    customer_evidence_types = _dedupe_customer_evidence_types(customer_evidence_types)
    if customer_evidence_types:
        evidence_changed = True
        existing = list(getattr(out, "customer_buyer_evidence_types", []))
        out.customer_buyer_evidence_types = _dedupe_customer_evidence_types(existing + customer_evidence_types)[:8]
    for text in page_texts + query_texts:
        if text:
            out.evidence_metadata.append({"description": text[:1200]})
    if evidence_changed:
        out.owner_readiness_score = 0
        out.owner_readiness_basis = []
        out.missing_owner_evidence = []
        out.recommended_owner_action = ""
        out.recommended_next_validation_step = ""
    return out


def _score_evidence_candidate(candidate: Candidate, *, eligible: bool, skip_reason: str, pages_checked: list[str], pages_failed: list[str], funding_query: str, funding_status: str, customer_query: str, customer_status: str, evidence_urls: list[str]) -> tuple[Candidate, OwnerEvidence]:
    if not candidate.stage_funding_evidence and candidate.maturity_evidence_urls:
        candidate.stage_funding_evidence = list(candidate.maturity_evidence_urls[:5])
    attio_confidence, attio_basis = _attio_confidence(candidate)
    candidate.attio_confidence = attio_confidence
    candidate.attio_confidence_basis = attio_basis
    score, basis, missing, next_step = score_owner_readiness(candidate)
    action = _recommended_action(candidate, score, missing)
    candidate.owner_readiness_score = score
    candidate.owner_readiness_basis = basis
    candidate.missing_owner_evidence = missing
    candidate.recommended_owner_action = action
    candidate.recommended_next_validation_step = next_step
    candidate.owner_evidence_status = "eligible" if eligible else "skipped"
    evidence = OwnerEvidence(
        candidate_key=_candidate_key(candidate),
        name=candidate.name,
        domain=candidate.domain,
        eligible=eligible,
        skip_reason=skip_reason,
        founder_team_evidence=list(candidate.founder_team_evidence),
        founder_profiles=list(candidate.founder_profiles),
        stage_funding_evidence=list(candidate.stage_funding_evidence or candidate.maturity_evidence_urls[:3]),
        customer_buyer_evidence=list(candidate.customer_buyer_evidence),
        customer_buyer_evidence_types=list(getattr(candidate, "customer_buyer_evidence_types", [])),
        official_site_pages_checked=pages_checked,
        official_site_pages_failed=pages_failed,
        funding_query=funding_query,
        funding_query_status=funding_status,
        customer_query=customer_query,
        customer_query_status=customer_status,
        attio_confidence=attio_confidence,
        attio_confidence_basis=attio_basis,
        owner_readiness_score=score,
        owner_readiness_basis=list(basis),
        missing_owner_evidence=list(missing),
        recommended_owner_action=action,
        recommended_next_validation_step=next_step,
        evidence_urls=list(dict.fromkeys(evidence_urls + candidate.sources[:3])),
    )
    return candidate, evidence


def enrich_owner_evidence(
    candidates: list[Candidate],
    *,
    query_runner: Callable | None = None,
    page_fetcher: Callable | None = None,
    cache_dir: Path | str | None = None,
    max_candidates: int = 5,
    max_pages_per_candidate: int = 7,
) -> tuple[list[Candidate], dict]:
    cache_path = Path(cache_dir) if cache_dir else None
    fetch_page = page_fetcher or _default_page_fetcher
    enriched: list[Candidate] = []
    evidence_items: list[OwnerEvidence] = []
    summary = {
        "eligible": 0,
        "skipped": 0,
        "page_fetches": 0,
        "page_cache_hits": 0,
        "queries_run": 0,
        "query_cache_hits": 0,
        "attio_blocked": 0,
    }
    eligible_seen = 0

    for candidate in candidates:
        eligible, skip_reason = _eligible_for_owner_evidence(candidate)
        if not eligible or eligible_seen >= max_candidates:
            reason = skip_reason or "owner_evidence_candidate_budget_exceeded"
            scored, item = _score_evidence_candidate(
                Candidate.from_dict(candidate.to_dict()),
                eligible=False,
                skip_reason=reason,
                pages_checked=[],
                pages_failed=[],
                funding_query="",
                funding_status="not_eligible",
                customer_query="",
                customer_status="not_eligible",
                evidence_urls=[],
            )
            enriched.append(scored)
            evidence_items.append(item)
            summary["skipped"] += 1
            if item.attio_confidence == "Low":
                summary["attio_blocked"] += 1
            continue

        eligible_seen += 1
        summary["eligible"] += 1
        domain = _domain(candidate)
        pages_checked: list[str] = []
        pages_failed: list[str] = []
        founder_urls: list[str] = []
        founder_profiles: list[dict] = []
        stage_urls: list[str] = []
        customer_urls: list[str] = []
        customer_evidence_types: list[dict] = []
        evidence_urls: list[str] = []
        page_texts: list[str] = []

        for path in OFFICIAL_SITE_PATHS[:max_pages_per_candidate]:
            url = _official_url(domain, path)
            payload = _read_cache(cache_path, "official-pages", url)
            if payload is None:
                payload = fetch_page(url)
                _write_cache(cache_path, "official-pages", url, {"payload": payload})
                summary["page_fetches"] += 1
            else:
                payload = payload.get("payload", "")
                summary["page_cache_hits"] += 1
            durable_links = _extract_durable_links_from_html(payload, base_domain=domain)
            evidence_urls_for_page = durable_links or [url]
            text = _page_text(payload)
            if not text:
                pages_failed.append(url)
                continue
            pages_checked.append(url)
            page_texts.append(text)
            found_profiles = _profiles_from_text(candidate, text=text, url=url)
            if found_profiles:
                founder_urls.extend(evidence_urls_for_page)
                if durable_links:
                    found_profiles = [dict(profile, source=durable_links[0]) for profile in found_profiles]
                founder_profiles.extend(found_profiles)
            if _has_stage_funding_evidence(text):
                stage_urls.extend(evidence_urls_for_page)
            customer_labels = classify_customer_buyer_evidence(text)
            if customer_labels:
                for evidence_url in evidence_urls_for_page:
                    customer_evidence_types.append({"url": evidence_url, "evidence_types": customer_labels})
            if any(label in STRONG_CUSTOMER_EVIDENCE_TYPES for label in customer_labels):
                customer_urls.extend(evidence_urls_for_page)

        funding_topic = funding_stage_query(candidate)
        funding_payload = _read_cache(cache_path, "queries", funding_topic)
        funding_status = "cache_hit" if funding_payload else "not_queried"
        if funding_payload:
            summary["query_cache_hits"] += 1
        elif query_runner:
            funding_payload = query_runner(
                funding_topic,
                sources="grounding",
                lookback_days=30,
                auto_resolve=True,
                store=True,
                web_backend="auto",
            )
            _write_cache(cache_path, "queries", funding_topic, funding_payload)
            funding_status = "queried"
            summary["queries_run"] += 1

        customer_topic = customer_buyer_query(candidate)
        customer_payload = _read_cache(cache_path, "queries", customer_topic)
        customer_status = "cache_hit" if customer_payload else "not_queried"
        if customer_payload:
            summary["query_cache_hits"] += 1
        elif query_runner:
            customer_payload = query_runner(
                customer_topic,
                sources="grounding",
                lookback_days=30,
                auto_resolve=True,
                store=True,
                web_backend="auto",
            )
            _write_cache(cache_path, "queries", customer_topic, customer_payload)
            customer_status = "queried"
            summary["queries_run"] += 1

        query_texts: list[str] = []
        funding_items = _query_items(funding_payload)
        if funding_items:
            funding_text = _items_text(funding_items)
            query_texts.append(funding_text)
            for item in funding_items:
                found_profiles = _profiles_from_text(candidate, text=_items_text([item]), url=item.get("url") or item.get("source_url") or "")
                if found_profiles:
                    founder_urls.extend(profile.get("source", "") for profile in found_profiles if profile.get("source"))
                    founder_profiles.extend(found_profiles)
            if _has_stage_funding_evidence(funding_text):
                stage_urls.extend(_item_urls(funding_items))
        customer_items = _query_items(customer_payload)
        if customer_items:
            customer_text = _items_text(customer_items)
            query_texts.append(customer_text)
            for item in customer_items:
                item_text = _items_text([item])
                item_url = item.get("url") or item.get("source_url") or ""
                found_profiles = _profiles_from_text(candidate, text=item_text, url=item_url)
                if found_profiles:
                    founder_urls.extend(profile.get("source", "") for profile in found_profiles if profile.get("source"))
                    founder_profiles.extend(found_profiles)
                customer_labels = classify_customer_buyer_evidence(item_text)
                if item_url and customer_labels:
                    customer_evidence_types.append({"url": item_url, "evidence_types": customer_labels})
                if item_url and any(label in STRONG_CUSTOMER_EVIDENCE_TYPES for label in customer_labels):
                    customer_urls.append(item_url)

        evidence_urls.extend(founder_urls + stage_urls + customer_urls)
        candidate_with_evidence = _apply_evidence(
            candidate,
            founder_urls=list(dict.fromkeys(founder_urls))[:3],
            founder_profiles=founder_profiles,
            stage_urls=list(dict.fromkeys(stage_urls))[:3],
            customer_urls=list(dict.fromkeys(customer_urls))[:3],
            customer_evidence_types=customer_evidence_types,
            page_texts=page_texts,
            query_texts=query_texts,
        )
        scored, item = _score_evidence_candidate(
            candidate_with_evidence,
            eligible=True,
            skip_reason="",
            pages_checked=pages_checked,
            pages_failed=pages_failed,
            funding_query=funding_topic,
            funding_status=funding_status,
            customer_query=customer_topic,
            customer_status=customer_status,
            evidence_urls=list(dict.fromkeys(evidence_urls)),
        )
        enriched.append(scored)
        evidence_items.append(item)
        if item.attio_confidence == "Low":
            summary["attio_blocked"] += 1

    return enriched, {
        "summary": summary,
        "items": [item.to_dict() for item in evidence_items],
    }


def write_owner_evidence_json(report: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    return path
