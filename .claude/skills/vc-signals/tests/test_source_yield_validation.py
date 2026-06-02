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


def test_review_worthy_accepts_hard_commercial_proof_for_launch_rows():
    from source_yield_validation import is_net_new_review_worthy_candidate

    row = _candidate(
        source_lane="Product Hunt",
        founders=[],
        founder_profiles=["https://www.producthunt.com/@alex"],
        stage="",
        raised="",
        headcount="",
        pricing_evidence=["https://clipto.ai/pricing"],
        docs_evidence=["https://clipto.ai/docs"],
        customer_buyer_evidence=["https://clipto.ai/customers"],
    )

    assert is_net_new_review_worthy_candidate(row) is True


def test_review_worthy_still_rejects_launch_rows_without_hard_commercial_proof():
    from source_yield_validation import is_net_new_review_worthy_candidate

    row = _candidate(
        source_lane="Product Hunt",
        founders=[],
        founder_profiles=["https://www.producthunt.com/@alex"],
        stage="",
        raised="",
        headcount="",
    )

    assert is_net_new_review_worthy_candidate(row) is False


def test_validation_counts_hard_evidence_product_hunt_rows_as_review_worthy(tmp_path):
    from source_yield_validation import build_source_yield_validation_report

    run_dir = tmp_path / "run"
    _write_json(run_dir / "candidates.json", [])
    _write_json(
        run_dir / "weekly-focus.json",
        {"workflow_view": {"Assign owner": [{"name": "Voker", "recommended_action": "Assign owner"}]}},
    )
    _write_json(run_dir / "runtime-ledger.json", {"source_health": []})
    _write_json(
        run_dir / "2026-06-01-raw-evidence.json",
        {
            "product_hunt": [
                {
                    "name": "Copycat Cafe",
                    "domain": "copycatcafe.com",
                    "website": "https://copycatcafe.com",
                    "product_hunt_url": "https://www.producthunt.com/products/copycat-cafe",
                    "maker_profiles": ["https://www.producthunt.com/@maker"],
                    "pricing_evidence": ["https://copycatcafe.com/pricing"],
                    "customer_buyer_evidence": ["https://copycatcafe.com/customers"],
                    "action": "research deeper",
                }
            ],
            "x_launches": [],
        },
    )

    report = build_source_yield_validation_report(run_dir, target_review_worthy_count=1)

    assert report["goal_assessment"]["net_new_review_worthy_count"] == 1
    assert report["review_worthy_rows"][0]["name"] == "Copycat Cafe"


def test_validation_rejects_rows_with_hard_evidence_identity_risk(tmp_path):
    from source_yield_validation import build_source_yield_validation_report

    run_dir = tmp_path / "run"
    _write_json(run_dir / "candidates.json", [])
    _write_json(
        run_dir / "weekly-focus.json",
        {"workflow_view": {"Assign owner": [{"name": "Voker", "recommended_action": "Assign owner"}]}},
    )
    _write_json(run_dir / "runtime-ledger.json", {"source_health": []})
    _write_json(
        run_dir / "2026-06-01-raw-evidence.json",
        {
            "product_hunt": [
                {
                    "name": "Sentinel",
                    "domain": "sentinelmarine.net",
                    "website": "https://www.sentinelmarine.net/api",
                    "product_hunt_url": "https://www.producthunt.com/products/sentinel-10",
                    "maker_profiles": ["https://www.producthunt.com/@maker"],
                    "pricing_evidence": ["https://www.sentinelmarine.net/pricing"],
                    "action": "research deeper",
                    "hard_evidence_dossier": {
                        "identity_risk_flags": ["ambiguous_official_domain_candidates"],
                        "official_domain_candidates": [
                            {"domain": "sentinel.co", "score": 130},
                            {"domain": "sentinelmarine.net", "score": 120},
                        ],
                    },
                }
            ],
            "x_launches": [],
        },
    )

    report = build_source_yield_validation_report(run_dir, target_review_worthy_count=1)

    assert report["goal_assessment"]["net_new_review_worthy_count"] == 0
    assert report["goal_assessment"]["partner_review_count"] == 0
    assert report["evidence_gap_queue"][0]["name"] == "Sentinel"


