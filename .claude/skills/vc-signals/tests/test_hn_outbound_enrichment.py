"""Tests for Phase 6B.2 HN outbound candidate enrichment."""

from __future__ import annotations

import json
from datetime import date, timedelta


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


def _veris_owner_ready_page_fetcher(url):
    if url.endswith("/blog"):
        return (
            "<html><body><h1>Introducing Veris AI</h1>"
            "<p>Mehdi Jamei, CEO and Co-founder of Veris, announced an $8.5M Series Seed.</p>"
            "<p>Enterprise teams can book demo access to validate agents before regulators find policy gaps.</p>"
            "</body></html>"
        )
    return "<html><title>Veris</title><body>Veris AI trains enterprise AI agents.</body></html>"


def _veris_row():
    return _hn_outbound(
        name="Veris",
        source_title="Show HN: Veris - Agent sandboxes with simulated external services",
        official_url="https://veris.ai/sandbox",
        outbound_domain="veris.ai",
        company_domain="veris.ai",
        maturity_status="unknown",
        maturity_basis=["maturity_not_verified"],
    )


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


def test_hn_enrichment_triage_routes_hosted_demo_to_context_before_live_budget():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    calls = {"query": 0, "attio": 0}

    def query_runner(topic, **kwargs):
        calls["query"] += 1
        return {"items": []}

    def attio_matcher(candidate):
        calls["attio"] += 1
        return {"attio_status": "no_match"}

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="ARC AGI Swarm Demo",
                    official_url="https://arc-agi-swarm.vercel.app",
                    outbound_domain="arc-agi-swarm.vercel.app",
                    company_domain="arc-agi-swarm.vercel.app",
                    source_title="Show HN: Launch an AI agent swarm for ARC-AGI-3",
                )
            ]
        ),
        page_fetcher=lambda url: "<html><title>ARC AGI Swarm Demo</title></html>",
        query_runner=query_runner,
        attio_matcher=attio_matcher,
        max_live_queries=5,
        max_attio_checks=5,
    )

    row = result["product_context_rows"][0]
    ledger = result["runtime_ledger"]["items"][0]
    assert row["recommended_action"] == "Research deeper"
    assert row["assign_owner"] is False
    assert ledger["priority"] == "skip_or_context"
    assert ledger["partial_reason"] == "hosted_demo_not_company_identity"
    assert row["recommended_lane"] == "HN Product / Project Context"
    assert "hosted_demo_not_company_identity" in row["missing_evidence"]
    assert result["summary"]["product_context_rows"] == 1
    assert calls["query"] == 0
    assert calls["attio"] == 0


def test_hn_enrichment_triage_does_not_skip_low_engagement_strong_company_signal():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="Veris",
                    source_title="Show HN: Veris - Agent sandboxes with simulated external services",
                    official_url="https://veris.ai/sandbox",
                    outbound_domain="veris.ai",
                    company_domain="veris.ai",
                    hn_engagement={"points": 1, "comments": 0},
                )
            ]
        ),
        page_fetcher=lambda url: "<html><title>Veris</title><body>Veris AI trains enterprise AI agents.</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
    )

    ledger = result["runtime_ledger"]["items"][0]
    assert ledger["priority"] in {"high_priority", "normal_priority"}
    assert ledger["partial_reason"] != "budget_skipped_low_priority"


def test_hn_enrichment_low_priority_is_enriched_when_budget_remains():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="TinyTool",
                    source_title="Show HN: TinyTool",
                    official_url="",
                    outbound_domain="tinytool",
                    company_domain="tinytool",
                    hn_engagement={"points": 0, "comments": 0},
                )
            ]
        ),
        page_fetcher=lambda url: "<html><title>TinyTool</title><body>TinyTool workflow automation</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
        max_candidates=1,
        max_runtime_seconds=30,
    )

    ledger = result["runtime_ledger"]["items"][0]
    assert ledger["priority"] == "low_priority"
    assert ledger["partial_reason"] != "budget_skipped_low_priority"
    assert result["summary"]["candidates_enriched"] == 1


