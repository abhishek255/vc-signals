"""Tests for the persistent company/signal ledger."""

from __future__ import annotations

import json
from pathlib import Path


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _entity(ledger: dict, entity_id: str) -> dict:
    return next(entity for entity in ledger["entities"] if entity["entity_id"] == entity_id)


def test_ledger_schema_merges_domain_entities_and_preserves_history(tmp_path: Path):
    from signal_ledger import build_company_signal_ledger, write_ledger

    first_run = tmp_path / "current-all-sector-clean-validation-2026-05-23-v3"
    second_run = tmp_path / "current-weekly-hn-default-runtime-patch-validation-2026-05-24"
    _write_json(
        first_run / "candidates.json",
        [
            {
                "name": "BeeSafe AI",
                "domain": "www.beesafe.ai",
                "source": "https://beesafe.ai",
                "source_lane": "Grounded web",
                "lead_route": "research_deeper",
                "action": "Research deeper",
                "attio_status": "no_match",
                "identity_type": "verified_company",
                "missing_owner_evidence": ["no founder/team evidence"],
                "evidence_metadata": [{"source_url": "https://beesafe.ai"}],
            }
        ],
    )
    _write_json(
        second_run / "owner-readiness.json",
        {
            "items": [
                {
                    "candidate_key": "beesafe.ai",
                    "name": "BeeSafe AI",
                    "domain": "beesafe.ai",
                    "eligible": False,
                    "owner_readiness_score": 60,
                    "missing_owner_evidence": ["no stage/funding evidence"],
                    "recommended_owner_action": "Research deeper",
                    "recommended_next_validation_step": "Find stage/funding source",
                    "founder_team_evidence": ["https://beesafe.ai/about"],
                    "stage_funding_evidence": [],
                    "customer_buyer_pull_evidence": ["https://beesafe.ai/customers"],
                    "evidence_urls": ["https://beesafe.ai/about", "https://beesafe.ai/customers"],
                }
            ],
            "summary": {"eligible": 0, "skipped": 1},
        },
    )

    ledger = build_company_signal_ledger(
        [first_run, second_run],
        generated_at="2026-05-24T00:00:00Z",
    )
    out_path = write_ledger(ledger, tmp_path / "company_signal_ledger.json")
    saved = json.loads(out_path.read_text())
    entity = _entity(saved, "company:beesafe.ai")

    required_keys = {
        "entity_id",
        "name",
        "domain",
        "entity_type",
        "first_seen_run",
        "first_seen_date",
        "last_seen_run",
        "last_seen_date",
        "sightings_count",
        "source_lanes_seen",
        "current_route",
        "current_action",
        "best_historical_action",
        "attio_status_history",
        "attio_status_current",
        "evidence_dimensions",
        "missing_evidence",
        "latest_evidence_urls",
        "status_movement",
        "sighting_history",
    }
    assert required_keys <= set(entity)
    assert saved["schema_version"] == 1
    assert entity["domain"] == "beesafe.ai"
    assert entity["sightings_count"] == 2
    assert entity["first_seen_run"] == first_run.name
    assert entity["last_seen_run"] == second_run.name
    assert entity["current_action"] == "Research deeper"
    assert entity["best_historical_action"] == "Research deeper"
    assert entity["evidence_dimensions"] == {
        "identity": True,
        "founder": True,
        "stage": False,
        "customer_commercial": True,
    }
    assert entity["missing_evidence"] == ["no stage/funding evidence"]
    assert entity["attio_status_current"] == "no_match"
    assert entity["status_movement"] == "repeated"


