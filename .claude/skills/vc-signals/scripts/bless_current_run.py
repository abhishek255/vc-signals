#!/usr/bin/env python3
"""Write a small blessed-current run folder without deleting experiment output."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_ARTIFACTS = [
    "README.md",
    "partner-decision-packet.json",
    "ledger-action-report.json",
    "run-manifest.json",
]
OPTIONAL_ARTIFACTS = [
    "source-yield-validation-report.json",
    "source-yield-validation-report.md",
    "source-yield-repeatability-report.json",
    "source-yield-repeatability-report.md",
    "targeted-manual-enrichment.json",
]


def build_current_run_manifest(
    *,
    source_run_dir: Path | str,
    current_dir: Path | str,
    partner_decision_packet: Path | str,
    ledger_action_report: Path | str,
    source_yield_validation_report: Path | str | None = None,
    source_yield_validation_markdown: Path | str | None = None,
    source_yield_repeatability_report: Path | str | None = None,
    source_yield_repeatability_markdown: Path | str | None = None,
    targeted_manual_enrichment_report: Path | str | None = None,
    generated_at: str | None = None,
) -> dict:
    inputs = {
        "partner_decision_packet": str(partner_decision_packet),
        "ledger_action_report": str(ledger_action_report),
    }
    decision_artifacts = []
    if source_yield_validation_report:
        inputs["source_yield_validation_report"] = str(source_yield_validation_report)
        decision_artifacts.append("source-yield-validation-report.json")
    if source_yield_validation_markdown:
        inputs["source_yield_validation_markdown"] = str(source_yield_validation_markdown)
        decision_artifacts.append("source-yield-validation-report.md")
    if source_yield_repeatability_report:
        inputs["source_yield_repeatability_report"] = str(source_yield_repeatability_report)
        decision_artifacts.append("source-yield-repeatability-report.json")
    if source_yield_repeatability_markdown:
        inputs["source_yield_repeatability_markdown"] = str(source_yield_repeatability_markdown)
        decision_artifacts.append("source-yield-repeatability-report.md")
    if targeted_manual_enrichment_report:
        inputs["targeted_manual_enrichment_report"] = str(targeted_manual_enrichment_report)
        decision_artifacts.append("targeted-manual-enrichment.json")
    return {
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "source_run_dir": str(source_run_dir),
        "blessed_current_dir": str(current_dir),
        "required_artifacts": list(REQUIRED_ARTIFACTS),
        "decision_artifacts": decision_artifacts,
        "inputs": inputs,
        "policy": {
            "assign_owner_gate": "unchanged_high_confidence_only",
            "review_worthy_goal": "increase credible Review-Worthy rows without unsafe owner promotion",
            "cleanup_mode": "bless_current_without_deleting_experiments",
        },
    }


def _copy_json(src: Path, dst: Path, fallback: dict) -> None:
    if src.exists():
        shutil.copyfile(src, dst)
        return
    dst.write_text(json.dumps(fallback, indent=2))


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _readme_text(manifest: dict, partner_packet: dict, ledger_report: dict) -> str:
    packet_summary = partner_packet.get("summary", {})
    ledger_summary = ledger_report.get("summary", {})
    assign_owner_rows = (
        packet_summary.get("assign_owner")
        or packet_summary.get("owner_follow_up")
        or ledger_summary.get("assign_owner_entities")
        or "unknown"
    )
    packet_rows = (
        packet_summary.get("entities")
        or packet_summary.get("total_rows")
        or (
            packet_summary.get("owner_follow_up", 0)
            + packet_summary.get("review_worthy_research", packet_summary.get("continue_research", 0))
        )
        or "unknown"
    )
    lines = [
        "# Blessed Current Radar Run",
        "",
        "This folder is the small, current-state pointer for the radar. It does not delete older experiment folders; it tells us which artifacts to trust first.",
        "",
        f"- Source run: `{manifest['source_run_dir']}`",
        f"- Generated at: `{manifest['generated_at']}`",
        f"- Decision packet rows: {packet_rows}",
        f"- Assign Owner rows: {assign_owner_rows}",
        f"- Unsafe promotion policy: {manifest['policy']['assign_owner_gate']}",
        "",
        "## Files",
        "",
        "- `partner-decision-packet.json`",
        "- `ledger-action-report.json`",
        "- `run-manifest.json`",
    ]
    if "source-yield-validation-report.json" in manifest.get("decision_artifacts", []):
        lines.append("- `source-yield-validation-report.json`")
    if "source-yield-validation-report.md" in manifest.get("decision_artifacts", []):
        lines.append("- `source-yield-validation-report.md`")
    if "source-yield-repeatability-report.json" in manifest.get("decision_artifacts", []):
        lines.append("- `source-yield-repeatability-report.json`")
    if "source-yield-repeatability-report.md" in manifest.get("decision_artifacts", []):
        lines.append("- `source-yield-repeatability-report.md`")
    if "targeted-manual-enrichment.json" in manifest.get("decision_artifacts", []):
        lines.append("- `targeted-manual-enrichment.json`")
    lines.extend(
        [
            "",
            "Older `docs/radar-runs/current-*` folders are historical experiments unless this manifest points at them.",
            "",
        ]
    )
    return "\n".join(lines)


def write_blessed_current_run(
    *,
    source_run_dir: Path | str,
    current_dir: Path | str,
    partner_decision_packet: Path | str,
    ledger_action_report: Path | str,
    source_yield_validation_report: Path | str | None = None,
    source_yield_validation_markdown: Path | str | None = None,
    source_yield_repeatability_report: Path | str | None = None,
    source_yield_repeatability_markdown: Path | str | None = None,
    targeted_manual_enrichment_report: Path | str | None = None,
    prune_current: bool = False,
) -> dict:
    source_run = Path(source_run_dir)
    current = Path(current_dir)
    partner_src = Path(partner_decision_packet)
    ledger_src = Path(ledger_action_report)
    report_src = Path(source_yield_validation_report) if source_yield_validation_report else None
    report_md_src = Path(source_yield_validation_markdown) if source_yield_validation_markdown else None
    repeatability_src = Path(source_yield_repeatability_report) if source_yield_repeatability_report else None
    repeatability_md_src = Path(source_yield_repeatability_markdown) if source_yield_repeatability_markdown else None
    targeted_manual_src = Path(targeted_manual_enrichment_report) if targeted_manual_enrichment_report else None
    if source_run.resolve() == current.resolve():
        raise ValueError("source_run_dir and current_dir must be different paths")
    current.mkdir(parents=True, exist_ok=True)

    partner_dst = current / "partner-decision-packet.json"
    ledger_dst = current / "ledger-action-report.json"
    report_dst = current / "source-yield-validation-report.json"
    report_md_dst = current / "source-yield-validation-report.md"
    repeatability_dst = current / "source-yield-repeatability-report.json"
    repeatability_md_dst = current / "source-yield-repeatability-report.md"
    targeted_manual_dst = current / "targeted-manual-enrichment.json"
    manifest_path = current / "run-manifest.json"
    manifest = build_current_run_manifest(
        source_run_dir=source_run,
        current_dir=current,
        partner_decision_packet=partner_src,
        ledger_action_report=ledger_src,
        source_yield_validation_report=report_src,
        source_yield_validation_markdown=report_md_src,
        source_yield_repeatability_report=repeatability_src,
        source_yield_repeatability_markdown=repeatability_md_src,
        targeted_manual_enrichment_report=targeted_manual_src,
    )
    if prune_current:
        keep_names = set(REQUIRED_ARTIFACTS + OPTIONAL_ARTIFACTS)
        for child in current.iterdir():
            if child.name not in keep_names:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
    _copy_json(partner_src, partner_dst, {"summary": {"source_missing": str(partner_src)}, "items": []})
    _copy_json(ledger_src, ledger_dst, {"summary": {"source_missing": str(ledger_src)}, "actions": []})
    if report_src:
        _copy_json(report_src, report_dst, {"summary": {"source_missing": str(report_src)}})
    elif report_dst.exists():
        report_dst.unlink()
    if report_md_src and report_md_src.exists():
        shutil.copyfile(report_md_src, report_md_dst)
    elif report_md_dst.exists():
        report_md_dst.unlink()
    if repeatability_src:
        _copy_json(repeatability_src, repeatability_dst, {"summary": {"source_missing": str(repeatability_src)}})
    elif repeatability_dst.exists():
        repeatability_dst.unlink()
    if repeatability_md_src and repeatability_md_src.exists():
        shutil.copyfile(repeatability_md_src, repeatability_md_dst)
    elif repeatability_md_dst.exists():
        repeatability_md_dst.unlink()
    if targeted_manual_src:
        _copy_json(targeted_manual_src, targeted_manual_dst, {"summary": {"source_missing": str(targeted_manual_src)}})
    elif targeted_manual_dst.exists():
        targeted_manual_dst.unlink()
    manifest_path.write_text(json.dumps(manifest, indent=2))
    (current / "README.md").write_text(_readme_text(manifest, _read_json(partner_dst), _read_json(ledger_dst)))
    return {
        "current_dir": str(current),
        "manifest": str(manifest_path),
        "required_artifacts": list(REQUIRED_ARTIFACTS),
    }


def _parse_args(argv: list[str]) -> dict:
    args = {}
    index = 0
    while index < len(argv):
        if argv[index].startswith("--"):
            key = argv[index][2:].replace("-", "_")
            if index + 1 < len(argv) and not argv[index + 1].startswith("--"):
                args[key] = argv[index + 1]
                index += 2
            else:
                args[key] = True
                index += 1
        else:
            index += 1
    return args


def main() -> None:
    args = _parse_args(sys.argv[1:])
    result = write_blessed_current_run(
        source_run_dir=Path(args["source_run_dir"]),
        current_dir=Path(args["current_dir"]),
        partner_decision_packet=Path(args["partner_decision_packet"]),
        ledger_action_report=Path(args["ledger_action_report"]),
        source_yield_validation_report=Path(args["source_yield_validation_report"]) if args.get("source_yield_validation_report") else None,
        source_yield_validation_markdown=Path(args["source_yield_validation_markdown"]) if args.get("source_yield_validation_markdown") else None,
        source_yield_repeatability_report=Path(args["source_yield_repeatability_report"]) if args.get("source_yield_repeatability_report") else None,
        source_yield_repeatability_markdown=Path(args["source_yield_repeatability_markdown"]) if args.get("source_yield_repeatability_markdown") else None,
        targeted_manual_enrichment_report=Path(args["targeted_manual_enrichment_report"]) if args.get("targeted_manual_enrichment_report") else None,
        prune_current=bool(args.get("prune_current")),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
