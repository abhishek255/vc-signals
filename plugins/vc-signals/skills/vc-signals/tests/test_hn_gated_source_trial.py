"""Tests for Phase 6B-HN gated source trial."""

from __future__ import annotations

import json


def _trial_payload(*, company_candidates=None, project_only=None, rejected=None):
    return {
        "summary": {
            "items_seen": len(company_candidates or []) + len(project_only or []) + len(rejected or []),
        },
        "company_candidates": list(company_candidates or []),
        "project_only_leads": list(project_only or []),
        "needs_detail_enrichment": [],
        "rejected_leads": list(rejected or []),
    }


def _hn_company(**overrides):
    row = {
        "name": "Burrow",
        "kind": "company_candidate",
        "lane": "launch_hn",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "source_url": "https://news.ycombinator.com/item?id=47761957",
        "official_url": "https://burrow.security",
        "domain": "burrow.security",
        "title": "Show HN: Burrow - Runtime Security for AI Agents",
        "snippet": "Show HN: Burrow - Runtime Security for AI Agents",
        "author": "founder",
        "points": 42,
        "comments": 9,
        "verification_basis": ["hn_launch_outbound_url"],
        "missing_evidence": [],
    }
    row.update(overrides)
    return row


def test_burrow_style_hn_company_routes_to_research_deeper_not_owner_ready():
    from hn_gated_source_trial import run_hn_gated_source_trial

    payload = _trial_payload(company_candidates=[_hn_company()])

    result = run_hn_gated_source_trial(payload)

    row = result["company_rows"][0]
    assert row["name"] == "Burrow"
    assert row["identity_type"] == "hn_outbound_candidate"
    assert row["company_domain"] == "burrow.security"
    assert row["lead_route"] == "research_deeper"
    assert row["recommended_action"] == "Research deeper"
    assert row["new_to_marathon"] is False
    assert row["assign_owner"] is False
    assert row["raw_source_kind"] == "hn_outbound_candidate"
    assert row["recommended_lane"] == "HN Outbound Candidates"
    assert row["hn_author"] == "founder"
    assert row["hn_engagement"] == {"points": 42, "comments": 9}
    assert "verified_company_identity" not in row["owner_readiness_basis"]
    assert "customer_buyer_pull_evidence" not in row["owner_readiness_basis"]
    assert "commercial_or_funding_evidence" not in row["owner_readiness_basis"]
    assert "no verified Attio-safe company identity" in row["missing_owner_evidence"]
    assert "no founder/team evidence" in row["missing_owner_evidence"]
    assert "no customer/buyer pull evidence" in row["missing_owner_evidence"]
    assert result["summary"]["research_deeper_rows"] == 1
    assert result["summary"]["assign_owner_rows"] == 0


def test_hn_github_outbound_stays_project_only():
    from hn_gated_source_trial import run_hn_gated_source_trial

    payload = _trial_payload(
        project_only=[
            {
                "name": "agentsec",
                "kind": "project_only",
                "lane": "launch_hn",
                "movement": "AI agent security",
                "market_sector": "Cybersecurity",
                "source_url": "https://news.ycombinator.com/item?id=1",
                "official_url": "",
                "title": "Show HN: AgentSec - Open source scanner",
                "missing_evidence": ["hn_outbound_github_project_only"],
            }
        ]
    )

    result = run_hn_gated_source_trial(payload)

    row = result["project_only_rows"][0]
    assert row["identity_type"] == "oss_project_watch"
    assert row["company_domain"] == ""
    assert row["lead_route"] == "project_watch"
    assert row["assign_owner"] is False
    assert row["new_to_marathon"] is False
    assert result["summary"]["project_only_rows"] == 1


def test_product_subdomain_hn_row_is_not_promoted():
    from hn_gated_source_trial import run_hn_gated_source_trial

    payload = _trial_payload(
        company_candidates=[
            _hn_company(
                name="Deepgram releases Deepgram CLI",
                official_url="https://cli.deepgram.com/",
                domain="cli.deepgram.com",
                title="Show HN: Deepgram releases Deepgram CLI (`dg`) an agent-aware CLI",
                snippet="Deepgram releases Deepgram CLI (`dg`) an agent-aware CLI",
            )
        ]
    )

    result = run_hn_gated_source_trial(payload)

    assert result["company_rows"] == []
    row = result["product_context_rows"][0]
    assert row["company_domain"] == ""
    assert row["outbound_domain"] == "cli.deepgram.com"
    assert row["identity_type"] == "launch_style_needs_identity"
    assert row["lead_route"] == "category_context"
    assert row["recommended_action"] == "Monitor only"
    assert row["recommended_lane"] == "HN Product / Category Context"
    assert "product_subdomain_not_company_proof" in row["missing_evidence"]
    assert row["assign_owner"] is False
    assert row["new_to_marathon"] is False
    assert result["summary"]["product_subdomain_guardrails"] == 1
    assert result["summary"]["product_context_rows"] == 1