def test_project_rows_do_not_merge_with_same_named_company(tmp_path: Path):
    from signal_ledger import build_company_signal_ledger

    run_dir = tmp_path / "current-weekly-hn-default-validation-2026-05-24"
    _write_json(
        run_dir / "weekly-focus.json",
        {
            "research_deeper_queue": [
                {
                    "id": "company:agentstack.ai",
                    "name": "AgentStack",
                    "company_domain": "agentstack.ai",
                    "recommended_action": "Research deeper",
                    "lead_route": "research_deeper",
                    "identity_type": "verified_company",
                    "evidence_urls": ["https://agentstack.ai"],
                    "missing_evidence": ["no stage/funding evidence"],
                }
            ],
            "oss_project_watch": [
                {
                    "id": "repo:github.com/acme/agentstack",
                    "name": "AgentStack",
                    "project_url": "https://github.com/acme/agentstack",
                    "recommended_action": "Research deeper",
                    "identity_type": "oss_project_watch",
                    "evidence_urls": ["https://github.com/acme/agentstack"],
                    "missing_evidence": ["OSS/project-only row"],
                }
            ],
        },
    )

    ledger = build_company_signal_ledger([run_dir], generated_at="2026-05-24T00:00:00Z")

    assert _entity(ledger, "company:agentstack.ai")["entity_type"] == "company"
    assert _entity(ledger, "project:github.com/acme/agentstack")["entity_type"] == "project"
    assert len(ledger["entities"]) == 2
    assert ledger["ambiguous_merges"]
    assert ledger["ambiguous_merges"][0]["reason"] == "same_name_different_entity_ids"


def test_voker_is_promoted_to_assign_owner_with_hn_history(tmp_path: Path):
    from signal_ledger import build_company_signal_ledger

    earlier = tmp_path / "current-owner-maturity-completion-2026-05-23"
    latest = tmp_path / "current-weekly-hn-default-runtime-patch-validation-2026-05-24"
    _write_json(
        earlier / "main-owner-readiness.json",
        {
            "items": [
                {
                    "candidate_key": "voker.ai",
                    "name": "Voker",
                    "domain": "voker.ai",
                    "recommended_owner_action": "Research deeper",
                    "recommended_next_validation_step": "Find founder/team source",
                    "missing_owner_evidence": ["no founder/team evidence", "no stage/funding evidence"],
                    "evidence_urls": ["https://voker.ai"],
                }
            ]
        },
    )
    _write_json(
        latest / "weekly-focus.json",
        {
            "partner_focus": [
                {
                    "id": "company:voker.ai",
                    "name": "Voker",
                    "company_domain": "voker.ai",
                    "recommended_action": "Assign owner",
                    "lead_route": "sourcing_candidate",
                    "attio_status": "no_match",
                    "identity_type": "verified_company",
                    "evidence_urls": [
                        "https://news.ycombinator.com/item?id=48109962",
                        "https://voker.ai",
                        "https://www.ycombinator.com/companies/voker",
                    ],
                    "missing_evidence": [],
                    "founder_team_evidence": ["https://www.ycombinator.com/companies/voker"],
                    "stage_funding_evidence": ["https://www.ycombinator.com/companies/voker"],
                    "customer_buyer_evidence": ["https://voker.ai"],
                }
            ]
        },
    )
    _write_json(
        latest / "hn-launch-trial" / "hn-trial-row-review.json",
        {
            "rows": [
                {
                    "name": "Voker",
                    "domain": "voker.ai",
                    "final_action": "Assign owner",
                    "completion_status": "completed_clean",
                    "attio_status": "no_match",
                    "evidence_dimensions": ["customer", "founder", "stage"],
                    "missing_evidence": [],
                    "unsafe_promotion": False,
                    "assign_owner_evidence_provenance": {
                        "hn_source": {"url": "https://news.ycombinator.com/item?id=48109962"},
                        "founder_evidence": {"url": "https://www.ycombinator.com/companies/voker"},
                        "stage_funding_evidence": {"url": "https://www.ycombinator.com/companies/voker"},
                        "commercial_customer_evidence": {"url": "https://voker.ai"},
                    },
                }
            ],
            "summary": {"unsafe_promotions": 0},
        },
    )

    ledger = build_company_signal_ledger([earlier, latest], generated_at="2026-05-24T00:00:00Z")
    voker = _entity(ledger, "company:voker.ai")

    assert voker["current_route"] == "Assign Owner"
    assert voker["current_action"] == "Assign owner"
    assert voker["best_historical_action"] == "Assign owner"
    assert voker["status_movement"] == "promoted"
    assert voker["source_lanes_seen"] == ["HN", "YC", "web"]
    assert voker["evidence_dimensions"] == {
        "identity": True,
        "founder": True,
        "stage": True,
        "customer_commercial": True,
    }
    assert len(voker["sighting_history"]) == 2