def test_partner_review_tier_accepts_credible_launches_before_strict_company_metadata(tmp_path):
    from source_yield_validation import (
        build_source_yield_decision_packet,
        build_source_yield_validation_report,
        render_source_yield_markdown,
    )

    run_dir = tmp_path / "run"
    _write_json(run_dir / "candidates.json", [])
    weekly_focus = {
        "workflow_view": {"Assign owner": [{"name": "Voker", "company_domain": "voker.ai"}]},
    }
    _write_json(run_dir / "weekly-focus.json", weekly_focus)
    _write_json(run_dir / "runtime-ledger.json", {"source_health": []})
    _write_json(
        run_dir / "2026-06-01-raw-evidence.json",
        {
            "product_hunt": [
                {
                    "name": "AgentFence",
                    "domain": "agentfence.dev",
                    "website": "https://agentfence.dev",
                    "product_hunt_url": "https://www.producthunt.com/products/agentfence",
                    "tagline": "Permission firewall for AI agents",
                    "maker_profiles": ["https://www.producthunt.com/@ada"],
                    "source_outbound_urls": ["https://agentfence.dev", "https://agentfence.dev/about"],
                    "action": "research deeper",
                }
            ],
            "x_launches": [
                {
                    "company_name": "BuildGraph",
                    "domain": "buildgraph.dev",
                    "website": "https://buildgraph.dev",
                    "url": "https://x.com/founder/status/1",
                    "snippet": "Launching a workflow graph for developer teams.",
                    "founder_profiles": ["https://x.com/founder"],
                    "source_outbound_urls": ["https://buildgraph.dev"],
                    "action": "watch",
                }
            ],
        },
    )

    report = build_source_yield_validation_report(
        run_dir,
        target_review_worthy_count=1,
        target_partner_review_count=2,
    )
    packet = build_source_yield_decision_packet(report, weekly_focus)
    markdown = render_source_yield_markdown(report)

    assert report["goal_assessment"]["net_new_review_worthy_count"] == 0
    assert report["goal_assessment"]["partner_review_count"] == 2
    assert report["target_status"]["partner_review_companies"]["met"] is True
    assert [row["name"] for row in report["partner_review_companies"]] == ["AgentFence", "BuildGraph"]
    assert report["partner_review_companies"][0]["confidence_grade"] == "C"
    assert "commercial_or_customer_signal_missing" in report["partner_review_companies"][0]["missing_evidence"]
    assert packet["summary"]["partner_review_companies"] == 2
    assert packet["sections"]["partner_review_companies"][0]["recommended_manual_check"]
    assert "## Partner Review Companies" in markdown
    assert "AgentFence" in markdown


def test_manual_evidence_queue_has_promote_and_discard_guidance(tmp_path):
    from source_yield_validation import build_source_yield_decision_packet, build_source_yield_validation_report

    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "candidates.json",
        [
            _candidate(),
            _candidate(
                name="SignalForge",
                domain="signalforge.ai",
                source_lane="Manual Web",
                weekly_tag="NEW",
                action="research deeper",
                founders=[],
                stage="",
                raised="",
                headcount="",
                source_outbound_urls=["https://signalforge.ai"],
            ),
        ],
    )
    weekly_focus = {"workflow_view": {"Assign owner": [{"name": "Voker", "company_domain": "voker.ai"}]}}
    _write_json(run_dir / "weekly-focus.json", weekly_focus)
    _write_json(run_dir / "runtime-ledger.json", {"source_health": []})
    _write_json(run_dir / "2026-06-01-raw-evidence.json", {})

    report = build_source_yield_validation_report(run_dir, target_review_worthy_count=1)
    packet = build_source_yield_decision_packet(report, weekly_focus)

    manual_row = next(row for row in report["manual_evidence_queue"] if row["name"] == "SignalForge")
    assert manual_row["promote_if"]
    assert manual_row["discard_if"]
    assert manual_row["recommended_manual_check"]
    assert manual_row["likely_payoff"]
    assert "manual_evidence_queue" in packet["sections"]
    assert packet["sections"]["manual_evidence_queue"][0]["promote_if"]


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
    assert report["source_diversity"]["review_worthy_rows_by_source_lane"]["hn"] == 1
    assert report["source_diversity"]["source_diversity_proven"] is True
    assert report["ledger_partner_packet_warning"]["unsafe_for_blessed_decision"] is True
    assert "last30days sector queries were degraded" in report["caveats"][0]