def test_hn_enrichment_processes_high_priority_before_low_priority_budget_skip():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="TinyTool",
                    source_title="Show HN: TinyTool",
                    official_url="",
                    outbound_domain="tinytool",
                    company_domain="tinytool",
                    hn_engagement={"points": 0, "comments": 0},
                ),
                _hn_outbound(
                    name="Veris",
                    source_title="Show HN: Veris - Agent sandboxes with simulated external services",
                    official_url="https://veris.ai/sandbox",
                    outbound_domain="veris.ai",
                    company_domain="veris.ai",
                ),
            ]
        ),
        page_fetcher=lambda url: "<html><title>Veris</title><body>Veris AI trains enterprise AI agents.</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
        max_candidates=1,
        max_runtime_seconds=30,
    )

    ledger_items = result["runtime_ledger"]["items"]
    assert ledger_items[0]["name"] == "Veris"
    assert ledger_items[0]["priority"] in {"high_priority", "normal_priority"}
    assert ledger_items[1]["name"] == "TinyTool"
    assert ledger_items[1]["priority"] == "low_priority"
    assert ledger_items[1]["partial_reason"] in {"max_candidates_exceeded", "budget_skipped_low_priority"}


def test_hn_enrichment_orders_engaged_priority_by_hn_engagement_before_budget_skip():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="QuietCo",
                    source_title="Show HN: QuietCo - Agent workflow logs",
                    official_url="https://quietco.ai",
                    outbound_domain="quietco.ai",
                    company_domain="quietco.ai",
                    hn_engagement={"points": 1, "comments": 0},
                ),
                _hn_outbound(
                    name="LoudCo",
                    source_title="Show HN: LoudCo - Agent runtime controls",
                    official_url="https://loudco.ai",
                    outbound_domain="loudco.ai",
                    company_domain="loudco.ai",
                    hn_engagement={"points": 30, "comments": 10},
                ),
            ]
        ),
        page_fetcher=lambda url: "<html><title>LoudCo</title><body>LoudCo runtime controls.</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
        max_candidates=1,
        max_runtime_seconds=30,
    )

    ledger_items = result["runtime_ledger"]["items"]
    assert ledger_items[0]["name"] == "LoudCo"
    assert ledger_items[0]["priority"] == "high_priority"
    assert ledger_items[1]["name"] == "QuietCo"
    assert ledger_items[1]["completion_status"] == "partial_budget"


def test_hn_triage_marks_engaged_official_domain_high_priority():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="LoudCo",
                    source_title="Show HN: LoudCo - Agent runtime controls",
                    official_url="https://loudco.ai",
                    outbound_domain="loudco.ai",
                    company_domain="loudco.ai",
                    hn_engagement={"points": 30, "comments": 10},
                ),
                _hn_outbound(
                    name="QuietCo",
                    source_title="Show HN: QuietCo - Agent workflow logs",
                    official_url="https://quietco.ai",
                    outbound_domain="quietco.ai",
                    company_domain="quietco.ai",
                    hn_engagement={"points": 1, "comments": 0},
                ),
            ]
        ),
        page_fetcher=lambda url: "<html><title>LoudCo</title><body>LoudCo runtime controls.</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
        max_candidates=2,
        max_runtime_seconds=30,
    )

    ledger_items = result["runtime_ledger"]["items"]
    assert ledger_items[0]["name"] == "LoudCo"
    assert ledger_items[0]["priority"] == "high_priority"
    assert ledger_items[1]["name"] == "QuietCo"
    assert ledger_items[1]["priority"] == "normal_priority"


