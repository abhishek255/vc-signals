from __future__ import annotations

import json
from pathlib import Path


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def test_product_hunt_audit_classifies_redirect_and_web_failures(tmp_path):
    from source_debug_audit import build_product_hunt_audit

    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "2026-06-01-raw-evidence.json",
        {
            "product_hunt": [
                {
                    "name": "AgentFence",
                    "tagline": "Permission firewall for AI agents",
                    "product_hunt_url": "https://www.producthunt.com/products/agentfence",
                    "outbound_url": "https://www.producthunt.com/r/p/123?app_id=339",
                    "domain_resolution_status": "unresolved",
                    "domain_resolution_warning": "403 Forbidden; web resolver failed: last30days query timed out (8s)",
                },
                {
                    "name": "ClipTo",
                    "domain": "clipto.ai",
                    "website": "https://clipto.ai",
                    "domain_resolution_status": "resolved",
                },
            ]
        },
    )

    audit = build_product_hunt_audit(run_dir)

    assert audit["total_launches"] == 2
    assert audit["resolved_launches"] == 1
    assert audit["unresolved_launches"] == 1
    assert audit["failure_cause_counts"]["product_hunt_redirect_403"] == 1
    assert audit["failure_cause_counts"]["web_resolver_timeout"] == 1
    row = audit["unresolved"][0]
    assert row["fields_product_hunt_provided"]["has_outbound_url"] is True
    assert row["manual_resolver_query"] == '"AgentFence" "Permission firewall for AI agents" official website'


def test_x_audit_records_empty_runtime_health(tmp_path):
    from source_debug_audit import build_x_audit

    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "runtime-ledger.json",
        {"source_health": [{"source": "x_launches", "status": "empty", "fresh_items": 0, "warnings": ["concentrated"]}]},
    )
    _write_json(run_dir / "source-yield-validation-report.json", {"source_counts": {"x_launches": 0}})

    audit = build_x_audit(run_dir)

    assert audit["observed_status"] == "empty"
    assert audit["observed_fresh_items"] == 0
    assert audit["observed_warnings"] == ["concentrated"]


def test_product_hunt_reprobe_records_resolved_domains_with_fake_resolver(tmp_path):
    from source_debug_audit import run_product_hunt_reprobe

    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "2026-06-01-raw-evidence.json",
        {
            "product_hunt": [
                {
                    "name": "AgentFence",
                    "tagline": "Permission firewall for AI agents",
                    "product_hunt_url": "https://www.producthunt.com/products/agentfence",
                    "outbound_url": "https://www.producthunt.com/r/p/123?app_id=339",
                    "domain_resolution_status": "unresolved",
                    "domain_resolution_warning": "403 Forbidden",
                }
            ]
        },
    )

    def fake_resolver(row, *, timeout_seconds):
        assert row["name"] == "AgentFence"
        assert timeout_seconds == 6
        return {
            "url": "https://agentfence.dev",
            "evidence": {"source": "web_fallback"},
        }

    reprobe = run_product_hunt_reprobe(run_dir, limit=1, timeout_seconds=6, resolver=fake_resolver)

    assert reprobe["attempted"] is True
    assert reprobe["attempted_count"] == 1
    assert reprobe["resolved_count"] == 1
    assert reprobe["attempts"][0]["domain"] == "agentfence.dev"
    assert reprobe["attempts"][0]["evidence_source"] == "web_fallback"


def test_evidence_gap_operational_audit_flags_missing_manual_fields(tmp_path):
    from source_debug_audit import build_evidence_gap_operational_audit

    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "source-yield-validation-report.json",
        {
            "evidence_gap_queue": [
                {
                    "name": "AgentFence",
                    "source_lane": "Product Hunt",
                    "missing_evidence": ["official_domain_missing"],
                },
                {
                    "name": "ClipTo",
                    "source_lane": "Product Hunt",
                    "recommended_manual_check": "Check pricing page.",
                    "recommended_next_step": "Check pricing page.",
                },
            ]
        },
    )

    audit = build_evidence_gap_operational_audit(run_dir)

    assert audit["evidence_gap_count"] == 2
    assert audit["rows_missing_operational_fields"] == 1
    assert audit["missing_rows"][0]["name"] == "AgentFence"
    assert audit["missing_rows"][0]["missing_operational_fields"] == [
        "recommended_manual_check",
        "recommended_next_step",
    ]


def test_source_debug_markdown_summarizes_core_sections(tmp_path):
    from source_debug_audit import build_source_debug_audit, render_markdown

    run_dir = tmp_path / "run"
    _write_json(run_dir / "2026-06-01-raw-evidence.json", {"product_hunt": []})
    _write_json(run_dir / "runtime-ledger.json", {"source_health": []})
    _write_json(run_dir / "source-yield-validation-report.json", {"evidence_gap_queue": []})

    audit = build_source_debug_audit(run_dir, x_probe=False)
    markdown = render_markdown(audit)

    assert "## Product Hunt" in markdown
    assert "## X" in markdown
    assert "## Evidence Gap Queue" in markdown
    assert "Coresignal skipped: `True`" in markdown
