from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from discovery_search_providers import load_provider_env_files, run_provider_query
from radar_company_discovery import (
    _apply_maturity_to_lead,
    _classify_maturity_from_items,
    classify_discovery_source,
    verify_discovery_item,
)


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_EVAL_SET_PATH = SKILL_DIR / "config" / "lead_discovery_eval_set.json"
DEFAULT_OUTPUT_DIR = SKILL_DIR / "data" / "discovery-yield-eval"

DISCOVERY_QUERY_FAMILIES = (
    "official_company_page",
    "yc_company_pages",
    "seed_funding",
    "launch_stealth",
    "founder_company_pages",
    "movement_startup",
    "movement_platform",
)
ROUTE_AGGRESSIVENESS = {
    "monitor_only": 0,
    "category_context": 1,
    "research_deeper": 2,
    "sourcing_candidate": 3,
    "assign_owner": 4,
}
EVAL_MODE_DEFAULTS = {
    "smoke": 40,
    "standard": 120,
    "full": 400,
}


@dataclass
class LeadDiscoveryEvalTarget:
    name: str
    domain: str
    expected_movement: str
    movement_aliases: list[str]
    market_sector: str
    maturity_expectation: str
    expected_route: str
    aliases: list[str] = field(default_factory=list)
    last_verified_at: str = ""
    verification_notes: str = ""

    @classmethod
    def from_dict(cls, payload: dict) -> "LeadDiscoveryEvalTarget":
        return cls(
            name=payload.get("name", ""),
            aliases=list(payload.get("aliases") or []),
            domain=payload.get("domain", ""),
            expected_movement=payload.get("expected_movement", ""),
            movement_aliases=list(payload.get("movement_aliases") or []),
            market_sector=payload.get("market_sector", ""),
            maturity_expectation=payload.get("maturity_expectation", ""),
            expected_route=payload.get("expected_route", ""),
            last_verified_at=payload.get("last_verified_at", ""),
            verification_notes=payload.get("verification_notes", ""),
        )

    def to_dict(self) -> dict:
        return asdict(self)


def load_eval_targets(path: Path | str = DEFAULT_EVAL_SET_PATH) -> list[LeadDiscoveryEvalTarget]:
    payload = json.loads(Path(path).read_text())
    targets = [LeadDiscoveryEvalTarget.from_dict(row) for row in payload.get("targets", payload)]
    validate_eval_targets(targets)
    return targets


def validate_eval_targets(targets: list[LeadDiscoveryEvalTarget]) -> None:
    for target in targets:
        if not target.name:
            raise ValueError("Eval target missing name")
        if not target.domain:
            raise ValueError(f"Eval target {target.name} missing domain")
        if not target.expected_movement:
            raise ValueError(f"Eval target {target.name} missing expected_movement")
        if not target.last_verified_at:
            raise ValueError(f"Eval target {target.name} missing last_verified_at")
        _validate_no_target_leakage(target)


def build_movement_only_queries(
    targets: list[LeadDiscoveryEvalTarget],
    *,
    max_aliases_per_target: int = 3,
) -> list[dict]:
    validate_eval_targets(targets)
    seen_topics = set()
    queries = []
    for target in targets:
        movement_terms = [target.expected_movement, *target.movement_aliases[:max_aliases_per_target]]
        for movement_term in movement_terms:
            for family in DISCOVERY_QUERY_FAMILIES:
                topic = _query_topic(family, movement_term, target.market_sector)
                normalized_topic = _normalize_topic(topic)
                if normalized_topic in seen_topics:
                    continue
                seen_topics.add(normalized_topic)
                query_id = f"eval:{family}:{len(queries) + 1}"
                queries.append(
                    {
                        "query_id": query_id,
                        "id": query_id,
                        "query_family": family,
                        "movement": target.expected_movement,
                        "movement_term": movement_term,
                        "market_sector": target.market_sector,
                        "topic": topic,
                        "normalized_topic": normalized_topic,
                        "target_name": "",
                        "target_domain": "",
                        "source_reason": "phase5_discovery_yield_eval",
                    }
                )
    return queries