def test_hn_enrichment_cache_priority_requires_same_domain_cache(tmp_path):
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    cache_dir = tmp_path / "cache"
    cache_folder = cache_dir / "hn-official-pages"
    cache_folder.mkdir(parents=True)
    (cache_folder / "other.json").write_text('{"url": "https://other.ai", "payload": "Other company"}')

    unrelated = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="Veris",
                    official_url="https://veris.ai/sandbox",
                    outbound_domain="veris.ai",
                    company_domain="veris.ai",
                    hn_engagement={"points": 1, "comments": 0},
                )
            ]
        ),
        page_fetcher=lambda url: "<html><title>Veris</title><body>Veris AI.</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
        cache_dir=cache_dir,
    )

    unrelated_ledger = unrelated["runtime_ledger"]["items"][0]
    assert "cache_available" not in unrelated_ledger["priority_reasons"]
    assert unrelated_ledger["priority"] == "normal_priority"

    (cache_folder / "veris.json").write_text('{"url": "https://veris.ai", "payload": "Veris AI"}')
    related = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="Veris",
                    official_url="https://veris.ai/sandbox",
                    outbound_domain="veris.ai",
                    company_domain="veris.ai",
                    hn_engagement={"points": 1, "comments": 0},
                )
            ]
        ),
        page_fetcher=lambda url: "<html><title>Veris</title><body>Veris AI.</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
        cache_dir=cache_dir,
    )

    related_ledger = related["runtime_ledger"]["items"][0]
    assert "cache_available" in related_ledger["priority_reasons"]
    assert related_ledger["priority"] == "high_priority"


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


def test_hn_enrichment_review_rows_rank_assign_owner_first_and_stage_failures_lower():
    from hn_outbound_enrichment import _CallTimeout, run_hn_outbound_enrichment

    def page_fetcher(url):
        if "veris.ai" in url:
            return _veris_owner_ready_page_fetcher(url)
        return "<html><title>Burrow</title><body>Burrow runtime security</body></html>"

    def query_runner(topic, **kwargs):
        if "Burrow" in topic:
            raise _CallTimeout()
        return {"items": []}

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound(name="Burrow"), _veris_row()]),
        page_fetcher=page_fetcher,
        query_runner=query_runner,
        attio_matcher=lambda candidate: {"attio_status": "no_owner"},
        max_candidates=2,
    )

    review_rows = result["review_rows"]
    assert len(review_rows) == 2
    assert review_rows[0]["name"] == "Veris"
    assert review_rows[0]["final_action"] == "Assign owner"
    assert review_rows[0]["review_rank_reason"] == "assign_owner"
    assert review_rows[1]["name"] == "Burrow"
    assert review_rows[1]["completion_status"] == "completed_with_stage_failure"
    assert "maturity_query_timeout" in review_rows[1]["stage_failure_reason"] or review_rows[1]["evidence_completeness"] < review_rows[0]["evidence_completeness"]


def test_hn_review_rows_rank_multi_evidence_research_above_single_evidence_stage_failures():
    from hn_outbound_enrichment import _CallTimeout, run_hn_outbound_enrichment

    def page_fetcher(url):
        if "multi.ai" in url:
            return (
                "<html><title>Multi</title><body>Multi was founded by Jane Doe. "
                "Multi works with enterprise security teams.</body></html>"
            )
        return "<html><title>LoudCo</title><body>LoudCo runtime controls.</body></html>"

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="LoudCo",
                    source_title="Show HN: LoudCo - Agent runtime controls",
                    official_url="https://loudco.ai",
                    outbound_domain="loudco.ai",
                    company_domain="loudco.ai",
                    hn_engagement={"points": 30, "comments": 10},
                ),
                _hn_outbound(
                    name="Multi",
                    source_title="Show HN: Multi - Enterprise agent guardrails",
                    official_url="https://multi.ai",
                    outbound_domain="multi.ai",
                    company_domain="multi.ai",
                    hn_engagement={"points": 1, "comments": 0},
                ),
            ]
        ),
        page_fetcher=page_fetcher,
        query_runner=lambda topic, **kwargs: (_ for _ in ()).throw(_CallTimeout()) if "LoudCo" in topic else {"items": []},
        max_candidates=2,
    )

    review_rows = result["review_rows"]
    assert review_rows[0]["name"] == "Multi"
    assert review_rows[0]["review_rank_reason"] == "research_deeper_multi_evidence"
    assert review_rows[0]["evidence_completeness"] >= 2
    assert review_rows[1]["name"] == "LoudCo"
    assert review_rows[1]["completion_status"] == "completed_with_stage_failure"


