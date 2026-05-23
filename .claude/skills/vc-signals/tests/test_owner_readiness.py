from __future__ import annotations

import json


def _candidate(**overrides):
    from radar_models import Candidate

    data = {
        "name": "Copperhelm",
        "sector": "Cybersecurity",
        "market_sector": "Cybersecurity",
        "theme": "Cybersecurity tooling",
        "source": "https://copperhelm.com/",
        "sources": ["https://copperhelm.com/"],
        "candidate_type": "company_web",
        "domain": "copperhelm.com",
        "identity_type": "verified_company",
        "attio_status": "no_match",
        "attio_safe_to_match": True,
        "maturity_status": "seed_to_series_b",
        "maturity_basis": ["seed_or_pre_seed"],
        "maturity_evidence_urls": ["https://example.com/copperhelm-seed"],
        "lead_route": "sourcing_candidate",
        "why_on_radar": "Copperhelm emerged from stealth with $7M seed funding.",
        "evidence_confidence_score": 70,
    }
    data.update(overrides)
    return Candidate(**data)


def test_owner_readiness_query_is_exact_company_and_domain_scoped():
    from owner_readiness import owner_readiness_query

    assert owner_readiness_query(_candidate()) == '"Copperhelm" "copperhelm.com" founder team seed funding customers'


def test_owner_readiness_enrichment_uses_cache_before_live_budget(tmp_path):
    from owner_readiness import _owner_cache_path, enrich_owner_readiness

    topic = '"Copperhelm" "copperhelm.com" founder team seed funding customers'
    cache_path = _owner_cache_path(tmp_path, topic)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "title": "Copperhelm Emerges from Stealth with $7M Seed Funding",
                        "url": "https://example.com/copperhelm-seed",
                        "snippet": "Founder Maya Rao launched Copperhelm after enterprise security teams joined design partner pilots.",
                    }
                ],
                "warnings": [],
            }
        )
    )

    def fake_query(topic, **kwargs):  # pragma: no cover - cache should prevent this
        raise AssertionError("live owner-readiness query should not run on fresh cache")

    enriched, report = enrich_owner_readiness(
        [_candidate()],
        query_runner=fake_query,
        cache_dir=tmp_path,
        max_queries=0,
    )

    candidate = enriched[0]
    assert report["summary"]["cache_hits"] == 1
    assert report["summary"]["queries_run"] == 0
    assert candidate.owner_readiness_score >= 80
    assert candidate.recommended_owner_action == "Assign owner"
    assert "founder_team_evidence" in candidate.owner_readiness_basis
    assert "customer_buyer_pull_evidence" in candidate.owner_readiness_basis


def test_owner_readiness_skips_category_context_and_oss_rows():
    from owner_readiness import enrich_owner_readiness

    calls = []

    def fake_query(topic, **kwargs):  # pragma: no cover - should not be called
        calls.append(topic)
        return {"items": []}

    category = _candidate(
        name="n8n",
        domain="n8n.io",
        maturity_status="likely_too_late",
        category_anchor=True,
        lead_route="category_context",
    )
    oss = _candidate(
        name="redwoodjs/agent-ci",
        candidate_type="oss_project",
        identity_type="oss_with_commercial_intent",
        domain="agent-ci.dev",
        lead_route="research_deeper",
    )

    enriched, report = enrich_owner_readiness([category, oss], query_runner=fake_query, cache_dir=None)

    assert calls == []
    assert report["summary"]["eligible"] == 0
    assert enriched[0].recommended_owner_action == "Monitor only"
    assert enriched[1].recommended_owner_action == "Research deeper"


def test_owner_readiness_skips_article_title_fragment_with_explicit_reason(tmp_path):
    from owner_readiness import enrich_owner_readiness

    def fail_query(topic, **kwargs):  # pragma: no cover - should not run
        raise AssertionError("bad candidate names should not spend owner-readiness query budget")

    enriched, report = enrich_owner_readiness(
        [
            _candidate(
                name="How",
                domain="nightfall.ai",
                source="https://www.nightfall.ai/blog/how-to-monitor-mcp-usage-a-10-step-security-checklist-for-2026",
                sources=["https://www.nightfall.ai/blog/how-to-monitor-mcp-usage-a-10-step-security-checklist-for-2026"],
                why_on_radar="How to Monitor MCP Usage: A 10-Step Security Checklist for 2026 | Nightfall AI",
                identity_type="verified_company",
                attio_safe_to_match=True,
            )
        ],
        query_runner=fail_query,
        cache_dir=tmp_path,
        max_queries=5,
    )

    item = report["items"][0]
    assert report["summary"]["eligible"] == 0
    assert report["summary"]["queries_run"] == 0
    assert item["eligible"] is False
    assert item["query_status"] == "candidate_name_quality_failed:article_title_fragment"
    assert enriched[0].recommended_owner_action == "Research deeper"


def test_owner_readiness_reports_live_query_disabled_for_eligible_rows(tmp_path):
    from owner_readiness import enrich_owner_readiness

    enriched, report = enrich_owner_readiness(
        [_candidate(founder_profiles=[], customer_buyer_evidence=[])],
        query_runner=None,
        cache_dir=tmp_path,
        max_queries=5,
    )

    item = report["items"][0]
    assert report["summary"]["eligible"] == 1
    assert report["summary"]["queries_run"] == 0
    assert item["query"]
    assert item["query_status"] == "live_query_disabled"
    assert enriched[0].recommended_owner_action == "Research deeper"


def test_write_owner_readiness_artifact(tmp_path):
    from owner_readiness import enrich_owner_readiness, write_owner_readiness_json

    enriched, report = enrich_owner_readiness([_candidate(founder_profiles=[{"name": "Maya Rao"}])], query_runner=None)
    path = write_owner_readiness_json(report, tmp_path / "owner-readiness.json")
    payload = json.loads(path.read_text())

    assert path.name == "owner-readiness.json"
    assert payload["items"][0]["name"] == "Copperhelm"
    assert payload["items"][0]["owner_readiness_score"] >= 0
    assert "summary" in payload
