#!/usr/bin/env python3
"""Focused manual-mode enrichment for the top few review candidates.

This is deliberately a web-search assist, not a LinkedIn/Crunchbase scraper.
It gathers public result snippets and URLs for the manual checks a human would
do on the top rows only.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from last30days_adapter import run_query


DEFAULT_OUTPUT_NAME = "targeted-manual-enrichment.json"


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    domain = (parsed.netloc or "").lower().strip()
    return domain[4:] if domain.startswith("www.") else domain


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


def _load_targets(run_dir: Path, *, target_source: str = "manual_or_gap_queue") -> list[dict]:
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
    query_runner=run_query,
) -> dict:
    selected = targets[:limit]
    rows = []
    total_queries = 0
    total_items = 0
    total_errors = 0

    for target in selected:
        query_rows = []
        collected_items = []
        for query in build_target_queries(target, queries_per_target=queries_per_target):
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
        },
        "items": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run focused manual-mode enrichment on top targets.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--queries-per-target", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--target-source", choices=("manual_or_gap_queue", "evidence_gap_queue"), default="manual_or_gap_queue")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    targets = _load_targets(run_dir, target_source=args.target_source)
    report = enrich_targets(
        targets,
        limit=args.limit,
        queries_per_target=args.queries_per_target,
        timeout_seconds=args.timeout_seconds,
    )
    report["run_dir"] = str(run_dir)
    output_path = run_dir / args.output_name
    output_path.write_text(json.dumps(report, indent=2))
    print(json.dumps({"output": str(output_path), "summary": report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
