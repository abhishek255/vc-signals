#!/usr/bin/env python3
"""Dry-run-first provider A/B helper for paid search experiments."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from discovery_search_providers import run_provider_query
from paid_search_guardrails import (
    configure_paid_search_guard,
    paid_search_summary,
    provider_cache_dir,
    provider_cost_usd,
    reset_paid_search_guard,
)


DEFAULT_PROVIDERS = ("brave", "exa", "serper", "dataforseo")


def _normalize_queries(queries: list[str | dict]) -> list[dict]:
    normalized = []
    for index, query in enumerate(queries or [], start=1):
        if isinstance(query, dict):
            topic = query.get("topic") or query.get("query") or ""
            query_id = query.get("query_id") or query.get("id") or f"q{index}"
            normalized.append({**query, "query_id": query_id, "topic": topic})
        else:
            normalized.append({"query_id": f"q{index}", "topic": str(query)})
    return [query for query in normalized if query.get("topic")]


def _normalize_providers(providers: list[str] | tuple[str, ...] | str | None) -> list[str]:
    if not providers:
        return list(DEFAULT_PROVIDERS)
    if isinstance(providers, str):
        raw = providers.split(",")
    else:
        raw = providers
    return [provider.strip().lower() for provider in raw if provider and provider.strip()]


def build_provider_ab_test_plan(
    *,
    queries: list[str | dict],
    providers: list[str] | tuple[str, ...] | str | None = None,
    max_results: int = 10,
) -> dict:
    normalized_queries = _normalize_queries(queries)
    normalized_providers = _normalize_providers(providers)
    planned_searches = []
    provider_estimates = {}
    for provider in normalized_providers:
        cost_per_query = provider_cost_usd(provider)
        provider_estimates[provider] = {
            "planned_queries": len(normalized_queries),
            "max_results": int(max_results),
            "estimated_cost_usd": round(cost_per_query * len(normalized_queries), 6),
            "cost_per_query_usd": cost_per_query,
        }
        for query in normalized_queries:
            planned_searches.append(
                {
                    "provider": provider,
                    "query_id": query["query_id"],
                    "topic": query["topic"],
                    "estimated_cost_usd": cost_per_query,
                }
            )
    return {
        "live": False,
        "query_count": len(normalized_queries),
        "provider_count": len(normalized_providers),
        "queries": normalized_queries,
        "providers": normalized_providers,
        "max_results": int(max_results),
        "planned_searches": planned_searches,
        "provider_estimates": provider_estimates,
        "estimated_cost_usd": round(sum(row["estimated_cost_usd"] for row in planned_searches), 6),
        "cache_dir": str(provider_cache_dir("provider-ab-test")),
    }


def run_provider_ab_test(
    *,
    queries: list[str | dict],
    providers: list[str] | tuple[str, ...] | str | None = None,
    live: bool = False,
    cache_dir: Path | str | None = None,
    ledger_path: Path | str | None = None,
    mode: str = "manual_enrichment",
    max_usd: float | None = None,
    max_results: int = 10,
    timeout_seconds: int = 20,
) -> dict:
    plan = build_provider_ab_test_plan(queries=queries, providers=providers, max_results=max_results)
    if not live:
        return plan

    configure_paid_search_guard(
        mode=mode,
        run_id="provider-ab-test",
        max_usd=max_usd,
        ledger_path=ledger_path,
    )
    try:
        results = []
        resolved_cache_dir = Path(cache_dir) if cache_dir else provider_cache_dir("provider-ab-test")
        for provider in plan["providers"]:
            for query in plan["queries"]:
                results.append(
                    run_provider_query(
                        provider,
                        query,
                        cache_dir=resolved_cache_dir,
                        max_results=max_results,
                        timeout_seconds=timeout_seconds,
                    )
                )
        return {
            **plan,
            "live": True,
            "results": results,
            "paid_search": paid_search_summary(),
            "cache_dir": str(resolved_cache_dir),
        }
    finally:
        reset_paid_search_guard()


def _parse_args(argv: list[str]) -> dict:
    args: dict[str, object] = {"query": []}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i][2:].replace("-", "_")
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                if key == "query":
                    args.setdefault("query", [])
                    args["query"].append(argv[i + 1])
                else:
                    args[key] = argv[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            i += 1
    return args


def _load_queries(args: dict) -> list[str | dict]:
    if args.get("queries_file"):
        payload = json.loads(Path(str(args["queries_file"])).read_text())
        if isinstance(payload, dict):
            payload = payload.get("queries") or []
        return list(payload or [])
    return list(args.get("query") or [])


def main() -> None:
    args = _parse_args(sys.argv[1:])
    queries = _load_queries(args)
    providers = str(args.get("providers") or ",".join(DEFAULT_PROVIDERS))
    live = bool(args.get("live") is True)
    result = run_provider_ab_test(
        queries=queries,
        providers=providers,
        live=live,
        cache_dir=Path(str(args["cache_dir"])) if args.get("cache_dir") else None,
        ledger_path=Path(str(args["ledger_path"])) if args.get("ledger_path") else None,
        mode=str(args.get("mode") or "manual_enrichment"),
        max_usd=float(args["max_usd"]) if args.get("max_usd") else None,
        max_results=int(args.get("max_results") or 10),
        timeout_seconds=int(args.get("timeout_seconds") or 20),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
