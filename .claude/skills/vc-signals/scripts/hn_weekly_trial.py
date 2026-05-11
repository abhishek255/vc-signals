#!/usr/bin/env python3
"""Controlled weekly HN launch trial orchestration.

This module keeps HN as an opt-in weekly trial lane. Retrieval remains
last30days-native; vc-signals only normalizes, gates, enriches, and reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from company_native_last30days import (
    build_last30days_native_queries,
    run_last30days_native_audit,
    write_last30days_native_artifacts,
)
from hn_gated_source_trial import run_hn_gated_source_trial, write_hn_gated_source_trial_artifacts
from hn_outbound_enrichment import run_hn_outbound_enrichment, write_hn_outbound_enrichment_artifacts


@dataclass
class HNLaunchTrialConfig:
    enabled: bool = False
    label: str = "Phase 6C HN Launch Trial"
    lookback_days: int = 30
    timeout_seconds: int = 120
    max_candidates: int = 15
    max_runtime_seconds: float | None = 90
    max_attio_checks: int | None = 10
    max_live_queries: int | None = 25
    per_candidate_timeout_seconds: float | None = 8


def run_hn_launch_weekly_trial(
    *,
    movements: list[dict],
    run_query_fn: Callable,
    query_runner: Callable | None = None,
    page_fetcher: Callable | None = None,
    attio_matcher: Callable | None = None,
    output_dir: Path | str | None = None,
    cache_dir: Path | str | None = None,
    config: HNLaunchTrialConfig | None = None,
) -> dict:
    config = config or HNLaunchTrialConfig(enabled=False)
    if not config.enabled:
        return {"enabled": False}

    root_dir = Path(output_dir) if output_dir else None
    cache_path = Path(cache_dir) if cache_dir else (root_dir / "cache" if root_dir else None)
    queries = build_last30days_native_queries(
        movements,
        lanes=("launch_hn",),
        lookback_days=config.lookback_days,
    )
    if not queries:
        payload = _summary(
            config=config,
            queries_planned=0,
            movement_seeds=movements,
            native_payload={"normalized_leads": {"summary": {"items_seen": 0}}},
            gated_payload={"summary": {}},
            enriched_payload={"summary": {}, "runtime_ledger": {"summary": {}}},
            artifacts=[],
        )
        payload["skipped_no_seed"] = True
        payload["completion_status"] = "skipped_no_seed"
        return _write_summary_artifacts(payload, root_dir)

    native_payload = run_last30days_native_audit(
        queries,
        run_query_fn=run_query_fn,
        output_dir=root_dir,
        timeout_seconds=config.timeout_seconds,
    )
    native_payload["normalized_leads"] = _dedupe_normalized_leads(native_payload.get("normalized_leads", {}))
    artifacts: list[str] = []
    if root_dir:
        artifacts.extend(str(path) for path in write_last30days_native_artifacts(native_payload, root_dir))

    gated_payload = run_hn_gated_source_trial(native_payload["normalized_leads"])
    if root_dir:
        artifacts.extend(str(path) for path in write_hn_gated_source_trial_artifacts(gated_payload, root_dir))

    enriched_payload = run_hn_outbound_enrichment(
        gated_payload,
        query_runner=query_runner,
        page_fetcher=page_fetcher,
        attio_matcher=attio_matcher,
        cache_dir=cache_path,
        max_candidates=config.max_candidates,
        max_runtime_seconds=config.max_runtime_seconds,
        max_attio_checks=config.max_attio_checks,
        max_live_queries=config.max_live_queries,
        per_candidate_timeout_seconds=config.per_candidate_timeout_seconds,
    )
    if root_dir:
        artifacts.extend(str(path) for path in write_hn_outbound_enrichment_artifacts(enriched_payload, root_dir))

    payload = _summary(
        config=config,
        queries_planned=len(queries),
        movement_seeds=movements,
        native_payload=native_payload,
        gated_payload=gated_payload,
        enriched_payload=enriched_payload,
        artifacts=artifacts,
    )
    return _write_summary_artifacts(payload, root_dir)


def _dedupe_normalized_leads(payload: dict) -> dict:
    out = {
        "summary": dict(payload.get("summary") or {}),
        "company_candidates": _dedupe_rows(payload.get("company_candidates") or []),
        "project_only_leads": _dedupe_rows(payload.get("project_only_leads") or []),
        "needs_detail_enrichment": _dedupe_rows(payload.get("needs_detail_enrichment") or []),
        "rejected_leads": _dedupe_rows(payload.get("rejected_leads") or []),
    }
    out["summary"]["company_candidates"] = len(out["company_candidates"])
    out["summary"]["project_only_leads"] = len(out["project_only_leads"])
    out["summary"]["needs_detail_enrichment"] = len(out["needs_detail_enrichment"])
    out["summary"]["rejected_leads"] = len(out["rejected_leads"])
    return out


def _dedupe_rows(rows: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for row in rows:
        key = (
            row.get("kind", ""),
            row.get("domain", ""),
            row.get("official_url", ""),
            row.get("source_url", ""),
            row.get("title", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _summary(
    *,
    config: HNLaunchTrialConfig,
    queries_planned: int,
    movement_seeds: list[dict],
    native_payload: dict,
    gated_payload: dict,
    enriched_payload: dict,
    artifacts: list[str],
) -> dict:
    native_summary = native_payload.get("normalized_leads", {}).get("summary", {})
    gated_summary = gated_payload.get("summary", {})
    enriched_summary = enriched_payload.get("summary", {})
    runtime_summary = enriched_payload.get("runtime_ledger", {}).get("summary", {})
    skipped_no_seed = queries_planned == 0
    return {
        "enabled": True,
        "label": config.label,
        "queries_planned": queries_planned,
        "queries_run": len(native_payload.get("audit", {}).get("rows") or []),
        "movement_seeds": _movement_seed_rows(movement_seeds),
        "skipped_no_seed": skipped_no_seed,
        "completion_status": _completion_status(
            skipped_no_seed=skipped_no_seed,
            partial=bool(enriched_payload.get("partial", False)),
            runtime_summary=runtime_summary,
        ),
        "items_seen": native_summary.get("items_seen", 0),
        "outbound_candidates": enriched_summary.get(
            "hn_outbound_candidates_input",
            gated_summary.get("hn_outbound_candidate_rows", 0),
        ),
        "project_only_rows": enriched_summary.get("project_only_rows", gated_summary.get("project_only_rows", 0)),
        "product_context_rows": enriched_summary.get("product_context_rows", gated_summary.get("product_context_rows", 0)),
        "research_deeper_rows": enriched_summary.get("research_deeper_rows", gated_summary.get("research_deeper_rows", 0)),
        "assign_owner_rows": enriched_summary.get("assign_owner_rows", gated_summary.get("assign_owner_rows", 0)),
        "new_to_marathon_rows": enriched_summary.get("new_to_marathon_rows", gated_summary.get("new_to_marathon_rows", 0)),
        "unsafe_promotions": enriched_summary.get("unsafe_promotions", gated_summary.get("unsafe_promotions", 0)),
        "partial": bool(enriched_payload.get("partial", False)),
        "budget_exceeded": bool(enriched_payload.get("budget_exceeded", False)),
        "budget_reasons": list(enriched_payload.get("budget_reasons") or []),
        "runtime": dict(runtime_summary),
        "artifacts": artifacts,
    }


def _movement_seed_rows(movements: list[dict]) -> list[dict]:
    rows = []
    for movement in movements or []:
        label = (movement.get("movement") or "").strip()
        if not label:
            continue
        rows.append(
            {
                "movement": label,
                "market_sector": movement.get("market_sector", ""),
                "origin_row_ids": list(movement.get("origin_row_ids") or []),
            }
        )
    return rows


def _completion_status(*, skipped_no_seed: bool, partial: bool, runtime_summary: dict) -> str:
    if skipped_no_seed:
        return "skipped_no_seed"
    if partial or runtime_summary.get("partial_budget"):
        return "partial_budget"
    if runtime_summary.get("completed_with_stage_failure"):
        return "completed_with_stage_failure"
    return "completed_clean"


def _write_summary_artifacts(payload: dict, output_dir: Path | None) -> dict:
    if not output_dir:
        return payload
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "hn-weekly-trial.json"
    md_path = output_dir / "hn-weekly-trial.md"
    json_path.write_text(_json_dumps(payload))
    md_path.write_text(_markdown(payload))
    artifacts = list(payload.get("artifacts") or [])
    for path in (json_path, md_path):
        value = str(path)
        if value not in artifacts:
            artifacts.append(value)
    out = dict(payload)
    out["artifacts"] = artifacts
    json_path.write_text(_json_dumps(out))
    return out


def _json_dumps(payload: dict) -> str:
    import json

    return json.dumps(payload, indent=2)


def _markdown(payload: dict) -> str:
    lines = [
        "# Phase 6C HN Launch Trial",
        "",
        "Controlled weekly HN trial. Retrieval uses last30days; weekly default behavior is unchanged.",
        "",
        f"- Queries planned: {payload.get('queries_planned', 0)}",
        f"- Queries run: {payload.get('queries_run', 0)}",
        f"- Completion status: {payload.get('completion_status', 'unknown')}",
        f"- Items seen: {payload.get('items_seen', 0)}",
        f"- Outbound candidates: {payload.get('outbound_candidates', 0)}",
        f"- Project-only rows: {payload.get('project_only_rows', 0)}",
        f"- Product/context rows: {payload.get('product_context_rows', 0)}",
        f"- Research deeper rows: {payload.get('research_deeper_rows', 0)}",
        f"- Assign owner rows: {payload.get('assign_owner_rows', 0)}",
        f"- Unsafe promotions: {payload.get('unsafe_promotions', 0)}",
    ]
    runtime = payload.get("runtime") or {}
    if runtime:
        lines.extend(
            [
                "",
                "## Runtime",
                "",
                f"- Completed: {runtime.get('candidates_completed', 0)}",
                f"- Partial: {runtime.get('candidates_partially_enriched', 0)}",
                f"- Stage failures: {runtime.get('stage_failures', 0)}",
                f"- Completion split: clean {runtime.get('completed_clean', 0)}, "
                f"stage-failed {runtime.get('completed_with_stage_failure', 0)}, "
                f"partial-budget {runtime.get('partial_budget', 0)}, "
                f"skipped-low-priority {runtime.get('skipped_low_priority', 0)}",
            ]
        )
    if not payload.get("queries_planned"):
        lines.extend(["", "No HN launch queries were planned from this weekly run's movement set."])
    elif payload.get("movement_seeds"):
        lines.extend(["", "## Movement Seeds", ""])
        for row in payload.get("movement_seeds", [])[:12]:
            sector = row.get("market_sector") or "unknown"
            lines.append(f"- {row.get('movement')} ({sector})")
    return "\n".join(lines) + "\n"
