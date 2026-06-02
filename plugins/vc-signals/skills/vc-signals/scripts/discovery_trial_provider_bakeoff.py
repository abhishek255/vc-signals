from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from discovery_search_providers import load_provider_env_files, run_provider_query
from radar_company_discovery import (
    TRIAL_QUERY_FAMILIES,
    _verify_lead_maturity,
    classify_discovery_source,
    verify_discovery_item,
)


DEFAULT_OUTPUT_DIR = Path("docs/radar-runs/current-phase5-4-provider-bakeoff")


def load_trial_queries_from_weekly_run(run_dir: Path | str) -> list[dict]:
    """Load the exact discovery-yield trial queries from a completed weekly run."""
    path = Path(run_dir) / "company-discovery.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    queries = []
    for query in payload.get("queries", []) or []:
        if query.get("discovery_lane") != "discovery_yield_trial":
            continue
        if query.get("query_family") not in TRIAL_QUERY_FAMILIES:
            continue
        queries.append(dict(query))
    return queries


def weekly_trial_provider_bakeoff(
    queries: list[dict],
    *,
    providers: list[str],
    provider_runner=run_provider_query,
    cache_dir: Path | str | None = None,
    max_results_per_query: int = 10,
    max_runtime_seconds: int | None = None,
) -> dict:
    started = time.monotonic()
    cache_root = Path(cache_dir) if cache_dir else None
    provider_summaries = []
    provider_family_summaries = []
    accepted_leads = []
    rejected_leads = []
    provider_runs = []

    for provider in [item for item in providers if item]:
        state = _provider_state(provider, len(queries))
        family_states: dict[str, dict] = {}
        maturity_cache: dict[str, dict] = {}
        for query in queries:
            if max_runtime_seconds is not None and time.monotonic() - started >= max_runtime_seconds:
                state["partial"] = True
                state["budget_exceeded"] = True
                state["skipped_queries"] += 1
                state["skip_reasons"]["max_runtime_seconds_exceeded"] += 1
                continue

            family = query.get("query_family", "") or "unknown"
            family_state = family_states.setdefault(family, _family_state(provider, family))
            family_state["queries_planned"] += 1
            run = provider_runner(
                provider,
                query,
                max_results=max_results_per_query,
                cache_dir=(cache_root / "provider-query-cache") if cache_root else None,
            )
            _attach_run_defaults(run, provider, query)
            provider_runs.append(run)
            state["latency_ms"] += int(run.get("latency_ms") or 0)
            state["cost_usd"] += float(run.get("cost_usd") or 0)
            family_state["queries_run"] += 0 if run.get("skipped") else 1

            if run.get("skipped"):
                state["skipped_queries"] += 1
                reason = run.get("skip_reason") or "provider_skipped"
                state["skip_reasons"][reason] += 1
                family_state["skipped_queries"] += 1
                family_state["skip_reasons"][reason] += 1
                continue

            state["queries_run"] += 1
            if run.get("cache_status") == "hit":
                state["cache_hits"] += 1
            elif run.get("cache_status") == "miss":
                state["live_calls"] += 1

            items = _provider_run_items(run)[:max_results_per_query]
            state["provider_items_seen"] += len(items)
            family_state["provider_items_seen"] += len(items)
            for item in items:
                source_type = classify_discovery_source(item)
                state["source_type_counts"][source_type] += 1
                enriched = dict(item)
                enriched.setdefault("query_kind", query.get("kind", ""))
                enriched.setdefault("query_topic", query.get("topic", ""))
                enriched.setdefault("query_theme", query.get("theme") or query.get("movement", ""))
                enriched.setdefault("market_sector", query.get("market_sector", ""))
                enriched.setdefault("candidate_eligible", True)
                enriched.setdefault("discovery_lane", "discovery_yield_trial")
                lead = verify_discovery_item(enriched, query)
                if lead.verification_status == "accepted":
                    lead, maturity_status = _apply_provider_maturity(
                        lead,
                        query,
                        provider,
                        provider_runner,
                        maturity_cache,
                        cache_root,
                        max_results_per_query,
                    )
                    if maturity_status in {"fresh", "stale", "memory"}:
                        state["maturity_cache_hits"] += 1
                    elif maturity_status == "miss":
                        state["maturity_queries_run"] += 1
                        state["live_calls"] += 1
                    row = lead.to_dict()
                    row.update({"provider": provider, "query_family": family})
                    accepted_leads.append(row)
                    _record_accepted(state, family_state, row)
                else:
                    row = lead.to_dict()
                    row.update({"provider": provider, "query_family": family})
                    rejected_leads.append(row)
                    _record_rejected(state, family_state, row)

        provider_summaries.append(_serialize_provider_state(state))
        provider_family_summaries.extend(
            _serialize_family_state(row) for row in family_states.values()
        )

    return {
        "summary": {
            "providers": [item for item in providers if item],
            "queries": len(queries),
            "runs": len(provider_runs),
            "duration_seconds": round(time.monotonic() - started, 3),
            "partial": any(row.get("partial") for row in provider_summaries),
            "budget_exceeded": any(row.get("budget_exceeded") for row in provider_summaries),
        },
        "queries": queries,
        "provider_runs": provider_runs,
        "provider_summaries": provider_summaries,
        "provider_family_summaries": provider_family_summaries,
        "accepted_leads": accepted_leads,
        "rejected_leads": rejected_leads,
    }


