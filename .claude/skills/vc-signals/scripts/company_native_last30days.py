#!/usr/bin/env python3
"""last30days-native source audit helpers for company-native lanes."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse


NATIVE_LANES = ("launch_hn", "yc_company")
IDENTITY_FIELDS = (
    "url",
    "hn_url",
    "outbound_url",
    "resolved_url",
    "story_url",
    "domain",
    "homepage",
    "website",
    "author",
    "engagement",
    "founders",
    "batch",
    "description",
)
BLOCKED_COMPANY_DOMAINS = {
    "github.com",
    "news.ycombinator.com",
    "ycombinator.com",
    "hn.algolia.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "medium.com",
    "substack.com",
    "youtube.com",
    "youtu.be",
}
PHASE5_4_BRAVE_BASELINE = {
    "verified_domains": 7,
    "maturity_confirmed_early_stage": 0,
    "research_worthy_unknown": 3,
    "category_or_monitor": 4,
    "assign_owner_rows": 0,
}


@dataclass
class Last30daysNativeQuery:
    id: str
    lane: str
    topic: str
    sources: str
    movement: str
    market_sector: str
    retrieval_engine: str = "last30days"
    discovery_lane: str = "last30days_native_source_audit"
    lookback_days: int = 30
    web_backend: str = "auto"
    origin_row_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def build_last30days_native_queries(
    movements: list[dict],
    *,
    lanes: tuple[str, ...] = NATIVE_LANES,
    lookback_days: int = 30,
) -> list[dict]:
    selected_lanes = [lane for lane in lanes if lane in NATIVE_LANES]
    queries: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for row in movements:
        movement = (row.get("movement") or "").strip()
        if not movement:
            continue
        market_sector = row.get("market_sector") or ""
        origin_ids = list(row.get("origin_row_ids") or [])
        specs: list[tuple[str, str, str]] = []
        if "launch_hn" in selected_lanes:
            specs.extend(
                [
                    ("launch_hn", f"Show HN {movement}", "hackernews"),
                    ("launch_hn", f"Launch HN {movement}", "hackernews"),
                ]
            )
        if "yc_company" in selected_lanes:
            specs.append(("yc_company", f'site:ycombinator.com/companies "{movement}" startup', "grounding"))

        for lane, topic, sources in specs:
            dedupe_key = (lane, topic.lower(), sources)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            query_id = f"phase6a:{lane}:{len(queries) + 1}"
            queries.append(
                Last30daysNativeQuery(
                    id=query_id,
                    lane=lane,
                    topic=topic,
                    sources=sources,
                    movement=movement,
                    market_sector=market_sector,
                    lookback_days=lookback_days,
                    origin_row_ids=origin_ids,
                ).to_dict()
            )
    return queries


def summarize_last30days_native_audit(query_payloads: list[tuple[dict, dict]]) -> dict:
    rows = []
    total_items = 0
    total_identity_fields: Counter[str] = Counter()
    total_field_presence: Counter[str] = Counter()

    for query, payload in query_payloads:
        items = payload.get("items", []) or []
        total_items += len(items)
        field_presence: Counter[str] = Counter()
        identity_presence: Counter[str] = Counter()
        for item in items:
            raw_fields = set(item.get("_raw_fields_present") or item.keys())
            for field in raw_fields:
                field_presence[field] += 1
                total_field_presence[field] += 1
            for field in IDENTITY_FIELDS:
                if item.get(field) not in ("", None, [], {}):
                    identity_presence[field] += 1
                    total_identity_fields[field] += 1
        rows.append(
            {
                "query_id": query.get("id", ""),
                "lane": query.get("lane", ""),
                "topic": query.get("topic", ""),
                "sources": query.get("sources", ""),
                "items_seen": len(items),
                "field_presence": dict(sorted(field_presence.items())),
                "identity_useful_fields_present": dict(sorted(identity_presence.items())),
                "warnings": payload.get("warnings", []),
                "errors_by_source": payload.get("errors_by_source", {}),
            }
        )

    return {
        "summary": {
            "queries": len(query_payloads),
            "items_seen": total_items,
            "field_presence": dict(sorted(total_field_presence.items())),
            "identity_useful_fields_present": dict(sorted(total_identity_fields.items())),
        },
        "rows": rows,
    }


def normalize_last30days_native_item(item: dict, query: dict) -> dict:
    lane = query.get("lane", "")
    if lane == "launch_hn":
        return _normalize_hn_native_item(item, query)
    if lane == "yc_company":
        return _normalize_yc_native_item(item, query)
    return _rejected_native_item(item, query, ["unsupported_native_lane"])


def _normalize_hn_native_item(item: dict, query: dict) -> dict:
    title = item.get("title") or ""
    outbound_url = item.get("outbound_url") or item.get("resolved_url") or item.get("story_url") or ""
    item_url = item.get("url") or ""
    hn_url = item.get("hn_url") or item.get("source_url") or ""
    if not outbound_url and "news.ycombinator.com" not in item_url:
        outbound_url = item_url
    if not hn_url and "news.ycombinator.com" in item_url:
        hn_url = item_url
    domain = _domain_from_url(outbound_url) or _normalize_domain(item.get("domain", ""))
    name = _name_from_hn_title(title)
    base = _base_native_item(
        item,
        query,
        name=name,
        source_url=hn_url or item_url,
        official_url=outbound_url,
        domain=domain,
    )

    if not title.lower().startswith(("show hn:", "launch hn:")):
        return {**base, "kind": "rejected", "verification_status": "rejected", "missing_evidence": ["not_launch_hn"]}
    if not outbound_url or not domain:
        return {
            **base,
            "kind": "rejected",
            "verification_status": "rejected",
            "missing_evidence": ["hn_outbound_url_missing"],
        }
    if _is_blocked_company_domain(domain):
        reason = "hn_outbound_github_project_only" if domain == "github.com" else "hn_outbound_not_company_domain"
        return {
            **base,
            "kind": "project_only",
            "domain": "",
            "official_url": "",
            "verification_status": "rejected",
            "missing_evidence": [reason],
        }
    return {
        **base,
        "kind": "company_candidate",
        "verification_status": "accepted",
        "verification_basis": ["hn_launch_outbound_url"],
    }


def _normalize_yc_native_item(item: dict, query: dict) -> dict:
    source_url = item.get("url") or item.get("source_url") or ""
    website = item.get("website") or item.get("homepage") or item.get("outbound_url") or ""
    domain = _domain_from_url(website) or _normalize_domain(item.get("domain", ""))
    name = item.get("company_name") or _name_from_yc_title(item.get("title") or "")
    base = _base_native_item(item, query, name=name, source_url=source_url, official_url=website, domain=domain)

    if "ycombinator.com/companies" not in source_url:
        return {
            **base,
            "kind": "rejected",
            "verification_status": "rejected",
            "missing_evidence": ["not_yc_company_page"],
        }
    if not website or not domain or _is_blocked_company_domain(domain):
        return {
            **base,
            "kind": "needs_detail_enrichment",
            "domain": "",
            "verification_status": "rejected",
            "missing_evidence": ["yc_official_website_missing"],
        }
    return {
        **base,
        "kind": "company_candidate",
        "verification_status": "accepted",
        "verification_basis": ["yc_company_official_website"],
    }


def _base_native_item(item: dict, query: dict, *, name: str, source_url: str, official_url: str, domain: str) -> dict:
    engagement = item.get("engagement") or {}
    return {
        "name": name,
        "lane": query.get("lane", ""),
        "movement": query.get("movement", ""),
        "market_sector": query.get("market_sector", ""),
        "source_url": source_url,
        "official_url": official_url,
        "domain": _normalize_domain(domain),
        "title": item.get("title", ""),
        "snippet": item.get("snippet") or item.get("description") or "",
        "author": item.get("author", ""),
        "points": engagement.get("points", 0),
        "comments": engagement.get("comments", 0),
        "founders": item.get("founders") or [],
        "batch": item.get("batch", ""),
        "query_id": query.get("id", ""),
        "query_topic": query.get("topic", ""),
        "verification_basis": [],
        "missing_evidence": [],
        "discovery_lane": "last30days_native_source_audit",
    }


def _rejected_native_item(item: dict, query: dict, missing: list[str]) -> dict:
    return {
        "name": item.get("title", ""),
        "lane": query.get("lane", ""),
        "movement": query.get("movement", ""),
        "market_sector": query.get("market_sector", ""),
        "source_url": item.get("url", ""),
        "domain": "",
        "kind": "rejected",
        "verification_status": "rejected",
        "missing_evidence": missing,
        "discovery_lane": "last30days_native_source_audit",
    }


def build_native_audit_metrics(leads: list[dict], *, items_seen: int) -> dict:
    company_leads = [lead for lead in leads if lead.get("kind") == "company_candidate" and lead.get("domain")]
    domains = {lead["domain"] for lead in company_leads}
    rows_by_lane = Counter(lead.get("lane", "unknown") for lead in leads)
    candidate_domains_by_lane: dict[str, set[str]] = {}
    rejected_reasons = Counter(
        reason
        for lead in leads
        if lead.get("kind") in {"rejected", "needs_detail_enrichment", "project_only"}
        for reason in lead.get("missing_evidence", [])
    )
    for lead in company_leads:
        candidate_domains_by_lane.setdefault(lead.get("lane", "unknown"), set()).add(lead["domain"])

    return {
        "items_seen": items_seen,
        "company_candidates": len(company_leads),
        "unique_candidate_domains": len(domains),
        "candidate_domain_list": sorted(domains),
        "project_only_leads": len([lead for lead in leads if lead.get("kind") == "project_only"]),
        "needs_detail_enrichment": len([lead for lead in leads if lead.get("kind") == "needs_detail_enrichment"]),
        "rejected_leads": len([lead for lead in leads if lead.get("kind") == "rejected"]),
        "rejected_reasons": dict(sorted(rejected_reasons.items())),
        "candidate_domains_per_100_items": round((len(domains) / items_seen) * 100, 2) if items_seen else 0.0,
        "rows_by_lane": dict(sorted(rows_by_lane.items())),
        "candidate_domains_by_lane": {
            lane: sorted(values) for lane, values in sorted(candidate_domains_by_lane.items())
        },
        "baseline_context": {
            "phase5_4_brave": PHASE5_4_BRAVE_BASELINE,
            "comparison_note": "Phase 6A audit metrics are not directly comparable to Phase 5.4 quality metrics until Phase 6B gates run.",
        },
    }


def run_last30days_native_audit(
    queries: list[dict],
    *,
    run_query_fn,
    output_dir: Path | str | None = None,
    timeout_seconds: int = 120,
) -> dict:
    query_payloads = []
    normalized_leads = []
    raw_dir = Path(output_dir) / "raw-last30days" if output_dir else None
    if raw_dir:
        raw_dir.mkdir(parents=True, exist_ok=True)

    for query in queries:
        payload = run_query_fn(
            topic=query["topic"],
            sources=query["sources"],
            lookback_days=query.get("lookback_days", 30),
            emit="json",
            auto_resolve=True,
            store=True,
            web_backend=query.get("web_backend") or "auto",
            plan=_last30days_external_plan(query),
            timeout_seconds=timeout_seconds,
        )
        query_payloads.append((query, payload))
        if raw_dir:
            raw_dir.joinpath(f"{query['id'].replace(':', '-')}.json").write_text(json.dumps(payload, indent=2))
        for item in payload.get("items", []) or []:
            normalized_leads.append(normalize_last30days_native_item(item, query))

    audit = summarize_last30days_native_audit(query_payloads)
    items_seen = sum(len(payload.get("items", []) or []) for _query, payload in query_payloads)
    return {
        "audit": audit,
        "normalized_leads": {
            "summary": build_native_audit_metrics(normalized_leads, items_seen=items_seen),
            "company_candidates": [lead for lead in normalized_leads if lead.get("kind") == "company_candidate"],
            "project_only_leads": [lead for lead in normalized_leads if lead.get("kind") == "project_only"],
            "needs_detail_enrichment": [lead for lead in normalized_leads if lead.get("kind") == "needs_detail_enrichment"],
            "rejected_leads": [lead for lead in normalized_leads if lead.get("kind") == "rejected"],
        },
    }


def write_last30days_native_artifacts(payload: dict, output_dir: Path | str) -> list[Path]:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    audit_path = path / "company-native-source-audit.json"
    normalized_path = path / "company-native-normalized-leads.json"
    md_path = path / "company-native-source-audit.md"
    audit_path.write_text(json.dumps(payload.get("audit", {}), indent=2))
    normalized_path.write_text(json.dumps(payload.get("normalized_leads", {}), indent=2))
    md_path.write_text(_native_audit_markdown(payload))
    return [audit_path, normalized_path, md_path]


def build_query_shape_debug_queries(movements: list[str] | None = None, *, lookback_days: int = 30) -> list[dict]:
    movement_terms = [(movement or "").strip() for movement in movements or [] if (movement or "").strip()]
    hn_topics = [
        "Show HN",
        "Launch HN",
        "Show HN AI",
        "Show HN agent",
        "Show HN security",
    ]
    yc_topics = [
        "site:ycombinator.com/companies AI",
        "site:ycombinator.com/companies security",
        "site:ycombinator.com/companies devtools",
        'site:ycombinator.com/companies "AI agent"',
    ]
    for movement in movement_terms:
        hn_topics.extend(
            [
                f"Show HN {movement}",
                f"Show HN {movement} startup",
                f"Launch HN {movement}",
            ]
        )
        yc_topics.extend(
            [
                f"site:ycombinator.com/companies {movement}",
                f'site:ycombinator.com/companies "{movement}"',
            ]
        )

    queries: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for topic in hn_topics:
        dedupe_key = ("hackernews", topic.lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        queries.append(
            {
                "id": f"shape:hn:{len([q for q in queries if q['sources'] == 'hackernews']) + 1}",
                "lane": "hn_shape",
                "topic": topic,
                "sources": "hackernews",
                "lookback_days": lookback_days,
                "retrieval_engine": "last30days",
            }
        )
    for topic in yc_topics:
        dedupe_key = ("grounding", topic.lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        queries.append(
            {
                "id": f"shape:yc:{len([q for q in queries if q['sources'] == 'grounding']) + 1}",
                "lane": "yc_shape",
                "topic": topic,
                "sources": "grounding",
                "lookback_days": lookback_days,
                "retrieval_engine": "last30days",
                "web_backend": "auto",
            }
        )
    return queries


def run_query_shape_debug(
    queries: list[dict],
    *,
    run_query_fn,
    output_dir: Path | str | None = None,
    timeout_seconds: int = 120,
    max_top_items: int = 5,
) -> dict:
    rows = []
    raw_dir = Path(output_dir) / "raw-last30days-query-shapes" if output_dir else None
    if raw_dir:
        raw_dir.mkdir(parents=True, exist_ok=True)

    for query in queries:
        payload = run_query_fn(
            topic=query["topic"],
            sources=query["sources"],
            lookback_days=query.get("lookback_days", 30),
            emit="json",
            auto_resolve=True,
            store=True,
            web_backend=query.get("web_backend") or "auto",
            plan=_last30days_external_plan(query),
            timeout_seconds=timeout_seconds,
        )
        if raw_dir:
            raw_dir.joinpath(f"{query['id'].replace(':', '-')}.json").write_text(json.dumps(payload, indent=2))
        rows.append(_query_shape_debug_row(query, payload, max_top_items=max_top_items))

    return {
        "summary": {
            "queries": len(rows),
            "items_seen": sum(row["items_returned"] for row in rows),
            "queries_with_items": sum(1 for row in rows if row["items_returned"] > 0),
            "hn_queries": sum(1 for row in rows if row["sources"] == "hackernews"),
            "hn_items": sum(row["items_returned"] for row in rows if row["sources"] == "hackernews"),
            "yc_queries": sum(1 for row in rows if row["sources"] == "grounding"),
            "yc_items": sum(row["items_returned"] for row in rows if row["sources"] == "grounding"),
        },
        "rows": rows,
    }


def write_query_shape_debug_artifact(payload: dict, output_dir: Path | str) -> Path:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    artifact_path = path / "last30days-query-shape-debug.json"
    artifact_path.write_text(json.dumps(payload, indent=2))
    return artifact_path


def load_movements_from_weekly_run(weekly_run_dir: Path | str) -> list[dict]:
    path = Path(weekly_run_dir) / "weekly-focus.json"
    payload = json.loads(path.read_text())
    movements: list[dict] = []
    seen: set[str] = set()
    for row in payload.get("market_movements", []) or []:
        movement = row.get("movement") or row.get("name") or ""
        if movement and movement not in seen:
            seen.add(movement)
            movements.append(
                {
                    "movement": movement,
                    "market_sector": row.get("market_sector", ""),
                    "origin_row_ids": row.get("origin_row_ids", []),
                }
            )
    for row in payload.get("research_deeper", []) or []:
        movement = row.get("market_movement") or ""
        if movement and movement not in seen:
            seen.add(movement)
            movements.append(
                {"movement": movement, "market_sector": row.get("market_sector", ""), "origin_row_ids": [row.get("id", "")]}
            )
    return movements


def _native_audit_markdown(payload: dict) -> str:
    summary = payload.get("normalized_leads", {}).get("summary", {})
    baseline = summary.get("baseline_context", {})
    lines = [
        "# last30days-Native Source Audit",
        "",
        "Phase 6A audit only. Retrieval uses last30days; vc-signals normalizes source-native items but does not run maturity, owner-readiness, Attio, or action gates in this phase.",
        "",
        f"- Items seen: {summary.get('items_seen', 0)}",
        f"- Company candidates: {summary.get('company_candidates', 0)}",
        f"- Unique candidate domains: {summary.get('unique_candidate_domains', 0)}",
        f"- Project-only leads: {summary.get('project_only_leads', 0)}",
        f"- Needs detail enrichment: {summary.get('needs_detail_enrichment', 0)}",
        f"- Rejected leads: {summary.get('rejected_leads', 0)}",
        f"- Candidate domains per 100 items: {summary.get('candidate_domains_per_100_items', 0)}",
        "",
        "## Baseline Context",
        "",
        baseline.get(
            "comparison_note",
            "Phase 6A audit metrics are not directly comparable to Phase 5.4 quality metrics until Phase 6B gates run.",
        ),
    ]
    return "\n".join(lines) + "\n"


def _last30days_external_plan(query: dict) -> str:
    """Force last30days to execute the exact source-specific audit query."""
    source = query.get("sources") or "grounding"
    topic = query.get("topic") or ""
    is_evergreen_identity = query.get("lane") in {"yc_company", "yc_shape"} or "ycombinator.com/companies" in topic.lower()
    plan = {
        "intent": "concept" if is_evergreen_identity else "product",
        "freshness_mode": "evergreen_ok" if is_evergreen_identity else "balanced_recent",
        "cluster_mode": "none",
        "subqueries": [
            {
                "label": query.get("id") or "source_native",
                "search_query": topic,
                "ranking_query": f"Find source-native launch or company evidence for {query.get('movement') or topic}.",
                "sources": [source],
                "weight": 1.0,
            }
        ],
        "source_weights": {source: 1.0},
        "notes": ["vc-signals Phase 6A source-native audit plan"],
    }
    return json.dumps(plan)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weekly-run-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--lanes", default="launch_hn,yc_company")
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--query-shape-debug", action="store_true")
    return parser.parse_args()


def main() -> None:
    from last30days_adapter import run_query as last30days_run_query

    args = _parse_args()
    movements = load_movements_from_weekly_run(args.weekly_run_dir)
    if args.query_shape_debug:
        queries = build_query_shape_debug_queries(
            [row["movement"] for row in movements],
            lookback_days=args.lookback_days,
        )
        payload = run_query_shape_debug(
            queries,
            run_query_fn=last30days_run_query,
            output_dir=args.output_dir,
            timeout_seconds=args.timeout_seconds,
        )
        write_query_shape_debug_artifact(payload, args.output_dir)
        print(json.dumps(payload["summary"], indent=2))
        return

    queries = build_last30days_native_queries(
        movements,
        lanes=tuple(item.strip() for item in args.lanes.split(",") if item.strip()),
        lookback_days=args.lookback_days,
    )
    payload = run_last30days_native_audit(
        queries,
        run_query_fn=last30days_run_query,
        output_dir=args.output_dir,
        timeout_seconds=args.timeout_seconds,
    )
    write_last30days_native_artifacts(payload, args.output_dir)
    print(json.dumps(payload["normalized_leads"]["summary"], indent=2))


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    return _normalize_domain(parsed.netloc)


def _normalize_domain(value: str) -> str:
    raw = (value or "").strip()
    if raw.startswith(("http://", "https://")):
        raw = urlparse(raw).netloc
    raw = raw.split("/", 1)[0].lower().strip("/")
    return raw[4:] if raw.startswith("www.") else raw


def _is_blocked_company_domain(domain: str) -> bool:
    normalized = _normalize_domain(domain)
    return any(normalized == blocked or normalized.endswith(f".{blocked}") for blocked in BLOCKED_COMPANY_DOMAINS)


def _name_from_hn_title(title: str) -> str:
    cleaned = (title or "").strip()
    for prefix in ("Show HN:", "Launch HN:"):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix) :].strip()
    for separator in (" - ", " – ", " — ", ": "):
        if separator in cleaned:
            cleaned = cleaned.split(separator, 1)[0].strip()
            break
    return cleaned[:80]


def _name_from_yc_title(title: str) -> str:
    return (title or "").split("|", 1)[0].strip()[:80]


def _query_shape_debug_row(query: dict, payload: dict, *, max_top_items: int) -> dict:
    items = payload.get("items", []) or []
    field_coverage: Counter[str] = Counter()
    identity_coverage: Counter[str] = Counter()
    for item in items:
        raw_fields = set(item.get("_raw_fields_present") or item.keys())
        for field in raw_fields:
            field_coverage[field] += 1
        for field in IDENTITY_FIELDS:
            if item.get(field) not in ("", None, [], {}):
                identity_coverage[field] += 1
    return {
        "id": query.get("id", ""),
        "lane": query.get("lane", ""),
        "sources": query.get("sources", ""),
        "query_text": query.get("topic", ""),
        "lookback_days": query.get("lookback_days", 30),
        "items_returned": len(items),
        "warnings": payload.get("warnings", []),
        "errors_by_source": payload.get("errors_by_source", {}),
        "error": payload.get("error"),
        "field_coverage": dict(sorted(field_coverage.items())),
        "identity_field_coverage": dict(sorted(identity_coverage.items())),
        "top_items": [_top_item_summary(item) for item in items[:max_top_items]],
    }


def _top_item_summary(item: dict) -> dict:
    return {
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "hn_url": item.get("hn_url", ""),
        "outbound_url": item.get("outbound_url") or item.get("resolved_url") or item.get("story_url") or "",
        "domain": item.get("domain", ""),
        "author": item.get("author", ""),
        "engagement": item.get("engagement", {}),
        "website": item.get("website") or item.get("homepage") or "",
        "founders": item.get("founders") or [],
        "batch": item.get("batch", ""),
        "description": item.get("description") or item.get("snippet", ""),
    }


if __name__ == "__main__":
    main()