def provider_bakeoff(
    queries: list[dict],
    *,
    providers: list[str],
    provider_runner=run_provider_query,
    max_queries_per_provider: int = 80,
    max_results_per_query: int = 10,
    max_total_cost_usd: float | None = None,
    max_runtime_seconds: int | None = None,
    cache_dir: Path | str | None = None,
) -> dict:
    started = time.monotonic()
    provider_runs = []
    total_cost = 0.0
    partial = False
    budget_exceeded = False

    for provider in [item for item in providers if item]:
        for index, query in enumerate(queries):
            if index >= max_queries_per_provider:
                partial = True
                break
            if max_runtime_seconds is not None and time.monotonic() - started >= max_runtime_seconds:
                partial = True
                budget_exceeded = True
                break
            if max_total_cost_usd is not None and total_cost >= max_total_cost_usd:
                partial = True
                budget_exceeded = True
                break
            run = provider_runner(
                provider,
                query,
                max_results=max_results_per_query,
                cache_dir=cache_dir,
            )
            run.setdefault("provider", provider)
            run.setdefault("query_id", query.get("query_id", ""))
            run.setdefault("query_family", query.get("query_family", ""))
            run.setdefault("movement", query.get("movement", ""))
            run.setdefault("market_sector", query.get("market_sector", ""))
            run.setdefault("query", query.get("topic", ""))
            provider_runs.append(run)
            total_cost += float(run.get("cost_usd") or 0)
        if budget_exceeded:
            break

    skipped = sum(1 for run in provider_runs if run.get("skipped"))
    completed = len(provider_runs) - skipped
    return {
        "provider_runs": provider_runs,
        "summary": {
            "providers": providers,
            "queries_available": len(queries),
            "runs": len(provider_runs),
            "completed_runs": completed,
            "skipped_runs": skipped,
            "partial_eval": partial,
            "budget_exceeded": budget_exceeded,
            "cost_usd": round(total_cost, 4),
            "duration_seconds": round(time.monotonic() - started, 3),
        },
    }


def score_provider_items_against_targets(
    provider_runs: list[dict],
    targets: list[LeadDiscoveryEvalTarget],
) -> dict:
    validate_eval_targets(targets)
    target_domains = {_normalize_domain(target.domain): target for target in targets}
    accepted = []
    rejected = []
    target_results = [_empty_target_result(target) for target in targets]
    total_items = 0
    publisher_or_content_junk = 0

    for run in provider_runs:
        if run.get("skipped"):
            continue
        query = _query_from_run(run)
        for item in run.get("items") or []:
            total_items += 1
            source_type = classify_discovery_source(item)
            if source_type in {
                "publisher_article",
                "content_platform",
                "directory_page",
                "listicle_or_seo",
                "government_or_academic",
            }:
                publisher_or_content_junk += 1
            lead = verify_discovery_item(item, query)
            if lead.verification_status == "accepted":
                maturity = _classify_maturity_from_items(
                    [item],
                    company_name=lead.display_name or lead.canonical_name or lead.name,
                    domain=lead.domain,
                )
                lead = _apply_maturity_to_lead(lead, maturity)
                accepted.append(_lead_eval_row(lead, run, evaluation_incomplete=False))
                _mark_target_if_matched(target_results, target_domains, lead, run, evaluation_incomplete=False)
            else:
                rejected.append(lead.to_dict())

    metrics = _score_metrics(provider_runs, accepted, target_results, total_items, publisher_or_content_junk, targets)
    return {
        "metrics": metrics,
        "accepted_leads": accepted,
        "rejected_leads": rejected,
        "target_results": target_results,
    }


def write_discovery_yield_artifacts(payload: dict, output_dir: Path | str) -> list[Path]:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    written = []
    files = {
        "lead-discovery-eval.json": {
            "eval_targets": payload.get("eval_targets", []),
            "queries": payload.get("queries", []),
            "score": payload.get("score", {}),
        },
        "provider-bakeoff.json": payload.get("bakeoff", {}),
        "query-family-bakeoff.json": _query_family_summary(payload.get("bakeoff", {}), payload.get("score", {})),
    }
    for name, body in files.items():
        target = path / name
        target.write_text(json.dumps(body, indent=2))
        written.append(target)
    summary = path / "discovery-yield-summary.md"
    summary.write_text(_summary_markdown(payload))
    written.append(summary)
    return written