def write_weekly_trial_provider_bakeoff_artifacts(payload: dict, output_dir: Path | str) -> list[Path]:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    json_path = path / "weekly-trial-provider-bakeoff.json"
    markdown_path = path / "weekly-trial-provider-summary.md"
    json_path.write_text(json.dumps(payload, indent=2))
    markdown_path.write_text(_summary_markdown(payload))
    return [json_path, markdown_path]


def _apply_provider_maturity(
    lead,
    query: dict,
    provider: str,
    provider_runner,
    maturity_cache: dict[str, dict],
    cache_root: Path | None,
    max_results_per_query: int,
):
    def maturity_runner(topic: str, **_kwargs):
        maturity_query = {
            "id": f"maturity:{lead.domain}:{topic}",
            "topic": topic,
            "query_family": "maturity_verification",
            "movement": query.get("movement", ""),
            "market_sector": query.get("market_sector", ""),
        }
        return provider_runner(
            provider,
            maturity_query,
            max_results=max_results_per_query,
            cache_dir=(cache_root / "provider-query-cache") if cache_root else None,
        )

    out, _warnings, _errors, _queries, cache_status = _verify_lead_maturity(
        lead,
        query,
        maturity_runner,
        maturity_cache,
        query_cache_dir=(cache_root / provider / "maturity-cache") if cache_root else None,
    )
    return out, cache_status


def _attach_run_defaults(run: dict, provider: str, query: dict) -> None:
    run.setdefault("provider", provider)
    run.setdefault("query_id", query.get("id") or query.get("query_id") or "")
    run.setdefault("query_family", query.get("query_family", ""))
    run.setdefault("movement", query.get("movement", ""))
    run.setdefault("market_sector", query.get("market_sector", ""))
    run.setdefault("query", query.get("topic", ""))
    run.setdefault("items", [])
    run.setdefault("skipped", False)
    run.setdefault("skip_reason", "")
    run.setdefault("cache_status", "")
    run.setdefault("latency_ms", 0)
    run.setdefault("cost_usd", 0.0)


def _provider_run_items(run: dict) -> list[dict]:
    if "items" in run:
        return list(run.get("items") or [])
    return list((run.get("provider_result") or {}).get("items") or [])


def _provider_state(provider: str, queries_planned: int) -> dict:
    return {
        "provider": provider,
        "queries_planned": queries_planned,
        "queries_run": 0,
        "skipped_queries": 0,
        "skip_reasons": Counter(),
        "cache_hits": 0,
        "live_calls": 0,
        "maturity_queries_run": 0,
        "maturity_cache_hits": 0,
        "provider_items_seen": 0,
        "accepted": 0,
        "rejected": 0,
        "rejection_reasons": Counter(),
        "source_type_counts": Counter(),
        "verified_domains": set(),
        "early_stage_domains": set(),
        "research_unknown_domains": set(),
        "category_anchor_domains": set(),
        "sourcing_candidate_domains": set(),
        "assign_owner_domains": set(),
        "unsafe_promotion_domains": set(),
        "latency_ms": 0,
        "cost_usd": 0.0,
        "partial": False,
        "budget_exceeded": False,
    }


def _family_state(provider: str, family: str) -> dict:
    state = _provider_state(provider, 0)
    state["query_family"] = family
    return state


def _record_accepted(state: dict, family_state: dict, lead: dict) -> None:
    for row in (state, family_state):
        row["accepted"] += 1
        domain = _normalize_domain(lead.get("domain", ""))
        if not domain:
            continue
        row["verified_domains"].add(domain)
        if lead.get("maturity_status") == "seed_to_series_b":
            row["early_stage_domains"].add(domain)
        if lead.get("lead_route") == "research_deeper" and lead.get("maturity_status") == "unknown":
            row["research_unknown_domains"].add(domain)
        if lead.get("category_anchor") or lead.get("lead_route") in {"category_context", "monitor_only"}:
            row["category_anchor_domains"].add(domain)
        if lead.get("lead_route") == "sourcing_candidate":
            row["sourcing_candidate_domains"].add(domain)
        if lead.get("recommended_owner_action") == "Assign owner":
            row["assign_owner_domains"].add(domain)
        if lead.get("lead_route") in {"sourcing_candidate", "assign_owner"} and lead.get("maturity_status") != "seed_to_series_b":
            row["unsafe_promotion_domains"].add(domain)


def _record_rejected(state: dict, family_state: dict, lead: dict) -> None:
    for row in (state, family_state):
        row["rejected"] += 1
        for reason in lead.get("missing_evidence", []) or ["rejected"]:
            row["rejection_reasons"][reason] += 1


