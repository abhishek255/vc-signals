"""Tests for Phase 6B.2 HN outbound candidate enrichment."""

from __future__ import annotations

import json


def _phase6b_payload(*, company_rows=None, product_rows=None, project_rows=None):
    return {
        "summary": {},
        "company_rows": list(company_rows or []),
        "product_context_rows": list(product_rows or []),
        "project_only_rows": list(project_rows or []),
        "rejected_rows": [],
    }


def _hn_outbound(**overrides):
    row = {
        "name": "Burrow",
        "source_title": "Show HN: Burrow - Runtime Security for AI Agents",
        "source_url": "https://news.ycombinator.com/item?id=47761957",
        "official_url": "https://burrow.security",
        "outbound_domain": "burrow.security",
        "company_domain": "burrow.security",
        "hn_author": "founder",
        "hn_engagement": {"points": 42, "comments": 9},
        "identity_type": "hn_outbound_candidate",
        "identity_risk": "hn_outbound_domain_needs_independent_company_verification",
        "maturity_status": "unknown",
        "maturity_basis": ["maturity_not_verified"],
        "lead_route": "research_deeper",
        "recommended_action": "Research deeper",
        "missing_owner_evidence": [
            "no verified Attio-safe company identity",
            "no founder/team evidence",
            "no stage/funding evidence",
            "no customer/buyer pull evidence",
            "Attio status unknown",
        ],
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "recommended_lane": "HN Outbound Candidates",
    }
    row.update(overrides)
    return row


def _query_runner(topic, **_kwargs):
    lowered = topic.lower()
    if "founder" in lowered or "co-founder" in lowered:
        return {
            "items": [
                {
                    "title": "Burrow founder",
                    "snippet": "Burrow was founded by Jane Doe, founder and CEO.",
                    "url": "https://burrow.security/about",
                }
            ]
        }
    if "funding" in lowered or "seed" in lowered:
        return {
            "items": [
                {
                    "title": "Burrow raises seed round",
                    "snippet": "Burrow raised a seed round for runtime security for AI agents.",
                    "url": "https://burrow.security/blog/seed",
                }
            ]
        }
    if "customers" in lowered or "case study" in lowered:
        return {
            "items": [
                {
                    "title": "Burrow customers",
                    "snippet": "Burrow works with design partner customers and security teams.",
                    "url": "https://burrow.security/customers",
                }
            ]
        }
    return {"items": []}


def test_hn_outbound_identity_promotion_requires_official_site_confirmation():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: "<html><title>Burrow Security</title><body>Burrow runtime security</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
    )

    row = result["enriched_outbound_candidates"][0]
    assert row["canonical_name"] == "Burrow"
    assert row["identity_type"] == "verified_company"
    assert row["identity_promotion_status"] == "promoted"
    assert row["official_domain"] == "burrow.security"
    assert row["recommended_action"] == "Research deeper"
    assert row["assign_owner"] is False
    assert "no founder/team evidence" in row["missing_owner_evidence"]
    assert result["summary"]["identity_promoted_rows"] == 1


def test_hn_outbound_without_official_identity_stays_outbound_candidate():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: "<html><title>Different Company</title></html>",
        query_runner=_query_runner,
        attio_matcher=lambda candidate: {"attio_status": "no_match"},
    )

    row = result["enriched_outbound_candidates"][0]
    assert row["identity_type"] == "hn_outbound_candidate"
    assert row["identity_promotion_status"] == "not_promoted"
    assert row["recommended_action"] == "Research deeper"
    assert row["assign_owner"] is False
    assert "official_domain_identity_not_confirmed" in row["missing_evidence"]
    assert result["summary"]["identity_not_promoted_rows"] == 1
    assert result["summary"]["assign_owner_rows"] == 0


def test_hn_outbound_can_assign_owner_only_after_all_existing_gates_pass():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: (
            "<html><title>Burrow</title><body>Burrow was founded by Jane Doe. "
            "Burrow customers include security teams.</body></html>"
        ),
        query_runner=_query_runner,
        attio_matcher=lambda candidate: {"attio_status": "no_match", "attio_action": "assign owner"},
    )

    row = result["enriched_outbound_candidates"][0]
    assert row["identity_type"] == "verified_company"
    assert row["maturity_status"] == "seed_to_series_b"
    assert row["lead_route"] == "sourcing_candidate"
    assert row["founder_team_evidence"]
    assert row["stage_funding_evidence"]
    assert row["customer_buyer_evidence"]
    assert row["attio_status"] == "no_match"
    assert row["owner_readiness_score"] >= 80
    assert row["recommended_action"] == "Assign owner"
    assert row["assign_owner"] is True
    assert result["summary"]["assign_owner_rows"] == 1
    assert result["summary"]["unsafe_promotions"] == 0