def test_arize_stays_category_context_after_too_late_demotions(tmp_path: Path):
    from signal_ledger import build_company_signal_ledger

    earlier = tmp_path / "current-owner-maturity-completion-2026-05-23"
    latest = tmp_path / "current-founder-stage-completion-2026-05-23"
    _write_json(
        earlier / "main-owner-readiness.json",
        {
            "items": [
                {
                    "candidate_key": "company:arize.com",
                    "name": "Arize",
                    "domain": "arize.com",
                    "recommended_owner_action": "Research deeper",
                    "missing_owner_evidence": ["no founder/team evidence", "no stage/funding evidence"],
                    "evidence_urls": ["https://arize.com/observe/"],
                }
            ]
        },
    )
    _write_json(
        latest / "owner-readiness.json",
        {
            "items": [
                {
                    "candidate_key": "arize.com",
                    "name": "Arize",
                    "domain": "arize.com",
                    "eligible": False,
                    "maturity_status": "likely_too_late",
                    "category_anchor": True,
                    "owner_readiness_score": 20,
                    "missing_owner_evidence": ["category context / mature incumbent"],
                    "recommended_owner_action": "Monitor only",
                    "recommended_next_validation_step": "category context / mature incumbent",
                    "evidence_urls": ["https://arize.com/"],
                    "query_status": "category_context_or_monitor_only",
                }
            ]
        },
    )

    ledger = build_company_signal_ledger([earlier, latest], generated_at="2026-05-24T00:00:00Z")
    arize = _entity(ledger, "company:arize.com")

    assert arize["entity_type"] == "market anchor"
    assert arize["current_route"] == "Category Context"
    assert arize["current_action"] == "Monitor only"
    assert arize["best_historical_action"] == "Research deeper"
    assert arize["status_movement"] == "demoted"
    assert arize["missing_evidence"] == ["category context / mature incumbent"]


def test_skipped_budget_hn_rows_are_tracked_as_incomplete_not_owner_ready(tmp_path: Path):
    from signal_ledger import build_company_signal_ledger

    run_dir = tmp_path / "current-weekly-hn-default-runtime-patch-validation-2026-05-24"
    _write_json(
        run_dir / "hn-launch-trial" / "hn-trial-row-review.json",
        {
            "rows": [
                {
                    "name": "Datapoint AI",
                    "domain": "trydatapoint.com",
                    "final_action": "Research deeper",
                    "completion_status": "skipped_budget",
                    "attio_status": "no_match",
                    "missing_evidence": ["no founder/team evidence", "no stage/funding evidence"],
                    "evidence_dimensions": ["customer"],
                    "unsafe_promotion": False,
                    "assign_owner_evidence_provenance": {
                        "hn_source": {"url": "https://news.ycombinator.com/item?id=1"},
                        "official_company_source": {"url": "https://trydatapoint.com"},
                    },
                }
            ],
            "summary": {"unsafe_promotions": 0},
        },
    )

    ledger = build_company_signal_ledger([run_dir], generated_at="2026-05-24T00:00:00Z")
    datapoint = _entity(ledger, "company:trydatapoint.com")

    assert datapoint["current_route"] == "Research Deeper"
    assert datapoint["current_action"] == "Research deeper"
    assert datapoint["evidence_dimensions"] == {
        "identity": True,
        "founder": False,
        "stage": False,
        "customer_commercial": True,
    }
    assert datapoint["missing_evidence"] == ["no founder/team evidence", "no stage/funding evidence"]
    assert datapoint["sighting_history"][0]["completion_status"] == "skipped_budget"
    assert datapoint["sighting_history"][0]["unsafe_promotion"] is False


