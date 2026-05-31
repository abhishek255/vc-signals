from __future__ import annotations

import json
from pathlib import Path


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _candidate(**overrides) -> dict:
    row = {
        "name": "Goldbridge",
        "domain": "goldbridgebanking.com",
        "weekly_tag": "NEW",
        "action": "research deeper",
        "tier": "Watchlist",
        "source_lane": "YC Directory",
        "founders": ["Alvin Salehi"],
        "stage": "PRE_SEED",
        "raised": 500000,
        "headcount": 5,
    }
    row.update(overrides)
    return row


def test_review_worthy_requires_company_identity_founder_and_stage():
    from source_yield_validation import is_net_new_review_worthy_candidate

    assert is_net_new_review_worthy_candidate(_candidate()) is True
    assert is_net_new_review_worthy_candidate(_candidate(domain="")) is False
    assert is_net_new_review_worthy_candidate(_candidate(founders=[])) is False
    assert is_net_new_review_worthy_candidate(_candidate(stage="", raised="", headcount="")) is False
    assert is_net_new_review_worthy_candidate(_candidate(action="Assign owner")) is False


def test_validation_report_preserves_assign_owner_bar_and_flags_ledger_packet(tmp_path):
    from source_yield_validation import build_source_yield_validation_report

    run_dir = tmp_path / "run"
    _write_json(run_dir / "candidates.json", [_candidate()])
    _write_json(
        run_dir / "weekly-focus.json",
        {
            "workflow_view": {
                "Assign owner": [
                    {
                        "name": "Voker",
                        "company_domain": "voker.ai",
                        "recommended_action": "Assign owner",
                        "evidence_urls": ["https://voker.ai"],
                    }
                ]
            }
        },
    )
    _write_json(
        run_dir / "runtime-ledger.json",
        {
            "source_health": [
                {"source": "yc_directory", "status": "complete", "fresh_items": 1},
                {"source": "last30days:devtools", "status": "degraded", "fresh_items": 0},
            ],
            "source_access": {"summary": {"configured": ["Product Hunt API", "X"], "manual_mode": ["Crunchbase"]}},
        },
    )
    _write_json(run_dir / "2026-05-31-raw-evidence.json", {"yc_directory": [{}], "github": [], "product_hunt": [], "x_launches": []})
    _write_json(
        run_dir / "hn-launch-trial" / "hn-trial-row-review.json",
        {"summary": {"rows": 5, "action_split": {"Assign owner": 1}, "unsafe_promotions": 0}},
    )
    _write_json(run_dir / "company-discovery.json", {"summary": {"accepted": 1}})
    _write_json(run_dir / "manual-enrichment-targets.json", {"summary": {"targets": 1}})
    _write_json(
        run_dir / "final-partner-packet" / "partner-decision-packet.json",
        {
            "summary": {"owner_follow_up": 2},
            "sections": {
                "owner_follow_up": [
                    {"entity_name": "Voker"},
                    {"entity_name": "Goldbridge"},
                ]
            },
        },
    )

    report = build_source_yield_validation_report(run_dir, target_review_worthy_count=1)

    assert report["goal_assessment"]["goal_reached"] is True
    assert report["goal_assessment"]["assign_owner_names"] == ["Voker"]
    assert report["goal_assessment"]["net_new_review_worthy_count"] == 1
    assert report["source_counts"]["hn_launch_trial_rows"] == 5
    assert report["source_counts"]["hn_launch_assign_owner"] == 1
    assert report["ledger_partner_packet_warning"]["unsafe_for_blessed_decision"] is True
    assert "last30days sector queries were degraded" in report["caveats"][0]


def test_decision_packet_uses_only_weekly_assign_owner(tmp_path):
    from source_yield_validation import (
        build_source_yield_decision_packet,
        build_source_yield_validation_report,
    )

    run_dir = tmp_path / "run"
    _write_json(run_dir / "candidates.json", [_candidate()])
    weekly_focus = {
        "workflow_view": {
            "Assign owner": [
                {
                    "name": "Voker",
                    "company_domain": "voker.ai",
                    "recommended_action": "Assign owner",
                    "owner_readiness_score": 90,
                    "evidence_urls": ["https://voker.ai"],
                }
            ]
        }
    }
    _write_json(run_dir / "weekly-focus.json", weekly_focus)
    _write_json(run_dir / "runtime-ledger.json", {"source_health": []})
    _write_json(run_dir / "2026-05-31-raw-evidence.json", {})

    report = build_source_yield_validation_report(run_dir, target_review_worthy_count=1)
    packet = build_source_yield_decision_packet(report, weekly_focus)

    assert packet["summary"]["owner_follow_up"] == 1
    assert packet["summary"]["review_worthy_research"] == 1
    assert packet["sections"]["owner_follow_up"][0]["name"] == "Voker"
    assert packet["sections"]["review_worthy_research"][0]["name"] == "Goldbridge"