def test_hn_title_fragment_routes_to_context_not_outbound_company():
    from hn_gated_source_trial import run_hn_gated_source_trial

    payload = _trial_payload(
        company_candidates=[
            _hn_company(
                name="AI CAD Harness",
                official_url="https://fusion.adam.new/install",
                domain="fusion.adam.new",
                title="Show HN: AI CAD Harness",
                snippet="Show HN: AI CAD Harness",
            )
        ]
    )

    result = run_hn_gated_source_trial(payload)

    assert result["company_rows"] == []
    row = result["product_context_rows"][0]
    assert row["company_domain"] == ""
    assert row["identity_type"] == "article_context"
    assert row["lead_route"] == "category_context"
    assert row["recommended_action"] == "Monitor only"
    assert "candidate name appears to be an article/title fragment" in row["missing_evidence"]


def test_yc_batch_title_counts_as_early_stage_context_not_assign_owner():
    from hn_gated_source_trial import run_hn_gated_source_trial

    payload = _trial_payload(
        company_candidates=[
            _hn_company(
                name="Twill.ai (YC S25)",
                official_url="https://twill.ai",
                domain="twill.ai",
                title="Launch HN: Twill.ai (YC S25) - Delegate to cloud agents, get back PRs",
                snippet="Launch HN: Twill.ai (YC S25) - Delegate to cloud agents, get back PRs",
                points=77,
                comments=95,
            )
        ]
    )

    result = run_hn_gated_source_trial(payload)

    row = result["company_rows"][0]
    assert row["maturity_status"] == "early_stage_context"
    assert row["identity_type"] == "hn_outbound_candidate"
    assert row["lead_route"] == "research_deeper"
    assert "accelerator_batch_evidence: YC S25" in row["maturity_basis"]
    assert row["maturity_evidence_urls"] == ["https://news.ycombinator.com/item?id=47761957"]
    assert "verified_company_identity" not in row["owner_readiness_basis"]
    assert "stage_funding_evidence" not in row["owner_readiness_basis"]
    assert "no verified Attio-safe company identity" in row["missing_owner_evidence"]
    assert "no stage/funding evidence" in row["missing_owner_evidence"]
    assert row["assign_owner"] is False
    assert result["summary"]["early_stage_context_rows"] == 1
    assert result["summary"]["maturity_unknown_rows"] == 0


def test_mature_hn_launch_routes_to_category_context():
    from hn_gated_source_trial import run_hn_gated_source_trial

    payload = _trial_payload(
        company_candidates=[
            _hn_company(
                name="BigCo",
                official_url="https://bigco.com",
                domain="bigco.com",
                title="Launch HN: BigCo raises $180M Series C for agent infrastructure",
                snippet="BigCo raises $180M Series C and is a category leader.",
            )
        ]
    )

    result = run_hn_gated_source_trial(payload)

    assert result["company_rows"] == []
    row = result["product_context_rows"][0]
    assert row["maturity_status"] == "likely_too_late"
    assert row["lead_route"] == "category_context"
    assert row["recommended_action"] == "Monitor only"
    assert row["recommended_lane"] == "HN Product / Category Context"
    assert row["assign_owner"] is False
    assert result["summary"]["category_context_rows"] == 1


def test_seed_stage_still_cannot_assign_owner_when_attio_is_not_checked():
    from hn_gated_source_trial import run_hn_gated_source_trial

    payload = _trial_payload(
        company_candidates=[
            _hn_company(
                name="SeedAgent",
                official_url="https://seedagent.ai",
                domain="seedagent.ai",
                title="Launch HN: SeedAgent raises seed round for agent reliability",
                snippet="SeedAgent raised a seed round and has early customer pilots.",
            )
        ]
    )

    result = run_hn_gated_source_trial(payload)

    row = result["company_rows"][0]
    assert row["maturity_status"] == "seed_to_series_b"
    assert row["lead_route"] == "sourcing_candidate"
    assert row["recommended_lane"] == "HN Outbound Candidates"
    assert row["recommended_action"] == "Research deeper"
    assert row["assign_owner"] is False
    assert "no verified Attio-safe company identity" in row["missing_owner_evidence"]
    assert result["summary"]["sourcing_candidate_rows"] == 0
    assert result["summary"]["unsafe_promotions"] == 0


def test_hn_gated_trial_artifacts_do_not_write_weekly_preview(tmp_path):
    from hn_gated_source_trial import run_hn_gated_source_trial, write_hn_gated_source_trial_artifacts

    result = run_hn_gated_source_trial(_trial_payload(company_candidates=[_hn_company()]))
    paths = write_hn_gated_source_trial_artifacts(result, tmp_path)

    assert tmp_path / "hn-gated-source-trial.json" in paths
    assert tmp_path / "hn-gated-source-trial.md" in paths
    assert not (tmp_path / "weekly-preview.md").exists()
    artifact = json.loads((tmp_path / "hn-gated-source-trial.json").read_text())
    assert artifact["summary"]["hn_outbound_candidate_rows"] == 1
    assert "HN Outbound Candidates" in (tmp_path / "hn-gated-source-trial.md").read_text()
    assert "HN Product / Category Context" in (tmp_path / "hn-gated-source-trial.md").read_text()
    assert "HN Project Watch / Technical Launch Signals" in (tmp_path / "hn-gated-source-trial.md").read_text()
