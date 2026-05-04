from __future__ import annotations

from collections.abc import Callable

from radar_models import ThemeSignal


def build_company_discovery_queries(
    theme_signals: list[ThemeSignal],
    *,
    grounded_available: bool,
    social_available: bool,
    lookback_days: int = 30,
    max_queries_per_theme: int = 3,
) -> list[dict]:
    """Build targeted company searches from non-company theme evidence."""
    queries = []
    sources = _sources(grounded_available=grounded_available, social_available=social_available)

    for signal in theme_signals:
        theme = signal.theme
        market_sector = signal.market_sector
        query_specs = [
            (
                "theme_company_search",
                signal.suggested_search or f"{theme} startups Seed Series A founder launch",
            ),
            (
                "theme_founder_search",
                f"{theme} startup founder launch company {market_sector}",
            ),
            (
                "theme_funding_search",
                f"{theme} startup raises seed Series A funding company",
            ),
        ]
        for kind, topic in query_specs[:max_queries_per_theme]:
            query = {
                "kind": kind,
                "topic": topic,
                "sources": sources,
                "lookback_days": lookback_days,
                "candidate_eligible": True,
                "market_sector": market_sector,
                "theme": theme,
            }
            if grounded_available:
                query["web_backend"] = "auto"
            else:
                query["limited"] = True
                query["reason"] = "Grounded company discovery unavailable; HN/social search may miss private company pages."
            queries.append(query)

    return queries


def collect_company_discovery(
    theme_signals: list[ThemeSignal],
    *,
    query_runner: Callable | None,
    grounded_available: bool,
    social_available: bool,
    lookback_days: int = 30,
    max_queries_per_theme: int = 3,
) -> dict:
    """Run theme-driven company searches and annotate returned evidence."""
    queries = build_company_discovery_queries(
        theme_signals,
        grounded_available=grounded_available,
        social_available=social_available,
        lookback_days=lookback_days,
        max_queries_per_theme=max_queries_per_theme,
    )
    result = {"queries": queries, "items": [], "warnings": [], "errors": []}
    if not query_runner or not queries:
        if queries and not query_runner:
            result["warnings"].append("Theme company discovery skipped because last30days query runner is unavailable.")
        return result

    items = []
    for query in queries:
        try:
            payload = query_runner(
                query["topic"],
                sources=query["sources"],
                lookback_days=query["lookback_days"],
                auto_resolve=True,
                store=True,
                web_backend=query.get("web_backend"),
            )
        except Exception as exc:  # pragma: no cover - defensive boundary around live tools
            result["errors"].append(f"{query['kind']}: {exc}")
            continue

        for warning in payload.get("warnings", []):
            if warning not in result["warnings"]:
                result["warnings"].append(warning)
        if payload.get("error"):
            result["errors"].append(payload["error"])

        for item in payload.get("items", []):
            enriched = dict(item)
            enriched.setdefault("query_kind", query["kind"])
            enriched.setdefault("query_topic", query["topic"])
            enriched.setdefault("query_theme", query["theme"])
            enriched.setdefault("market_sector", query["market_sector"])
            enriched.setdefault("candidate_eligible", True)
            enriched.setdefault("discovery_lane", "theme_company_discovery")
            items.append(enriched)

    result["items"] = _dedupe_items(items)
    return result


def _sources(*, grounded_available: bool, social_available: bool) -> str:
    sources = ["grounding", "hackernews"] if grounded_available else ["hackernews"]
    if social_available:
        sources.append("youtube")
    return ",".join(dict.fromkeys(sources))


def _dedupe_items(items: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for item in items:
        key = (item.get("domain") or item.get("url") or item.get("title") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