def _serialize_provider_state(state: dict) -> dict:
    provider_items = state["provider_items_seen"]
    junk_rejections = sum(
        count
        for reason, count in state["rejection_reasons"].items()
        if reason
        in {
            "source_domain_not_company_proof",
            "content_platform_not_company_domain",
            "listicle_or_seo_not_company_domain",
            "directory_page_not_company_domain",
            "github_only_not_company_proof",
            "publisher_article_needs_official_domain",
            "official_company_domain_not_verified",
        }
    )
    return {
        "provider": state["provider"],
        "queries_planned": state["queries_planned"],
        "queries_run": state["queries_run"],
        "skipped_queries": state["skipped_queries"],
        "skip_reasons": dict(state["skip_reasons"]),
        "cache_hits": state["cache_hits"],
        "live_calls": state["live_calls"],
        "maturity_queries_run": state["maturity_queries_run"],
        "maturity_cache_hits": state["maturity_cache_hits"],
        "provider_items_seen": provider_items,
        "verified_domains": len(state["verified_domains"]),
        "verified_domain_list": sorted(state["verified_domains"]),
        "maturity_confirmed_early_stage": len(state["early_stage_domains"]),
        "research_worthy_unknown": len(state["research_unknown_domains"]),
        "category_anchors": len(state["category_anchor_domains"]),
        "sourcing_candidates": len(state["sourcing_candidate_domains"]),
        "assign_owner_rows": len(state["assign_owner_domains"]),
        "unsafe_promotions": len(state["unsafe_promotion_domains"]),
        "accepted": state["accepted"],
        "rejected": state["rejected"],
        "rejection_reasons": dict(state["rejection_reasons"].most_common()),
        "source_type_counts": dict(state["source_type_counts"].most_common()),
        "junk_source_authority_rejection_rate": round(junk_rejections / provider_items, 4) if provider_items else 0,
        "latency_ms": state["latency_ms"],
        "cost_usd": round(state["cost_usd"], 4),
        "partial": state["partial"],
        "budget_exceeded": state["budget_exceeded"],
    }


def _serialize_family_state(state: dict) -> dict:
    row = _serialize_provider_state(state)
    row["query_family"] = state.get("query_family", "")
    return row


def _normalize_domain(value: str) -> str:
    raw = (value or "").lower().strip().replace("https://", "").replace("http://", "")
    raw = raw.split("/", 1)[0]
    return raw[4:] if raw.startswith("www.") else raw


def _summary_markdown(payload: dict) -> str:
    lines = [
        "# Weekly Trial Provider Bakeoff",
        "",
        f"- Providers: {', '.join(payload.get('summary', {}).get('providers', []))}",
        f"- Trial queries: {payload.get('summary', {}).get('queries', 0)}",
        f"- Partial: {payload.get('summary', {}).get('partial', False)}",
        f"- Budget exceeded: {payload.get('summary', {}).get('budget_exceeded', False)}",
        "",
        "| Provider | Queries | Verified Domains | Early | Unknown Research | Category | Assign Owner | Junk Rejection Rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload.get("provider_summaries", []):
        lines.append(
            "| {provider} | {queries_run} | {verified_domains} | {maturity_confirmed_early_stage} | "
            "{research_worthy_unknown} | {category_anchors} | {assign_owner_rows} | {junk_source_authority_rejection_rate} |".format(
                **row
            )
        )
    lines.extend(["", "## Recommendation", "", _recommendation(payload)])
    return "\n".join(lines) + "\n"


def _recommendation(payload: dict) -> str:
    winners = [
        row
        for row in payload.get("provider_summaries", [])
        if row.get("maturity_confirmed_early_stage", 0) or row.get("research_worthy_unknown", 0)
    ]
    if not winners:
        return "No provider produced enough trial yield to graduate. Keep providers in trial or move to a company-native source lane."
    best = sorted(
        winners,
        key=lambda row: (
            row.get("maturity_confirmed_early_stage", 0),
            row.get("research_worthy_unknown", 0),
            -row.get("unsafe_promotions", 0),
        ),
        reverse=True,
    )[0]
    return f"{best['provider']} produced the strongest trial yield, but graduation still requires low false positives across repeated weekly runs."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 5.4 provider bakeoff for weekly discovery-yield trial queries.")
    parser.add_argument("--weekly-run-dir", required=True)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--cache-dir", default="")
    parser.add_argument("--providers", default="brave,you")
    parser.add_argument("--max-results-per-query", type=int, default=10)
    parser.add_argument("--max-runtime-seconds", type=int, default=900)
    args = parser.parse_args(argv)

    load_provider_env_files()
    queries = load_trial_queries_from_weekly_run(args.weekly_run_dir)
    payload = weekly_trial_provider_bakeoff(
        queries,
        providers=[provider.strip() for provider in args.providers.split(",") if provider.strip()],
        cache_dir=args.cache_dir or Path(args.output_dir) / "provider-cache",
        max_results_per_query=args.max_results_per_query,
        max_runtime_seconds=args.max_runtime_seconds,
    )
    write_weekly_trial_provider_bakeoff_artifacts(payload, args.output_dir)
    print(json.dumps(payload["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