def test_hn_enrichment_skips_maturity_query_for_weak_hn_rows():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    calls = {"query": 0}

    def query_runner(topic, **kwargs):
        calls["query"] += 1
        return {"items": []}

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="QuietCo",
                    source_title="Show HN: QuietCo - Agent workflow notes",
                    official_url="https://quietco.ai",
                    outbound_domain="quietco.ai",
                    company_domain="quietco.ai",
                    hn_engagement={"points": 1, "comments": 0},
                )
            ]
        ),
        page_fetcher=lambda url: "<html><title>QuietCo</title><body>QuietCo agent workflow notes.</body></html>",
        query_runner=query_runner,
        max_candidates=1,
    )

    row = result["enriched_outbound_candidates"][0]
    ledger = result["runtime_ledger"]["items"][0]
    maturity_report = result["reports"]["maturity"][0]
    assert calls["query"] == 0
    assert ledger["maturity_queries"] == 0
    assert maturity_report["skip_reason"] == "maturity_query_skipped_weak_hn_signal"
    assert row["recommended_action"] == "Research deeper"
    assert "no stage/funding evidence" in row["missing_owner_evidence"]


def test_hn_enrichment_cache_priority_alone_does_not_trigger_maturity_query(tmp_path):
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    cache_dir = tmp_path / "cache"
    cache_file = cache_dir / "hn-official-pages" / "quietco.json"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_text('{"url": "https://quietco.ai", "payload": "QuietCo agent workflow notes."}')
    calls = {"query": 0}

    def query_runner(topic, **kwargs):
        calls["query"] += 1
        return {"items": []}

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="QuietCo",
                    source_title="Show HN: QuietCo - Agent workflow notes",
                    official_url="https://quietco.ai",
                    outbound_domain="quietco.ai",
                    company_domain="quietco.ai",
                    hn_engagement={"points": 1, "comments": 0},
                )
            ]
        ),
        page_fetcher=lambda url: "<html><title>QuietCo</title><body>QuietCo agent workflow notes.</body></html>",
        query_runner=query_runner,
        cache_dir=cache_dir,
        max_candidates=1,
    )

    ledger = result["runtime_ledger"]["items"][0]
    maturity_report = result["reports"]["maturity"][0]
    assert ledger["priority"] == "high_priority"
    assert "cache_available" in ledger["priority_reasons"]
    assert calls["query"] == 0
    assert ledger["maturity_queries"] == 0
    assert maturity_report["skip_reason"] == "maturity_query_skipped_weak_hn_signal"


def test_hn_enrichment_does_not_call_attio_before_meaningful_evidence():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    calls = {"attio": 0}

    def attio_matcher(candidate):
        calls["attio"] += 1
        return {"attio_status": "no_match", "attio_action": "assign owner"}

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: "<html><title>Burrow</title><body>Burrow runtime security</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
        attio_matcher=attio_matcher,
        max_attio_checks=5,
    )

    row = result["enriched_outbound_candidates"][0]
    assert row["identity_type"] == "verified_company"
    assert row["recommended_action"] == "Research deeper"
    assert row["assign_owner"] is False
    assert calls["attio"] == 0
    assert result["runtime_ledger"]["summary"]["attio_checks"] == 0


def test_hn_enrichment_calls_attio_after_identity_and_evidence_threshold():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    calls = {"attio": 0}

    def attio_matcher(candidate):
        calls["attio"] += 1
        return {"attio_status": "no_owner"}

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: (
            "<html><title>Burrow</title><body>Burrow was founded by Jane Doe. "
            "Burrow raised a seed round. Burrow works with security teams.</body></html>"
        ),
        query_runner=lambda topic, **kwargs: {"items": []},
        attio_matcher=attio_matcher,
        max_attio_checks=5,
    )

    row = result["enriched_outbound_candidates"][0]
    assert calls["attio"] == 1
    assert row["attio_status"] == "no_owner"
    assert result["runtime_ledger"]["summary"]["attio_checks"] == 1


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


def test_veris_evidence_prefers_durable_urls_over_blog_index():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    durable_url = "https://veris.ai/blog-posts/introducing-veris-ai-a-new-way-to-train-enterprise-ai-agents-through-simulated-experience"

    def fake_fetcher(url):
        if url.endswith("/blog"):
            return (
                f'<html><body><a href="{durable_url}">Introducing Veris AI</a>'
                "<p>Mehdi Jamei, CEO and Co-founder of Veris, announced an $8.5M Series Seed.</p>"
                "<p>Enterprise teams can book demo access for AI agent validation.</p></body></html>"
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
        max_live_queries=0,
    )

    row = result["enriched_outbound_candidates"][0]
    evidence_urls = set(row["founder_team_evidence"] + row["stage_funding_evidence"] + row["customer_buyer_evidence"])
    assert durable_url in evidence_urls
    assert row["assign_owner"] is True