def run_eval(args: argparse.Namespace) -> dict:
    loaded_env = load_provider_env_files()
    targets = load_eval_targets(args.eval_set)
    queries = build_movement_only_queries(targets, max_aliases_per_target=args.max_aliases_per_target)
    max_queries = args.max_queries_per_provider
    if max_queries is None:
        max_queries = EVAL_MODE_DEFAULTS[args.eval_mode]
    providers = [provider.strip() for provider in (args.providers or "").split(",") if provider.strip()]
    bakeoff = provider_bakeoff(
        queries,
        providers=providers,
        max_queries_per_provider=max_queries,
        max_results_per_query=args.max_results_per_query,
        max_total_cost_usd=args.max_total_cost_usd,
        max_runtime_seconds=args.max_runtime_seconds,
        cache_dir=args.cache_dir,
    )
    score = score_provider_items_against_targets(bakeoff["provider_runs"], targets)
    payload = {
        "eval_targets": [target.to_dict() for target in targets],
        "queries": queries,
        "bakeoff": bakeoff,
        "score": score,
        "provider_env_loaded": sorted(loaded_env),
    }
    write_discovery_yield_artifacts(payload, args.output_dir)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 5 discovery-yield provider/query bakeoff.")
    parser.add_argument("--eval-set", default=str(DEFAULT_EVAL_SET_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--cache-dir", default=str(DEFAULT_OUTPUT_DIR / "provider-cache"))
    parser.add_argument("--providers", default="brave")
    parser.add_argument("--eval-mode", choices=sorted(EVAL_MODE_DEFAULTS), default="smoke")
    parser.add_argument("--max-queries-per-provider", type=int, default=None)
    parser.add_argument("--max-results-per-query", type=int, default=10)
    parser.add_argument("--max-total-cost-usd", type=float, default=None)
    parser.add_argument("--max-runtime-seconds", type=int, default=None)
    parser.add_argument("--max-aliases-per-target", type=int, default=3)
    parser.add_argument("--weekly-preview-path", default="")
    args = parser.parse_args(argv)
    run_eval(args)
    return 0


def _query_topic(family: str, movement: str, market_sector: str) -> str:
    if family == "official_company_page":
        return f"{movement} startup platform official {market_sector}".strip()
    if family == "yc_company_pages":
        return f"site:ycombinator.com/companies {movement} startup"
    if family == "seed_funding":
        return f"{movement} seed Series A startup raises"
    if family == "launch_stealth":
        return f"{movement} launches emerged from stealth startup"
    if family == "founder_company_pages":
        return f"{movement} founder company startup official"
    if family == "movement_startup":
        return f"{movement} startup company founder launch"
    if family == "movement_platform":
        return f"{movement} platform company official"
    raise ValueError(f"Unsupported query family: {family}")


def _validate_no_target_leakage(target: LeadDiscoveryEvalTarget) -> None:
    forbidden = [_normalize_text(target.name), _normalize_text(target.domain.split(".", 1)[0])]
    forbidden.extend(_normalize_text(alias) for alias in target.aliases)
    forbidden = [item for item in forbidden if item]
    for alias in target.movement_aliases:
        normalized_alias = _normalize_text(alias)
        for term in forbidden:
            if term and term in normalized_alias:
                raise ValueError(f"movement_aliases for {target.name} leak target name/domain")


def _normalize_topic(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").lower().replace('"', "")).strip()


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _normalize_domain(value: str) -> str:
    raw = (value or "").lower().strip().replace("https://", "").replace("http://", "")
    raw = raw.split("/", 1)[0]
    return raw[4:] if raw.startswith("www.") else raw


def _query_from_run(run: dict) -> dict:
    movement = run.get("movement", "")
    return {
        "id": run.get("query_id", ""),
        "topic": run.get("query", ""),
        "movement": movement,
        "market_sector": run.get("market_sector", ""),
        "required_terms": _movement_terms(movement),
    }


def _movement_terms(movement: str) -> list[str]:
    return [term for term in re.split(r"[^a-z0-9]+", (movement or "").lower()) if len(term) >= 3]


def _lead_eval_row(lead, run: dict, *, evaluation_incomplete: bool) -> dict:
    row = lead.to_dict()
    row.update(
        {
            "provider": run.get("provider", ""),
            "query_family": run.get("query_family", ""),
            "evaluation_incomplete": evaluation_incomplete,
            "owner_ready": lead.recommended_owner_action == "Assign owner",
        }
    )
    return row


def _empty_target_result(target: LeadDiscoveryEvalTarget) -> dict:
    return {
        "target_name": target.name,
        "target_domain": _normalize_domain(target.domain),
        "expected_route": target.expected_route,
        "expected_maturity": target.maturity_expectation,
        "found": False,
        "actual_route": "",
        "actual_maturity": "",
        "provider": "",
        "query_family": "",
        "over_promoted": False,
        "evaluation_incomplete": False,
    }


def _mark_target_if_matched(
    target_results: list[dict],
    target_domains: dict,
    lead,
    run: dict,
    *,
    evaluation_incomplete: bool,
) -> None:
    target = target_domains.get(_normalize_domain(lead.domain))
    if not target:
        return
    for row in target_results:
        if row["target_domain"] != _normalize_domain(target.domain):
            continue
        row["found"] = True
        row["actual_route"] = lead.lead_route
        row["actual_maturity"] = lead.maturity_status
        row["provider"] = run.get("provider", "")
        row["query_family"] = run.get("query_family", "")
        row["evaluation_incomplete"] = evaluation_incomplete
        row["over_promoted"] = _route_rank(lead.lead_route) > _route_rank(target.expected_route)
        return


def _score_metrics(
    provider_runs: list[dict],
    accepted: list[dict],
    target_results: list[dict],
    total_items: int,
    publisher_or_content_junk: int,
    targets: list[LeadDiscoveryEvalTarget],
) -> dict:
    completed_queries = sum(1 for run in provider_runs if not run.get("skipped"))
    verified_domains = {_normalize_domain(row.get("domain", "")) for row in accepted if row.get("domain")}
    target_domains = {_normalize_domain(target.domain) for target in targets}
    early_stage_rows = [
        row
        for row in accepted
        if row.get("domain")
        and not row.get("evaluation_incomplete")
        and row.get("lead_route") in {"sourcing_candidate", "research_deeper"}
        and not row.get("likely_too_late")
    ]
    early_stage_domains = {_normalize_domain(row.get("domain", "")) for row in early_stage_rows if row.get("domain")}
    target_matches = [row for row in target_results if row["found"]]
    correct_target_matches = [row for row in target_matches if not row["over_promoted"] and not row["evaluation_incomplete"]]
    net_new_domains = {
        _normalize_domain(row.get("domain", ""))
        for row in early_stage_rows
        if _normalize_domain(row.get("domain", "")) not in target_domains
    }
    false_positive_rows = [row for row in target_matches if row["over_promoted"]]
    return {
        "queries_run": completed_queries,
        "provider_items_seen": total_items,
        "verified_domains_found": len(verified_domains),
        "early_stage_rows_found": len(early_stage_rows),
        "credible_early_stage_leads": len(early_stage_domains),
        "credible_early_stage_leads_per_100_queries": round((len(early_stage_domains) / completed_queries) * 100, 2)
        if completed_queries
        else 0,
        "owner_ready_rows_found": sum(1 for row in accepted if row.get("owner_ready") and not row.get("evaluation_incomplete")),
        "research_deeper_rows_found": sum(1 for row in early_stage_rows if row.get("lead_route") == "research_deeper"),
        "category_anchors_found": sum(1 for row in accepted if row.get("lead_route") == "category_context"),
        "known_target_matches": len(target_matches),
        "known_target_recall": round(len(target_matches) / len(targets), 4) if targets else 0,
        "known_target_precision": round(len(correct_target_matches) / len(target_matches), 4) if target_matches else 0,
        "net_new_verified_domains": len(net_new_domains),
        "net_new_credible_early_stage_leads": len(net_new_domains),
        "net_new_false_positive_rate": round(len(false_positive_rows) / max(1, len(accepted)), 4),
        "false_positives": len(false_positive_rows),
        "publisher_content_junk_rate": round(publisher_or_content_junk / total_items, 4) if total_items else 0,
    }


def _query_family_summary(bakeoff: dict, score: dict) -> dict:
    rows = {}
    for run in bakeoff.get("provider_runs", []):
        family = run.get("query_family", "") or "unknown"
        row = rows.setdefault(family, {"query_family": family, "runs": 0, "items": 0, "skipped": 0})
        row["runs"] += 1
        row["items"] += len(run.get("items") or [])
        if run.get("skipped"):
            row["skipped"] += 1
    return {"families": list(rows.values()), "score_metrics": score.get("metrics", {})}


def _summary_markdown(payload: dict) -> str:
    metrics = payload.get("score", {}).get("metrics", {})
    lines = [
        "# Discovery Yield Evaluation",
        "",
        f"- Queries run: {metrics.get('queries_run', 0)}",
        f"- Verified domains found: {metrics.get('verified_domains_found', 0)}",
        f"- Credible early-stage leads per 100 queries: {metrics.get('credible_early_stage_leads_per_100_queries', 0)}",
        f"- Known-target recall: {metrics.get('known_target_recall', 0)}",
        f"- Known-target precision: {metrics.get('known_target_precision', 0)}",
        "",
    ]
    return "\n".join(lines)


def _route_rank(route: str) -> int:
    return ROUTE_AGGRESSIVENESS.get(route or "", -1)


if __name__ == "__main__":
    raise SystemExit(main())