def test_validation_report_includes_llm_signal_investigation_summary(tmp_path):
    from source_yield_validation import build_source_yield_validation_report, render_source_yield_markdown

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
                    }
                ]
            }
        },
    )
    _write_json(run_dir / "runtime-ledger.json", {"source_health": []})
    _write_json(
        run_dir / "2026-06-01-raw-evidence.json",
        {
            "github": [{"full_name": "pullfrog/pullfrog"}],
            "product_hunt": [{"name": "AgentFence"}],
            "x_launches": [{"name": "Envio"}],
            "yc_directory": [],
        },
    )
    _write_json(
        run_dir / "signal-investigation.json",
        {
            "summary": {
                "enabled": True,
                "provider_mode": "llm",
                "rows_considered": 12,
                "rows_investigated": 8,
                "search_queries_planned": 18,
                "search_queries_run": 10,
                "official_domains_resolved": 3,
                "url_roles_classified": 21,
                "unsafe_domain_attempts_blocked": 4,
            },
            "items": [
                {"source_lane": "Product Hunt"},
                {"source_lane": "X"},
                {"source_lane": "OSS"},
                {"source_lane": "Hacker News"},
            ],
        },
    )

    report = build_source_yield_validation_report(run_dir, target_review_worthy_count=1)
    markdown = render_source_yield_markdown(report)

    summary = report["llm_signal_investigation_summary"]
    assert summary["enabled"] is True
    assert summary["provider_mode"] == "llm"
    assert summary["rows_investigated"] == 8
    assert summary["official_domains_resolved"] == 3
    assert summary["unsafe_domain_attempts_blocked"] == 4
    assert summary["source_lanes_investigated"] == ["Hacker News", "OSS", "Product Hunt", "X"]
    assert summary["completion_ready"] is True
    assert "## Harness LLM Signal Investigation" in markdown
    assert "provider_mode=llm" in markdown


def test_validation_report_treats_harness_signal_investigation_as_completion_ready(tmp_path):
    from source_yield_validation import build_source_yield_validation_report, render_source_yield_markdown

    run_dir = tmp_path / "run"
    _write_json(run_dir / "candidates.json", [_candidate()])
    _write_json(run_dir / "weekly-focus.json", {"workflow_view": {"Assign owner": []}})
    _write_json(run_dir / "runtime-ledger.json", {"source_health": []})
    _write_json(run_dir / "2026-06-01-raw-evidence.json", {"product_hunt": [{"name": "AgentFence"}]})
    _write_json(
        run_dir / "signal-investigation.json",
        {
            "summary": {
                "enabled": True,
                "provider_mode": "harness_llm",
                "planner_mode": "heuristic_fallback",
                "rows_considered": 2,
                "rows_investigated": 2,
                "search_queries_planned": 4,
                "search_queries_run": 2,
                "official_domains_resolved": 1,
                "url_roles_classified": 5,
                "unsafe_domain_attempts_blocked": 1,
                "harness_llm": {"status": "default", "runtime": "Claude Code or Codex harness"},
                "direct_llm_api": {"enabled": False, "status": "disabled_by_default"},
            },
            "items": [{"source_lane": "Product Hunt"}],
        },
    )

    report = build_source_yield_validation_report(run_dir, target_review_worthy_count=1)
    markdown = render_source_yield_markdown(report)

    summary = report["llm_signal_investigation_summary"]
    assert summary["provider_mode"] == "harness_llm"
    assert summary["planner_mode"] == "heuristic_fallback"
    assert summary["harness_llm"]["status"] == "default"
    assert summary["direct_llm_api"]["status"] == "disabled_by_default"
    assert summary["completion_ready"] is True
    assert "provider_mode=harness_llm" in markdown
    assert "direct_llm_api=disabled_by_default" in markdown


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
    assert packet["summary"]["review_worthy_companies"] == 1
    assert packet["summary"]["review_worthy_research"] == 1
    assert packet["sections"]["owner_follow_up"][0]["name"] == "Voker"
    assert packet["sections"]["review_worthy_companies"][0]["name"] == "Goldbridge"
    assert packet["sections"]["review_worthy_research"][0]["name"] == "Goldbridge"