def test_hn_assign_owner_row_separates_exact_evidence_provenance():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    durable_url = "https://veris.ai/blog-posts/introducing-veris-ai-a-new-way-to-train-enterprise-ai-agents-through-simulated-experience"
    veris_fixture = _veris_row()

    def fake_fetcher(url):
        if url.endswith("/blog"):
            return (
                f'<html><body><a href="{durable_url}">Introducing Veris AI</a>'
                "<p>Mehdi Jamei, CEO and Co-founder of Veris, announced an $8.5M Series Seed.</p>"
                "<p>Enterprise teams can book demo access to validate agents before regulators find policy gaps.</p>"
                "</body></html>"
            )
        return "<html><title>Veris</title><body>Veris AI trains enterprise AI agents.</body></html>"

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[veris_fixture]),
        page_fetcher=fake_fetcher,
        query_runner=lambda topic, **kwargs: {"items": []},
        attio_matcher=lambda candidate: {"attio_status": "no_owner"},
        max_live_queries=0,
    )

    row = result["enriched_outbound_candidates"][0]
    provenance = row["assign_owner_evidence_provenance"]
    assert row["recommended_action"] == "Assign owner"
    assert provenance["hn_source"]["url"] == veris_fixture["source_url"]
    assert provenance["official_company_source"]["url"] == "https://veris.ai/sandbox"
    assert provenance["founder_evidence"]["url"] == durable_url
    assert provenance["stage_funding_evidence"]["url"] == durable_url
    assert provenance["commercial_customer_evidence"]["url"] == durable_url
    assert provenance["attio_status_evidence"] == {
        "status": "no_owner",
        "source": "attio_read",
        "action_safe": True,
    }


def test_hn_research_deeper_row_does_not_require_assign_owner_provenance():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="QuietCo",
                    source_title="Show HN: QuietCo - Agent workflow notes",
                    official_url="https://quietco.ai",
                    outbound_domain="quietco.ai",
                    company_domain="quietco.ai",
                    hn_engagement={"points": 1, "comments": 0},
                )
            ]
        ),
        page_fetcher=lambda url: "<html><title>QuietCo</title><body>QuietCo agent workflow notes.</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
        attio_matcher=lambda candidate: {"attio_status": "unknown"},
    )

    row = result["enriched_outbound_candidates"][0]
    assert row["recommended_action"] == "Research deeper"
    assert row["assign_owner_evidence_provenance"] == {}


def test_best_exact_evidence_url_prefers_precise_pages_over_root_and_blog():
    from hn_outbound_enrichment import _best_exact_evidence_url

    assert (
        _best_exact_evidence_url(
            [
                "https://veris.ai",
                "https://veris.ai/blog",
                "https://veris.ai/sandbox",
            ]
        )
        == "https://veris.ai/sandbox"
    )
    assert (
        _best_exact_evidence_url(
            [
                "https://veris.ai/about",
                "https://veris.ai/blog",
                "https://www.businesswire.com/news/home/veris-ai-seed",
            ]
        )
        == "https://www.businesswire.com/news/home/veris-ai-seed"
    )


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
    assert ledger["summary"]["partial_budget"] == 1
    assert ledger["items"][-1]["status"] == "skipped"
    assert ledger["items"][-1]["completion_status"] == "partial_budget"


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
    assert row["partial"] is False
    assert "attio_budget_exceeded" in row["missing_evidence"]
    assert "attio_budget_exceeded" in result["runtime_ledger"]["items"][0]["stage_failures"]
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


