from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from radar_company_discovery import _domain_from_url, _normalize_domain, classify_discovery_source
from radar_models import Candidate


WEAK_SOURCE_LANES = {"product hunt", "oss"}
WEAK_CANDIDATE_TYPES = {"producthunt_launch", "oss_project"}
BLOCKED_SOURCE_TYPES = {
    "content_platform",
    "directory_page",
    "funding_press_release",
    "government_or_academic",
    "investor_page",
    "listicle_or_seo",
    "marketplace_project_page",
    "publisher_article",
}


def _stable_cache_name(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _cache_path(cache_dir: Path | None, query: str) -> Path | None:
    if not cache_dir:
        return None
    return cache_dir / "weak-source-identity" / f"{_stable_cache_name(query)}.json"


def _read_cache(cache_dir: Path | None, query: str) -> dict | None:
    path = _cache_path(cache_dir, query)
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _write_cache(cache_dir: Path | None, query: str, payload: dict) -> None:
    path = _cache_path(cache_dir, query)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _candidate_key(candidate: Candidate) -> str:
    return candidate.stable_key or candidate.domain or candidate.name


def _compact(value: str) -> str:
    return "".join(ch.lower() for ch in value or "" if ch.isalnum())


def _name_tokens(candidate: Candidate) -> list[str]:
    values = [
        candidate.name,
        candidate.display_name,
        candidate.canonical_name,
        candidate.source_headline,
    ]
    parsed = urlparse(candidate.source or "")
    if "github.com" in parsed.netloc.lower():
        parts = [part for part in parsed.path.split("/") if part]
        values.extend(parts[:2])
    tokens: list[str] = []
    for value in values:
        for token in re.split(r"[^A-Za-z0-9]+", value or ""):
            compact = _compact(token)
            if len(compact) >= 3 and compact not in {"github", "producthunt", "official", "company"}:
                tokens.append(compact)
        compact_value = _compact(value or "")
        if len(compact_value) >= 3:
            tokens.append(compact_value)
    return list(dict.fromkeys(tokens))


def _domain_matches_candidate(domain: str, candidate: Candidate) -> bool:
    root = _compact(_normalize_domain(domain).split(".", 1)[0])
    if not root:
        return False
    return any(token in root or root in token for token in _name_tokens(candidate))


def _text_matches_candidate(item: dict, candidate: Candidate) -> bool:
    text = _compact(" ".join(str(item.get(key, "")) for key in ("title", "snippet", "description", "url")))
    return any(token and token in text for token in _name_tokens(candidate))


def _eligible(candidate: Candidate) -> tuple[bool, str]:
    if candidate.domain or candidate.candidate_domain:
        return False, "domain_already_present"
    if candidate.category_anchor or candidate.lead_route in {"category_context", "monitor_only"}:
        return False, "category_context_or_monitor_only"
    source_lane = (candidate.source_lane or "").strip().lower()
    candidate_type = (candidate.candidate_type or "").strip().lower()
    if source_lane not in WEAK_SOURCE_LANES and candidate_type not in WEAK_CANDIDATE_TYPES:
        return False, "not_weak_source_lane"
    if not (candidate.name or "").strip():
        return False, "missing_candidate_name"
    return True, ""


def _query_priority(candidate: Candidate) -> tuple[int, str]:
    source_lane = (candidate.source_lane or "").strip().lower()
    candidate_type = (candidate.candidate_type or "").strip().lower()
    if source_lane == "product hunt" or candidate_type == "producthunt_launch":
        return (0, candidate.name.lower())
    if candidate_type != "oss_project":
        return (1, candidate.name.lower())
    return (2, candidate.name.lower())


def _search_name(candidate: Candidate) -> str:
    if candidate.candidate_type == "oss_project" and "/" in candidate.name:
        return candidate.name.split("/", 1)[1]
    return candidate.display_name or candidate.canonical_name or candidate.name


def build_weak_source_identity_query(candidate: Candidate) -> str:
    name = _search_name(candidate)
    if candidate.candidate_type == "oss_project" and candidate.name != name:
        return f'"{name}" "{candidate.name}" official website founder company'
    return f'"{name}" official website founder company'


def _query_items(payload: dict | None) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    return [item for item in payload.get("items", []) if isinstance(item, dict)]


def _item_domain(item: dict) -> str:
    return _normalize_domain(item.get("domain") or item.get("website") or _domain_from_url(item.get("url") or ""))


def _select_official_identity_item(candidate: Candidate, items: list[dict]) -> tuple[dict | None, list[str]]:
    rejection_reasons: list[str] = []
    for item in items:
        source_type = classify_discovery_source(item)
        if source_type in BLOCKED_SOURCE_TYPES:
            rejection_reasons.append(f"{source_type}_not_company_identity")
            continue
        domain = _item_domain(item)
        if not domain:
            rejection_reasons.append("no_source_backed_domain")
            continue
        if not (_domain_matches_candidate(domain, candidate) or _text_matches_candidate(item, candidate)):
            rejection_reasons.append("domain_or_text_does_not_match_candidate")
            continue
        if source_type != "official_company_page" and not _domain_matches_candidate(domain, candidate):
            rejection_reasons.append(f"{source_type}_not_strong_identity")
            continue
        return item, list(dict.fromkeys(rejection_reasons))
    return None, list(dict.fromkeys(rejection_reasons or ["no_official_identity_result"]))


def _apply_identity_item(candidate: Candidate, item: dict, *, query: str) -> Candidate:
    out = Candidate.from_dict(candidate.to_dict())
    domain = _item_domain(item)
    url = item.get("url") or item.get("source_url") or f"https://{domain}"
    out.domain = domain
    if url and url not in out.sources:
        out.sources.append(url)
    if "weak_source_official_search_result" not in out.verified_domain_basis:
        out.verified_domain_basis.append("weak_source_official_search_result")
    if "weak_source_identity_enrichment" not in out.identity_resolved_from:
        out.identity_resolved_from.append("weak_source_identity_enrichment")
    out.source_outbound_urls = list(dict.fromkeys(list(out.source_outbound_urls or []) + [url]))
    out.missing_identity_evidence = [
        gap
        for gap in out.missing_identity_evidence
        if "verified domain" not in gap.lower() and "company identity" not in gap.lower()
    ]
    out.evidence_metadata.append(
        {
            "source": item.get("source") or "grounding",
            "source_url": url,
            "url": url,
            "title": item.get("title") or "",
            "description": item.get("snippet") or item.get("description") or "",
            "domain": domain,
            "query_topic": query,
            "query_kind": "weak_source_identity_search",
            "query_family": "exact_weak_source_identity",
        }
    )
    out.owner_readiness_score = 0
    out.owner_readiness_basis = []
    out.missing_owner_evidence = []
    out.recommended_owner_action = ""
    out.recommended_next_validation_step = ""
    return out


def enrich_weak_source_identity(
    candidates: list[Candidate],
    *,
    query_runner=None,
    cache_dir: Path | str | None = None,
    max_candidates: int = 5,
) -> tuple[list[Candidate], dict]:
    cache_path = Path(cache_dir) if cache_dir else None
    enriched: list[Candidate] = []
    items: list[dict] = []
    summary = {
        "eligible": 0,
        "skipped": 0,
        "queries_run": 0,
        "query_cache_hits": 0,
        "domains_resolved": 0,
        "unresolved": 0,
    }
    eligible_rows = [
        (index, candidate)
        for index, candidate in enumerate(candidates)
        if _eligible(candidate)[0]
    ]
    query_budget_indices = {
        index
        for index, _candidate in sorted(eligible_rows, key=lambda row: _query_priority(row[1]))[:max_candidates]
    }

    for index, candidate in enumerate(candidates):
        eligible, skip_reason = _eligible(candidate)
        if not eligible or index not in query_budget_indices or not query_runner:
            reason = skip_reason
            if eligible and index not in query_budget_indices:
                reason = "weak_source_identity_candidate_budget_exceeded"
            elif eligible and not query_runner:
                reason = "query_runner_unavailable"
            enriched.append(Candidate.from_dict(candidate.to_dict()))
            items.append(
                {
                    "candidate_key": _candidate_key(candidate),
                    "name": candidate.name,
                    "source_lane": candidate.source_lane,
                    "candidate_type": candidate.candidate_type,
                    "status": "skipped",
                    "skip_reason": reason,
                    "query": "",
                    "resolved_domain": "",
                    "rejection_reasons": [],
                }
            )
            summary["skipped"] += 1
            continue

        summary["eligible"] += 1
        query = build_weak_source_identity_query(candidate)
        payload = _read_cache(cache_path, query)
        if payload:
            summary["query_cache_hits"] += 1
        else:
            payload = query_runner(
                query,
                sources="grounding",
                lookback_days=30,
                auto_resolve=True,
                store=True,
                web_backend="auto",
            )
            _write_cache(cache_path, query, payload)
            summary["queries_run"] += 1

        selected, rejection_reasons = _select_official_identity_item(candidate, _query_items(payload))
        if selected:
            updated = _apply_identity_item(candidate, selected, query=query)
            enriched.append(updated)
            summary["domains_resolved"] += 1
            items.append(
                {
                    "candidate_key": _candidate_key(candidate),
                    "name": candidate.name,
                    "source_lane": candidate.source_lane,
                    "candidate_type": candidate.candidate_type,
                    "status": "resolved",
                    "skip_reason": "",
                    "query": query,
                    "resolved_domain": updated.domain,
                    "evidence_url": updated.sources[-1] if updated.sources else "",
                    "rejection_reasons": rejection_reasons,
                }
            )
        else:
            enriched.append(Candidate.from_dict(candidate.to_dict()))
            summary["unresolved"] += 1
            items.append(
                {
                    "candidate_key": _candidate_key(candidate),
                    "name": candidate.name,
                    "source_lane": candidate.source_lane,
                    "candidate_type": candidate.candidate_type,
                    "status": "unresolved",
                    "skip_reason": "",
                    "query": query,
                    "resolved_domain": "",
                    "rejection_reasons": rejection_reasons,
                }
            )

    return enriched, {"summary": summary, "items": items}


def write_weak_source_identity_enrichment_json(report: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    return path