def test_hn_outbound_skipped_candidate_not_elsewhere_is_added_to_ledger(tmp_path: Path):
    from signal_ledger import build_company_signal_ledger

    run_dir = tmp_path / "current-weekly-hn-default-runtime-patch-validation-2026-05-24"
    _write_json(
        run_dir / "hn-launch-trial" / "hn-outbound-enrichment.json",
        {
            "skipped_candidates": [
                {
                    "name": "Aide-memory",
                    "canonical_name": "Aide-memory",
                    "official_domain": "aide-memory.dev",
                    "source_url": "https://news.ycombinator.com/item?id=47979991",
                    "official_url": "https://www.aide-memory.dev/blog/launch",
                    "identity_type": "hn_outbound_candidate",
                    "identity_promotion_status": "skipped",
                    "lead_route": "research_deeper",
                    "recommended_action": "Research deeper",
                    "assign_owner": False,
                    "unsafe_promotion": False,
                    "partial": True,
                    "partial_reason": "max_candidates_exceeded",
                    "missing_evidence": ["max_candidates_exceeded"],
                }
            ],
            "summary": {"candidates_skipped": 1},
        },
    )

    ledger = build_company_signal_ledger([run_dir], generated_at="2026-05-24T00:00:00Z")
    aide_memory = _entity(ledger, "company:aide-memory.dev")

    assert aide_memory["name"] == "Aide-memory"
    assert aide_memory["domain"] == "aide-memory.dev"
    assert aide_memory["current_route"] == "Research Deeper"
    assert aide_memory["current_action"] == "Research deeper"
    assert aide_memory["best_historical_action"] == "Research deeper"
    assert aide_memory["missing_evidence"] == ["max_candidates_exceeded"]
    assert aide_memory["latest_evidence_urls"] == [
        "https://news.ycombinator.com/item?id=47979991",
        "https://www.aide-memory.dev/blog/launch",
    ]
    sighting = aide_memory["sighting_history"][0]
    assert sighting["canonical_name"] == "Aide-memory"
    assert sighting["source_file"] == "hn-launch-trial/hn-outbound-enrichment.json"
    assert sighting["raw_kind"] == "hn_skipped_candidate"
    assert sighting["completion_status"] == "skipped_budget"
    assert sighting["partial_reason"] == "max_candidates_exceeded"
    assert sighting["source_lanes"] == ["HN", "web"]
    assert sighting["unsafe_promotion"] is False


def test_hn_outbound_skipped_candidate_adds_latest_incomplete_sighting_to_existing_entity(tmp_path: Path):
    from signal_ledger import build_company_signal_ledger

    earlier = tmp_path / "current-all-sector-clean-validation-2026-05-23-v3"
    latest = tmp_path / "current-weekly-hn-default-runtime-patch-validation-2026-05-24"
    _write_json(
        earlier / "weekly-focus.json",
        {
            "research_deeper_queue": [
                {
                    "id": "company:trydatapoint.com",
                    "name": "Datapoint AI",
                    "company_domain": "trydatapoint.com",
                    "recommended_action": "Research deeper",
                    "lead_route": "research_deeper",
                    "identity_type": "verified_company",
                    "evidence_urls": ["https://trydatapoint.com"],
                    "missing_evidence": ["no founder/team evidence"],
                }
            ]
        },
    )
    _write_json(
        latest / "hn-launch-trial" / "hn-outbound-enrichment.json",
        {
            "skipped_candidates": [
                {
                    "name": "Datapoint AI",
                    "canonical_name": "Datapoint AI",
                    "official_domain": "trydatapoint.com",
                    "source_url": "https://news.ycombinator.com/item?id=48241139",
                    "official_url": "https://trydatapoint.com",
                    "identity_type": "hn_outbound_candidate",
                    "identity_promotion_status": "skipped",
                    "lead_route": "research_deeper",
                    "recommended_action": "Research deeper",
                    "assign_owner": False,
                    "partial": True,
                    "partial_reason": "max_candidates_exceeded",
                    "missing_evidence": ["max_candidates_exceeded"],
                }
            ]
        },
    )

    ledger = build_company_signal_ledger([earlier, latest], generated_at="2026-05-24T00:00:00Z")
    datapoint = _entity(ledger, "company:trydatapoint.com")

    assert datapoint["sightings_count"] == 2
    assert datapoint["current_route"] == "Research Deeper"
    assert datapoint["current_action"] == "Research deeper"
    assert datapoint["missing_evidence"] == ["max_candidates_exceeded"]
    assert datapoint["status_movement"] == "repeated"
    latest_sighting = datapoint["sighting_history"][-1]
    assert latest_sighting["source_file"] == "hn-launch-trial/hn-outbound-enrichment.json"
    assert latest_sighting["completion_status"] == "skipped_budget"
    assert latest_sighting["partial_reason"] == "max_candidates_exceeded"