def test_veris_warm_page_evidence_assigns_owner_with_zero_live_queries_and_stage_cache_ledger():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_veris_row()]),
        page_fetcher=_veris_owner_ready_page_fetcher,
        query_runner=lambda topic, **kwargs: (_ for _ in ()).throw(AssertionError("live query should not run")),
        attio_matcher=lambda candidate: {"attio_status": "no_owner"},
        max_live_queries=0,
        max_attio_checks=1,
    )

    row = result["enriched_outbound_candidates"][0]
    ledger = result["runtime_ledger"]["items"][0]
    assert row["assign_owner"] is True
    assert ledger["live_queries"] == 0
    assert ledger["page_fetches"] >= 1
    assert ledger["completion_status"] == "completed_clean"
    assert result["runtime_ledger"]["summary"]["completed_clean"] == 1
    assert ledger["evidence_dimensions"] == ["customer", "founder", "stage"]
    assert "commercial_intent_evidence" in ledger["customer_evidence_labels"]


def test_veris_attio_timeout_is_action_blocked_not_generic_research_deeper():
    import time

    from hn_outbound_enrichment import run_hn_outbound_enrichment

    def slow_attio(_candidate):
        time.sleep(0.05)
        return {"attio_status": "no_owner"}

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_veris_row()]),
        page_fetcher=_veris_owner_ready_page_fetcher,
        query_runner=lambda topic, **kwargs: (_ for _ in ()).throw(AssertionError("live query should not run")),
        attio_matcher=slow_attio,
        max_live_queries=0,
        max_attio_checks=2,
        per_candidate_timeout_seconds=0.01,
    )

    row = result["enriched_outbound_candidates"][0]
    ledger = result["runtime_ledger"]["items"][0]
    runtime = result["runtime_ledger"]["summary"]
    assert row["recommended_action"] == "Research deeper"
    assert row["recommended_lane"] == "Action blocked by Attio"
    assert row["action_blocker"] == "attio_timeout"
    assert row["potential_action_if_attio_confirms"] == "Assign owner"
    assert row["assign_owner"] is False
    assert row["unsafe_promotion"] is False
    assert "attio_timeout" in row["missing_evidence"]
    assert ledger["action_blocker"] == "attio_timeout"
    assert runtime["attio_timeouts"] == 1
    assert runtime["attio_blocked_owner_ready_rows"] == 1
    assert result["summary"]["attio_blocked_owner_ready_rows"] == 1


def test_veris_attio_retry_success_clears_timeout_blocker():
    from hn_outbound_enrichment import _CallTimeout, run_hn_outbound_enrichment

    calls = {"attio": 0}

    def flaky_attio(_candidate):
        calls["attio"] += 1
        if calls["attio"] == 1:
            raise _CallTimeout()
        return {"attio_status": "no_owner"}

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_veris_row()]),
        page_fetcher=_veris_owner_ready_page_fetcher,
        query_runner=lambda topic, **kwargs: (_ for _ in ()).throw(AssertionError("live query should not run")),
        attio_matcher=flaky_attio,
        max_live_queries=0,
        max_attio_checks=2,
        per_candidate_timeout_seconds=0.2,
    )

    row = result["enriched_outbound_candidates"][0]
    ledger = result["runtime_ledger"]["items"][0]
    runtime = result["runtime_ledger"]["summary"]
    assert calls["attio"] == 2
    assert row["recommended_action"] == "Assign owner"
    assert row["assign_owner"] is True
    assert row["recommended_lane"] == "HN Enriched Outbound Candidates"
    assert row["action_blocker"] == ""
    assert "attio_timeout" not in row["missing_evidence"]
    assert "attio_timeout" not in ledger["stage_failures"]
    assert runtime["attio_retry_attempts"] == 1
    assert runtime["attio_timeouts"] == 1
    assert runtime["attio_blocked_owner_ready_rows"] == 0