def test_validation_report_promotes_oss_market_signals_and_gap_queue(tmp_path):
    from source_yield_validation import (
        build_source_yield_decision_packet,
        build_source_yield_validation_report,
        render_source_yield_markdown,
    )

    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "candidates.json",
        [
            _candidate(),
            _candidate(
                name="redwoodjs/agent-ci",
                domain="agent-ci.dev",
                source_lane="OSS",
                candidate_type="oss_project",
                source="https://github.com/redwoodjs/agent-ci",
                sources=["https://github.com/redwoodjs/agent-ci"],
                theme="Emerging technical signal",
                market_sector="Devtools",
                weekly_tag="NEW",
                action="watch",
                founders=[],
                stage="",
                raised="",
                headcount="",
                stars=700,
                stars_30d=90,
                repo_age_days=100,
                identity_type="oss_with_commercial_intent",
                missing_owner_evidence=["OSS/project-only row"],
                why_on_radar="Agent-CI is local GitHub Actions for agents. +90 stars in 30d.",
            ),
        ],
    )
    weekly_focus = {
        "workflow_view": {
            "Assign owner": [
                {
                    "name": "Voker",
                    "company_domain": "voker.ai",
                    "recommended_action": "Assign owner",
                }
            ]
        }
    }
    _write_json(run_dir / "weekly-focus.json", weekly_focus)
    _write_json(run_dir / "runtime-ledger.json", {"source_health": []})
    _write_json(run_dir / "2026-05-31-raw-evidence.json", {"github": [{}], "product_hunt": [], "x_launches": [], "yc_directory": []})
    _write_json(run_dir / "hn-launch-trial" / "hn-trial-row-review.json", {"summary": {"rows": 1, "action_split": {"Assign owner": 1}}})

    report = build_source_yield_validation_report(run_dir, target_review_worthy_count=1)
    packet = build_source_yield_decision_packet(report, weekly_focus)
    markdown = render_source_yield_markdown(report)

    assert report["two_track_summary"]["review_worthy_companies"] == 1
    assert report["two_track_summary"]["review_worthy_market_signals"] == 1
    assert report["review_worthy_market_signals"][0]["name"] == "redwoodjs/agent-ci"
    assert report["review_worthy_market_signals"][0]["theme"] == "Devtools workflow automation"
    assert report["evidence_gap_queue"][0]["name"] == "redwoodjs/agent-ci"
    assert packet["summary"]["review_worthy_market_signals"] == 1
    assert packet["sections"]["review_worthy_market_signals"][0]["promotion_path"].startswith("Review-Worthy Market Signal")
    assert "## Review-Worthy Market Signals" in markdown
    assert "## Evidence Gap Queue" in markdown


def test_validation_report_uses_latest_raw_evidence_and_reports_source_diversity(tmp_path):
    from source_yield_validation import build_source_yield_validation_report, render_source_yield_markdown

    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "candidates.json",
        [
            _candidate(),
            _candidate(
                name="Clipto",
                domain="clipto.com",
                source_lane="Product Hunt",
                founders=["Asha Mehta"],
                stage="SEED",
                raised=1200000,
                headcount=8,
            ),
        ],
    )
    _write_json(
        run_dir / "weekly-focus.json",
        {
            "workflow_view": {
                "Assign owner": [
                    {
                        "name": "Voker",
                        "company_domain": "voker.ai",
                        "recommended_action": "Assign owner",
                    }
                ]
            }
        },
    )
    _write_json(run_dir / "runtime-ledger.json", {"source_health": []})
    _write_json(run_dir / "2026-05-30-raw-evidence.json", {"product_hunt": [], "github": [], "yc_directory": [], "x_launches": []})
    _write_json(
        run_dir / "2026-05-31-raw-evidence.json",
        {
            "product_hunt": [
                {"name": "Clipto", "domain": "clipto.com"},
                {
                    "name": "Unresolved",
                    "domain": "",
                    "outbound_url": "https://www.producthunt.com/r/abc123",
                },
            ],
            "x_launches": [{"name": "Signal", "website": "https://signalco.ai"}],
            "github": [{}],
            "yc_directory": [{}],
        },
    )
    _write_json(run_dir / "hn-launch-trial" / "hn-trial-row-review.json", {"summary": {"rows": 2}})

    report = build_source_yield_validation_report(run_dir, target_review_worthy_count=2)

    assert report["source_counts"]["product_hunt"] == 2
    assert report["source_counts"]["x_launches"] == 1
    assert report["source_diversity"]["review_worthy_rows_by_source_lane"]["product_hunt"] == 1
    assert report["source_diversity"]["review_worthy_rows_by_source_lane"]["yc_directory"] == 1
    assert report["source_diversity"]["non_yc_review_worthy_count"] == 1
    assert report["source_diversity"]["source_diversity_proven"] is True
    assert report["source_diversity"]["raw_domain_resolution"]["product_hunt"]["resolved_domains"] == 1
    assert "Non-YC review-worthy rows: 1" in render_source_yield_markdown(report)