def test_hn_outbound_skipped_candidate_never_becomes_assign_owner(tmp_path: Path):
    from signal_ledger import build_company_signal_ledger

    run_dir = tmp_path / "current-weekly-hn-default-runtime-patch-validation-2026-05-24"
    _write_json(
        run_dir / "hn-launch-trial" / "hn-outbound-enrichment.json",
        {
            "skipped_candidates": [
                {
                    "name": "Budget Skipped AI",
                    "canonical_name": "Budget Skipped AI",
                    "official_domain": "budgetskipped.ai",
                    "source_url": "https://news.ycombinator.com/item?id=9",
                    "official_url": "https://budgetskipped.ai",
                    "recommended_action": "Assign owner",
                    "assign_owner": True,
                    "partial": True,
                    "partial_reason": "max_candidates_exceeded",
                    "missing_evidence": ["max_candidates_exceeded"],
                }
            ]
        },
    )

    ledger = build_company_signal_ledger([run_dir], generated_at="2026-05-24T00:00:00Z")
    skipped = _entity(ledger, "company:budgetskipped.ai")

    assert skipped["current_route"] == "Research Deeper"
    assert skipped["current_action"] == "Research deeper"
    assert skipped["best_historical_action"] == "Research deeper"
    assert ledger["summary"]["assign_owner_entities"] == 0
    assert skipped["sighting_history"][0]["completion_status"] == "skipped_budget"


def test_weekly_cli_threads_optional_ledger_update_hook(tmp_path: Path, monkeypatch, capsys):
    import radar_run

    seen = {}

    def fake_run_weekly_artifacts(**kwargs):
        seen.update(kwargs)
        return {
            "weekly_focus": str(tmp_path / "weekly-focus.md"),
            "company_signal_ledger": str(tmp_path / "company_signal_ledger.json"),
        }

    monkeypatch.setattr(radar_run, "run_weekly_artifacts", fake_run_weekly_artifacts)
    monkeypatch.setattr(
        "sys.argv",
        [
            "radar_run.py",
            "weekly",
            "--output-dir",
            str(tmp_path),
            "--update-signal-ledger",
            "--signal-ledger-path",
            str(tmp_path / "company_signal_ledger.json"),
        ],
    )

    radar_run._cli_main()
    result = json.loads(capsys.readouterr().out)

    assert seen["update_signal_ledger"] is True
    assert seen["signal_ledger_path"] == tmp_path / "company_signal_ledger.json"
    assert result["company_signal_ledger"].endswith("company_signal_ledger.json")


