from __future__ import annotations

import json


def test_build_current_run_manifest_points_to_blessed_artifacts(tmp_path):
    from bless_current_run import build_current_run_manifest

    run_dir = tmp_path / "source-run"
    run_dir.mkdir()
    (run_dir / "weekly-focus.json").write_text(json.dumps({"partner_focus": []}))
    (run_dir / "runtime-ledger.json").write_text(json.dumps({"source_health": []}))
    current_dir = tmp_path / "current"

    manifest = build_current_run_manifest(
        source_run_dir=run_dir,
        current_dir=current_dir,
        partner_decision_packet=current_dir / "partner-decision-packet.json",
        ledger_action_report=current_dir / "ledger-action-report.json",
    )

    assert manifest["source_run_dir"] == str(run_dir)
    assert manifest["blessed_current_dir"] == str(current_dir)
    assert manifest["required_artifacts"] == [
        "README.md",
        "partner-decision-packet.json",
        "ledger-action-report.json",
        "run-manifest.json",
    ]
    assert manifest["decision_artifacts"] == []
    assert manifest["policy"]["assign_owner_gate"] == "unchanged_high_confidence_only"


def test_write_blessed_current_run_can_prune_stale_pointer_files(tmp_path):
    from bless_current_run import write_blessed_current_run

    run_dir = tmp_path / "source-run"
    run_dir.mkdir()
    packet = run_dir / "partner-decision-packet.json"
    ledger = run_dir / "ledger-action-report.json"
    report = run_dir / "source-yield-validation-report.json"
    report_md = run_dir / "source-yield-validation-report.md"
    packet.write_text(json.dumps({"summary": {"owner_follow_up": 1}}))
    ledger.write_text(json.dumps({"summary": {"assign_owner_entities": 1}}))
    report.write_text(json.dumps({"goal_assessment": {"goal_reached": True}}))
    report_md.write_text("# Source Yield Validation\n")
    current_dir = tmp_path / "current"
    current_dir.mkdir()
    (current_dir / "stale-raw-evidence.json").write_text("{}")

    result = write_blessed_current_run(
        source_run_dir=run_dir,
        current_dir=current_dir,
        partner_decision_packet=packet,
        ledger_action_report=ledger,
        source_yield_validation_report=report,
        source_yield_validation_markdown=report_md,
        prune_current=True,
    )

    assert result["manifest"] == str(current_dir / "run-manifest.json")
    assert not (current_dir / "stale-raw-evidence.json").exists()
    assert (current_dir / "source-yield-validation-report.json").exists()
    manifest = json.loads((current_dir / "run-manifest.json").read_text())
    assert manifest["decision_artifacts"] == [
        "source-yield-validation-report.json",
        "source-yield-validation-report.md",
    ]