def test_validation_report_includes_targets_and_operational_gap_buckets(tmp_path):
    from source_yield_validation import build_source_yield_validation_report, render_source_yield_markdown

    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "candidates.json",
        [
            _candidate(),
            _candidate(
                name="AgentFence",
                domain="agentfence.dev",
                source_lane="Product Hunt",
                weekly_tag="NEW",
                action="research deeper",
                founders=[],
                stage="",
                raised="",
                headcount="",
                customer_buyer_evidence=[],
                missing_owner_evidence=["pricing_docs_or_careers_missing"],
            ),
        ],
    )
    _write_json(
        run_dir / "weekly-focus.json",
        {"workflow_view": {"Assign owner": [{"name": "Voker", "company_domain": "voker.ai"}]}},
    )
    _write_json(run_dir / "runtime-ledger.json", {"source_health": []})
    _write_json(run_dir / "2026-05-31-raw-evidence.json", {"product_hunt": [{"name": "AgentFence", "domain": "agentfence.dev"}]})

    report = build_source_yield_validation_report(run_dir, target_review_worthy_count=1)
    markdown = render_source_yield_markdown(report)

    assert report["source_yield_targets"]["assign_owner"]["min"] == 1
    assert report["source_yield_targets"]["unsafe_promotions"]["max"] == 0
    assert report["target_status"]["unsafe_promotions"]["met"] is True
    assert report["structured_provider_decision"]["status"] == "public_sources_still_sufficient_for_next_pass"
    gap = report["evidence_gap_queue"][0]
    assert gap["name"] == "AgentFence"
    assert gap["gap_buckets"]["founder_team"]["status"] == "missing"
    assert gap["gap_buckets"]["stage_funding_headcount"]["status"] == "missing"
    assert gap["gap_buckets"]["commercial_customer_signal"]["status"] == "missing"
    assert gap["gap_buckets"]["pricing_docs_careers"]["status"] == "missing"
    assert "LinkedIn" in gap["manual_check_sources"]
    assert gap["recommended_manual_check"]
    assert gap["recommended_next_step"]
    assert gap["manual_work_required"] is True
    assert gap["promote_if"]
    assert gap["discard_if"]
    assert gap["likely_payoff"]
    assert "## Source-Yield Targets" in markdown
    assert "Review-Worthy Companies" in markdown


def test_source_yield_targets_treat_above_max_as_not_met():
    from source_yield_validation import _source_yield_targets, _target_status

    status = _target_status(
        _source_yield_targets(target_review_worthy_count=8, target_partner_review_count=8),
        {
            "assign_owner": 1,
            "partner_review_companies": 19,
            "review_worthy_companies": 16,
            "review_worthy_market_signals": 5,
            "evidence_gap_queue": 12,
            "unsafe_promotions": 0,
        },
    )

    assert status["partner_review_companies"]["met"] is False
    assert status["partner_review_companies"]["status"] == "above_max"
    assert status["review_worthy_companies"]["met"] is False
    assert status["review_worthy_companies"]["status"] == "above_max"


