from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from discovery_search_providers import load_provider_env_files, run_provider_query
from radar_company_discovery import _classify_maturity_from_items


STRONG_DISCOVERY_FAMILIES = {"official_company_page", "founder_company_pages", "movement_platform"}
MATURITY_QUERY_KINDS = {
    "funding_stage": '"{company}" "{domain}" funding "seed round" "Series A" "Series B"',
    "late_stage_or_valuation": '"{company}" "{domain}" "Series C" valuation "$100M" unicorn',
    "acquisition": '"{company}" "{domain}" acquired acquisition buys',
    "founder_stage_context": '"{company}" "{domain}" founders funding startup',
}
EARLY_STAGE_PATTERNS = (
    r"\bpre[- ]?seed\b",
    r"\bseed\s+round\b",
    r"\braised\s+(?:a\s+)?seed\b",
    r"\braises\s+(?:a\s+)?seed\b",
    r"\bseries\s+[ab]\b",
)
MATURE_STAGE_PATTERNS = (
    r"\bseries\s+[cdefg]\b",
    r"\$\s?[0-9]+(?:\.[0-9]+)?\s?(?:m|million|b|billion)\b",
    r"\bvaluation\b",
    r"\bunicorn\b",
    r"\bacquir(?:ed|es|ing|e|er|ition)\b",
    r"\bcategory leader\b",
    r"\bmarket leader\b",
)


def normalize_domain(value: str) -> str:
    raw = (value or "").lower().strip()
    raw = raw.replace("https://", "").replace("http://", "")
    raw = raw.split("/", 1)[0]
    return raw[4:] if raw.startswith("www.") else raw


def same_domain_or_subdomain(value: str, domain: str) -> bool:
    normalized = normalize_domain(value)
    target = normalize_domain(domain)
    return bool(target and (normalized == target or normalized.endswith(f".{target}")))


def extract_maturity_targets(
    score_payload: dict,
    *,
    priority_domains: list[str] | None = None,
    limit: int | None = None,
) -> list[dict]:
    priority = [normalize_domain(domain) for domain in priority_domains or [] if domain]
    rows_by_domain: dict[str, dict] = {}
    for row in score_payload.get("accepted_leads", []):
        domain = normalize_domain(row.get("domain", ""))
        if not domain:
            continue
        target = rows_by_domain.setdefault(
            domain,
            {
                "company_name": row.get("display_name") or row.get("canonical_name") or row.get("name") or domain.split(".")[0],
                "domain": domain,
                "source_query_families": set(),
                "source_rows": [],
                "priority_reason": "",
            },
        )
        if row.get("query_family"):
            target["source_query_families"].add(row["query_family"])
        target["source_rows"].append(row)

    targets = []
    for domain, target in rows_by_domain.items():
        families = sorted(target["source_query_families"])
        target["source_query_families"] = families
        if domain in priority:
            target["priority_reason"] = "known_eval_target"
        elif any(family in STRONG_DISCOVERY_FAMILIES for family in families):
            target["priority_reason"] = "strong_discovery_family"
        else:
            target["priority_reason"] = "verified_domain"
        targets.append(target)

    priority_index = {domain: index for index, domain in enumerate(priority)}
    targets.sort(
        key=lambda row: (
            priority_index.get(row["domain"], 999),
            row["priority_reason"] != "strong_discovery_family",
            row["domain"],
        )
    )
    return targets[:limit] if limit else targets


def build_maturity_queries(targets: list[dict], *, per_domain_cap: int = 4) -> list[dict]:
    queries = []
    seen = set()
    for target in targets:
        company = (target.get("company_name") or "").strip()
        domain = normalize_domain(target.get("domain", ""))
        if not company or not domain:
            continue
        for kind, template in list(MATURITY_QUERY_KINDS.items())[:per_domain_cap]:
            topic = template.format(company=company, domain=domain)
            key = topic.lower()
            if key in seen:
                continue
            seen.add(key)
            queries.append(
                {
                    "query_id": f"maturity:{domain}:{kind}",
                    "query_kind": kind,
                    "company_name": company,
                    "domain": domain,
                    "topic": topic,
                }
            )
    return queries


def run_maturity_evidence_bakeoff(
    queries: list[dict],
    *,
    providers: list[str],
    provider_runner=run_provider_query,
    max_queries_per_provider: int = 80,
    max_results_per_query: int = 5,
    max_runtime_seconds: int | None = None,
    cache_dir: Path | str | None = None,
) -> dict:
    started = time.monotonic()
    provider_runs = []
    partial = False
    for provider in [item for item in providers if item]:
        for index, query in enumerate(queries):
            if index >= max_queries_per_provider:
                partial = True
                break
            if max_runtime_seconds is not None and time.monotonic() - started >= max_runtime_seconds:
                partial = True
                break
            run = provider_runner(
                provider,
                query,
                max_results=max_results_per_query,
                cache_dir=cache_dir,
            )
            run.setdefault("provider", provider)
            run.setdefault("query_id", query.get("query_id", ""))
            run.setdefault("query_kind", query.get("query_kind", ""))
            run.setdefault("domain", query.get("domain", ""))
            run.setdefault("company_name", query.get("company_name", ""))
            run.setdefault("query", query.get("topic", ""))
            provider_runs.append(run)
    return {
        "provider_runs": provider_runs,
        "summary": {
            "queries_available": len(queries),
            "runs": len(provider_runs),
            "queries_run": sum(1 for run in provider_runs if not run.get("skipped")),
            "skipped_runs": sum(1 for run in provider_runs if run.get("skipped")),
            "cache_hits": sum(1 for run in provider_runs if run.get("cache_status") == "hit"),
            "live_calls": sum(1 for run in provider_runs if run.get("cache_status") == "miss"),
            "partial_eval": partial,
            "duration_seconds": round(time.monotonic() - started, 3),
        },
    }


