#!/usr/bin/env python3
"""Phase 6B.3 evidence-recall audit for HN outbound candidates.

This script is audit-only. It inspects HN outbound candidates and the evidence
retrieved around them, but it does not promote rows, write weekly artifacts, or
change default weekly behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from html import unescape
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from founder_team_verification import _extract_founders_from_text
from hn_outbound_enrichment import _default_query_runner, _normalize_domain
from owner_evidence import (
    _default_page_fetcher,
    _has_customer_buyer_evidence,
    _has_stage_funding_evidence,
)


HN_TEXT_FIELDS = ("source_title", "source_body", "body", "story_text", "snippet", "description")
OFFICIAL_PATHS = ("", "/about", "/team", "/blog")
SOURCE_KIND_OFFICIAL = "official_site"
SOURCE_KIND_HN_BODY = "hackernews_body"
SOURCE_KIND_QUERY = "query_result"

PERSON_NAME_RE = r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+"


def run_hn_candidate_evidence_audit(
    enrichment_payload: dict,
    *,
    phase6b_payload: dict | None = None,
    query_runner: Callable | None = None,
    page_fetcher: Callable | None = None,
    cache_dir: Path | str | None = None,
    max_candidates: int = 5,
) -> dict:
    """Audit evidence recall for enriched HN outbound candidates."""
    cache_path = Path(cache_dir) if cache_dir else None
    source_rows_by_url = _source_rows_by_url(phase6b_payload or {})
    rows = list(enrichment_payload.get("enriched_outbound_candidates") or [])[:max_candidates]
    candidates = [
        _audit_candidate(
            row,
            source_rows_by_url.get(row.get("source_url", ""), {}),
            query_runner=query_runner,
            page_fetcher=page_fetcher,
            cache_dir=cache_path,
        )
        for row in rows
    ]
    return {
        "phase": "Phase 6B.3-HN",
        "scope": "Audit only: no sourcing scoring, no Assign owner, no New To Marathon, no weekly default behavior change.",
        "summary": _summary(candidates, enrichment_payload),
        "candidates": candidates,
        "product_context_rows": list(enrichment_payload.get("product_context_rows") or []),
        "project_only_rows": list(enrichment_payload.get("project_only_rows") or []),
        "rejected_rows": list(enrichment_payload.get("rejected_rows") or []),
    }


def load_json(path: Path | str) -> dict:
    return json.loads(Path(path).read_text())


def write_hn_candidate_evidence_audit_artifacts(payload: dict, output_dir: Path | str) -> list[Path]:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    json_path = path / "hn-candidate-evidence-audit.json"
    md_path = path / "hn-candidate-evidence-audit.md"
    json_path.write_text(json.dumps(payload, indent=2))
    md_path.write_text(_markdown(payload))
    return [json_path, md_path]


def _audit_candidate(
    row: dict,
    source_row: dict,
    *,
    query_runner: Callable | None,
    page_fetcher: Callable | None,
    cache_dir: Path | None,
) -> dict:
    name = row.get("canonical_name") or row.get("name") or ""
    domain = _normalize_domain(row.get("official_domain") or row.get("domain") or row.get("official_url", ""))
    aliases = _aliases(row, source_row, domain)
    official_pages = _audit_official_pages(row, domain, aliases, page_fetcher=page_fetcher, cache_dir=cache_dir)
    hn_source = _audit_hn_source_text(row, source_row, aliases)
    query_audits = _audit_queries(row, domain, aliases, query_runner=query_runner, cache_dir=cache_dir)

    accepted = _accepted_evidence(official_pages, hn_source, query_audits)
    missing = _final_missing(row.get("missing_owner_evidence") or [], accepted)
    return {
        "canonical_name": name,
        "display_name": row.get("name") or name,
        "domain": domain,
        "source_url": row.get("source_url", ""),
        "outbound_url": row.get("official_url", ""),
        "hn_author": row.get("hn_author") or source_row.get("hn_author") or source_row.get("author", ""),
        "hn_engagement": row.get("hn_engagement") or source_row.get("hn_engagement") or {},
        "aliases_used": aliases,
        "current_route": row.get("lead_route", ""),
        "current_action": row.get("recommended_action", ""),
        "current_maturity_status": row.get("maturity_status", "unknown"),
        "current_maturity_basis": list(row.get("maturity_basis") or []),
        "current_attio_status": row.get("attio_status", "unknown"),
        "current_owner_readiness_score": row.get("owner_readiness_score", 0),
        "current_missing_evidence": list(row.get("missing_owner_evidence") or []),
        "hn_source_text": hn_source["source_text"],
        "official_pages": official_pages,
        "queries": query_audits,
        "accepted_evidence": accepted,
        "rejected_evidence": _rejected_evidence(official_pages, hn_source, query_audits),
        "final_missing_evidence": missing,
        "next_validation_step": _next_step(missing),
        "audit_findings": {
            "official_page_founder_hit": bool(_filter_by_source_kind(accepted["founder_team"], SOURCE_KIND_OFFICIAL)),
            "hn_body_founder_hit": bool(_filter_by_source_kind(accepted["founder_team"], SOURCE_KIND_HN_BODY)),
            "query_founder_hit": bool(_filter_by_source_kind(accepted["founder_team"], SOURCE_KIND_QUERY)),
            "stage_evidence_found": bool(accepted["stage_funding"]),
            "customer_evidence_found": bool(accepted["customer_buyer"]),
            "audit_only_no_route_change": True,
        },
        "proposed_route_note": "Evidence recall audit only; rerun existing gates before changing action.",
    }


def _audit_official_pages(
    row: dict,
    domain: str,
    aliases: list[str],
    *,
    page_fetcher: Callable | None,
    cache_dir: Path | None,
) -> list[dict]:
    urls = _official_page_urls(row, domain)
    pages: list[dict] = []
    for url in urls:
        payload, status = _read_or_fetch_page(url, page_fetcher=page_fetcher, cache_dir=cache_dir)
        text = _page_text(payload)
        founder_profiles, rejected = _extract_profiles_with_aliases(aliases, text, url, SOURCE_KIND_OFFICIAL)
        stage_found = _has_stage_funding_evidence(text)
        customer_found = _has_customer_buyer_evidence(text)
        pages.append(
            {
                "url": url,
                "status": status,
                "text_available": bool(text),
                "accepted_founder_profiles": founder_profiles,
                "rejected_founder_reasons": rejected if text else ["no_page_text"],
                "stage_funding_evidence": _evidence_item(url, SOURCE_KIND_OFFICIAL, "official_page_stage_funding") if stage_found else None,
                "customer_buyer_evidence": _evidence_item(url, SOURCE_KIND_OFFICIAL, "official_page_customer_buyer") if customer_found else None,
            }
        )
    return pages


def _audit_hn_source_text(row: dict, source_row: dict, aliases: list[str]) -> dict:
    available_fields = [field for field in HN_TEXT_FIELDS if row.get(field) or source_row.get(field)]
    text = " ".join(str(row.get(field) or source_row.get(field) or "") for field in HN_TEXT_FIELDS)
    text = _page_text(text)
    url = row.get("source_url") or source_row.get("source_url") or source_row.get("url") or ""
    profiles, rejected = _extract_profiles_with_aliases(aliases, text, url, SOURCE_KIND_HN_BODY)
    return {
        "source_text": {
            "available_fields": available_fields,
            "text_available": bool(text),
            "source_url": url,
            "text_excerpt": text[:700],
        },
        "accepted_founder_profiles": profiles,
        "rejected_founder_reasons": rejected if text else ["no_hn_body_or_snippet_text"],
    }


def _audit_queries(
    row: dict,
    domain: str,
    aliases: list[str],
    *,
    query_runner: Callable | None,
    cache_dir: Path | None,
) -> dict:
    return {
        "founder_team": [
            _audit_query(topic, "founder_team", aliases, query_runner=query_runner, cache_dir=cache_dir)
            for topic in _founder_queries(aliases, domain)
        ],
        "stage_funding": [
            _audit_query(topic, "stage_funding", aliases, query_runner=query_runner, cache_dir=cache_dir)
            for topic in _stage_queries(aliases, domain)
        ],
        "customer_buyer": [
            _audit_query(topic, "customer_buyer", aliases, query_runner=query_runner, cache_dir=cache_dir)
            for topic in _customer_queries(aliases, domain)
        ],
        "attio": {
            "status": row.get("attio_status", "unknown"),
            "confidence": row.get("attio_confidence", ""),
            "note": "read_only_status_from_phase6b2_enrichment",
        },
    }


def _audit_query(
    topic: str,
    kind: str,
    aliases: list[str],
    *,
    query_runner: Callable | None,
    cache_dir: Path | None,
) -> dict:
    payload, status = _run_cached_query(topic, query_runner=query_runner, cache_dir=cache_dir)
    items = list(payload.get("items") or []) if isinstance(payload, dict) else []
    accepted_founders: list[dict] = []
    rejected_founders: list[dict] = []
    accepted_stage: list[dict] = []
    accepted_customer: list[dict] = []
    for item in items:
        text = _item_text(item)
        url = _item_url(item)
        profiles, rejected = _extract_profiles_with_aliases(aliases, text, url, SOURCE_KIND_QUERY)
        accepted_founders.extend(profiles)
        if rejected:
            rejected_founders.append({"url": url, "title": item.get("title", ""), "reasons": rejected})
        if _has_stage_funding_evidence(text):
            accepted_stage.append(_evidence_item(url, SOURCE_KIND_QUERY, "query_stage_funding", title=item.get("title", "")))
        if _has_customer_buyer_evidence(text):
            accepted_customer.append(_evidence_item(url, SOURCE_KIND_QUERY, "query_customer_buyer", title=item.get("title", "")))
    return {
        "topic": topic,
        "kind": kind,
        "status": status,
        "items_seen": len(items),
        "accepted_founder_profiles": _dedupe_profiles(accepted_founders),
        "rejected_founder_items": rejected_founders,
        "accepted_stage_funding": _dedupe_evidence(accepted_stage),
        "accepted_customer_buyer": _dedupe_evidence(accepted_customer),
    }


def _accepted_evidence(official_pages: list[dict], hn_source: dict, queries: dict) -> dict:
    founder: list[dict] = []
    stage: list[dict] = []
    customer: list[dict] = []
    for page in official_pages:
        founder.extend(page.get("accepted_founder_profiles") or [])
        if page.get("stage_funding_evidence"):
            stage.append(page["stage_funding_evidence"])
        if page.get("customer_buyer_evidence"):
            customer.append(page["customer_buyer_evidence"])
    founder.extend(hn_source.get("accepted_founder_profiles") or [])
    for rows in (queries.get("founder_team") or [], queries.get("stage_funding") or [], queries.get("customer_buyer") or []):
        for item in rows:
            founder.extend(item.get("accepted_founder_profiles") or [])
            stage.extend(item.get("accepted_stage_funding") or [])
            customer.extend(item.get("accepted_customer_buyer") or [])
    return {
        "founder_team": _dedupe_profiles(founder),
        "stage_funding": _dedupe_evidence(stage),
        "customer_buyer": _dedupe_evidence(customer),
    }


def _rejected_evidence(official_pages: list[dict], hn_source: dict, queries: dict) -> dict:
    founder_rejections: list[dict] = []
    for page in official_pages:
        if page.get("rejected_founder_reasons") and not page.get("accepted_founder_profiles"):
            founder_rejections.append({"url": page.get("url", ""), "source_kind": SOURCE_KIND_OFFICIAL, "reasons": page["rejected_founder_reasons"]})
    if hn_source.get("rejected_founder_reasons") and not hn_source.get("accepted_founder_profiles"):
        founder_rejections.append(
            {
                "url": hn_source.get("source_text", {}).get("source_url", ""),
                "source_kind": SOURCE_KIND_HN_BODY,
                "reasons": hn_source["rejected_founder_reasons"],
            }
        )
    for rows in (queries.get("founder_team") or [], queries.get("stage_funding") or [], queries.get("customer_buyer") or []):
        for query in rows:
            founder_rejections.extend(query.get("rejected_founder_items") or [])
    return {"founder_team": founder_rejections}


def _final_missing(current_missing: list[str], accepted: dict) -> list[str]:
    missing = list(current_missing)
    if accepted["founder_team"]:
        missing = [item for item in missing if "founder" not in item.lower()]
    if accepted["stage_funding"]:
        missing = [item for item in missing if "stage" not in item.lower() and "funding" not in item.lower()]
    if accepted["customer_buyer"]:
        missing = [item for item in missing if "customer" not in item.lower() and "buyer" not in item.lower()]
    if accepted["stage_funding"] or accepted["customer_buyer"]:
        missing = [item for item in missing if "commercial" not in item.lower()]
    return list(dict.fromkeys(missing))


def _next_step(missing: list[str]) -> str:
    if any("founder" in item.lower() for item in missing):
        return "Find founder/team source"
    if any("stage" in item.lower() or "funding" in item.lower() for item in missing):
        return "Verify stage/funding source"
    if any("customer" in item.lower() or "buyer" in item.lower() for item in missing):
        return "Find buyer/customer pull evidence"
    if any("attio" in item.lower() for item in missing):
        return "Check Attio match/status"
    return "Rerun existing gates with accepted audit evidence"


def _summary(candidates: list[dict], enrichment_payload: dict) -> dict:
    return {
        "candidates_audited": len(candidates),
        "founder_evidence_found": sum(1 for item in candidates if item["accepted_evidence"]["founder_team"]),
        "official_page_founder_hits": sum(1 for item in candidates if item["audit_findings"]["official_page_founder_hit"]),
        "hn_body_founder_hits": sum(1 for item in candidates if item["audit_findings"]["hn_body_founder_hit"]),
        "query_founder_hits": sum(1 for item in candidates if item["audit_findings"]["query_founder_hit"]),
        "stage_evidence_found": sum(1 for item in candidates if item["accepted_evidence"]["stage_funding"]),
        "customer_evidence_found": sum(1 for item in candidates if item["accepted_evidence"]["customer_buyer"]),
        "assign_owner_rows": 0,
        "new_to_marathon_rows": 0,
        "product_context_rows_preserved": len(enrichment_payload.get("product_context_rows") or []),
        "project_only_rows_preserved": len(enrichment_payload.get("project_only_rows") or []),
    }


def _markdown(payload: dict) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Phase 6B.3 HN Candidate Evidence Recall Audit",
        "",
        payload.get("scope", ""),
        "",
        "## Summary",
        "",
    ]
    for key in (
        "candidates_audited",
        "founder_evidence_found",
        "official_page_founder_hits",
        "hn_body_founder_hits",
        "query_founder_hits",
        "stage_evidence_found",
        "customer_evidence_found",
        "assign_owner_rows",
        "new_to_marathon_rows",
    ):
        lines.append(f"- {key}: {summary.get(key, 0)}")
    lines.extend(["", "## Candidate Audit", ""])
    for row in payload.get("candidates", []) or []:
        founders = ", ".join(item.get("name", "") for item in row.get("accepted_evidence", {}).get("founder_team", []) if item.get("name"))
        missing = ", ".join(row.get("final_missing_evidence") or []) or "none after audit evidence"
        lines.append(
            f"- {row.get('canonical_name')} ({row.get('domain')}) - current: {row.get('current_action')} - "
            f"founders: {founders or 'none'} - final missing: {missing}"
        )
        lines.append(f"  - HN: {row.get('source_url')} by {row.get('hn_author') or 'unknown'}")
        lines.append(
            "  - Current state: "
            f"maturity={row.get('current_maturity_status')}, "
            f"attio={row.get('current_attio_status')}, "
            f"owner_readiness={row.get('current_owner_readiness_score')}"
        )
        lines.append(
            "  - Evidence found: "
            f"founder={len(row.get('accepted_evidence', {}).get('founder_team') or [])}, "
            f"stage={len(row.get('accepted_evidence', {}).get('stage_funding') or [])}, "
            f"customer={len(row.get('accepted_evidence', {}).get('customer_buyer') or [])}"
        )
        lines.append(f"  - Next: {row.get('next_validation_step')}")
        query_summary = _markdown_query_summary(row.get("queries", {}))
        if query_summary:
            lines.append(f"  - Query status: {query_summary}")
    if not payload.get("candidates"):
        lines.append("- None")
    lines.extend(["", "## Preserved Lanes", ""])
    lines.append(f"- Product/category rows preserved: {summary.get('product_context_rows_preserved', 0)}")
    lines.append(f"- Project-only rows preserved: {summary.get('project_only_rows_preserved', 0)}")
    return "\n".join(lines) + "\n"


def _markdown_query_summary(queries: dict) -> str:
    parts: list[str] = []
    for kind in ("founder_team", "stage_funding", "customer_buyer"):
        rows = queries.get(kind) or []
        if not rows:
            continue
        cached = sum(1 for row in rows if str(row.get("status", "")).startswith("cache_hit"))
        queried = sum(1 for row in rows if row.get("status") == "queried")
        planned = len(rows)
        items = sum(int(row.get("items_seen") or 0) for row in rows)
        parts.append(f"{kind} {cached + queried}/{planned} run-or-cached, {items} items")
    return "; ".join(parts)


def _source_rows_by_url(payload: dict) -> dict[str, dict]:
    rows = list(payload.get("company_rows") or [])
    return {row.get("source_url", ""): row for row in rows if row.get("source_url")}


def _aliases(row: dict, source_row: dict, domain: str) -> list[str]:
    values = [
        row.get("canonical_name", ""),
        row.get("name", ""),
        source_row.get("name", ""),
        row.get("source_title", ""),
        source_row.get("source_title", "") or source_row.get("title", ""),
    ]
    aliases: list[str] = []
    for value in values:
        for alias in _aliases_from_text(value, domain):
            if alias and alias.lower() not in {item.lower() for item in aliases}:
                aliases.append(alias)
    root = domain.split(".")[0] if domain else ""
    if root:
        root_title = root[:1].upper() + root[1:]
        for alias in (root_title, f"{root_title} AI" if domain.endswith(".ai") else ""):
            if alias and alias.lower() not in {item.lower() for item in aliases}:
                aliases.append(alias)
    return aliases[:8]


def _aliases_from_text(value: str, domain: str) -> list[str]:
    text = re.sub(r"\s*\((?:YC|Y\s+Combinator)\s+[SWF]\d{2}\)\s*", " ", value or "", flags=re.IGNORECASE)
    text = re.sub(r"^(?:Show|Launch)\s+HN:\s*", "", text, flags=re.IGNORECASE)
    for sep in (" - ", " – ", " — ", " | "):
        if sep in text:
            text = text.split(sep, 1)[0]
            break
    text = re.sub(r"\s+", " ", text).strip()
    aliases = [text]
    if text.endswith(".ai"):
        aliases.append(text[:-3])
    if domain:
        aliases.append(domain)
    return aliases


def _official_page_urls(row: dict, domain: str) -> list[str]:
    urls: list[str] = []
    for value in (
        row.get("official_url", ""),
        *(row.get("founder_team_evidence") or []),
        *(row.get("stage_funding_evidence") or []),
        *(row.get("customer_buyer_evidence") or []),
    ):
        if value:
            urls.append(value)
    if domain:
        urls.extend(f"https://{domain}{path}" for path in OFFICIAL_PATHS)
    return list(dict.fromkeys(urls))[:10]


def _read_or_fetch_page(url: str, *, page_fetcher: Callable | None, cache_dir: Path | None) -> tuple[object, str]:
    cached = _read_cache(cache_dir, "official-pages", url)
    if cached is not None:
        return cached.get("payload", cached), "cache_hit"
    cached = _read_cache(cache_dir, "hn-official-pages", url)
    if cached is not None:
        return cached.get("payload", cached), "cache_hit"
    if page_fetcher:
        payload = page_fetcher(url)
        _write_cache(cache_dir, "hn-candidate-evidence-pages", url, {"payload": payload})
        return payload, "fetched"
    return "", "not_fetched"


def _run_cached_query(topic: str, *, query_runner: Callable | None, cache_dir: Path | None) -> tuple[dict, str]:
    for namespace in ("hn-evidence-audit-queries", "founder-team-queries", "hn-outbound-queries", "queries"):
        cached = _read_cache(cache_dir, namespace, topic)
        if cached is not None:
            return cached, f"cache_hit:{namespace}"
    if not query_runner:
        return {"items": []}, "not_queried"
    payload = query_runner(
        topic,
        sources="grounding",
        lookback_days=30,
        auto_resolve=True,
        store=True,
        web_backend="auto",
    )
    _write_cache(cache_dir, "hn-evidence-audit-queries", topic, payload)
    return payload, "queried"


def _read_cache(cache_dir: Path | None, namespace: str, key: str):
    path = _cache_path(cache_dir, namespace, key)
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _write_cache(cache_dir: Path | None, namespace: str, key: str, payload: dict) -> None:
    path = _cache_path(cache_dir, namespace, key)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _cache_path(cache_dir: Path | None, namespace: str, key: str) -> Path | None:
    if not cache_dir:
        return None
    return cache_dir / namespace / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()[:24]}.json"


def _founder_queries(aliases: list[str], domain: str) -> list[str]:
    primary = aliases[:3] or [domain]
    queries = [f'"{alias}" "{domain}" founder OR co-founder OR CEO OR CTO' for alias in primary if alias and domain]
    queries.extend(f'"{alias}" "co-founder"' for alias in primary[:2] if alias)
    return list(dict.fromkeys(queries))[:5]


def _stage_queries(aliases: list[str], domain: str) -> list[str]:
    primary = aliases[:3] or [domain]
    queries = [f'"{alias}" "{domain}" funding seed series A series B' for alias in primary if alias and domain]
    queries.extend(f'"{alias}" "Series Seed"' for alias in primary[:2] if alias)
    return list(dict.fromkeys(queries))[:5]


def _customer_queries(aliases: list[str], domain: str) -> list[str]:
    primary = aliases[:2] or [domain]
    return list(
        dict.fromkeys(
            f'"{alias}" "{domain}" customers users case study enterprise'
            for alias in primary
            if alias and domain
        )
    )[:3]


def _extract_profiles_with_aliases(aliases: list[str], text: str, url: str, source_kind: str) -> tuple[list[dict], list[str]]:
    profiles: list[dict] = []
    rejected: list[str] = []
    for alias in aliases:
        found, reasons = _extract_founders_from_text(company_name=alias, text=text, url=url)
        profiles.extend(_tag_profiles(found, source_kind))
        rejected.extend(reasons)
    profiles.extend(_tag_profiles(_extract_hn_cofounder_names(text=text, aliases=aliases, url=url), source_kind))
    return _dedupe_profiles(profiles), list(dict.fromkeys(rejected))


def _extract_hn_cofounder_names(*, text: str, aliases: list[str], url: str) -> list[dict]:
    if not text or not url:
        return []
    profiles: list[dict] = []
    alias_re = "|".join(re.escape(alias) for alias in aliases if alias and len(alias) > 2)
    if not alias_re:
        return []
    patterns = [
        re.compile(
            rf"(?:we(?:'re| are)\s+)?(?P<names>{PERSON_NAME_RE}(?:\s+and\s+{PERSON_NAME_RE})+),\s+co-?founders?\s+of\s+(?:{alias_re})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"(?P<names>{PERSON_NAME_RE}(?:\s+and\s+{PERSON_NAME_RE})+)\s*,\s+co-?founders?\s+of\s+(?:{alias_re})",
            re.IGNORECASE,
        ),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            for name in re.split(r"\s+and\s+", match.group("names")):
                clean = re.sub(r"\s+", " ", name).strip()
                if re.match(rf"^{PERSON_NAME_RE}$", clean):
                    profiles.append({"name": clean, "role": "co-founder", "source": url})
    return profiles


def _tag_profiles(profiles: list[dict], source_kind: str) -> list[dict]:
    tagged: list[dict] = []
    for profile in profiles:
        out = dict(profile)
        out["source_kind"] = source_kind
        out["evidence_type"] = "founder_team"
        tagged.append(out)
    return tagged


def _filter_by_source_kind(items: list[dict], source_kind: str) -> list[dict]:
    return [item for item in items if item.get("source_kind") == source_kind]


def _evidence_item(url: str, source_kind: str, evidence_type: str, *, title: str = "") -> dict:
    return {
        "source": url,
        "source_kind": source_kind,
        "evidence_type": evidence_type,
        "title": title,
    }


def _dedupe_profiles(items: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen = set()
    for item in items:
        key = (item.get("name"), item.get("role"), item.get("source"), item.get("source_kind"))
        if item.get("name") and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _dedupe_evidence(items: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen = set()
    for item in items:
        key = (item.get("source"), item.get("evidence_type"))
        if item.get("source") and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _item_text(item: dict) -> str:
    return _page_text(" ".join(str(item.get(key, "")) for key in ("title", "snippet", "description", "body", "url")))


def _item_url(item: dict) -> str:
    return str(item.get("url") or item.get("source_url") or "").strip()


def _page_text(payload) -> str:
    if isinstance(payload, dict):
        payload = " ".join(str(payload.get(key, "")) for key in ("title", "snippet", "description", "body", "html", "payload"))
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", str(payload or ""))
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 6B.3 HN candidate evidence recall audit.")
    parser.add_argument("--enrichment-json", required=True)
    parser.add_argument("--phase6b-json", default="")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--cache-dir", default="")
    parser.add_argument("--live-queries", action="store_true")
    parser.add_argument("--fetch-pages", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_hn_candidate_evidence_audit(
        load_json(args.enrichment_json),
        phase6b_payload=load_json(args.phase6b_json) if args.phase6b_json else None,
        query_runner=_default_query_runner if args.live_queries else None,
        page_fetcher=_default_page_fetcher if args.fetch_pages else None,
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
        max_candidates=args.max_candidates,
    )
    write_hn_candidate_evidence_audit_artifacts(payload, args.output_dir)
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