def test_structured_provider_decision_recommends_trial_when_public_sources_miss_company_target(tmp_path):
    from source_yield_validation import build_source_yield_validation_report

    run_dir = tmp_path / "run"
    _write_json(run_dir / "candidates.json", [_candidate()])
    _write_json(
        run_dir / "weekly-focus.json",
        {"workflow_view": {"Assign owner": [{"name": "Voker", "company_domain": "voker.ai"}]}},
    )
    _write_json(run_dir / "runtime-ledger.json", {"source_health": []})
    _write_json(run_dir / "2026-05-31-raw-evidence.json", {"product_hunt": [{"name": "AgentFence", "domain": ""}]})
    _write_json(
        run_dir / "targeted-manual-enrichment.json",
        {"summary": {"targets_enriched": 5, "items_seen": 0, "queries_run": 20}},
    )

    report = build_source_yield_validation_report(run_dir, target_review_worthy_count=8)

    decision = report["structured_provider_decision"]
    assert decision["status"] == "recommend_structured_provider_trial"
    assert decision["best_unlock"] == "Coresignal or Crunchbase-style company metadata"
    assert "Review-Worthy Company target missed" in decision["reasons"]


def test_repeatability_report_compares_multiple_validation_runs(tmp_path):
    from source_yield_validation import build_repeatability_validation_report

    first = tmp_path / "run-a"
    second = tmp_path / "run-b"
    for run_dir, ph_count in ((first, 1), (second, 2)):
        _write_json(run_dir / "candidates.json", [_candidate()])
        _write_json(
            run_dir / "weekly-focus.json",
            {"workflow_view": {"Assign owner": [{"name": "Voker", "company_domain": "voker.ai"}]}},
        )
        _write_json(run_dir / "runtime-ledger.json", {"source_health": []})
        _write_json(
            run_dir / "2026-05-31-raw-evidence.json",
            {"product_hunt": [{"name": f"PH {idx}", "domain": f"ph{idx}.dev"} for idx in range(ph_count)]},
        )

    repeatability = build_repeatability_validation_report([first, second], target_review_worthy_count=1)

    assert repeatability["summary"]["runs_compared"] == 2
    assert repeatability["summary"]["repeatability_proven"] is True
    assert repeatability["summary"]["unsafe_promotions_total"] == 0
    assert repeatability["runs"][0]["review_worthy_companies"] == 1
    assert repeatability["source_lane_totals"]["product_hunt"]["raw_launches"] == 3


def test_raw_product_hunt_and_x_launches_feed_gap_queue_when_not_candidates(tmp_path):
    from source_yield_validation import build_source_yield_validation_report

    run_dir = tmp_path / "run"
    _write_json(run_dir / "candidates.json", [_candidate()])
    _write_json(
        run_dir / "weekly-focus.json",
        {"workflow_view": {"Assign owner": [{"name": "Voker", "company_domain": "voker.ai"}]}},
    )
    _write_json(run_dir / "runtime-ledger.json", {"source_health": []})
    _write_json(
        run_dir / "2026-05-31-raw-evidence.json",
        {
            "product_hunt": [
                {
                    "name": "AgentFence",
                    "domain": "agentfence.dev",
                    "product_hunt_url": "https://www.producthunt.com/products/agentfence",
                    "tagline": "Permission firewall for AI agents",
                    "missing_evidence": ["stage_funding_or_headcount_missing"],
                }
            ],
            "x_launches": [
                {
                    "company_name": "BuildGraph",
                    "url": "https://x.com/founder/status/1",
                    "snippet": "Testing an early workflow graph for developer teams.",
                    "missing_evidence": ["official_domain_identity_not_confirmed"],
                    "action": "watch",
                }
            ],
        },
    )

    report = build_source_yield_validation_report(run_dir, target_review_worthy_count=1)

    gap_names = {row["name"] for row in report["evidence_gap_queue"]}
    assert {"AgentFence", "BuildGraph"} <= gap_names
    for row in report["evidence_gap_queue"]:
        assert row["recommended_manual_check"]
        assert row["recommended_next_step"]
        assert row["manual_work_required"] is True
    assert report["source_diversity"]["candidate_rows_by_source_lane"]["product_hunt"] == 1
    assert report["source_diversity"]["candidate_rows_by_source_lane"]["x"] == 1
