#!/usr/bin/env python3
"""Resolve weak launch/social signals into hard company-evidence dossiers."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from discovery_search_providers import load_provider_env_files, provider_available, run_provider_query
from signal_investigator import (
    build_investigation_packet,
    build_search_plan,
    classify_url_role,
    reconcile_search_evidence,
)


DEFAULT_PROVIDER = "exa,brave"
DEFAULT_MAX_QUERIES = 2
DEFAULT_MAX_RESULTS = 8
DEFAULT_TIMEOUT_SECONDS = 12
DEFAULT_SITE_EVIDENCE_PATHS = (
    "/about",
    "/team",
    "/pricing",
    "/docs",
    "/documentation",
    "/customers",
    "/case-studies",
    "/careers",
    "/jobs",
    "/blog",
)
SOURCE_OR_DIRECTORY_DOMAINS = {
    "apps.apple.com",
    "github.com",
    "linkedin.com",
    "news.ycombinator.com",
    "producthunt.com",
    "reddit.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}
AMBIGUOUS_IDENTITY_GAP = "official_domain_identity_ambiguous"


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dedupe(items: list[Any]) -> list[str]:
    return [item for item in dict.fromkeys(str(value).strip() for value in items) if item]


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    if "://" not in url:
        url = f"https://{url}"
    try:
        host = urlparse(url).netloc.lower().strip().removeprefix("www.")
    except Exception:
        return ""
    return host


def _is_source_or_directory_domain(domain: str) -> bool:
    normalized = (domain or "").lower().strip().removeprefix("www.")
    return any(normalized == blocked or normalized.endswith(f".{blocked}") for blocked in SOURCE_OR_DIRECTORY_DOMAINS)


def _same_domain_urls(urls: list[Any], official_domain: str) -> list[str]:
    domain = (official_domain or "").lower().strip().removeprefix("www.")
    return _dedupe([str(url) for url in urls if domain and _domain_from_url(str(url)) == domain])


def _commercial_path_url(url: str) -> bool:
    path = (urlparse(str(url or "")).path or "").lower()
    return any(
        marker in path
        for marker in (
            "/api",
            "/careers",
            "/case-studies",
            "/customers",
            "/developer",
            "/developers",
            "/docs",
            "/documentation",
            "/jobs",
            "/pricing",
        )
    )


def _same_domain_commercial_urls(urls: list[Any], official_domain: str) -> list[str]:
    return _dedupe([url for url in _same_domain_urls(urls, official_domain) if _commercial_path_url(url)])


def _row_name(row: dict) -> str:
    return str(row.get("name") or row.get("company_name") or row.get("title") or row.get("display_name") or "").strip()


def _seed_items_from_row(row: dict) -> list[dict]:
    urls = _dedupe(
        [
            row.get("website"),
            row.get("homepage"),
            row.get("outbound_url"),
            row.get("product_hunt_url"),
            row.get("company_x"),
            row.get("url"),
            row.get("source"),
        ]
        + _as_list(row.get("source_outbound_urls"))
        + _as_list(row.get("sources"))
    )
    text = " ".join(
        str(row.get(key) or "")
        for key in ("title", "tagline", "description", "snippet", "body", "text", "why_on_radar")
    ).strip()
    items = [
        {
            "title": _row_name(row),
            "url": url,
            "snippet": text,
            "source": "signal_seed_url",
        }
        for url in urls
    ]
    if text:
        items.append(
            {
                "title": _row_name(row),
                "url": urls[0] if urls else "",
                "snippet": text,
                "source": "signal_seed_text",
            }
        )
    return items


def _provider_names(provider: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(provider, str):
        raw_names = provider.split(",")
    else:
        raw_names = list(provider or [])
    names = []
    seen = set()
    for raw_name in raw_names:
        name = str(raw_name or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _default_search_runner(
    query: str,
    *,
    provider: str | list[str] | tuple[str, ...] = DEFAULT_PROVIDER,
    cache_dir: Path | str | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    load_provider_env_files()
    attempted_payloads = []
    missing = []
    for provider_name in _provider_names(provider):
        if not provider_available(provider_name):
            missing.append(provider_name)
            continue
        try:
            payload = run_provider_query(
                provider_name,
                {"query": query, "query_family": "hard_evidence_resolver"},
                cache_dir=cache_dir,
                max_results=max_results,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            payload = {
                "provider": provider_name,
                "query": query,
                "items": [],
                "skipped": True,
                "skip_reason": f"provider_error:{exc}",
            }
        attempted_payloads.append(payload)
        if payload.get("items"):
            return payload
    for payload in attempted_payloads:
        if not payload.get("skipped"):
            return payload
    return {
        "provider": ",".join(_provider_names(provider)),
        "query": query,
        "items": [],
        "skipped": True,
        "skip_reason": "missing_provider_key" if missing else "no_provider_result",
    }


def _run_search_query(
    query: dict,
    *,
    search_runner,
    provider: str,
    cache_dir: Path | str | None,
    max_results: int,
    timeout_seconds: int,
) -> dict:
    query_text = str(query.get("query") or "").strip()
    if not query_text:
        return {"items": [], "skipped": True, "skip_reason": "empty_query"}
    runner = search_runner or _default_search_runner
    try:
        return runner(
            query_text,
            provider=provider,
            cache_dir=cache_dir,
            max_results=max_results,
            timeout_seconds=timeout_seconds,
        )
    except TypeError:
        return runner(
            topic=query_text,
            provider=provider,
            cache_dir=cache_dir,
            max_results=max_results,
            timeout_seconds=timeout_seconds,
        )


def _normalize_base_url(base_url: str) -> tuple[str, str]:
    value = str(base_url or "").strip()
    if not value:
        return "", ""
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    domain = parsed.netloc.lower().strip().removeprefix("www.")
    if not domain or _is_source_or_directory_domain(domain):
        return "", ""
    return f"{parsed.scheme or 'https'}://{domain}", domain


def _default_page_fetcher(url: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict:
    response = requests.get(
        url,
        headers={"User-Agent": "vc-signals-official-site-evidence/1.0"},
        timeout=timeout_seconds,
        allow_redirects=True,
    )
    return {
        "url": response.url,
        "status_code": response.status_code,
        "text": response.text[:120000],
    }


def _page_text(payload: dict) -> str:
    return str(payload.get("text") or payload.get("body") or payload.get("content") or "")


def crawl_official_site_evidence(
    base_url: str,
    *,
    page_fetcher=None,
    paths: tuple[str, ...] = DEFAULT_SITE_EVIDENCE_PATHS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Fetch a small set of official-site pages and classify evidence links."""

    base, domain = _normalize_base_url(base_url)
    evidence = {
        "official_domain": domain,
        "official_url": base,
        "pages_checked": [],
        "pages_seen": [],
        "fetch_errors": [],
        "founder_team_evidence": [],
        "pricing_evidence": [],
        "docs_evidence": [],
        "customer_buyer_evidence": [],
        "careers_evidence": [],
        "product_evidence": [],
        "evidence_urls": [],
    }
    if not base:
        return evidence
    fetcher = page_fetcher or _default_page_fetcher
    for path in paths:
        normalized_path = f"/{str(path).lstrip('/')}"
        url = urljoin(base + "/", normalized_path.lstrip("/"))
        evidence["pages_checked"].append(url)
        try:
            payload = fetcher(url, timeout_seconds=timeout_seconds)
        except TypeError:
            payload = fetcher(url)
        except Exception as exc:
            evidence["fetch_errors"].append({"url": url, "error": str(exc)})
            continue
        if not isinstance(payload, dict):
            continue
        status = int(payload.get("status_code") or payload.get("status") or 0)
        final_url = str(payload.get("url") or url)
        if status and not (200 <= status < 400):
            continue
        if _domain_from_url(final_url) != domain:
            continue
        text = _page_text(payload).lower()
        if not text:
            continue
        evidence["pages_seen"].append(final_url)
        evidence["evidence_urls"].append(final_url)
        role = classify_url_role(final_url).get("role")
        path_text = final_url.lower()
        if role in {"official_site"} and any(term in path_text or term in text for term in ("about", "team", "founder", "co-founder", "company")):
            evidence["founder_team_evidence"].append(final_url)
        if role == "pricing" or any(term in path_text or term in text for term in ("pricing", "plans", "paid", "subscription")):
            evidence["pricing_evidence"].append(final_url)
        if role == "docs" or any(term in path_text or term in text for term in ("docs", "documentation", "api reference", "developer")):
            evidence["docs_evidence"].append(final_url)
        if any(term in path_text or term in text for term in ("customers", "case-studies", "case studies", "trusted by", "used by")):
            evidence["customer_buyer_evidence"].append(final_url)
        if role == "careers" or any(term in path_text or term in text for term in ("careers", "jobs", "hiring", "we are hiring")):
            evidence["careers_evidence"].append(final_url)
        if any(term in path_text or term in text for term in ("blog", "changelog", "launch", "product update", "release notes")):
            evidence["product_evidence"].append(final_url)
    for key in (
        "pages_checked",
        "pages_seen",
        "founder_team_evidence",
        "pricing_evidence",
        "docs_evidence",
        "customer_buyer_evidence",
        "careers_evidence",
        "product_evidence",
        "evidence_urls",
    ):
        evidence[key] = _dedupe(evidence[key])
    return evidence