def test_veris_fresh_attio_cache_can_support_assign_owner(tmp_path):
    from hn_outbound_enrichment import _attio_cache_path, run_hn_outbound_enrichment

    cache_dir = tmp_path / "cache"
    path = _attio_cache_path(cache_dir, "Veris", "veris.ai")
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "fetched_at": date.today().isoformat(),
                "payload": {"attio_status": "no_owner"},
                "match_key": {"name": "Veris", "domain": "veris.ai"},
            }
        )
    )

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_veris_row()]),
        page_fetcher=_veris_owner_ready_page_fetcher,
        query_runner=lambda topic, **kwargs: (_ for _ in ()).throw(AssertionError("live query should not run")),
        attio_matcher=lambda candidate: (_ for _ in ()).throw(AssertionError("fresh Attio cache should avoid live read")),
        cache_dir=cache_dir,
        max_live_queries=0,
        max_attio_checks=1,
    )

    row = result["enriched_outbound_candidates"][0]
    runtime = result["runtime_ledger"]["summary"]
    assert row["recommended_action"] == "Assign owner"
    assert row["assign_owner"] is True
    assert row["attio_status"] == "no_owner"
    assert "attio_cache:fresh" in row["attio_confidence_basis"]
    assert runtime["attio_checks"] == 0
    assert runtime["attio_cache_fresh_hits"] == 1


def test_veris_stale_attio_cache_is_context_not_assign_owner(tmp_path):
    from hn_outbound_enrichment import _attio_cache_path, run_hn_outbound_enrichment

    cache_dir = tmp_path / "cache"
    path = _attio_cache_path(cache_dir, "Veris", "veris.ai")
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "fetched_at": (date.today() - timedelta(days=14)).isoformat(),
                "payload": {"attio_status": "no_owner"},
                "match_key": {"name": "Veris", "domain": "veris.ai"},
            }
        )
    )

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_veris_row()]),
        page_fetcher=_veris_owner_ready_page_fetcher,
        query_runner=lambda topic, **kwargs: (_ for _ in ()).throw(AssertionError("live query should not run")),
        attio_matcher=None,
        cache_dir=cache_dir,
        max_live_queries=0,
        max_attio_checks=1,
    )

    row = result["enriched_outbound_candidates"][0]
    runtime = result["runtime_ledger"]["summary"]
    assert row["recommended_action"] == "Research deeper"
    assert row["recommended_lane"] == "Action blocked by Attio"
    assert row["action_blocker"] == "attio_cache_stale"
    assert row["potential_action_if_attio_confirms"] == "Assign owner"
    assert row["assign_owner"] is False
    assert row["attio_status"] == "no_owner"
    assert "attio_cache_stale" in row["missing_evidence"]
    assert runtime["attio_cache_stale_hits"] == 1
    assert runtime["attio_blocked_owner_ready_rows"] == 1


def test_hn_enrichment_runtime_ledger_reports_priority_and_stage_counts(tmp_path):
    from hn_outbound_enrichment import run_hn_outbound_enrichment, write_hn_outbound_enrichment_artifacts

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: "<html><title>Burrow</title><body>Burrow runtime security</body></html>",
        query_runner=lambda topic, **kwargs: {"items": []},
    )

    paths = write_hn_outbound_enrichment_artifacts(result, tmp_path)
    ledger = json.loads((tmp_path / "hn-enrichment-runtime-ledger.json").read_text())
    item = ledger["items"][0]
    assert "priority" in item
    assert "priority_reasons" in item
    assert "evidence_dimensions" in item
    assert "customer_evidence_labels" in item
    assert "attio_skip_reason" in item
    assert "completion_status" in item
    assert "maturity_queries" in item
    assert "founder_queries" in item
    assert "owner_queries" in item
    assert tmp_path / "hn-outbound-enrichment.md" in paths


def test_hn_enrichment_query_timeout_uses_stage_specific_reason():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    def timed_out_query(topic, **kwargs):
        return {"items": [], "error": f"last30days query timed out ({kwargs.get('timeout_seconds')}s)"}

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: "<html><title>Burrow</title><body>Burrow runtime security</body></html>",
        query_runner=timed_out_query,
        max_runtime_seconds=1,
        per_candidate_timeout_seconds=0.01,
    )

    row = result["enriched_outbound_candidates"][0]
    ledger = result["runtime_ledger"]["items"][0]
    assert row["assign_owner"] is False
    stage_reasons = {
        "maturity_query_timeout",
        "founder_query_timeout",
        "customer_query_timeout",
        "owner_query_timeout",
    }
    assert row["partial"] is False
    assert ledger["status"] == "completed"
    assert ledger["completion_status"] == "completed_with_stage_failure"
    assert result["runtime_ledger"]["summary"]["completed_with_stage_failure"] == 1
    assert result["runtime_ledger"]["summary"]["completed_clean"] == 0
    assert ledger["partial_reason"] == ""
    assert set(ledger["stage_failures"]) & stage_reasons
    assert set(row["missing_evidence"]) & stage_reasons
    assert "live_query_timeout" not in result["budget_reasons"]


