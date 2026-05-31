#!/usr/bin/env python3
"""Build a source-yield validation report and strict decision packet."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REVIEW_WORTHY_ACTIONS = {"research deeper", "contact maintainer", "watch"}
DEFAULT_ASSIGN_OWNER_ALLOWLIST = ("Voker",)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _normalized_action(row: dict) -> str:
    return str(row.get("action") or row.get("recommended_action") or "").strip().lower()


def _row_name(row: dict) -> str:
    return str(row.get("name") or row.get("canonical_name") or row.get("display_name") or "").strip()


def _row_domain(row: dict) -> str:
    return str(row.get("domain") or row.get("company_domain") or row.get("candidate_domain") or "").strip()


def _has_founder_evidence(row: dict) -> bool:
    return _has_value(row.get("founders")) or _has_value(row.get("founder_profiles"))


def _has_stage_or_size_evidence(row: dict) -> bool:
    return (
        _has_value(row.get("stage"))
        or _has_value(row.get("raised"))
        or _has_value(row.get("raised_amount"))
        or _has_value(row.get("headcount"))
    )


def is_net_new_review_worthy_candidate(row: dict) -> bool:
    """Conservative review-worthy bar used for the source-yield sprint."""

    return (
        str(row.get("weekly_tag") or "").upper() == "NEW"
        and bool(_row_domain(row))
        and _has_founder_evidence(row)
        and _has_stage_or_size_evidence(row)
        and _normalized_action(row) in REVIEW_WORTHY_ACTIONS
    )


def _review_worthy_summary(row: dict) -> dict:
    return {
        "name": _row_name(row),
        "domain": _row_domain(row),
        "action": row.get("action", ""),
        "tier": row.get("tier", ""),
        "source_lane": row.get("source_lane", ""),
        "founders": _as_list(row.get("founders")),
        "stage": row.get("stage", ""),
        "raised": row.get("raised", row.get("raised_amount", "")),
        "headcount": row.get("headcount", ""),
        "company_linkedin": row.get("company_linkedin", ""),
        "company_x": row.get("company_x", ""),
        "evidence_urls": sorted(
            {
                str(url)
                for url in (
                    _as_list(row.get("founder_team_evidence"))
                    + _as_list(row.get("stage_funding_evidence"))
                    + _as_list(row.get("customer_buyer_evidence"))
                    + _as_list(row.get("source_outbound_urls"))
                )
                if str(url).strip()
            }
        ),
    }


def _workflow_assign_owner_rows(weekly_focus: dict) -> list[dict]:
    workflow = weekly_focus.get("workflow_view") or {}
    rows = workflow.get("Assign owner") or workflow.get("Assign Owner") or []
    return rows if isinstance(rows, list) else []


def _assign_owner_names(rows: list[dict]) -> list[str]:
    names = []
    for row in rows:
        name = _row_name(row)
        if name:
            names.append(name)
    return names


def _hn_launch_trial_summary(run_dir: Path) -> dict:
    payload = _read_json(run_dir / "hn-launch-trial" / "hn-trial-row-review.json", {})
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    return summary if isinstance(summary, dict) else {}


def _source_counts(raw_evidence: dict, run_dir: Path) -> dict:
    counts = {}
    for source in ("github", "product_hunt", "yc_directory", "x_launches"):
        value = raw_evidence.get(source)
        counts[source] = len(value) if isinstance(value, list) else 0
    last30days = raw_evidence.get("last30days")
    counts["last30days_queries"] = len(last30days) if isinstance(last30days, dict) else 0
    hn_summary = _hn_launch_trial_summary(run_dir)
    counts["hn_launch_trial_rows"] = hn_summary.get("rows", 0)
    counts["hn_launch_assign_owner"] = (hn_summary.get("action_split") or {}).get("Assign owner", 0)
    counts["hn_launch_unsafe_promotions"] = hn_summary.get("unsafe_promotions", 0)
    return counts


def _latest_raw_evidence_path(run_path: Path) -> Path:
    matches = sorted(
        run_path.glob("*-raw-evidence.json"),
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    if matches:
        return matches[0]
    return run_path / "2026-05-31-raw-evidence.json"


def _domain_from_url(url: str) -> str:
    if not url or "://" not in url:
        return ""
    try:
        from urllib.parse import urlparse

        host = urlparse(url).netloc.lower().removeprefix("www.")
        return host
    except Exception:
        return ""


def _looks_like_source_or_directory_domain(domain: str) -> bool:
    normalized = (domain or "").lower().strip().removeprefix("www.")
    blocked = {
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
    return any(normalized == item or normalized.endswith(f".{item}") for item in blocked)


def _official_domain_hint(item: dict) -> str:
    domain = _row_domain(item)
    if domain and not _looks_like_source_or_directory_domain(domain):
        return domain
    for key in ("website", "homepage", "resolved_url"):
        candidate = _domain_from_url(str(item.get(key) or ""))
        if candidate and not _looks_like_source_or_directory_domain(candidate):
            return candidate
    return ""


def _row_source_bucket(row: dict) -> str:
    text = " ".join(
        str(value or "")
        for value in (
            row.get("source_lane"),
            row.get("candidate_type"),
            row.get("evidence_role"),
            row.get("source"),
            row.get("url"),
        )
    ).lower()
    if "producthunt" in text or "product hunt" in text:
        return "product_hunt"
    if "yc directory" in text or "ycombinator.com/companies" in text or "yc_company" in text:
        return "yc_directory"
    if "news.ycombinator.com" in text or "hackernews" in text or "hacker news" in text:
        return "hn"
    if "github.com" in text or "oss_project" in text or row.get("source_lane") == "OSS":
        return "github"
    if "x.com" in text or "twitter.com" in text or row.get("source_lane") == "X":
        return "x"
    if "grounded web" in text or "company_discovery" in text or "official_company_page" in text:
        return "manual_web"
    return "other"


def _count_by_source_bucket(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        bucket = _row_source_bucket(row)
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts


def _raw_domain_resolution_summary(raw_evidence: dict) -> dict:
    product_hunt = raw_evidence.get("product_hunt") if isinstance(raw_evidence, dict) else []
    x_launches = raw_evidence.get("x_launches") if isinstance(raw_evidence, dict) else []
    product_hunt = product_hunt if isinstance(product_hunt, list) else []
    x_launches = x_launches if isinstance(x_launches, list) else []
    ph_resolved = [
        item
        for item in product_hunt
        if _official_domain_hint(item)
    ]
    x_resolved = [
        item
        for item in x_launches
        if _official_domain_hint(item)
    ]
    return {
        "product_hunt": {
            "launches": len(product_hunt),
            "resolved_domains": len(ph_resolved),
            "unresolved_domains": max(0, len(product_hunt) - len(ph_resolved)),
        },
        "x": {
            "launches": len(x_launches),
            "resolved_domains": len(x_resolved),
            "unresolved_domains": max(0, len(x_launches) - len(x_resolved)),
        },
    }


def _source_diversity_summary(
    *,
    candidate_rows: list[dict],
    review_worthy_rows: list[dict],
    raw_evidence: dict,
    run_dir: Path,
) -> dict:
    review_counts = _count_by_source_bucket(review_worthy_rows)
    candidate_counts = _count_by_source_bucket(candidate_rows)
    hn_summary = _hn_launch_trial_summary(run_dir)
    hn_assign_owner_count = (hn_summary.get("action_split") or {}).get("Assign owner", 0)
    if hn_assign_owner_count:
        review_counts["hn"] = review_counts.get("hn", 0) + hn_assign_owner_count
    desired = ("hn", "github", "product_hunt", "x", "manual_web", "yc_directory")
    non_yc_review_worthy = sum(
        count for bucket, count in review_counts.items() if bucket != "yc_directory"
    )
    review_lanes = [bucket for bucket in desired if review_counts.get(bucket, 0)]
    return {
        "desired_source_lanes": list(desired),
        "candidate_rows_by_source_lane": {bucket: candidate_counts.get(bucket, 0) for bucket in desired},
        "review_worthy_rows_by_source_lane": {bucket: review_counts.get(bucket, 0) for bucket in desired},
        "review_worthy_source_lanes": review_lanes,
        "non_yc_review_worthy_count": non_yc_review_worthy,
        "yc_review_worthy_count": review_counts.get("yc_directory", 0),
        "raw_domain_resolution": _raw_domain_resolution_summary(raw_evidence),
        "hn_launch_trial_rows": hn_summary.get("rows", 0),
        "hn_launch_trial_assign_owner": hn_assign_owner_count,
        "source_diversity_proven": non_yc_review_worthy > 0 and len(review_lanes) >= 2,
        "interpretation": (
            "Source diversity is proven when at least one non-YC lane produces a partner-grade row. "
            "HN Assign Owner rows count here; raw Product Hunt/X/GitHub/manual-web rows are discovery coverage until they clear the same evidence bar."
        ),
    }


def _ledger_packet_warning(run_dir: Path, strict_assign_owner_names: list[str]) -> dict:
    packet = _read_json(run_dir / "final-partner-packet" / "partner-decision-packet.json", {})
    sections = packet.get("sections") if isinstance(packet, dict) else {}
    owner_rows = sections.get("owner_follow_up") if isinstance(sections, dict) else []
    if not isinstance(owner_rows, list):
        owner_rows = []
    generated_names = [str(row.get("entity_name") or "").strip() for row in owner_rows if str(row.get("entity_name") or "").strip()]
    generated_count = packet.get("summary", {}).get("owner_follow_up", len(owner_rows)) if isinstance(packet, dict) else len(owner_rows)
    strict_names = set(strict_assign_owner_names)
    generated_name_set = set(generated_names)
    unsafe_for_blessed_decision = bool(generated_count and (generated_count > len(strict_names) or not generated_name_set <= strict_names))
    return {
        "generated_partner_packet_owner_follow_up_count": generated_count,
        "generated_partner_packet_owner_follow_up_names": generated_names,
        "strict_weekly_assign_owner_names": strict_assign_owner_names,
        "unsafe_for_blessed_decision": unsafe_for_blessed_decision,
        "warning": (
            "The generated historical ledger partner packet has more owner follow-up rows than the strict weekly workflow. "
            "Use the source-yield decision packet for this sprint until the ledger packet respects the weekly action gate."
            if unsafe_for_blessed_decision
            else ""
        ),
    }


def _manual_mode_summary(runtime_ledger: dict) -> dict:
    source_access = runtime_ledger.get("source_access") or {}
    summary = source_access.get("summary") or {}
    return {
        "configured": summary.get("configured", []),
        "manual_mode": summary.get("manual_mode", []),
        "missing": summary.get("missing", []),
        "recommendation": summary.get("recommendation", ""),
    }


def build_source_yield_validation_report(
    run_dir: Path | str,
    *,
    target_review_worthy_count: int = 5,
    assign_owner_allowlist: tuple[str, ...] = DEFAULT_ASSIGN_OWNER_ALLOWLIST,
    generated_at: str | None = None,
) -> dict:
    run_path = Path(run_dir)
    candidates = _read_json(run_path / "candidates.json", [])
    weekly_focus = _read_json(run_path / "weekly-focus.json", {})
    runtime_ledger = _read_json(run_path / "runtime-ledger.json", {})
    raw_evidence = _read_json(_latest_raw_evidence_path(run_path), {})
    company_discovery = _read_json(run_path / "company-discovery.json", {})
    manual_targets = _read_json(run_path / "manual-enrichment-targets.json", {})

    candidate_rows = candidates if isinstance(candidates, list) else []
    assign_owner_rows = _workflow_assign_owner_rows(weekly_focus if isinstance(weekly_focus, dict) else {})
    assign_owner_names = _assign_owner_names(assign_owner_rows)
    candidate_assign_owner_names = [_row_name(row) for row in candidate_rows if _normalized_action(row) == "assign owner"]
    review_worthy_rows = [_review_worthy_summary(row) for row in candidate_rows if is_net_new_review_worthy_candidate(row)]

    allowlist = {name.lower() for name in assign_owner_allowlist}
    weekly_owner_set = {name.lower() for name in assign_owner_names}
    candidate_owner_set = {name.lower() for name in candidate_assign_owner_names if name}
    voker_present = "voker" in weekly_owner_set
    unexpected_weekly_owners = sorted(weekly_owner_set - allowlist)
    unexpected_candidate_owners = sorted(candidate_owner_set - allowlist)
    assign_owner_bar_preserved = (
        voker_present
        and len(assign_owner_names) == 1
        and not unexpected_weekly_owners
        and not unexpected_candidate_owners
    )

    source_health = runtime_ledger.get("source_health", []) if isinstance(runtime_ledger, dict) else []
    source_health_summary = [
        {
            "source": item.get("source", ""),
            "status": item.get("status", ""),
            "fresh_items": item.get("fresh_items", 0),
            "duration_seconds": item.get("duration_seconds", 0),
            "warnings": item.get("warnings", []),
        }
        for item in source_health
        if isinstance(item, dict)
    ]
    hn_summary = _hn_launch_trial_summary(run_path)
    if hn_summary:
        source_health_summary.append(
            {
                "source": "hn_launch_trial",
                "status": "complete",
                "fresh_items": hn_summary.get("rows", 0),
                "duration_seconds": 0,
                "warnings": [],
            }
        )
    caveats = []
    unhealthy_last30days = [
        item
        for item in source_health_summary
        if str(item.get("source", "")).startswith("last30days:") and item.get("status") in {"error", "degraded"}
    ]
    if unhealthy_last30days:
        caveats.append("last30days sector queries were degraded or errored, mostly from Safari cookie permissions and timeouts.")
    ph_warnings = [item for item in source_health_summary if item.get("source") == "product_hunt" and item.get("warnings")]
    if ph_warnings:
        caveats.append("Product Hunt API worked, but several launch redirects still needed fallback domain resolution or stayed unresolved.")
    x_warnings = [item for item in source_health_summary if item.get("source") == "x_launches" and item.get("warnings")]
    if x_warnings:
        caveats.append("X worked as a launch signal, but evidence was thin and still needs domain enrichment for some rows.")

    ledger_warning = _ledger_packet_warning(run_path, assign_owner_names)
    if ledger_warning["warning"]:
        caveats.append(ledger_warning["warning"])

    net_new_count = len(review_worthy_rows)
    goal_reached = assign_owner_bar_preserved and net_new_count >= target_review_worthy_count
    return {
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_path),
        "goal_assessment": {
            "goal_reached": goal_reached,
            "target_assign_owner": list(assign_owner_allowlist),
            "assign_owner_names": assign_owner_names,
            "candidate_assign_owner_names": candidate_assign_owner_names,
            "voker_assign_owner_present": voker_present,
            "assign_owner_bar_preserved": assign_owner_bar_preserved,
            "unexpected_weekly_assign_owner_names": unexpected_weekly_owners,
            "unexpected_candidate_assign_owner_names": unexpected_candidate_owners,
            "target_net_new_review_worthy_count": target_review_worthy_count,
            "net_new_review_worthy_count": net_new_count,
            "review_worthy_target_met": net_new_count >= target_review_worthy_count,
        },
        "review_worthy_rows": review_worthy_rows,
        "source_counts": _source_counts(raw_evidence if isinstance(raw_evidence, dict) else {}, run_path),
        "source_diversity": _source_diversity_summary(
            candidate_rows=candidate_rows,
            review_worthy_rows=review_worthy_rows,
            raw_evidence=raw_evidence if isinstance(raw_evidence, dict) else {},
            run_dir=run_path,
        ),
        "source_health": source_health_summary,
        "source_access": _manual_mode_summary(runtime_ledger if isinstance(runtime_ledger, dict) else {}),
        "manual_enrichment_summary": manual_targets.get("summary", {}) if isinstance(manual_targets, dict) else {},
        "company_discovery_summary": company_discovery.get("summary", {}) if isinstance(company_discovery, dict) else {},
        "ledger_partner_packet_warning": ledger_warning,
        "caveats": caveats,
    }


def build_source_yield_decision_packet(report: dict, weekly_focus: dict) -> dict:
    assign_owner_rows = _workflow_assign_owner_rows(weekly_focus)
    owner_follow_up = [
        {
            "name": _row_name(row),
            "domain": row.get("company_domain") or row.get("domain", ""),
            "recommended_action": "Assign owner",
            "lead_route": row.get("lead_route", ""),
            "owner_readiness_score": row.get("owner_readiness_score", ""),
            "evidence_urls": row.get("evidence_urls", []),
            "why_system_call": "Only row clearing the strict weekly Assign Owner gate.",
        }
        for row in assign_owner_rows
    ]
    review_rows = report["review_worthy_rows"]
    return {
        "generated_at": report["generated_at"],
        "packet_type": "source_yield_strict_decision_packet",
        "source_run_dir": report["run_dir"],
        "summary": {
            "goal_reached": report["goal_assessment"]["goal_reached"],
            "owner_follow_up": len(owner_follow_up),
            "review_worthy_research": len(review_rows),
            "continue_research": len(review_rows),
            "unsafe_promotions": 0 if report["goal_assessment"]["assign_owner_bar_preserved"] else 1,
            "assign_owner_bar_preserved": report["goal_assessment"]["assign_owner_bar_preserved"],
        },
        "sections": {
            "owner_follow_up": owner_follow_up,
            "review_worthy_research": review_rows,
            "continue_research": review_rows,
            "source_caveats": report["caveats"],
        },
    }


def build_source_yield_ledger_action_report(report: dict) -> dict:
    return {
        "generated_at": report["generated_at"],
        "report_type": "source_yield_strict_action_report",
        "source_run_dir": report["run_dir"],
        "summary": {
            "goal_reached": report["goal_assessment"]["goal_reached"],
            "assign_owner_entities": len(report["goal_assessment"]["assign_owner_names"]),
            "review_worthy_research_entities": report["goal_assessment"]["net_new_review_worthy_count"],
            "unsafe_promotions": 0 if report["goal_assessment"]["assign_owner_bar_preserved"] else 1,
        },
        "actions": [
            {
                "action": "Assign owner",
                "count": len(report["goal_assessment"]["assign_owner_names"]),
                "names": report["goal_assessment"]["assign_owner_names"],
            },
            {
                "action": "Review worthy - research deeper",
                "count": report["goal_assessment"]["net_new_review_worthy_count"],
                "names": [row["name"] for row in report["review_worthy_rows"]],
            },
        ],
        "caveats": report["caveats"],
    }


def render_source_yield_markdown(report: dict) -> str:
    assessment = report["goal_assessment"]
    status = "yes" if assessment["goal_reached"] else "no"
    lines = [
        "# Source Yield Validation",
        "",
        f"- Goal reached: {status}",
        f"- Assign Owner rows: {', '.join(assessment['assign_owner_names']) or 'none'}",
        f"- Assign Owner bar preserved: {'yes' if assessment['assign_owner_bar_preserved'] else 'no'}",
        f"- Net-new credible Review-Worthy rows: {assessment['net_new_review_worthy_count']} / {assessment['target_net_new_review_worthy_count']}",
        "",
        "## Review-Worthy Rows",
        "",
        "| Company | Domain | Action | Stage | Raised | Headcount | Source |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["review_worthy_rows"]:
        lines.append(
            "| {name} | {domain} | {action} | {stage} | {raised} | {headcount} | {source_lane} |".format(
                name=str(row["name"]).replace("|", "/"),
                domain=str(row["domain"]).replace("|", "/"),
                action=str(row["action"]).replace("|", "/"),
                stage=str(row["stage"]).replace("|", "/"),
                raised=str(row["raised"]).replace("|", "/"),
                headcount=str(row["headcount"]).replace("|", "/"),
                source_lane=str(row["source_lane"]).replace("|", "/"),
            )
        )
    diversity = report.get("source_diversity", {})
    lines.extend(["", "## Source Diversity", ""])
    lines.append(
        "- Non-YC review-worthy rows: {non_yc}".format(
            non_yc=diversity.get("non_yc_review_worthy_count", 0)
        )
    )
    lines.append(
        "- Review-worthy lanes: {lanes}".format(
            lanes=", ".join(diversity.get("review_worthy_source_lanes", [])) or "none"
        )
    )
    for source, item in (diversity.get("raw_domain_resolution") or {}).items():
        lines.append(
            "- {source}: launches={launches}, resolved_domains={resolved}, unresolved_domains={unresolved}".format(
                source=source,
                launches=item.get("launches", 0),
                resolved=item.get("resolved_domains", 0),
                unresolved=item.get("unresolved_domains", 0),
            )
        )
    lines.extend(["", "## Source Health", ""])
    for item in report["source_health"]:
        lines.append(
            f"- {item['source']}: {item['status']}, fresh_items={item['fresh_items']}, duration_seconds={item['duration_seconds']}"
        )
    lines.extend(["", "## Caveats", ""])
    if report["caveats"]:
        lines.extend(f"- {caveat}" for caveat in report["caveats"])
    else:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def write_source_yield_outputs(
    run_dir: Path | str,
    *,
    target_review_worthy_count: int = 5,
    assign_owner_allowlist: tuple[str, ...] = DEFAULT_ASSIGN_OWNER_ALLOWLIST,
    packet_dir: Path | str | None = None,
) -> dict:
    run_path = Path(run_dir)
    report = build_source_yield_validation_report(
        run_path,
        target_review_worthy_count=target_review_worthy_count,
        assign_owner_allowlist=assign_owner_allowlist,
    )
    weekly_focus = _read_json(run_path / "weekly-focus.json", {})
    packet = build_source_yield_decision_packet(report, weekly_focus if isinstance(weekly_focus, dict) else {})
    ledger_report = build_source_yield_ledger_action_report(report)
    packet_path = Path(packet_dir) if packet_dir is not None else run_path / "source-yield-decision-packet"

    report_json_path = run_path / "source-yield-validation-report.json"
    report_md_path = run_path / "source-yield-validation-report.md"
    _write_json(report_json_path, report)
    report_md_path.write_text(render_source_yield_markdown(report))
    _write_json(packet_path / "partner-decision-packet.json", packet)
    _write_json(packet_path / "ledger-action-report.json", ledger_report)
    (packet_path / "README.md").write_text(
        "# Source Yield Decision Packet\n\n"
        "This packet is the strict source-yield sprint decision view. It keeps Assign Owner limited to rows that cleared the weekly workflow gate.\n"
    )
    return {
        "report_json": str(report_json_path),
        "report_markdown": str(report_md_path),
        "partner_decision_packet": str(packet_path / "partner-decision-packet.json"),
        "ledger_action_report": str(packet_path / "ledger-action-report.json"),
        "goal_reached": report["goal_assessment"]["goal_reached"],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--target-review-worthy-count", type=int, default=5)
    parser.add_argument("--assign-owner-allowlist", default=",".join(DEFAULT_ASSIGN_OWNER_ALLOWLIST))
    parser.add_argument("--packet-dir", default="")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    allowlist = tuple(name.strip() for name in args.assign_owner_allowlist.split(",") if name.strip())
    result = write_source_yield_outputs(
        args.run_dir,
        target_review_worthy_count=args.target_review_worthy_count,
        assign_owner_allowlist=allowlist or DEFAULT_ASSIGN_OWNER_ALLOWLIST,
        packet_dir=args.packet_dir or None,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
