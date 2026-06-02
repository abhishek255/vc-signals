#!/usr/bin/env python3
"""Focused source-yield audit for Product Hunt, X, and Evidence Gap rows."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


PRODUCT_HUNT_HOSTS = {"producthunt.com", "www.producthunt.com"}
DEFAULT_OUTPUT_PREFIX = "source-debug-audit"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def _host(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _latest_raw_evidence_path(run_dir: Path) -> Path | None:
    matches = sorted(run_dir.glob("*raw-evidence.json"))
    return matches[-1] if matches else None


def _raw_product_hunt_rows(run_dir: Path) -> tuple[Path | None, list[dict]]:
    raw_path = _latest_raw_evidence_path(run_dir)
    if not raw_path:
        return None, []
    raw = _read_json(raw_path, {})
    rows = raw.get("product_hunt") if isinstance(raw, dict) else []
    return raw_path, rows if isinstance(rows, list) else []


def _runtime_source_health(run_dir: Path) -> list[dict]:
    ledger = _read_json(run_dir / "runtime-ledger.json", {})
    health = ledger.get("source_health") if isinstance(ledger, dict) else []
    return health if isinstance(health, list) else []


def _source_health_for(run_dir: Path, source: str) -> dict:
    for item in _runtime_source_health(run_dir):
        if item.get("source") == source:
            return item
    return {}


def _validation_report(run_dir: Path) -> dict:
    return _read_json(run_dir / "source-yield-validation-report.json", {})


def _has_value(value: object) -> bool:
    if isinstance(value, list):
        return any(_has_value(item) for item in value)
    return str(value or "").strip() != ""


def _manual_query_for_product(row: dict) -> str:
    name = str(row.get("name") or row.get("company_name") or "").strip()
    tagline = str(row.get("tagline") or row.get("description") or "").strip()
    parts = []
    if name:
        parts.append(f'"{name}"')
    if tagline:
        parts.append(f'"{tagline}"')
    parts.append("official website")
    return " ".join(parts)


def classify_product_hunt_failure(row: dict) -> list[str]:
    warning = str(row.get("domain_resolution_warning") or "").lower()
    outbound_url = str(row.get("outbound_url") or "").strip()
    product_url = str(row.get("product_hunt_url") or row.get("url") or "").strip()
    causes: list[str] = []
    if not product_url:
        causes.append("missing_product_hunt_url")
    if not outbound_url:
        causes.append("missing_outbound_url")
    if _host(outbound_url) in PRODUCT_HUNT_HOSTS and "/r/" in outbound_url:
        if "403" in warning or "forbidden" in warning:
            causes.append("product_hunt_redirect_403")
        else:
            causes.append("product_hunt_redirect_needs_follow")
    if "timed out" in warning or "timeout" in warning:
        causes.append("web_resolver_timeout")
    if "no verified official domain" in warning:
        causes.append("web_resolver_no_verified_domain")
    elif "web resolver failed" in warning:
        causes.append("web_resolver_failed")
    if not causes and not _has_value(row.get("domain")):
        causes.append("official_domain_unresolved")
    return causes


def _product_hunt_status(row: dict) -> str:
    if _has_value(row.get("domain")) or _has_value(row.get("website")):
        return "resolved"
    return str(row.get("domain_resolution_status") or "unresolved")


def build_product_hunt_audit(run_dir: Path) -> dict:
    raw_path, rows = _raw_product_hunt_rows(run_dir)
    unresolved = []
    cause_counts: Counter[str] = Counter()
    resolved = 0
    for row in rows:
        status = _product_hunt_status(row)
        if status == "resolved":
            resolved += 1
            continue
        causes = classify_product_hunt_failure(row)
        cause_counts.update(causes)
        unresolved.append(
            {
                "name": row.get("name") or row.get("company_name") or "",
                "tagline": row.get("tagline") or row.get("description") or "",
                "product_hunt_url": row.get("product_hunt_url") or row.get("url") or "",
                "outbound_url": row.get("outbound_url") or "",
                "domain_resolution_status": row.get("domain_resolution_status") or "",
                "domain_resolution_warning": row.get("domain_resolution_warning") or "",
                "failure_causes": causes,
                "fields_product_hunt_provided": {
                    "has_name": _has_value(row.get("name") or row.get("company_name")),
                    "has_tagline": _has_value(row.get("tagline") or row.get("description")),
                    "has_maker_name": _has_value(row.get("maker_name")),
                    "has_product_hunt_url": _has_value(row.get("product_hunt_url") or row.get("url")),
                    "has_outbound_url": _has_value(row.get("outbound_url")),
                    "has_domain": _has_value(row.get("domain")),
                },
                "manual_resolver_query": _manual_query_for_product(row),
                "manual_check_needed": True,
            }
        )
    return {
        "raw_evidence_path": str(raw_path) if raw_path else "",
        "total_launches": len(rows),
        "resolved_launches": resolved,
        "unresolved_launches": len(unresolved),
        "failure_cause_counts": dict(cause_counts),
        "unresolved": unresolved,
    }


def run_product_hunt_reprobe(
    run_dir: Path,
    *,
    limit: int = 17,
    timeout_seconds: int = 8,
    max_queries: int = 1,
    resolver=None,
) -> dict:
    _raw_path, rows = _raw_product_hunt_rows(run_dir)
    unresolved = [row for row in rows if _product_hunt_status(row) != "resolved"]
    if resolver is None:
        try:
            from product_hunt_launches import resolve_launch_domain_via_web
        except ImportError as exc:
            return {
                "attempted": True,
                "status": "unavailable",
                "error": f"import failed: {exc}",
                "total_unresolved": len(unresolved),
                "attempted_count": 0,
                "resolved_count": 0,
                "attempts": [],
            }
        resolver = resolve_launch_domain_via_web

    attempts = []
    for row in unresolved[:limit]:
        try:
            try:
                result = resolver(row, timeout_seconds=timeout_seconds, max_queries=max_queries)
            except TypeError:
                result = resolver(row, timeout_seconds=timeout_seconds)
        except Exception as exc:
            result = {"url": "", "warning": str(exc)}
        url = str(result.get("url") or "").strip() if isinstance(result, dict) else ""
        domain = _host(url)
        attempts.append(
            {
                "name": row.get("name") or row.get("company_name") or "",
                "attempted": True,
                "resolved": bool(domain),
                "url": url,
                "domain": domain,
                "warning": str(result.get("warning") or "").strip() if isinstance(result, dict) else "",
                "evidence_source": str((result.get("evidence") or {}).get("source") or "") if isinstance(result, dict) else "",
                "failure_causes": classify_product_hunt_failure(row),
            }
        )
    return {
        "attempted": True,
        "status": "complete",
        "total_unresolved": len(unresolved),
        "attempted_count": len(attempts),
        "max_queries_per_row": max_queries,
        "resolved_count": sum(1 for item in attempts if item["resolved"]),
        "attempts": attempts,
    }


def build_x_audit(run_dir: Path) -> dict:
    health = _source_health_for(run_dir, "x_launches")
    report = _validation_report(run_dir)
    source_counts = report.get("source_counts") if isinstance(report, dict) else {}
    x_rows = source_counts.get("x_launches") or source_counts.get("x") if isinstance(source_counts, dict) else None
    return {
        "runtime_health": health,
        "validation_source_count": x_rows,
        "observed_status": health.get("status") or ("missing" if not health else ""),
        "observed_fresh_items": health.get("fresh_items", 0),
        "observed_warnings": health.get("warnings", []),
    }


def _gap_missing_operational_fields(row: dict) -> list[str]:
    missing = []
    for key in ("recommended_manual_check", "recommended_next_step"):
        if not _has_value(row.get(key)):
            missing.append(key)
    return missing


def build_evidence_gap_operational_audit(run_dir: Path) -> dict:
    report = _validation_report(run_dir)
    gaps = report.get("evidence_gap_queue") if isinstance(report, dict) else []
    gaps = gaps if isinstance(gaps, list) else []
    missing_rows = []
    for row in gaps:
        missing_fields = _gap_missing_operational_fields(row)
        if missing_fields:
            missing_rows.append(
                {
                    "name": row.get("name", ""),
                    "source_lane": row.get("source_lane", ""),
                    "missing_operational_fields": missing_fields,
                    "missing_evidence": row.get("missing_evidence", []),
                }
            )
    return {
        "evidence_gap_count": len(gaps),
        "rows_missing_operational_fields": len(missing_rows),
        "missing_rows": missing_rows,
    }


def _sample_launch(row: dict) -> dict:
    return {
        "name": row.get("name") or row.get("company_name") or "",
        "url": row.get("url") or row.get("company_x") or "",
        "domain": row.get("domain") or "",
        "website": row.get("website") or "",
        "launch_intent_score": row.get("launch_intent_score"),
        "missing_evidence": row.get("missing_evidence", []),
    }


def run_x_probe(*, movement: str, timeout_seconds: int, limit: int, max_queries: int) -> dict:
    try:
        from last30days_adapter import run_query as run_last30days_query
        from x_launches import run_x_launches, x_credentials_available
    except ImportError as exc:
        return {
            "attempted": True,
            "status": "unavailable",
            "credentials_available": False,
            "error": f"import failed: {exc}",
            "launch_count": 0,
            "warnings": [],
        }

    credentials_available = bool(x_credentials_available())
    if not credentials_available:
        return {
            "attempted": True,
            "status": "unavailable",
            "credentials_available": False,
            "error": "X credentials are not configured.",
            "launch_count": 0,
            "warnings": [],
        }
    payload = run_x_launches(
        movements=[{"movement": movement, "market_sector": "source-yield-probe"}],
        query_runner=run_last30days_query,
        limit=limit,
        timeout_seconds=timeout_seconds,
        max_queries=max_queries,
        max_domain_resolutions=0,
    )
    launches = payload.get("launches", []) if isinstance(payload, dict) else []
    return {
        "attempted": True,
        "status": payload.get("status", "unknown") if isinstance(payload, dict) else "unknown",
        "credentials_available": True,
        "movement": movement,
        "timeout_seconds": timeout_seconds,
        "query_count": len(payload.get("queries", [])) if isinstance(payload, dict) else 0,
        "launch_count": len(launches),
        "warnings": payload.get("warnings", []) if isinstance(payload, dict) else [],
        "sample_launches": [_sample_launch(row) for row in launches[:5]],
    }


def build_source_debug_audit(
    run_dir: Path,
    *,
    product_hunt_reprobe: bool = False,
    product_hunt_reprobe_limit: int = 17,
    product_hunt_reprobe_timeout_seconds: int = 8,
    product_hunt_reprobe_max_queries: int = 1,
    x_probe: bool = False,
    x_probe_movement: str = "AI agent security",
    x_probe_timeout_seconds: int = 35,
    x_probe_limit: int = 5,
    x_probe_max_queries: int = 1,
) -> dict:
    audit = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "coresignal_skipped": True,
        "product_hunt": build_product_hunt_audit(run_dir),
        "x": build_x_audit(run_dir),
        "evidence_gap_queue": build_evidence_gap_operational_audit(run_dir),
    }
    if product_hunt_reprobe:
        audit["product_hunt"]["reprobe"] = run_product_hunt_reprobe(
            run_dir,
            limit=product_hunt_reprobe_limit,
            timeout_seconds=product_hunt_reprobe_timeout_seconds,
            max_queries=product_hunt_reprobe_max_queries,
        )
    else:
        audit["product_hunt"]["reprobe"] = {"attempted": False}
    if x_probe:
        audit["x"]["live_probe"] = run_x_probe(
            movement=x_probe_movement,
            timeout_seconds=x_probe_timeout_seconds,
            limit=x_probe_limit,
            max_queries=x_probe_max_queries,
        )
    else:
        audit["x"]["live_probe"] = {"attempted": False}
    return audit


def _render_cause_counts(counts: dict) -> str:
    if not counts:
        return "- None\n"
    return "".join(f"- {cause}: {count}\n" for cause, count in sorted(counts.items()))


def render_markdown(audit: dict) -> str:
    ph = audit["product_hunt"]
    x = audit["x"]
    gaps = audit["evidence_gap_queue"]
    probe = x.get("live_probe", {})
    lines = [
        "# Source Debug Audit",
        "",
        f"- Run: `{audit['run_dir']}`",
        f"- Coresignal skipped: `{audit['coresignal_skipped']}`",
        "",
        "## Product Hunt",
        "",
        f"- Total launches: {ph['total_launches']}",
        f"- Resolved launches: {ph['resolved_launches']}",
        f"- Unresolved launches: {ph['unresolved_launches']}",
        "",
        "Failure causes:",
        "",
        _render_cause_counts(ph["failure_cause_counts"]).rstrip(),
        "",
        "| Launch | Failure causes | Manual resolver query |",
        "| --- | --- | --- |",
    ]
    for row in ph["unresolved"]:
        causes = ", ".join(row["failure_causes"])
        query = str(row["manual_resolver_query"]).replace("|", "/")
        name = str(row["name"]).replace("|", "/")
        lines.append(f"| {name} | {causes} | `{query}` |")
    reprobe = ph.get("reprobe", {})
    lines.extend(
        [
            "",
            "Product Hunt reprobe:",
            "",
            f"- Reprobe attempted: {reprobe.get('attempted')}",
        ]
    )
    if reprobe.get("attempted"):
        lines.extend(
            [
                f"- Reprobe status: {reprobe.get('status')}",
                f"- Reprobe attempted rows: {reprobe.get('attempted_count')}",
                f"- Reprobe max queries per row: {reprobe.get('max_queries_per_row')}",
                f"- Reprobe resolved rows: {reprobe.get('resolved_count')}",
            ]
        )
        if reprobe.get("attempts"):
            lines.extend(["", "| Launch | Resolved domain | Warning |", "| --- | --- | --- |"])
            for item in reprobe.get("attempts", [])[:20]:
                lines.append(
                    f"| {str(item.get('name') or '').replace('|', '/')} | {item.get('domain') or ''} | {str(item.get('warning') or '').replace('|', '/')} |"
                )
    lines.extend(
        [
            "",
            "## X",
            "",
            f"- Runtime status: {x.get('observed_status')}",
            f"- Runtime fresh items: {x.get('observed_fresh_items')}",
            f"- Runtime warnings: {len(x.get('observed_warnings') or [])}",
            f"- Live probe attempted: {probe.get('attempted')}",
        ]
    )
    if probe.get("attempted"):
        lines.extend(
            [
                f"- Live probe credentials available: {probe.get('credentials_available')}",
                f"- Live probe status: {probe.get('status')}",
                f"- Live probe launch count: {probe.get('launch_count')}",
                f"- Live probe warnings: {len(probe.get('warnings') or [])}",
            ]
        )
        if probe.get("warnings"):
            lines.extend(["", "Live probe warnings:"])
            lines.extend(f"- {warning}" for warning in probe.get("warnings", [])[:5])
        if probe.get("sample_launches"):
            lines.extend(
                [
                    "",
                    "| Sample launch | Domain | Launch score | Missing evidence |",
                    "| --- | --- | --- | --- |",
                ]
            )
            for row in probe.get("sample_launches", [])[:5]:
                lines.append(
                    f"| {str(row.get('name') or '').replace('|', '/')} | {row.get('domain') or ''} | {row.get('launch_intent_score') or ''} | {', '.join(row.get('missing_evidence') or [])} |"
                )
    lines.extend(
        [
            "",
            "## Evidence Gap Queue",
            "",
            f"- Evidence Gap rows: {gaps['evidence_gap_count']}",
            f"- Rows missing manual-check fields: {gaps['rows_missing_operational_fields']}",
        ]
    )
    if gaps["missing_rows"]:
        lines.extend(["", "| Row | Missing operational fields | Missing evidence |", "| --- | --- | --- |"])
        for row in gaps["missing_rows"]:
            lines.append(
                f"| {str(row['name']).replace('|', '/')} | {', '.join(row['missing_operational_fields'])} | {', '.join(row.get('missing_evidence') or [])} |"
            )
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-prefix", default=DEFAULT_OUTPUT_PREFIX)
    parser.add_argument("--product-hunt-reprobe", action="store_true")
    parser.add_argument("--product-hunt-reprobe-limit", type=int, default=17)
    parser.add_argument("--product-hunt-reprobe-timeout-seconds", type=int, default=8)
    parser.add_argument("--product-hunt-reprobe-max-queries", type=int, default=1)
    parser.add_argument("--x-probe", action="store_true")
    parser.add_argument("--x-probe-movement", default="AI agent security")
    parser.add_argument("--x-probe-timeout-seconds", type=int, default=35)
    parser.add_argument("--x-probe-limit", type=int, default=5)
    parser.add_argument("--x-probe-max-queries", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = build_source_debug_audit(
        args.run_dir,
        product_hunt_reprobe=args.product_hunt_reprobe,
        product_hunt_reprobe_limit=args.product_hunt_reprobe_limit,
        product_hunt_reprobe_timeout_seconds=args.product_hunt_reprobe_timeout_seconds,
        product_hunt_reprobe_max_queries=args.product_hunt_reprobe_max_queries,
        x_probe=args.x_probe,
        x_probe_movement=args.x_probe_movement,
        x_probe_timeout_seconds=args.x_probe_timeout_seconds,
        x_probe_limit=args.x_probe_limit,
        x_probe_max_queries=args.x_probe_max_queries,
    )
    json_path = args.run_dir / f"{args.output_prefix}.json"
    markdown_path = args.run_dir / f"{args.output_prefix}.md"
    _write_json(json_path, audit)
    markdown_path.write_text(render_markdown(audit))
    print(json.dumps({"json": str(json_path), "markdown": str(markdown_path)}, indent=2))


if __name__ == "__main__":
    main()