def build_hard_evidence_dossier(
    row: dict,
    *,
    source_lane: str = "",
    search_runner=None,
    site_page_fetcher=None,
    plan_provider=None,
    provider: str = DEFAULT_PROVIDER,
    cache_dir: Path | str | None = None,
    max_queries: int = DEFAULT_MAX_QUERIES,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    crawl_official_site: bool = False,
) -> dict:
    """Build a structured evidence dossier for one weak source row."""

    payload = dict(row)
    if source_lane:
        payload["source_lane"] = source_lane
    packet = build_investigation_packet(payload)
    plan = build_search_plan(packet, provider=plan_provider)
    search_items: list[dict] = []
    queries_run: list[dict] = []
    provider_payloads: list[dict] = []
    for query in (plan.get("search_plan") or [])[:max_queries]:
        payload = _run_search_query(
            query,
            search_runner=search_runner,
            provider=provider,
            cache_dir=cache_dir,
            max_results=max_results,
            timeout_seconds=timeout_seconds,
        )
        queries_run.append(query)
        if isinstance(payload, dict):
            provider_payloads.append(
                {
                    "provider": payload.get("provider", provider),
                    "query": payload.get("query") or query.get("query", ""),
                    "skipped": bool(payload.get("skipped")),
                    "skip_reason": payload.get("skip_reason", ""),
                    "items": len(payload.get("items") or []),
                }
            )
            search_items.extend(item for item in payload.get("items", []) or [] if isinstance(item, dict))
    investigation = reconcile_search_evidence({**packet, **plan}, _seed_items_from_row(row) + search_items)
    official_url = investigation.get("official_url", "")
    site_evidence = {}
    if crawl_official_site and official_url:
        site_evidence = crawl_official_site_evidence(
            official_url,
            page_fetcher=site_page_fetcher,
            timeout_seconds=timeout_seconds,
        )
    site_commercial_hints = _dedupe(
        _as_list(site_evidence.get("pricing_evidence"))
        + _as_list(site_evidence.get("docs_evidence"))
        + _as_list(site_evidence.get("customer_buyer_evidence"))
        + _as_list(site_evidence.get("careers_evidence"))
    )
    return {
        "enabled": True,
        "name": packet.get("name", ""),
        "source_lane": packet.get("source_lane", source_lane),
        "provider": provider,
        "plan_mode": plan.get("mode", ""),
        "plan": plan,
        "queries_run": queries_run,
        "provider_payloads": provider_payloads,
        "search_items_seen": len(search_items),
        "official_domain": investigation.get("official_domain", ""),
        "official_url": official_url,
        "official_domain_confidence": investigation.get("official_domain_confidence", 0),
        "official_domain_candidates": investigation.get("official_domain_candidates", []),
        "identity_risk_flags": investigation.get("identity_risk_flags", []),
        "url_roles": investigation.get("url_roles", []),
        "evidence_urls": _dedupe(_as_list(investigation.get("evidence_urls")) + _as_list(site_evidence.get("evidence_urls"))),
        "founder_hints": _dedupe(_as_list(investigation.get("founder_hints")) + _as_list(site_evidence.get("founder_team_evidence"))),
        "stage_hints": investigation.get("stage_hints", []),
        "commercial_hints": _dedupe(
            _same_domain_commercial_urls(_as_list(investigation.get("commercial_hints")), str(investigation.get("official_domain") or ""))
            + site_commercial_hints
        ),
        "external_commercial_hints": _dedupe(
            [
                str(value)
                for value in _as_list(investigation.get("commercial_hints"))
                if str(value)
                not in _same_domain_commercial_urls(_as_list(investigation.get("commercial_hints")), str(investigation.get("official_domain") or ""))
            ]
        ),
        "product_hints": _dedupe(_as_list(site_evidence.get("product_evidence"))),
        "site_evidence": site_evidence,
        "evidence_needed": investigation.get("evidence_needed", []),
        "route": investigation.get("route", ""),
        "unsafe_domain_attempts_blocked": investigation.get("unsafe_domain_attempts_blocked", 0),
    }