def test_ledger_action_report_groups_promoted_demoted_repeated_skipped_and_stale_rows():
    from signal_ledger import build_ledger_action_report

    ledger = {
        "generated_at": "2026-05-24T00:00:00Z",
        "runs_backfilled": [
            {"run_id": "current-prior-run", "run_sequence": 0},
            {"run_id": "current-latest-run", "run_sequence": 1},
        ],
        "summary": {"entities": 5, "sightings": 8, "assign_owner_entities": 1, "unsafe_promotions": 0},
        "entities": [
            {
                "entity_id": "company:voker.ai",
                "name": "Voker",
                "domain": "voker.ai",
                "current_route": "Assign Owner",
                "current_action": "Assign owner",
                "status_movement": "promoted",
                "source_lanes_seen": ["HN", "YC", "web"],
                "missing_evidence": [],
                "last_seen_run": "current-latest-run",
                "sighting_history": [{"completion_status": "completed_clean", "missing_evidence": []}],
            },
            {
                "entity_id": "company:arize.com",
                "name": "Arize",
                "domain": "arize.com",
                "current_route": "Category Context",
                "current_action": "Monitor only",
                "status_movement": "demoted",
                "source_lanes_seen": ["web"],
                "missing_evidence": ["category context / mature incumbent"],
                "last_seen_run": "current-latest-run",
                "sighting_history": [{"completion_status": "", "missing_evidence": ["category context / mature incumbent"]}],
            },
            {
                "entity_id": "company:repeat.ai",
                "name": "Repeat AI",
                "domain": "repeat.ai",
                "current_route": "Research Deeper",
                "current_action": "Research deeper",
                "status_movement": "repeated",
                "source_lanes_seen": ["web"],
                "missing_evidence": ["no founder/team evidence", "no stage/funding evidence"],
                "last_seen_run": "current-latest-run",
                "sighting_history": [
                    {"completion_status": "", "missing_evidence": ["no founder/team evidence"]},
                    {"completion_status": "", "missing_evidence": ["no founder/team evidence", "no stage/funding evidence"]},
                ],
            },
            {
                "entity_id": "company:aide-memory.dev",
                "name": "Aide-memory",
                "domain": "aide-memory.dev",
                "current_route": "Research Deeper",
                "current_action": "Research deeper",
                "status_movement": "repeated",
                "source_lanes_seen": ["HN", "web"],
                "missing_evidence": ["max_candidates_exceeded"],
                "last_seen_run": "current-latest-run",
                "sighting_history": [
                    {
                        "completion_status": "skipped_budget",
                        "partial_reason": "max_candidates_exceeded",
                        "missing_evidence": ["max_candidates_exceeded"],
                    }
                ],
            },
            {
                "entity_id": "company:stale.ai",
                "name": "Stale AI",
                "domain": "stale.ai",
                "current_route": "Research Deeper",
                "current_action": "Research deeper",
                "status_movement": "repeated",
                "source_lanes_seen": ["web"],
                "missing_evidence": ["no customer/buyer pull evidence"],
                "last_seen_run": "current-prior-run",
                "sighting_history": [{"completion_status": "", "missing_evidence": ["no customer/buyer pull evidence"]}],
            },
        ],
    }

    report = build_ledger_action_report(ledger, generated_at="2026-05-24T12:00:00Z")
    sections = report["sections"]

    assert [item["entity_id"] for item in sections["current_assign_owner"]] == ["company:voker.ai"]
    assert [item["entity_id"] for item in sections["newly_promoted"]] == ["company:voker.ai"]
    assert [item["entity_id"] for item in sections["demoted_category_context"]] == ["company:arize.com"]
    assert [item["entity_id"] for item in sections["repeated_research_deeper"]] == ["company:repeat.ai"]
    assert [item["entity_id"] for item in sections["skipped_or_incomplete"]] == ["company:aide-memory.dev"]
    assert [item["entity_id"] for item in sections["stale_or_missing_from_latest"]] == ["company:stale.ai"]
    assert report["top_missing_evidence_buckets"][0] == {"missing_evidence": "max_candidates_exceeded", "count": 1}
    assert any(action["entity_id"] == "company:voker.ai" and action["next_action"] == "Owner follow-up" for action in report["recommended_actions"])
    assert any(action["entity_id"] == "company:aide-memory.dev" and action["next_action"] == "Rerun bounded HN completion" for action in report["recommended_actions"])
    for action in report["recommended_actions"]:
        assert {
            "entity_name",
            "domain",
            "current_route",
            "current_action",
            "status_movement",
            "source_lanes_seen",
            "missing_evidence",
            "why_next_best_action",
        } <= set(action)


def test_ledger_action_report_refines_completed_clean_missing_evidence_recommendations():
    from signal_ledger import build_ledger_action_report

    ledger = {
        "generated_at": "2026-05-24T00:00:00Z",
        "runs_backfilled": [{"run_id": "current-latest-run", "run_sequence": 0}],
        "summary": {"entities": 5, "sightings": 5, "assign_owner_entities": 0, "unsafe_promotions": 0},
        "entities": [
            {
                "entity_id": "company:completed.ai",
                "name": "Completed AI",
                "domain": "completed.ai",
                "current_route": "Research Deeper",
                "current_action": "Research deeper",
                "status_movement": "repeated",
                "source_lanes_seen": ["HN", "web"],
                "missing_evidence": ["no founder/team evidence", "no stage/funding evidence"],
                "last_seen_run": "current-latest-run",
                "sighting_history": [
                    {
                        "completion_status": "completed_clean",
                        "missing_evidence": ["no founder/team evidence", "no stage/funding evidence"],
                    }
                ],
            },
            {
                "entity_id": "company:attio-unknown.ai",
                "name": "Attio Unknown AI",
                "domain": "attio-unknown.ai",
                "current_route": "Research Deeper",
                "current_action": "Research deeper",
                "status_movement": "repeated",
                "source_lanes_seen": ["web"],
                "missing_evidence": ["Attio status unknown"],
                "last_seen_run": "current-latest-run",
                "sighting_history": [{"completion_status": "completed_clean", "missing_evidence": ["Attio status unknown"]}],
            },
            {
                "entity_id": "company:identity-missing.ai",
                "name": "Identity Missing AI",
                "domain": "identity-missing.ai",
                "current_route": "Research Deeper",
                "current_action": "Research deeper",
                "status_movement": "repeated",
                "source_lanes_seen": ["HN", "web"],
                "missing_evidence": ["official_domain_identity_not_confirmed", "no founder/team evidence"],
                "last_seen_run": "current-latest-run",
                "sighting_history": [
                    {
                        "completion_status": "completed_clean",
                        "missing_evidence": ["official_domain_identity_not_confirmed", "no founder/team evidence"],
                    }
                ],
            },
            {
                "entity_id": "project:github.com/example/project",
                "name": "example/project",
                "domain": "",
                "current_route": "OSS Watch",
                "current_action": "Research deeper",
                "status_movement": "repeated",
                "source_lanes_seen": ["OSS"],
                "missing_evidence": ["OSS/project-only row"],
                "last_seen_run": "current-latest-run",
                "sighting_history": [{"completion_status": "", "missing_evidence": ["OSS/project-only row"]}],
            },
            {
                "entity_id": "company:budget-skipped.ai",
                "name": "Budget Skipped AI",
                "domain": "budget-skipped.ai",
                "current_route": "Research Deeper",
                "current_action": "Research deeper",
                "status_movement": "repeated",
                "source_lanes_seen": ["HN", "web"],
                "missing_evidence": ["max_candidates_exceeded"],
                "last_seen_run": "current-latest-run",
                "sighting_history": [
                    {
                        "completion_status": "skipped_budget",
                        "partial_reason": "max_candidates_exceeded",
                        "missing_evidence": ["max_candidates_exceeded"],
                    }
                ],
            },
        ],
    }

    report = build_ledger_action_report(ledger, generated_at="2026-05-24T12:00:00Z")
    actions = {item["entity_id"]: item["next_action"] for item in report["recommended_actions"]}

    assert actions["company:completed.ai"] == "Run targeted evidence search"
    assert actions["company:attio-unknown.ai"] == "Run Attio read check only after owner-actionable evidence exists"
    assert actions["company:identity-missing.ai"] == "Verify official identity"
    assert actions["project:github.com/example/project"] == "Track OSS/company formation"
    assert actions["company:budget-skipped.ai"] == "Rerun bounded HN completion"