def test_twill_yc_context_needs_corroboration_before_seed_status():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="Twill.ai (YC S25)",
                    official_url="https://twill.ai",
                    outbound_domain="twill.ai",
                    company_domain="twill.ai",
                    source_title="Launch HN: Twill.ai (YC S25) - Delegate to cloud agents, get back PRs",
                    maturity_status="early_stage_context",
                    maturity_basis=["accelerator_batch_evidence: YC S25"],
                )
            ]
        ),
        page_fetcher=lambda url: "<html><title>Twill.ai</title><body>Twill.ai cloud agents</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
    )

    row = result["enriched_outbound_candidates"][0]
    assert row["canonical_name"] == "Twill.ai"
    assert row["identity_type"] == "verified_company"
    assert row["maturity_status"] == "early_stage_context"
    assert "accelerator_batch_evidence: YC S25" in row["maturity_basis"]
    assert row["stage_funding_evidence"] == []
    assert "stage_funding_evidence" not in row["owner_readiness_basis"]
    assert row["lead_route"] == "research_deeper"
    assert row["assign_owner"] is False


def test_veris_official_page_founder_handoff_removes_founder_missing():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    def fake_fetcher(url):
        if url.endswith("/blog"):
            return (
                "<html><body><h1>Introducing Veris AI</h1>"
                "<p>Mehdi Jamei, CEO and Co-founder of Veris, announced an $8.5M Series Seed.</p>"
                "<p>Veris customers use simulated environments for enterprise AI agents.</p></body></html>"
            )
        return "<html><title>Veris</title><body>Veris AI trains enterprise AI agents.</body></html>"

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="Veris",
                    source_title="Show HN: Veris - Agent sandboxes with simulated external services",
                    official_url="https://veris.ai/sandbox",
                    outbound_domain="veris.ai",
                    company_domain="veris.ai",
                    maturity_status="unknown",
                    maturity_basis=["maturity_not_verified"],
                )
            ]
        ),
        page_fetcher=fake_fetcher,
        query_runner=lambda topic, **kwargs: {"items": []},
        attio_matcher=lambda candidate: {"attio_status": "no_owner"},
    )

    row = result["enriched_outbound_candidates"][0]
    assert row["canonical_name"] == "Veris"
    assert row["identity_type"] == "verified_company"
    assert row["maturity_status"] == "seed_to_series_b"
    assert row["founders"] == ["Mehdi Jamei"]
    assert row["founder_profiles"] == [
        {"name": "Mehdi Jamei", "role": "co-founder", "source": "https://veris.ai/blog"}
    ]
    assert row["founder_team_evidence"] == ["https://veris.ai/blog"]
    assert row["customer_buyer_evidence_types"] == [
        {
            "url": "https://veris.ai/blog",
            "evidence_types": ["commercial_intent_evidence"],
        }
    ]
    assert "founder_team_evidence" in row["owner_readiness_basis"]
    assert "no founder/team evidence" not in row["missing_owner_evidence"]
    assert row["next_validation_step"] != "Find founder/team source"
    assert row["unsafe_promotion"] is False


def test_generic_founder_page_evidence_is_not_reported_as_founder_team():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: (
            "<html><title>Burrow</title><body>Our founder-led team built runtime security tooling.</body></html>"
        ),
        query_runner=lambda topic, **kwargs: {"items": []},
    )

    row = result["enriched_outbound_candidates"][0]
    assert row["identity_type"] == "verified_company"
    assert row["founder_team_evidence"] == []
    assert "founder_team_evidence" not in row["owner_readiness_basis"]
    assert "no founder/team evidence" in row["missing_owner_evidence"]


def test_product_and_project_rows_are_preserved_not_enriched(tmp_path):
    from hn_outbound_enrichment import run_hn_outbound_enrichment, write_hn_outbound_enrichment_artifacts

    product = {"name": "Deepgram CLI", "recommended_lane": "HN Product / Category Context"}
    project = {"name": "AgentSwift", "recommended_lane": "HN Project Watch / Technical Launch Signals"}
    result = run_hn_outbound_enrichment(_phase6b_payload(product_rows=[product], project_rows=[project]))

    assert result["product_context_rows"] == [product]
    assert result["project_only_rows"] == [project]
    assert result["summary"]["product_context_rows"] == 1
    assert result["summary"]["project_only_rows"] == 1

    paths = write_hn_outbound_enrichment_artifacts(result, tmp_path)
    assert tmp_path / "hn-outbound-enrichment.json" in paths
    assert tmp_path / "hn-outbound-enrichment.md" in paths
    assert not (tmp_path / "weekly-preview.md").exists()
    assert json.loads((tmp_path / "hn-outbound-enrichment.json").read_text())["summary"]["project_only_rows"] == 1