def test_hn_enrichment_forwards_short_timeout_to_live_query_runner():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    timeouts = []

    def recording_query(topic, **kwargs):
        timeouts.append(kwargs.get("timeout_seconds"))
        return {"items": []}

    run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: "<html><title>Burrow</title><body>Burrow runtime security</body></html>",
        query_runner=recording_query,
        max_runtime_seconds=30,
        per_candidate_timeout_seconds=8,
        max_live_queries=1,
    )

    assert timeouts
    assert timeouts[0] <= 3


def test_hn_enrichment_records_last30days_timeout_return_as_stage_failure():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=lambda url: "<html><title>Burrow</title><body>Burrow runtime security</body></html>",
        query_runner=lambda topic, **kwargs: {"items": [], "error": "last30days query timed out (3s)"},
        max_runtime_seconds=30,
        per_candidate_timeout_seconds=8,
        max_live_queries=1,
    )

    ledger = result["runtime_ledger"]["items"][0]
    assert ledger["timeouts"] == 1
    assert set(ledger["stage_failures"]) & {
        "maturity_query_timeout",
        "founder_query_timeout",
        "customer_query_timeout",
        "owner_query_timeout",
    }


def test_hn_enrichment_page_fetch_timeout_completes_as_closed_identity_miss():
    import time

    from hn_outbound_enrichment import run_hn_outbound_enrichment

    def slow_page(_url):
        time.sleep(0.05)
        return "<html><title>Burrow</title><body>Burrow runtime security</body></html>"

    result = run_hn_outbound_enrichment(
        _phase6b_payload(company_rows=[_hn_outbound()]),
        page_fetcher=slow_page,
        query_runner=lambda topic, **kwargs: {"items": []},
        max_runtime_seconds=1,
        per_candidate_timeout_seconds=0.01,
    )

    row = result["enriched_outbound_candidates"][0]
    ledger = result["runtime_ledger"]["items"][0]
    assert row["partial"] is False
    assert row["assign_owner"] is False
    assert row["identity_promotion_status"] == "not_promoted"
    assert "page_fetch_timeout" in ledger["stage_failures"]
    assert "page_fetch_timeout" in row["missing_evidence"]
    assert ledger["status"] == "completed"
    assert ledger["completion_status"] == "completed_with_stage_failure"


def test_hn_source_text_named_founders_are_used_before_live_founder_query():
    from hn_outbound_enrichment import run_hn_outbound_enrichment

    def failing_query(topic, **kwargs):
        if "founder" in topic.lower() or "co-founder" in topic.lower():
            raise AssertionError("HN source text should avoid live founder query")
        return {"items": []}

    result = run_hn_outbound_enrichment(
        _phase6b_payload(
            company_rows=[
                _hn_outbound(
                    name="Twill.ai (YC S25)",
                    official_url="https://twill.ai",
                    outbound_domain="twill.ai",
                    company_domain="twill.ai",
                    source_title="Launch HN: Twill.ai (YC S25) - Delegate to cloud agents, get back PRs",
                    source_text="We're Willy Johnson and Dan Smith, co-founders of Twill.ai.",
                    maturity_status="early_stage_context",
                    maturity_basis=["accelerator_batch_evidence: YC S25"],
                )
            ]
        ),
        page_fetcher=lambda url: "<html><title>Twill.ai</title><body>Twill.ai cloud agents</body></html>",
        query_runner=failing_query,
    )

    row = result["enriched_outbound_candidates"][0]
    ledger = result["runtime_ledger"]["items"][0]
    assert row["founders"] == ["Willy Johnson", "Dan Smith"]
    assert row["founder_team_evidence"] == ["https://news.ycombinator.com/item?id=47761957"]
    assert "no founder/team evidence" not in row["missing_owner_evidence"]
    assert ledger["founder_queries"] == 0


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
    assert result["runtime_ledger"]["items"][-1]["completion_status"] == "partial_budget"