def classify_maturity_evidence(targets: list[dict], provider_runs: list[dict]) -> dict:
    by_domain = {normalize_domain(target.get("domain", "")): target for target in targets}
    items_by_domain = {domain: [] for domain in by_domain}
    matching_results_without_maturity = {domain: 0 for domain in by_domain}

    for run in provider_runs:
        domain = normalize_domain(run.get("domain", ""))
        target = by_domain.get(domain)
        if not target or run.get("skipped"):
            continue
        for item in _run_items(run):
            if not _item_matches_target(item, target):
                continue
            if _has_maturity_terms(item):
                items_by_domain[domain].append(item)
            else:
                matching_results_without_maturity[domain] += 1

    rows = {}
    for domain, target in by_domain.items():
        items = items_by_domain.get(domain, [])
        maturity = _classify_maturity_from_items(items, company_name=target.get("company_name", ""), domain=domain)
        basis = list(maturity.get("maturity_basis") or [])
        if maturity.get("maturity_status") != "unknown" and basis:
            status = "evaluated_with_evidence"
            reason = "maturity_evidence_found"
        elif matching_results_without_maturity.get(domain):
            status = "evaluated_no_maturity_evidence"
            reason = "domains_with_matching_results_but_no_maturity_terms"
        else:
            status = "evaluated_no_maturity_evidence"
            reason = "domains_with_no_maturity_results"
        rows[domain] = {
            "company_name": target.get("company_name", ""),
            "domain": domain,
            "maturity_evaluation_status": status,
            "maturity_result_reason": reason,
            "matching_results_without_maturity_terms": matching_results_without_maturity.get(domain, 0),
            **maturity,
        }

    return {
        "domains": rows,
        "summary": {
            "domains_evaluated": len(rows),
            "domains_with_maturity_evidence": sum(1 for row in rows.values() if row["maturity_evaluation_status"] == "evaluated_with_evidence"),
            "domains_with_no_maturity_results": sum(1 for row in rows.values() if row["maturity_result_reason"] == "domains_with_no_maturity_results"),
            "domains_with_matching_results_but_no_maturity_terms": sum(
                1 for row in rows.values() if row["maturity_result_reason"] == "domains_with_matching_results_but_no_maturity_terms"
            ),
        },
    }


def write_maturity_evidence_artifact(payload: dict, output_dir: Path | str) -> Path:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    out = path / "maturity-evidence-bakeoff.json"
    out.write_text(json.dumps(payload, indent=2))
    return out


def _run_items(run: dict) -> list[dict]:
    if "items" in run:
        return list(run.get("items") or [])
    return list((run.get("provider_result") or {}).get("items") or [])


def _item_matches_target(item: dict, target: dict) -> bool:
    domain = normalize_domain(target.get("domain", ""))
    company_key = _key(target.get("company_name", ""))
    text_key = _key(f"{item.get('title', '')} {item.get('snippet', '')} {item.get('description', '')} {item.get('url', '')}")
    item_domain = normalize_domain(item.get("url", ""))
    return bool(
        same_domain_or_subdomain(item_domain, domain)
        or (domain and _key(domain) in text_key)
        or (company_key and len(company_key) >= 3 and company_key in text_key)
    )


def _has_maturity_terms(item: dict) -> bool:
    text = f"{item.get('title', '')} {item.get('snippet', '')} {item.get('description', '')}".lower()
    return any(re.search(pattern, text) for pattern in (*EARLY_STAGE_PATTERNS, *MATURE_STAGE_PATTERNS))


def _key(value: str) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


def _priority_domains(score_payload: dict) -> list[str]:
    domains = []
    for row in score_payload.get("target_results", []):
        if row.get("found"):
            domain = row.get("target_domain") or row.get("domain") or row.get("expected_domain")
            if domain:
                domains.append(domain)
    return domains


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run maturity evidence retrieval for Phase 5 verified domains.")
    parser.add_argument("--lead-discovery-eval", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--cache-dir", default="")
    parser.add_argument("--providers", default="brave")
    parser.add_argument("--max-targets", type=int, default=20)
    parser.add_argument("--max-queries-per-provider", type=int, default=80)
    parser.add_argument("--max-results-per-query", type=int, default=5)
    parser.add_argument("--max-runtime-seconds", type=int, default=300)
    args = parser.parse_args(argv)

    load_provider_env_files()
    lead_eval = json.loads(Path(args.lead_discovery_eval).read_text())
    score_payload = lead_eval.get("score", {})
    targets = extract_maturity_targets(
        score_payload,
        priority_domains=_priority_domains(score_payload),
        limit=args.max_targets,
    )
    queries = build_maturity_queries(targets)
    bakeoff = run_maturity_evidence_bakeoff(
        queries,
        providers=[provider.strip() for provider in args.providers.split(",") if provider.strip()],
        max_queries_per_provider=args.max_queries_per_provider,
        max_results_per_query=args.max_results_per_query,
        max_runtime_seconds=args.max_runtime_seconds,
        cache_dir=args.cache_dir or None,
    )
    classification = classify_maturity_evidence(targets, bakeoff["provider_runs"])
    write_maturity_evidence_artifact(
        {"targets": targets, "queries": queries, "bakeoff": bakeoff, "classification": classification},
        args.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