def test_write_ledger_action_report_reads_ledger_and_renders_markdown(tmp_path: Path):
    from signal_ledger import write_ledger_action_report

    ledger_path = tmp_path / "company_signal_ledger.json"
    report_dir = tmp_path / "current-ledger-action-report-2026-05-24"
    _write_json(
        ledger_path,
        {
            "generated_at": "2026-05-24T00:00:00Z",
            "runs_backfilled": [{"run_id": "current-latest-run", "run_sequence": 0}],
            "summary": {"entities": 2, "sightings": 2, "assign_owner_entities": 1, "unsafe_promotions": 0},
            "entities": [
                {
                    "entity_id": "company:voker.ai",
                    "name": "Voker",
                    "domain": "voker.ai",
                    "current_route": "Assign Owner",
                    "current_action": "Assign owner",
                    "status_movement": "promoted",
                    "source_lanes_seen": ["HN", "YC", "web"],
                    "missing_evidence": [],
                    "last_seen_run": "current-latest-run",
                    "sighting_history": [{"completion_status": "completed_clean", "missing_evidence": []}],
                },
                {
                    "entity_id": "company:aide-memory.dev",
                    "name": "Aide-memory",
                    "domain": "aide-memory.dev",
                    "current_route": "Research Deeper",
                    "current_action": "Research deeper",
                    "status_movement": "repeated",
                    "source_lanes_seen": ["HN", "web"],
                    "missing_evidence": ["max_candidates_exceeded"],
                    "last_seen_run": "current-latest-run",
                    "sighting_history": [{"completion_status": "skipped_budget", "partial_reason": "max_candidates_exceeded"}],
                },
            ],
        },
    )

    result = write_ledger_action_report(
        ledger_path=ledger_path,
        report_dir=report_dir,
        generated_at="2026-05-24T12:00:00Z",
    )

    markdown = (report_dir / "README.md").read_text()
    report_json = json.loads((report_dir / "ledger-action-report.json").read_text())
    assert result["report"] == str(report_dir / "README.md")
    assert result["report_json"] == str(report_dir / "ledger-action-report.json")
    assert "# Ledger Action Report" in markdown
    assert "## Current Assign Owner" in markdown
    assert "## Skipped or Incomplete Rows" in markdown
    assert "## Recommended Next Codex Actions" in markdown
    assert "Voker" in markdown
    assert "Aide-memory" in markdown
    assert report_json["sections"]["current_assign_owner"][0]["entity_id"] == "company:voker.ai"
