from __future__ import annotations

from radar_models import Candidate


def _candidate(**overrides) -> Candidate:
    payload = {
        "name": "AgentFence",
        "sector": "Devtools",
        "theme": "AI agent security",
        "source": "https://www.producthunt.com/products/agentfence",
        "sources": ["https://www.producthunt.com/products/agentfence"],
        "candidate_type": "producthunt_launch",
        "stable_key": "entity:agentfence",
        "domain": "",
        "source_lane": "Product Hunt",
        "lead_route": "research_deeper",
        "action": "research deeper",
        "why_on_radar": "Permission firewall for AI agents",
        "why_this_may_be_noise": "Needs official identity evidence.",
        "missing_identity_evidence": ["no verified domain", "no founder or maintainer identity"],
    }
    payload.update(overrides)
    return Candidate(**payload)


def test_product_hunt_launch_enrichment_resolves_official_domain_without_promoting():
    from weak_source_identity_enrichment import enrich_weak_source_identity

    calls = []

    def fake_query_runner(topic: str, **kwargs):
        calls.append((topic, kwargs))
        return {
            "items": [
                {
                    "title": "AgentFence - AI agent permissions",
                    "url": "https://agentfence.dev",
                    "snippet": "AgentFence is a startup building a permission firewall for AI agents.",
                    "source": "grounding",
                }
            ]
        }

    enriched, report = enrich_weak_source_identity([_candidate()], query_runner=fake_query_runner, max_candidates=3)

    assert enriched[0].domain == "agentfence.dev"
    assert enriched[0].action == "research deeper"
    assert enriched[0].lead_route == "research_deeper"
    assert "weak_source_official_search_result" in enriched[0].verified_domain_basis
    assert "https://agentfence.dev" in enriched[0].sources
    assert enriched[0].evidence_metadata[-1]["source"] == "grounding"
    assert report["summary"]["domains_resolved"] == 1
    assert report["items"][0]["status"] == "resolved"
    assert calls[0][1]["sources"] == "grounding"


def test_github_project_enrichment_can_add_domain_but_keeps_project_routing():
    from weak_source_identity_enrichment import enrich_weak_source_identity

    candidate = _candidate(
        name="affaan-m/agentshield",
        source="https://github.com/affaan-m/agentshield",
        sources=["https://github.com/affaan-m/agentshield"],
        candidate_type="oss_project",
        source_lane="OSS",
        action="watch",
        why_on_radar="AI agent security scanner for MCP servers.",
    )

    def fake_query_runner(topic: str, **kwargs):
        return {
            "items": [
                {
                    "title": "AgentShield - MCP server security scanner",
                    "url": "https://agentshield.dev",
                    "snippet": "AgentShield helps teams scan MCP servers for AI agent security risk.",
                    "source": "grounding",
                }
            ]
        }

    enriched, report = enrich_weak_source_identity([candidate], query_runner=fake_query_runner, max_candidates=3)

    assert enriched[0].domain == "agentshield.dev"
    assert enriched[0].candidate_type == "oss_project"
    assert enriched[0].source_lane == "OSS"
    assert enriched[0].action == "watch"
    assert report["items"][0]["status"] == "resolved"


def test_weak_source_enrichment_rejects_publisher_domains_as_identity():
    from weak_source_identity_enrichment import enrich_weak_source_identity

    def fake_query_runner(topic: str, **kwargs):
        return {
            "items": [
                {
                    "title": "AgentFence launches from stealth",
                    "url": "https://techcrunch.com/2026/05/25/agentfence-launches",
                    "snippet": "AgentFence launches from stealth.",
                    "source": "grounding",
                }
            ]
        }

    enriched, report = enrich_weak_source_identity([_candidate()], query_runner=fake_query_runner, max_candidates=3)

    assert enriched[0].domain == ""
    assert report["summary"]["domains_resolved"] == 0
    assert report["items"][0]["status"] == "unresolved"
    assert "publisher_article_not_company_identity" in report["items"][0]["rejection_reasons"]


def test_weak_source_enrichment_skips_verified_or_category_rows():
    from weak_source_identity_enrichment import enrich_weak_source_identity

    rows = [
        _candidate(domain="agentfence.dev"),
        _candidate(name="Arize", domain="arize.com", category_anchor=True, lead_route="category_context"),
    ]

    def fail_query_runner(topic: str, **kwargs):
        raise AssertionError("verified and category rows should not query")

    enriched, report = enrich_weak_source_identity(rows, query_runner=fail_query_runner, max_candidates=3)

    assert [row.domain for row in enriched] == ["agentfence.dev", "arize.com"]
    assert report["summary"]["skipped"] == 2
    assert report["summary"]["queries_run"] == 0


def test_weak_source_enrichment_prioritizes_product_hunt_with_limited_budget():
    from weak_source_identity_enrichment import enrich_weak_source_identity

    rows = [
        _candidate(
            name="owner/repo-one",
            source="https://github.com/owner/repo-one",
            sources=["https://github.com/owner/repo-one"],
            candidate_type="oss_project",
            source_lane="OSS",
        ),
        _candidate(name="LaunchCo"),
    ]
    queried = []

    def fake_query_runner(topic: str, **kwargs):
        queried.append(topic)
        return {"items": []}

    _enriched, report = enrich_weak_source_identity(rows, query_runner=fake_query_runner, max_candidates=1)

    assert queried == ['"LaunchCo" official website founder company']
    assert report["items"][0]["status"] == "skipped"
    assert report["items"][0]["skip_reason"] == "weak_source_identity_candidate_budget_exceeded"
    assert report["items"][1]["status"] == "unresolved"
