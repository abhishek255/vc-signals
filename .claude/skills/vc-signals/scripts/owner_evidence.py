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


OFFICIAL_SITE_PATHS = ("", "/about", "/team", "/customers", "/pricing", "/contact", "/blog")
LATE_OR_CONTEXT_STATUSES = {"likely_too_late", "acquired", "incumbent", "category_leader"}
FOUNDER_TERMS = ("founded by", "founder", "co-founder", "cofounder", "ceo", "cto", "leadership team")
FUNDING_TERMS = ("pre-seed", "pre seed", "seed", "series a", "series b", "funding", "raised")
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
    "enterprise",
    "security teams",
    "ciso",
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


def _apply_evidence(candidate: Candidate, *, founder_urls: list[str], stage_urls: list[str], customer_urls: list[str], page_texts: list[str], query_texts: list[str]) -> Candidate:
    out = Candidate.from_dict(candidate.to_dict())
    combined_text = " ".join(page_texts + query_texts).lower()
    if founder_urls:
        out.founder_team_evidence = list(dict.fromkeys(out.founder_team_evidence + founder_urls))[:5]
        if not out.founder_profiles and not out.founders:
            out.founder_profiles = [{"name": "source-backed founder/team evidence", "source": founder_urls[0]}]
    if stage_urls:
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
        out.customer_buyer_evidence = list(dict.fromkeys(out.customer_buyer_evidence + customer_urls))[:5]
    for text in page_texts + query_texts:
        if text:
            out.evidence_metadata.append({"description": text[:1200]})
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
        stage_funding_evidence=list(candidate.stage_funding_evidence or candidate.maturity_evidence_urls[:3]),
        customer_buyer_evidence=list(candidate.customer_buyer_evidence),
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
        stage_urls: list[str] = []
        customer_urls: list[str] = []
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
            text = _page_text(payload)
            if not text:
                pages_failed.append(url)
                continue
            pages_checked.append(url)
            page_texts.append(text)
            if _contains_any(text, FOUNDER_TERMS):
                founder_urls.append(url)
            if _contains_any(text, FUNDING_TERMS):
                stage_urls.append(url)
            if _contains_any(text, CUSTOMER_TERMS):
                customer_urls.append(url)

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
            if _contains_any(funding_text, FUNDING_TERMS):
                stage_urls.extend(_item_urls(funding_items))
        customer_items = _query_items(customer_payload)
        if customer_items:
            customer_text = _items_text(customer_items)
            query_texts.append(customer_text)
            if _contains_any(customer_text, CUSTOMER_TERMS):
                customer_urls.extend(_item_urls(customer_items))

        evidence_urls.extend(founder_urls + stage_urls + customer_urls)
        candidate_with_evidence = _apply_evidence(
            candidate,
            founder_urls=list(dict.fromkeys(founder_urls))[:3],
            stage_urls=list(dict.fromkeys(stage_urls))[:3],
            customer_urls=list(dict.fromkeys(customer_urls))[:3],
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