def _commercial_hints_by_role(hints: list[str]) -> dict[str, list[str]]:
    grouped = {"pricing_evidence": [], "docs_evidence": [], "careers_evidence": [], "customer_buyer_evidence": []}
    for hint in hints:
        role = classify_url_role(str(hint))
        text = str(hint).lower()
        if role.get("role") == "pricing" or "/pricing" in text or "/plans" in text:
            grouped["pricing_evidence"].append(str(hint))
        if role.get("role") == "docs" or "/docs" in text or "/documentation" in text or "/developers" in text:
            grouped["docs_evidence"].append(str(hint))
        if role.get("role") == "careers" or "/careers" in text or "/jobs" in text or "/hiring" in text:
            grouped["careers_evidence"].append(str(hint))
        grouped["customer_buyer_evidence"].append(str(hint))
    return {key: _dedupe(value) for key, value in grouped.items()}


def _remove_resolved_gaps(gaps: list[Any], *, domain: bool, founder: bool, commercial: bool) -> list[str]:
    out = []
    for gap in gaps:
        normalized = str(gap or "").strip()
        if not normalized:
            continue
        lower = normalized.lower()
        if domain and ("domain" in lower or "identity" in lower or "official" in lower):
            continue
        if founder and ("founder" in lower or "maker" in lower or "operator" in lower or "team" in lower):
            continue
        if commercial and ("commercial" in lower or "customer" in lower or "pricing" in lower or "docs" in lower):
            continue
        out.append(normalized)
    return out


