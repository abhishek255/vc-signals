#!/usr/bin/env python3
"""Focused manual-mode enrichment for the top few review candidates.

This is deliberately a web-search assist, not a LinkedIn/Crunchbase scraper.
It gathers public result snippets and URLs for the manual checks a human would
do on the top rows only.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from discovery_search_providers import load_provider_env_files, provider_available, run_provider_query
from last30days_adapter import run_query as run_last30days_query
from paid_search_guardrails import (
    configure_paid_search_guard,
    paid_search_summary,
    provider_cache_dir,
    reset_paid_search_guard,
)


DEFAULT_OUTPUT_NAME = "targeted-manual-enrichment.json"
DEFAULT_PROVIDER_ORDER = ("exa", "brave")
DEFAULT_MAX_RESULTS = 6


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    domain = (parsed.netloc or "").lower().strip()
    return domain[4:] if domain.startswith("www.") else domain


def _provider_order(value: str | None = None) -> list[str]:
    raw = value or os.environ.get("VC_SIGNALS_TARGETED_MANUAL_PROVIDER_ORDER") or ",".join(DEFAULT_PROVIDER_ORDER)
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def run_public_search_query(
    topic: str,
    *,
    sources: str = "web",
    lookback_days: int = 365,
    auto_resolve: bool = True,
    store: bool = True,
    timeout_seconds: int = 45,
    provider_order: str | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> dict:
    """Run targeted public search through guarded direct providers before fallback.

    The return shape intentionally matches last30days_adapter.run_query enough for
    the enrichment pipeline: items, warnings, errors_by_source, and error.
    """
    load_provider_env_files()
    errors_by_source: dict[str, str] = {}
    configured_provider_seen = False
    for provider in _provider_order(provider_order):
        if not provider_available(provider):
            errors_by_source[provider] = "missing_api_key"
            continue
        configured_provider_seen = True
        try:
            payload = run_provider_query(
                provider,
                {
                    "query": topic,
                    "query_family": "targeted_manual_enrichment",
                },
                cache_dir=provider_cache_dir("targeted-manual-enrichment"),
                max_results=max_results,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            errors_by_source[provider] = str(exc)
            continue
        if payload.get("skipped"):
            errors_by_source[provider] = payload.get("skip_reason") or "provider_skipped"
            continue
        result = {
            "items": payload.get("items") or [],
            "provider": provider,
            "warnings": payload.get("warnings") or [],
            "errors_by_source": errors_by_source,
            "cost_usd": payload.get("cost_usd", 0.0),
            "cache_status": payload.get("cache_status", ""),
        }
        return result

    if configured_provider_seen:
        return {
            "items": [],
            "error": "direct_provider_search_unavailable",
            "warnings": ["Configured direct search providers were unavailable, skipped, or over budget."],
            "errors_by_source": errors_by_source,
        }

    payload = run_last30days_query(
        topic,
        sources=sources,
        lookback_days=lookback_days,
        auto_resolve=auto_resolve,
        store=store,
        timeout_seconds=timeout_seconds,
    )
    warnings = list(payload.get("warnings") or [])
    warnings.append("direct_search_provider_unavailable_last30days_fallback")
    return {**payload, "warnings": warnings, "errors_by_source": {**errors_by_source, **(payload.get("errors_by_source") or {})}}


def _targets_from_source_yield_gap_queue(run_dir: Path) -> list[dict]:
    source_yield_path = run_dir / "source-yield-validation-report.json"
    if not source_yield_path.exists():
        return []
    payload = json.loads(source_yield_path.read_text())
    items = payload.get("evidence_gap_queue") or []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["recommended_next_step"] = row.get("recommended_next_step") or row.get("next_step") or ""
        normalized.append(row)
    return normalized


def _targets_from_source_yield_partner_review(run_dir: Path) -> list[dict]:
    source_yield_path = run_dir / "source-yield-validation-report.json"
    if not source_yield_path.exists():
        return []
    payload = json.loads(source_yield_path.read_text())
    items = payload.get("partner_review_companies") or []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["recommended_next_step"] = (
            row.get("recommended_next_step")
            or row.get("recommended_manual_check")
            or row.get("next_step")
            or ""
        )
        normalized.append(row)
    return normalized


def _load_targets(run_dir: Path, *, target_source: str = "manual_or_gap_queue") -> list[dict]:
    if target_source == "partner_review_companies":
        items = _targets_from_source_yield_partner_review(run_dir)
        if items:
            return items
        raise FileNotFoundError(f"source-yield Partner Review rows missing: {run_dir / 'source-yield-validation-report.json'}")
    if target_source == "evidence_gap_queue":
        items = _targets_from_source_yield_gap_queue(run_dir)
        if items:
            return items
        raise FileNotFoundError(f"source-yield evidence gap queue missing: {run_dir / 'source-yield-validation-report.json'}")
    path = run_dir / "manual-enrichment-targets.json"
    if path.exists():
        payload = json.loads(path.read_text())
        items = payload.get("items") or []
        return [item for item in items if isinstance(item, dict)]
    items = _targets_from_source_yield_gap_queue(run_dir)
    if items:
        return items
    raise FileNotFoundError(f"manual enrichment targets missing: {path}")


def build_target_queries(target: dict, *, queries_per_target: int = 2) -> list[dict]:
    name = (target.get("name") or "").strip()
    domain = (target.get("domain") or "").strip()
    missing = set(target.get("missing_evidence") or [])
    search_name = name.split("/", 1)[1] if "/" in name else name
    quoted_identity = f'"{name}" "{domain}"'.strip()
    quoted_name = f'"{search_name}"'

    queries = []
    if "official_domain_missing" in missing:
        queries.append(
            {
                "kind": "official_domain",
                "query": f'{quoted_name} official website company startup product',
                "why": "Resolve the official company or product website before any promotion.",
            }
        )
    queries.append(
        {
            "kind": "linkedin_company_and_founders",
            "query": f'{quoted_name} LinkedIn company founder co-founder CEO CTO',
            "why": "Find company LinkedIn and founder/team sources.",
        }
    )
    if missing & {"commercial_or_customer_signal_missing", "customer_buyer_evidence_missing"}:
        queries.append(
            {
                "kind": "commercial_customer_proof",
                "query": f'{quoted_identity or quoted_name} pricing customers case studies docs users deployments',
                "why": "Find commercial proof such as pricing, customers, case studies, docs, or deployments.",
            }
        )
    if "pricing_docs_or_careers_missing" in missing:
        queries.append(
            {
                "kind": "pricing_docs_careers",
                "query": f'{quoted_identity or quoted_name} pricing docs careers jobs hiring customers',
                "why": "Find pricing, docs, careers, jobs, or customer-facing pages.",
            }
        )
    if missing & {"stage_or_funding_missing", "stage_funding_or_headcount_missing", "headcount_missing", "founder_team_missing"}:
        queries.append(
            {
                "kind": "funding_stage_headcount",
                "query": f'{quoted_identity} seed funding headcount Crunchbase Dealroom careers founders',
                "why": "Find public funding/stage/headcount metadata hints.",
            }
        )
    else:
        queries.append(
            {
                "kind": "company_linkedin",
                "query": f'{quoted_name} site:linkedin.com/company LinkedIn company',
                "why": "Fill the missing company LinkedIn field.",
            }
        )
    return queries[: max(1, queries_per_target)]


def _summarize_items(items: list[dict], *, max_items: int = 6) -> list[dict]:
    summarized = []
    for item in items[:max_items]:
        url = item.get("url") or item.get("source_url") or ""
        summarized.append(
            {
                "title": item.get("title") or "",
                "url": url,
                "domain": item.get("domain") or _domain_from_url(url),
                "source": item.get("source") or "",
                "snippet": item.get("snippet") or item.get("description") or "",
                "published_at": item.get("published_at") or "",
            }
        )
    return summarized


def _evidence_hints(items: list[dict], target: dict) -> dict:
    target_domain = (target.get("domain") or "").lower().removeprefix("www.")
    hints = {
        "official_domain_hits": [],
        "company_linkedin_candidates": [],
        "founder_linkedin_candidates": [],
        "funding_metadata_candidates": [],
        "careers_or_headcount_candidates": [],
    }
    for item in items:
        url = item.get("url") or item.get("source_url") or ""
        domain = (item.get("domain") or _domain_from_url(url)).lower().removeprefix("www.")
        blob = " ".join(
            str(item.get(key) or "")
            for key in ("title", "snippet", "description", "url", "domain")
        ).lower()
        compact = {"title": item.get("title") or "", "url": url, "domain": domain}
        if target_domain and (domain == target_domain or domain.endswith(f".{target_domain}") or target_domain in blob):
            hints["official_domain_hits"].append(compact)
        if "linkedin.com/company" in url.lower():
            hints["company_linkedin_candidates"].append(compact)
        if "linkedin.com/in/" in url.lower():
            hints["founder_linkedin_candidates"].append(compact)
        if any(host in url.lower() for host in ("crunchbase.com/organization", "dealroom.co/companies")):
            hints["funding_metadata_candidates"].append(compact)
        if any(term in blob for term in ("headcount", "employees", "careers", "jobs", "hiring")):
            hints["careers_or_headcount_candidates"].append(compact)
    return {key: value[:5] for key, value in hints.items()}


def _unresolved_gaps(target: dict, hints: dict) -> list[str]:
    unresolved = []
    missing = set(target.get("missing_evidence") or [])
    if ("company_linkedin_missing" in missing or "company_linkedin_or_social_missing" in missing) and not hints["company_linkedin_candidates"]:
        unresolved.append("company_linkedin_still_missing")
    if "founder_team_missing" in missing and not hints["founder_linkedin_candidates"]:
        unresolved.append("founder_team_source_still_missing")
    if ("stage_or_funding_missing" in missing or "stage_funding_or_headcount_missing" in missing) and not hints["funding_metadata_candidates"]:
        unresolved.append("stage_or_funding_source_still_missing")
    if ("headcount_missing" in missing or "stage_funding_or_headcount_missing" in missing) and not hints["careers_or_headcount_candidates"]:
        unresolved.append("headcount_source_still_missing")
    if "official_domain_missing" in missing and not hints["official_domain_hits"]:
        unresolved.append("official_domain_still_missing")
    if "pricing_docs_or_careers_missing" in missing and not hints["careers_or_headcount_candidates"]:
        unresolved.append("pricing_docs_or_careers_still_missing")
    return unresolved


def enrich_targets(
    targets: list[dict],
    *,
    limit: int = 3,
    queries_per_target: int = 2,
    timeout_seconds: int = 45,
    max_runtime_seconds: int | None = None,
    query_runner=None,
    provider_order: str | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> dict:
    if query_runner is None:
        query_runner = lambda topic, **kwargs: run_public_search_query(
            topic,
            provider_order=provider_order,
            max_results=max_results,
            **kwargs,
        )
    selected = targets[:limit]
    rows = []
    total_queries = 0
    total_items = 0
    total_errors = 0
    stopped_early = False
    started_at = time.monotonic()

    for target in selected:
        if max_runtime_seconds is not None and time.monotonic() - started_at >= max_runtime_seconds:
            stopped_early = True
            break
        query_rows = []
        collected_items = []
        for query in build_target_queries(target, queries_per_target=queries_per_target):
            if max_runtime_seconds is not None and time.monotonic() - started_at >= max_runtime_seconds:
                stopped_early = True
                break
            total_queries += 1
            payload = query_runner(
                query["query"],
                sources="web",
                lookback_days=365,
                auto_resolve=True,
                store=True,
                timeout_seconds=timeout_seconds,
            )
            items = payload.get("items") or []
            if payload.get("error"):
                total_errors += 1
            total_items += len(items)
            collected_items.extend(items)
            query_rows.append(
                {
                    **query,
                    "error": payload.get("error", ""),
                    "items_seen": len(items),
                    "top_items": _summarize_items(items),
                    "warnings": payload.get("warnings") or [],
                    "errors_by_source": payload.get("errors_by_source") or {},
                }
            )
        hints = _evidence_hints(collected_items, target)
        rows.append(
            {
                "name": target.get("name") or "",
                "domain": target.get("domain") or "",
                "source_lane": target.get("source_lane") or "",
                "action": target.get("action") or "",
                "tier": target.get("tier") or "",
                "missing_evidence": target.get("missing_evidence") or [],
                "recommended_next_step": target.get("recommended_next_step") or "",
                "queries": query_rows,
                "evidence_hints": hints,
                "unresolved_gaps": _unresolved_gaps(target, hints),
                "manual_policy": "Public web-search assist only; do not scrape gated LinkedIn/Crunchbase pages.",
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": "Manual-mode enrichment for the top targets only. Uses public web search snippets/results and keeps LinkedIn/Crunchbase-style checks as human review cues.",
        "summary": {
            "targets_considered": len(targets),
            "targets_enriched": len(rows),
            "queries_run": total_queries,
            "items_seen": total_items,
            "errors": total_errors,
            "queries_per_target": queries_per_target,
            "limit": limit,
            "max_runtime_seconds": max_runtime_seconds,
            "stopped_early": stopped_early,
            "provider_order": _provider_order(provider_order),
            "max_results": max_results,
        },
        "items": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run focused manual-mode enrichment on top targets.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--queries-per-target", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--max-runtime-seconds", type=int, default=None)
    parser.add_argument("--provider-order", default=None)
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS)
    parser.add_argument("--paid-search-max-usd", type=float, default=2.0)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument(
        "--target-source",
        choices=("manual_or_gap_queue", "evidence_gap_queue", "partner_review_companies"),
        default="manual_or_gap_queue",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    targets = _load_targets(run_dir, target_source=args.target_source)
    configure_paid_search_guard(
        mode="manual_enrichment",
        run_id=f"targeted-manual-enrichment:{run_dir.name}",
        max_usd=args.paid_search_max_usd,
    )
    try:
        report = enrich_targets(
            targets,
            limit=args.limit,
            queries_per_target=args.queries_per_target,
            timeout_seconds=args.timeout_seconds,
            max_runtime_seconds=args.max_runtime_seconds,
            provider_order=args.provider_order,
            max_results=args.max_results,
        )
        report["paid_search"] = paid_search_summary()
    finally:
        reset_paid_search_guard()
    report["run_dir"] = str(run_dir)
    output_path = run_dir / args.output_name
    output_path.write_text(json.dumps(report, indent=2))
    print(json.dumps({"output": str(output_path), "summary": report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