def test_hn_enrichment_candidate_budget_writes_partial_skipped_rows(tmp_path):
    from hn_outbound_enrichment import run_hn_outbound_enrichment, write_hn_outbound_enrichment_artifacts

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(name="Burrow", official_url="https://burrow.security", company_domain="burrow.security"),
                _hn_outbound(name="Second", official_url="https://second.ai", company_domain="second.ai"),
            ]
        ),
        page_fetcher=lambda url: "<html><title>Burrow</title><body>Burrow runtime security</body></html>",
        max_candidates=1,
    )

    assert result["partial"] is True
    assert result["budget_exceeded"] is True
    assert result["summary"]["candidates_skipped"] == 1
    skipped = result["skipped_candidates"][0]
    assert skipped["name"] == "Second"
    assert skipped["assign_owner"] is False
    assert skipped["recommended_action"] == "Research deeper"
    assert skipped["partial_reason"] == "max_candidates_exceeded"

    paths = write_hn_outbound_enrichment_artifacts(result, tmp_path)
    assert tmp_path / "hn-enrichment-runtime-ledger.json" in paths
    ledger = json.loads((tmp_path / "hn-enrichment-runtime-ledger.json").read_text())
    assert ledger["summary"]["candidates_skipped"] == 1
    assert ledger["items"][-1]["status"] == "skipped"


def test_hn_enrichment_attio_budget_prevents_assign_owner():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: (
            "<html><title>Burrow</title><body>Burrow was founded by Jane Doe. "
            "Burrow customers include security teams.</body></html>"
        ),
        query_runner=_query_runner,
        attio_matcher=lambda candidate: {"attio_status": "no_match", "attio_action": "assign owner"},
        max_attio_checks=0,
    )

    row = result["enriched_outbound_candidates"][0]
    assert result["partial"] is True
    assert row["assign_owner"] is False
    assert row["recommended_action"] == "Research deeper"
    assert row["partial"] is True
    assert "attio_budget_exceeded" in row["missing_evidence"]
    assert result["runtime_ledger"]["items"][0]["attio_checks"] == 0


def test_hn_enrichment_live_query_budget_preserves_cached_or_page_evidence():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    def fake_fetcher(url):
        if url.endswith("/blog"):
            return (
                "<html><body><h1>Introducing Veris AI</h1>"
                "<p>Mehdi Jamei, CEO and Co-founder of Veris, announced an $8.5M Series Seed.</p>"
                "<p>Enterprise teams can book demo access to validate agents before regulators find policy gaps.</p>"
                "</body></html>"
            )
        return "<html><title>Veris</title><body>Veris AI trains enterprise AI agents.</body></html>"

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="Veris",
                    source_title="Show HN: Veris - Agent sandboxes with simulated external services",
                    official_url="https://veris.ai/sandbox",
                    outbound_domain="veris.ai",
                    company_domain="veris.ai",
                    maturity_status="unknown",
                    maturity_basis=["maturity_not_verified"],
                )
            ]
        ),
        page_fetcher=fake_fetcher,
        query_runner=lambda topic, **kwargs: (_ for _ in ()).throw(AssertionError("live queries should be skipped")),
        attio_matcher=lambda candidate: {"attio_status": "no_owner"},
        max_live_queries=0,
    )

    row = result["enriched_outbound_candidates"][0]
    assert row["recommended_action"] == "Assign owner"
    assert row["assign_owner"] is True
    assert result["runtime_ledger"]["summary"]["live_queries"] == 0


def test_hn_enrichment_runtime_budget_marks_remaining_rows_partial():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    calls = {"count": 0}

    def fake_time():
        calls["count"] += 1
        return 0.0 if calls["count"] < 12 else 5.0

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound(), _hn_outbound(name="Late", company_domain="late.ai")]),
        page_fetcher=lambda url: "<html><title>Burrow</title><body>Burrow runtime security</body></html>",
        max_runtime_seconds=1,
        time_fn=fake_time,
    )

    assert result["partial"] is True
    assert result["budget_exceeded"] is True
    assert result["summary"]["candidates_skipped"] == 1
    assert result["skipped_candidates"][0]["partial_reason"] == "max_runtime_seconds_exceeded"
    assert result["runtime_ledger"]["items"][-1]["partial_reason"] == "max_runtime_seconds_exceeded"