def apply_dossier_to_source_row(row: dict, dossier: dict) -> dict:
    """Attach verified hard evidence to a source row without inventing facts."""

    out = deepcopy(row)
    out.setdefault("stage", "")
    out.setdefault("headcount", "")
    out.setdefault("raised", "")
    official_domain = str(dossier.get("official_domain") or "").strip().lower().removeprefix("www.")
    official_url = str(dossier.get("official_url") or "").strip() or (f"https://{official_domain}" if official_domain else "")
    confidence = int(dossier.get("official_domain_confidence") or 0)
    identity_risk_flags = _dedupe(_as_list(dossier.get("identity_risk_flags")))
    backed_by_official_role = any(
        isinstance(role, dict)
        and role.get("domain") == official_domain
        and role.get("role") in {"official_site", "docs", "pricing", "careers"}
        for role in dossier.get("url_roles") or []
    )
    if not backed_by_official_role and official_url:
        role = classify_url_role(official_url)
        backed_by_official_role = role.get("domain") == official_domain and role.get("role") in {
            "official_site",
            "docs",
            "pricing",
            "careers",
        }
    domain_is_safe = bool(official_domain and confidence >= 70 and backed_by_official_role and not identity_risk_flags)
    if domain_is_safe:
        out["domain"] = official_domain
        out["website"] = official_url
        out["domain_resolution_source"] = "hard_evidence"
        out["domain_resolution_status"] = "resolved"
        out["domain_resolution_evidence"] = {
            "official_url": official_url,
            "evidence_urls": _dedupe(_as_list(dossier.get("evidence_urls"))),
            "url_roles": deepcopy(dossier.get("url_roles") or []),
        }
    elif identity_risk_flags:
        source_lane = str(out.get("source_lane") or "").strip().lower()
        resolution_source = str(out.get("domain_resolution_source") or "").strip().lower()
        if source_lane in {"product hunt", "x"} and resolution_source in {"web_fallback", "hard_evidence"}:
            out["domain"] = ""
            out["website"] = ""
            out["domain_resolution_status"] = "ambiguous"
            out["domain_resolution_warning"] = "; ".join(identity_risk_flags)
        missing = _as_list(out.get("missing_evidence"))
        if AMBIGUOUS_IDENTITY_GAP not in missing:
            missing.append(AMBIGUOUS_IDENTITY_GAP)
        if "official_domain_identity_not_confirmed" not in missing:
            missing.append("official_domain_identity_not_confirmed")
        out["missing_evidence"] = _dedupe(missing)
    founder_hints = _dedupe(_as_list(dossier.get("founder_hints")))
    if founder_hints:
        out["founder_team_evidence"] = _dedupe(_as_list(out.get("founder_team_evidence")) + founder_hints)
    stage_hints = _dedupe(_as_list(dossier.get("stage_hints")))
    if stage_hints:
        out["stage_funding_evidence"] = _dedupe(_as_list(out.get("stage_funding_evidence")) + stage_hints)
    commercial_hints = _same_domain_commercial_urls(_as_list(dossier.get("commercial_hints")), official_domain)
    if commercial_hints:
        grouped = _commercial_hints_by_role(commercial_hints)
        for key, values in grouped.items():
            if values:
                out[key] = _dedupe(_as_list(out.get(key)) + values)
    product_hints = _dedupe(_as_list(dossier.get("product_hints")))
    if product_hints:
        out["product_evidence"] = _dedupe(_as_list(out.get("product_evidence")) + product_hints)
    evidence_urls = _dedupe(
        _as_list(out.get("source_outbound_urls"))
        + _as_list(dossier.get("evidence_urls"))
        + product_hints
        + [official_url]
    )
    if evidence_urls:
        out["source_outbound_urls"] = evidence_urls
    out["hard_evidence_dossier"] = deepcopy(dossier)
    out["missing_evidence"] = _remove_resolved_gaps(
        _as_list(out.get("missing_evidence")),
        domain=domain_is_safe,
        founder=bool(founder_hints),
        commercial=bool(commercial_hints),
    )
    if out.get("domain") and commercial_hints:
        out["evidence_confidence_score"] = max(int(out.get("evidence_confidence_score") or 0), 55)
    return out


