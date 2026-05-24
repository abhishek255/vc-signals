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