def _empty_report(*, enabled: bool, provider: str, reason: str = "") -> dict:
    return {
        "summary": {
            "enabled": enabled,
            "provider": provider,
            "skip_reason": reason,
            "rows_considered": 0,
            "rows_investigated": 0,
            "search_queries_planned": 0,
            "search_queries_run": 0,
            "official_domains_resolved": 0,
            "commercial_evidence_rows": 0,
            "url_roles_classified": 0,
            "official_site_pages_seen": 0,
            "unsafe_domain_attempts_blocked": 0,
        },
        "items": [],
    }


def enrich_source_rows_with_hard_evidence(
    rows: list[dict],
    *,
    source_lane: str = "",
    search_runner=None,
    site_page_fetcher=None,
    plan_provider=None,
    provider: str = DEFAULT_PROVIDER,
    cache_dir: Path | str | None = None,
    max_rows: int | None = None,
    max_queries_per_row: int = DEFAULT_MAX_QUERIES,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    crawl_official_site: bool = False,
) -> tuple[list[dict], dict]:
    """Enrich source rows with public/manual hard evidence before promotion."""

    if not rows:
        return rows, _empty_report(enabled=True, provider=provider)
    enriched: list[dict] = []
    items: list[dict] = []
    summary = _empty_report(enabled=True, provider=provider)["summary"]
    summary["rows_considered"] = len(rows)
    limit = len(rows) if max_rows is None else min(max_rows, len(rows))
    for index, row in enumerate(rows):
        if index >= limit or not isinstance(row, dict):
            enriched.append(row)
            continue
        dossier = build_hard_evidence_dossier(
            row,
            source_lane=source_lane or str(row.get("source_lane") or ""),
            search_runner=search_runner,
            site_page_fetcher=site_page_fetcher,
            plan_provider=plan_provider,
            provider=provider,
            cache_dir=cache_dir,
            max_queries=max_queries_per_row,
            max_results=max_results,
            timeout_seconds=timeout_seconds,
            crawl_official_site=crawl_official_site,
        )
        updated = apply_dossier_to_source_row(row, dossier)
        enriched.append(updated)
        summary["rows_investigated"] += 1
        summary["search_queries_planned"] += len((dossier.get("plan") or {}).get("search_plan") or [])
        summary["search_queries_run"] += len(dossier.get("queries_run") or [])
        if dossier.get("official_domain"):
            summary["official_domains_resolved"] += 1
        if dossier.get("commercial_hints"):
            summary["commercial_evidence_rows"] += 1
        summary["url_roles_classified"] += len(dossier.get("url_roles") or [])
        site_evidence = dossier.get("site_evidence") if isinstance(dossier.get("site_evidence"), dict) else {}
        if site_evidence.get("pages_seen"):
            summary["official_site_pages_seen"] = int(summary.get("official_site_pages_seen") or 0) + len(site_evidence.get("pages_seen") or [])
        summary["unsafe_domain_attempts_blocked"] += int(dossier.get("unsafe_domain_attempts_blocked") or 0)
        items.append(
            {
                "name": dossier.get("name", _row_name(row)),
                "source_lane": dossier.get("source_lane", source_lane),
                "resolved_domain": dossier.get("official_domain", ""),
                "resolved_url": dossier.get("official_url", ""),
                "queries_run": dossier.get("queries_run", []),
                "commercial_hints": dossier.get("commercial_hints", []),
                "evidence_needed": dossier.get("evidence_needed", []),
                "unsafe_domain_attempts_blocked": dossier.get("unsafe_domain_attempts_blocked", 0),
                "dossier": dossier,
            }
        )
    return enriched, {"summary": summary, "items": items}


def write_hard_evidence_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
