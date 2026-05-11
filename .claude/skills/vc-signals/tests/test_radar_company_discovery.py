from __future__ import annotations

import json


def _theme_signal():
    from radar_models import ThemeSignal

    return ThemeSignal(
        market_sector="Cybersecurity",
        theme="AI agent security",
        evidence_count=3,
        evidence_summary="Teams are asking how to control MCP tool permissions.",
        why_it_matters="Agent tool access creates a new security surface.",
        why_no_company_yet="No verified company/domain/founder evidence appeared in this run.",
        suggested_search="AI agent security startups Seed Series A founder launch",
        confidence="Medium",
    )


def test_build_company_discovery_queries_from_theme_signal():
    from radar_company_discovery import build_company_discovery_queries

    queries = build_company_discovery_queries(
        [_theme_signal()],
        grounded_available=True,
        social_available=True,
        max_queries_per_theme=4,
    )

    assert [query["kind"] for query in queries] == [
        "theme_company_search",
        "theme_funding_search",
        "theme_yc_accelerator_search",
        "theme_company_context_search",
    ]
    assert [query["query_family"] for query in queries] == [
        "official_company_page",
        "funding_launch_article",
        "yc_accelerator",
        "company_context",
    ]
    assert queries[0]["market_sector"] == "Cybersecurity"
    assert queries[0]["theme"] == "AI agent security"
    assert queries[0]["movement"] == "AI agent security"
    assert queries[0]["source_reason"] == "theme_signal"
    assert queries[0]["candidate_eligible"] is True
    assert queries[0]["sources"] == "grounding"
    assert "official" in queries[0]["topic"].lower()
    assert "raises" in queries[1]["topic"].lower()
    assert "site:ycombinator.com/companies" in queries[2]["topic"]
    assert "market map" in queries[3]["topic"].lower()


def test_build_company_discovery_queries_adds_exact_row_identity_family():
    from radar_company_discovery import build_company_discovery_queries
    from radar_models import Candidate, FocusItem

    focus = FocusItem(
        id="burrow",
        name="Burrow",
        market_movement="AI agent security",
        market_sector="Cybersecurity",
        missing_evidence=["no verified domain", "no founder or maintainer identity"],
        evidence_urls=["https://news.ycombinator.com/item?id=47761957"],
        recommended_action="Research deeper",
        noise_risk_score=40,
        why_focus_this_week="Show HN: Burrow - Runtime Security for AI Agents",
    )
    candidate = Candidate(
        name="Burrow",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://news.ycombinator.com/item?id=47761957",
        candidate_type="company_web",
        stable_key="burrow",
        why_on_radar="Show HN: Burrow - Runtime Security for AI Agents",
        sources=["https://news.ycombinator.com/item?id=47761957"],
        missing_identity_evidence=["no verified domain"],
    )

    queries = build_company_discovery_queries(
        [],
        focus_items=[focus],
        unresolved_candidates=[candidate],
        grounded_available=True,
        social_available=False,
    )

    assert queries
    families = {query["query_family"] for query in queries}
    assert "exact_row_identity" in families
    assert {"official_company_page", "funding_launch_article"}.issubset(families)
    exact_queries = [query for query in queries if query["query_family"] == "exact_row_identity"]
    assert exact_queries
    assert all('"Burrow"' in query["topic"] for query in exact_queries)


def test_build_company_discovery_queries_without_grounding_marks_limited_lane():
    from radar_company_discovery import build_company_discovery_queries

    queries = build_company_discovery_queries([_theme_signal()], grounded_available=False, social_available=False)

    assert queries[0]["sources"] == ""
    assert queries[0]["limited"] is True
    assert "grounded company discovery unavailable" in queries[0]["reason"].lower()


def test_build_company_discovery_queries_uses_theme_and_unresolved_rows():
    from radar_company_discovery import build_company_discovery_queries
    from radar_models import Candidate, FocusItem

    theme = _theme_signal()
    focus = FocusItem(
        id="burrow",
        name="Burrow",
        market_movement="AI agent security",
        market_sector="Cybersecurity",
        missing_evidence=["no verified domain", "no founder or maintainer identity"],
        evidence_urls=["https://news.ycombinator.com/item?id=47761957"],
        recommended_action="Research deeper",
        noise_risk_score=40,
        why_focus_this_week="Show HN: Burrow - Runtime Security for AI Agents",
    )
    candidate = Candidate(
        name="Burrow",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://news.ycombinator.com/item?id=47761957",
        candidate_type="company_web",
        stable_key="burrow",
        why_on_radar="Show HN: Burrow - Runtime Security for AI Agents",
        sources=["https://news.ycombinator.com/item?id=47761957"],
        missing_identity_evidence=["no verified domain"],
    )

    queries = build_company_discovery_queries(
        [theme],
        focus_items=[focus],
        unresolved_candidates=[candidate],
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=2,
    )

    assert queries
    assert all(query["sources"] == "grounding" for query in queries)
    assert all(query["source_reason"] in {"theme_signal", "needs_more_evidence", "identity_resolution_target"} for query in queries)
    assert all("AI agent security" in query["movement"] for query in queries)
    assert all(query["query_family"] in {"official_company_page", "funding_launch_article", "exact_row_identity"} for query in queries)
    assert all(any(term in query["topic"].lower() for term in ["startup", "company", "founder", "launch", "yc", "seed"]) for query in queries)


def test_build_company_discovery_queries_refuses_broad_vibe_queries():
    from radar_company_discovery import build_company_discovery_queries
    from radar_models import ThemeSignal

    broad = ThemeSignal(
        market_sector="AI Infra",
        theme="AI",
        evidence_summary="Generic AI chatter.",
        suggested_search="AI startups",
    )

    queries = build_company_discovery_queries(
        [broad],
        grounded_available=True,
        social_available=False,
    )

    assert queries == []


def test_collect_company_discovery_budget_records_skipped_queries_and_partial(tmp_path):
    from radar_company_discovery import DiscoveryRunBudget, collect_company_discovery
    from radar_models import ThemeSignal

    calls = []

    def fake_query(topic, **kwargs):
        calls.append((topic, kwargs))
        return {"items": [], "warnings": []}

    budget = DiscoveryRunBudget.for_mode(
        "smoke",
        max_company_discovery_queries=1,
        max_maturity_queries=0,
        max_article_fetches=0,
    )
    result = collect_company_discovery(
        [
            _theme_signal(),
            ThemeSignal(
                market_sector="Devtools",
                theme="Devtools workflow automation",
                evidence_count=5,
                suggested_search="Devtools workflow automation startup company founder launch",
                confidence="Medium",
            ),
        ],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
        run_budget=budget,
        partial_output_path=tmp_path / "company-discovery.json",
    )

    assert len(calls) == 1
    assert result["summary"]["queries_run"] == 1
    assert result["summary"]["partial"] is True
    assert result["summary"]["budget_exceeded"] is True
    assert result["runtime_ledger"]["completed_queries"] == 1
    assert result["runtime_ledger"]["skipped_queries"] >= 1
    assert result["runtime_ledger"]["skip_reasons"]["company_discovery_query_budget_exceeded"] >= 1
    assert result["runtime_ledger"]["query_events"][0]["query_family"] == "official_company_page"
    assert "priority_score" in result["runtime_ledger"]["query_events"][0]
    assert (tmp_path / "company-discovery.json").exists()


def test_collect_company_discovery_uses_query_cache_before_live_call(tmp_path):
    from radar_company_discovery import DiscoveryRunBudget, _query_cache_path, collect_company_discovery

    topic = "AI agent security startup company platform official Cybersecurity"
    cache_path = _query_cache_path(tmp_path, topic)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "source": "grounding",
                        "title": "AgentFence launches AI agent permission firewall",
                        "url": "https://agentfence.dev",
                        "snippet": "AgentFence helps teams control MCP tool permissions for AI agents.",
                        "company_name": "AgentFence",
                        "domain": "agentfence.dev",
                    }
                ],
                "warnings": [],
            }
        )
    )

    def fake_query(topic, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("live query should not run when cache is fresh")

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
        run_budget=DiscoveryRunBudget.for_mode("smoke", max_company_discovery_queries=0, max_maturity_queries=0),
        query_cache_dir=tmp_path,
    )

    assert result["summary"]["queries_run"] == 0
    assert result["summary"]["cache_hits"] == 1
    assert result["runtime_ledger"]["cache_hits"] == 1
    assert result["runtime_ledger"]["live_calls"] == 0
    assert result["items"][0]["company_name"] == "AgentFence"


def test_collect_company_discovery_uses_cached_maturity_before_live_budget(tmp_path):
    from radar_company_discovery import DiscoveryRunBudget, _query_cache_path, collect_company_discovery
    from radar_models import ThemeSignal

    maturity_topic = '"n8n" funding valuation acquisition Series C'
    cache_path = _query_cache_path(tmp_path, maturity_topic)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "source": "grounding",
                        "title": "n8n raises $180m to get AI closer to value with orchestration",
                        "url": "https://blog.n8n.io/series-c/",
                        "snippet": "n8n raised $180 million in Series C funding at a $2.5 billion valuation.",
                    }
                ],
                "warnings": [],
            }
        )
    )

    def fake_query(topic, **kwargs):
        if "funding valuation acquisition Series C" in topic:  # pragma: no cover - cache should prevent this
            raise AssertionError("live maturity query should not run when maturity cache is fresh")
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "n8n.io - AI workflow automation platform",
                    "url": "https://n8n.io/",
                    "snippet": "AI workflow automation for technical teams.",
                }
            ],
            "warnings": [],
        }

    result = collect_company_discovery(
        [
            ThemeSignal(
                market_sector="Devtools",
                theme="Devtools workflow automation",
                evidence_count=3,
                suggested_search="Devtools workflow automation startup company founder launch Devtools",
                confidence="Medium",
            )
        ],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
        run_budget=DiscoveryRunBudget.for_mode("smoke", max_maturity_queries=0),
        query_cache_dir=tmp_path,
    )

    lead = result["accepted_leads"][0]
    assert result["summary"]["maturity_queries_run"] == 0
    assert result["summary"]["maturity_cache_hits"] == 1
    assert lead["maturity_status"] == "likely_too_late"
    assert "series_c_or_later" in lead["maturity_basis"]
    assert lead["lead_route"] == "category_context"


def test_maturity_budget_exceeded_records_explicit_unknown_basis():
    from radar_company_discovery import DiscoveryRunBudget, collect_company_discovery

    def fake_query(topic, **kwargs):
        if "funding valuation acquisition Series C" in topic:  # pragma: no cover - budget should prevent this
            raise AssertionError("live maturity query should not run when maturity budget is exhausted")
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "AgentFence launches AI agent permission firewall",
                    "url": "https://agentfence.dev/",
                    "snippet": "AgentFence helps security teams control AI agent tool permissions.",
                    "company_name": "AgentFence",
                    "domain": "agentfence.dev",
                }
            ],
            "warnings": [],
        }

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
        run_budget=DiscoveryRunBudget.for_mode("smoke", max_maturity_queries=0),
    )

    lead = result["accepted_leads"][0]
    diagnostic = result["query_diagnostics"][0]
    assert lead["maturity_status"] == "unknown"
    assert lead["lead_route"] == "research_deeper"
    assert "maturity_not_verified_budget_exceeded" in lead["maturity_basis"]
    assert diagnostic["skip_reason_counts"]["maturity_query_budget_exceeded"] == 1


def test_discovery_query_priority_prefers_hot_identity_gaps_over_generic_queries():
    from radar_company_discovery import prioritize_discovery_queries

    generic = {
        "id": "generic",
        "topic": "AI startup company",
        "movement": "AI",
        "source_reason": "theme_signal",
        "missing_identity_evidence": [],
        "origin_row_ids": [],
    }
    identity_gap = {
        "id": "burrow",
        "topic": "AI agent security startup company founder launch",
        "movement": "AI agent security",
        "source_reason": "identity_resolution_target",
        "missing_identity_evidence": ["no verified domain", "no founder identity"],
        "origin_row_ids": ["burrow"],
        "evidence_count": 4,
    }

    prioritized = prioritize_discovery_queries([generic, identity_gap])

    assert prioritized[0]["id"] == "burrow"
    assert prioritized[0]["query_priority"]["missing_identity_evidence"] > 0
    assert prioritized[1]["query_priority"]["generic_penalty"] > 0


def test_discovery_source_eval_fixture_matches_expected_labels():
    from pathlib import Path

    from radar_company_discovery import build_discovery_source_eval_report

    fixture = Path(__file__).parent / "fixtures" / "company_discovery_source_eval.json"
    report = build_discovery_source_eval_report(json.loads(fixture.read_text())["items"])

    assert report["total"] >= 8
    assert report["matched"] == report["total"]
    assert report["mismatches"] == []
    assert report["expected_counts"]["official_company_page"] == 1
    assert report["expected_counts"]["funding_press_release"] == 1


def test_build_company_discovery_queries_skips_execution_without_grounding():
    from radar_company_discovery import build_company_discovery_queries

    queries = build_company_discovery_queries([_theme_signal()], grounded_available=False, social_available=False)

    assert queries
    assert all(query["limited"] is True for query in queries)
    assert all(query["sources"] == "" for query in queries)
    assert "grounded company discovery unavailable" in queries[0]["reason"].lower()


def test_weak_unclassified_row_does_not_generate_discovery_query():
    from radar_company_discovery import build_company_discovery_queries
    from radar_models import FocusItem

    weak = FocusItem(
        id="bearcove-vixen",
        name="bearcove/vixen",
        market_movement="Unclassified technical tooling",
        market_sector="Unclassified",
        missing_evidence=["no verified domain"],
        evidence_urls=["https://github.com/bearcove/vixen"],
        recommended_action="Research deeper",
        noise_risk_score=75,
    )

    queries = build_company_discovery_queries(
        [],
        focus_items=[weak],
        unresolved_candidates=[],
        grounded_available=True,
        social_available=False,
    )

    assert queries == []


def test_github_only_project_row_seeds_movement_queries_not_exact_identity_query():
    from radar_company_discovery import build_company_discovery_queries
    from radar_models import Candidate, FocusItem

    focus = FocusItem(
        id="agentshield",
        name="affaan-m/agentshield",
        market_movement="AI agent security",
        market_sector="Cybersecurity",
        project_url="https://github.com/affaan-m/agentshield",
        missing_evidence=["no verified domain", "no founder identity"],
        evidence_urls=["https://github.com/affaan-m/agentshield"],
        recommended_action="Research deeper",
        noise_risk_score=40,
        why_focus_this_week="AI agent security scanner for MCP permissions.",
    )
    candidate = Candidate(
        name="affaan-m/agentshield",
        sector="Cybersecurity",
        theme="AI agent security",
        source="https://github.com/affaan-m/agentshield",
        candidate_type="oss_project",
        stable_key="agentshield",
        why_on_radar="AI agent security scanner for MCP permissions.",
        sources=["https://github.com/affaan-m/agentshield"],
        missing_identity_evidence=["no verified domain"],
    )

    queries = build_company_discovery_queries(
        [],
        focus_items=[focus],
        unresolved_candidates=[candidate],
        grounded_available=True,
        social_available=False,
    )

    assert queries
    assert "exact_row_identity" not in {query["query_family"] for query in queries}
    assert {query["query_family"] for query in queries} == {"official_company_page", "funding_launch_article"}
    assert all("affaan-m/agentshield" not in query["topic"] for query in queries)


def test_collect_company_discovery_annotates_and_dedupes_items():
    from radar_company_discovery import collect_company_discovery

    seen_topics = []

    def fake_query(topic, **kwargs):
        seen_topics.append(topic)
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "AgentFence launches AI agent permission firewall",
                    "url": "https://agentfence.dev",
                    "company_name": "AgentFence",
                    "domain": "agentfence.dev",
                },
                {
                    "source": "grounding",
                    "title": "AgentFence launches AI agent permission firewall",
                    "url": "https://agentfence.dev",
                    "company_name": "AgentFence",
                    "domain": "agentfence.dev",
                },
            ],
            "warnings": ["minor warning"],
        }

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
    )

    assert seen_topics == [
        "AI agent security startup company platform official Cybersecurity",
        '"AgentFence" funding valuation acquisition Series C',
    ]
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["company_name"] == "AgentFence"
    assert item["candidate_eligible"] is True
    assert item["query_kind"] == "theme_company_search"
    assert item["query_theme"] == "AI agent security"
    assert item["market_sector"] == "Cybersecurity"
    assert result["warnings"] == ["minor warning"]


def test_collect_company_discovery_returns_accepted_and_rejected_leads():
    from radar_company_discovery import collect_company_discovery

    def fake_query(topic, **kwargs):
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "AgentFence launches AI agent permission firewall",
                    "url": "https://agentfence.dev",
                    "snippet": "AgentFence helps security teams control AI agent tool permissions.",
                    "company_name": "AgentFence",
                    "domain": "agentfence.dev",
                },
                {
                    "source": "grounding",
                    "title": "Generic devtools company launches",
                    "url": "https://generic.dev",
                    "snippet": "A generic developer productivity platform.",
                    "company_name": "GenericDev",
                    "domain": "generic.dev",
                },
            ],
            "warnings": [],
        }

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
    )

    assert result["summary"]["accepted"] == 1
    assert result["summary"]["rejected"] == 1
    assert result["accepted_leads"][0]["name"] == "AgentFence"
    assert result["rejected_leads"][0]["name"] == "GenericDev"
    assert result["items"][0]["company_name"] == "AgentFence"
    assert result["items"][0]["domain"] == "agentfence.dev"
    assert result["items"][0]["discovery_verification_status"] == "accepted"
    assert result["items"][0]["signal_role"] == "launch"
    assert result["items"][0]["source_lane"] == "Grounded web"


def test_collect_company_discovery_records_query_diagnostics_for_processed_items():
    from radar_company_discovery import collect_company_discovery

    def fake_query(topic, **kwargs):
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "AgentFence launches AI agent permission firewall",
                    "url": "https://agentfence.dev",
                    "snippet": "AgentFence helps security teams control AI agent tool permissions.",
                    "company_name": "AgentFence",
                    "domain": "agentfence.dev",
                },
                {
                    "source": "grounding",
                    "title": "Generic devtools company launches",
                    "url": "https://generic.dev",
                    "snippet": "A generic developer productivity platform.",
                    "company_name": "GenericDev",
                    "domain": "generic.dev",
                },
            ],
            "warnings": ["minor warning"],
        }

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
    )

    diagnostic = result["query_diagnostics"][0]
    assert diagnostic["status"] == "processed"
    assert diagnostic["provider_item_count"] == 2
    assert diagnostic["accepted_count"] == 1
    assert diagnostic["rejected_count"] == 1
    assert diagnostic["top_result_urls"] == ["https://agentfence.dev", "https://generic.dev"]
    assert diagnostic["top_result_domains"] == ["agentfence.dev", "generic.dev"]
    assert diagnostic["source_type_counts"] == {"official_company_page": 2}
    assert diagnostic["skip_reason_counts"] == {"movement_terms_missing": 1}
    assert diagnostic["warnings"] == ["minor warning"]


def test_collect_company_discovery_records_no_items_query_diagnostic():
    from radar_company_discovery import collect_company_discovery

    def fake_query(topic, **kwargs):
        return {
            "items": [],
            "warnings": ["Some sources failed: grounding"],
            "errors_by_source": {"grounding": "HTTP 402: Payment Required"},
        }

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
    )

    diagnostic = result["query_diagnostics"][0]
    assert diagnostic["status"] == "no_items"
    assert diagnostic["provider_item_count"] == 0
    assert diagnostic["skip_reason_counts"] == {"provider_returned_no_items": 1}
    assert diagnostic["source_errors"] == {"grounding": "HTTP 402: Payment Required"}
    assert "grounding: HTTP 402: Payment Required" in diagnostic["errors"]
    assert "grounding: HTTP 402: Payment Required" in result["errors"]
    assert result["summary"]["provider_items_seen"] == 0


def test_collect_company_discovery_without_grounding_is_artifact_only():
    from radar_company_discovery import collect_company_discovery

    def fail_query(topic, **kwargs):
        raise AssertionError("query runner should not execute without grounding")

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fail_query,
        grounded_available=False,
        social_available=False,
        max_queries_per_theme=1,
    )

    assert result["queries"]
    assert result["items"] == []
    assert result["accepted_leads"] == []
    assert result["rejected_leads"] == []
    assert result["summary"]["queries_run"] == 0
    assert result["summary"]["accepted"] == 0
    assert result["summary"]["rejected"] == 0
    assert result["summary"]["grounded_available"] is False
    assert any("grounded company discovery unavailable" in warning.lower() for warning in result["warnings"])
    assert result["query_diagnostics"][0]["status"] == "not_executed"
    assert result["query_diagnostics"][0]["skip_reason_counts"] == {"grounded_company_discovery_unavailable": 1}



def test_verify_discovery_item_accepts_source_backed_company_domain():
    from radar_company_discovery import verify_discovery_item

    query = {
        "id": "ai-agent-security-theme-company-search",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "topic": "AI agent security startup company founder launch",
        "required_terms": ["agent", "security"],
        "source_reason": "theme_signal",
    }
    item = {
        "source": "grounding",
        "title": "AgentFence launches AI agent permission firewall",
        "url": "https://agentfence.dev",
        "snippet": "AgentFence helps security teams control AI agent tool permissions.",
        "company_name": "AgentFence",
        "domain": "agentfence.dev",
    }

    lead = verify_discovery_item(item, query)

    assert lead.verification_status == "accepted"
    assert lead.name == "AgentFence"
    assert lead.domain == "agentfence.dev"
    assert lead.candidate_type == "verified_company"
    assert "official_homepage_domain" in lead.verification_basis
    assert any("movement_terms_present" in item for item in lead.movement_assignment_basis)


def test_classifies_project_marketplace_page_as_evidence_not_identity():
    from radar_company_discovery import classify_discovery_source, verify_discovery_item

    item = {
        "source": "grounding",
        "title": "AERIS-10 Open Source Phased Array Radar - Share Project - PCBWay",
        "url": "https://www.pcbway.com/project/shareproject/AERIS_10_Open_Source_Phased_Array_Radar_61e8cdb0.html",
        "snippet": "AERIS is an open source phased array radar project shared on PCBWay.",
        "company_name": "AERIS",
        "domain": "pcbway.com",
    }

    assert classify_discovery_source(item) == "marketplace_project_page"

    lead = verify_discovery_item(
        item,
        {
            "movement": "Hardware systems",
            "market_sector": "Hardware",
            "required_terms": ["radar", "hardware"],
        },
    )

    assert lead.verification_status == "rejected"
    assert lead.domain == ""
    assert "marketplace_project_page_not_company_domain" in lead.missing_evidence


def test_verify_discovery_item_accepts_official_homepage_domain():
    from radar_company_discovery import verify_discovery_item

    query = {
        "id": "agent-reliability-theme-company-search",
        "movement": "Agent reliability",
        "market_sector": "AI Infra",
        "topic": "Agent reliability startup company founder launch",
        "required_terms": ["agent", "reliability"],
        "source_reason": "theme_signal",
    }
    item = {
        "source": "grounding",
        "title": "Take your AI agents to production, faster.",
        "url": "https://lyzr.ai/",
        "snippet": "Lyzr helps teams deploy reliable AI agents.",
    }

    lead = verify_discovery_item(item, query)

    assert lead.verification_status == "accepted"
    assert lead.domain == "lyzr.ai"
    assert "official_homepage_domain" in lead.verification_basis


def test_verify_discovery_item_rejects_publisher_article_domain_as_company_proof():
    from radar_company_discovery import verify_discovery_item

    query = {
        "id": "ai-agent-security-theme-company-search",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "topic": "AI agent security startup company founder launch",
        "required_terms": ["agent", "security"],
        "source_reason": "theme_signal",
    }
    item = {
        "source": "grounding",
        "title": "General Analysis Raises $10M in Seed Funding to Secure Agentic AI - Las Vegas Sun News",
        "url": "https://lasvegassun.com/news/2026/apr/29/general-analysis-raises-10m-in-seed-funding-to-sec/",
        "snippet": "General Analysis is building agentic AI security tools.",
    }

    lead = verify_discovery_item(item, query)

    assert lead.verification_status == "rejected"
    assert "source_domain_not_company_proof" in lead.missing_evidence
    assert lead.domain == ""


def test_verify_discovery_item_rejects_vibe_match_without_movement_terms():
    from radar_company_discovery import verify_discovery_item

    query = {
        "id": "ai-agent-security-theme-company-search",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "topic": "AI agent security startup company founder launch",
        "required_terms": ["agent", "security"],
        "source_reason": "theme_signal",
    }
    item = {
        "source": "grounding",
        "title": "New devtools company launches",
        "url": "https://generic.dev",
        "snippet": "A generic developer productivity platform.",
        "company_name": "GenericDev",
        "domain": "generic.dev",
    }

    lead = verify_discovery_item(item, query)

    assert lead.verification_status == "rejected"
    assert "movement_terms_missing" in lead.missing_evidence


def test_verify_discovery_item_rejects_single_generic_term_match():
    from radar_company_discovery import verify_discovery_item

    query = {
        "id": "ai-agent-security-theme-company-search",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "topic": "AI agent security startup company founder launch",
        "required_terms": ["ai", "agent", "security"],
        "source_reason": "theme_signal",
    }
    item = {
        "source": "grounding",
        "title": "Security startup launches",
        "url": "https://genericsecurity.dev",
        "snippet": "A security platform for developer teams.",
        "company_name": "GenericSecurity",
        "domain": "genericsecurity.dev",
    }

    lead = verify_discovery_item(item, query)

    assert lead.verification_status == "rejected"
    assert "movement_terms_missing" in lead.missing_evidence


def test_verify_discovery_item_rejects_content_platform_domain():
    from radar_company_discovery import verify_discovery_item

    query = {
        "id": "ai-agent-security-theme-company-search",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "topic": "AI agent security startup company founder launch",
        "required_terms": ["agent", "security"],
        "source_reason": "theme_signal",
    }
    item = {
        "source": "grounding",
        "title": "AgentFence discusses AI agent security",
        "url": "https://medium.com/@agentfence/ai-agent-security",
        "snippet": "AgentFence discusses AI agent security and MCP permissions.",
        "company_name": "AgentFence",
        "domain": "medium.com",
    }

    lead = verify_discovery_item(item, query)

    assert lead.verification_status == "rejected"
    assert "content_platform_not_company_domain" in lead.missing_evidence


def test_verify_discovery_item_rejects_github_only_company_proof():
    from radar_company_discovery import verify_discovery_item

    query = {
        "id": "ai-agent-security-theme-company-search",
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "topic": "AI agent security startup company founder launch",
        "required_terms": ["agent", "security"],
        "source_reason": "needs_more_evidence",
    }
    item = {
        "source": "github",
        "title": "affaan-m/agentshield",
        "url": "https://github.com/affaan-m/agentshield",
        "snippet": "AI agent security scanner for MCP permissions.",
        "company_name": "AgentShield",
        "domain": "cerebralvalley.ai",
    }

    lead = verify_discovery_item(item, query)

    assert lead.verification_status == "rejected"
    assert "github_only_not_company_proof" in lead.missing_evidence


def test_classify_discovery_source_marks_publisher_article():
    from radar_company_discovery import classify_discovery_source

    item = {
        "source": "grounding",
        "title": "Straiker raises seed funding to secure AI agents",
        "url": "https://techcrunch.com/2026/05/01/straiker-raises-seed-funding/",
    }

    assert classify_discovery_source(item) == "publisher_article"


def test_classify_discovery_source_marks_funding_press_release():
    from radar_company_discovery import classify_discovery_source, verify_discovery_item

    item = {
        "source": "grounding",
        "title": "AgentFence raises $8M seed round for AI agent security",
        "url": "https://www.prnewswire.com/news-releases/agentfence-raises-seed-round.html",
        "snippet": "AgentFence raised seed funding to secure AI agent permissions.",
    }
    query = {
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "required_terms": ["ai agent", "security"],
    }

    assert classify_discovery_source(item) == "funding_press_release"
    lead = verify_discovery_item(item, query)
    assert lead.verification_status == "rejected"
    assert lead.source_type == "funding_press_release"
    assert "funding_press_release_not_company_domain" in lead.missing_evidence
    assert lead.supporting_evidence_urls == [item["url"]]


def test_classify_discovery_source_marks_investor_page_as_supporting_evidence():
    from radar_company_discovery import classify_discovery_source, verify_discovery_item

    item = {
        "source": "grounding",
        "title": "AgentFence | Portfolio",
        "url": "https://www.sequoiacap.com/companies/agentfence/",
        "snippet": "AgentFence secures AI agent permissions.",
    }
    query = {
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "required_terms": ["ai agent", "security"],
    }

    assert classify_discovery_source(item) == "investor_page"
    lead = verify_discovery_item(item, query)
    assert lead.verification_status == "rejected"
    assert "investor_page_not_company_domain" in lead.missing_evidence
    assert lead.supporting_evidence_urls == [item["url"]]


def test_classify_discovery_source_marks_government_or_academic_page():
    from radar_company_discovery import classify_discovery_source, verify_discovery_item

    item = {
        "source": "grounding",
        "title": "AI Agent Security Guidance",
        "url": "https://www.cisa.gov/resources-tools/resources/ai-agent-security",
        "snippet": "Security guidance for AI agents and tool permissions.",
    }
    query = {
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "required_terms": ["ai agent", "security"],
    }

    assert classify_discovery_source(item) == "government_or_academic"
    lead = verify_discovery_item(item, query)
    assert lead.verification_status == "rejected"
    assert "government_or_academic_not_company_domain" in lead.missing_evidence


def test_classify_discovery_source_marks_listicle_or_seo_page():
    from radar_company_discovery import classify_discovery_source, verify_discovery_item

    item = {
        "source": "grounding",
        "title": "Top 10 AI agent security startups to watch",
        "url": "https://example-seo.com/blog/top-ai-agent-security-startups",
        "snippet": "A list of companies building AI agent security products.",
    }
    query = {
        "movement": "AI agent security",
        "market_sector": "Cybersecurity",
        "required_terms": ["ai agent", "security"],
    }

    assert classify_discovery_source(item) == "listicle_or_seo"
    lead = verify_discovery_item(item, query)
    assert lead.verification_status == "rejected"
    assert "listicle_or_seo_not_company_domain" in lead.missing_evidence
    assert lead.supporting_evidence_urls == [item["url"]]


def test_extract_company_from_publisher_article_clear_pattern():
    from radar_company_discovery import extract_company_from_publisher_article

    extracted = extract_company_from_publisher_article(
        {
            "title": "Straiker raises $21M to secure AI agents",
            "snippet": "Straiker, a startup building runtime security for AI agents, raised seed funding.",
        }
    )

    assert extracted["company_name"] == "Straiker"
    assert extracted["confidence"] == "High"
    assert "raises_pattern" in extracted["basis"]


def test_extract_company_from_generic_article_returns_none():
    from radar_company_discovery import extract_company_from_publisher_article

    assert extract_company_from_publisher_article({
        "title": "AI startups are booming in enterprise security",
        "snippet": "A broad market overview of agentic AI security.",
    }) is None


def test_parse_publisher_article_detail_keeps_compact_metadata_paragraphs_and_links():
    from radar_company_discovery import parse_publisher_article_detail

    html = """
    <html>
      <head>
        <title>Meet the AI security startup challenging incumbents</title>
        <meta name="description" content="Straiker is building runtime security for AI agents.">
        <script type="application/ld+json">
          {"headline": "Straiker raises seed funding", "description": "Straiker, a startup securing AI agents, raised seed funding."}
        </script>
      </head>
      <body>
        <p>Advertisement</p>
        <p>Straiker, a startup building runtime security for AI agents, raised seed funding this week.</p>
        <p>The company helps enterprises monitor agent permissions and tool use.</p>
        <a href="https://straiker.ai/">Straiker website</a>
      </body>
    </html>
    """

    detail = parse_publisher_article_detail(html, "https://techcrunch.com/story")

    assert detail["title"] == "Meet the AI security startup challenging incumbents"
    assert detail["description"] == "Straiker is building runtime security for AI agents."
    assert detail["paragraphs"] == [
        "Straiker, a startup building runtime security for AI agents, raised seed funding this week.",
        "The company helps enterprises monitor agent permissions and tool use.",
    ]
    assert detail["outbound_links"] == [{"url": "https://straiker.ai/", "text": "Straiker website"}]
    assert any("Straiker raises seed funding" in text for text in detail["structured_texts"])


def test_extract_company_from_publisher_article_detail_body():
    from radar_company_discovery import extract_company_from_publisher_article

    extracted = extract_company_from_publisher_article({
        "title": "Meet the $250M startup challenging Salesforce with AI agents",
        "snippet": "The company is chasing AI workflow automation.",
        "article_detail": {
            "paragraphs": [
                "Straiker, a startup building runtime security for AI agents, raised seed funding this week.",
            ],
            "structured_texts": [],
        },
    })

    assert extracted["company_name"] == "Straiker"
    assert extracted["confidence"] == "Medium"
    assert "startup_apposition_pattern" in extracted["basis"]


def test_vague_publisher_article_detail_extracts_nothing():
    from radar_company_discovery import extract_company_from_publisher_article

    extracted = extract_company_from_publisher_article({
        "title": "AI startups are booming in enterprise security",
        "snippet": "A broad market overview of agentic AI security.",
        "article_detail": {
            "paragraphs": [
                "Investors are increasingly watching companies building agentic AI security tools.",
                "The category remains early and fragmented.",
            ]
        },
    })

    assert extracted is None


def test_collect_company_discovery_verifies_article_company_with_exact_query():
    from radar_company_discovery import collect_company_discovery

    calls = []

    def fake_query(topic, **kwargs):
        calls.append(topic)
        if topic == '"Straiker" "AI agent security" official':
            assert topic == '"Straiker" "AI agent security" official'
            return {
                "items": [
                    {
                        "source": "grounding",
                        "title": "Straiker | AI Security Platform",
                        "url": "https://www.straiker.ai/",
                        "snippet": "Straiker secures AI agents and agentic workflows for enterprises.",
                    }
                ],
                "warnings": [],
            }
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "Straiker raises $21M to secure AI agents - TechCrunch",
                    "url": "https://techcrunch.com/2026/05/01/straiker-raises-ai-agent-security/",
                    "snippet": "Straiker, a startup building runtime security for AI agents, raised seed funding.",
                }
            ],
            "warnings": [],
        }

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
    )

    assert calls == [
        "AI agent security startup company platform official Cybersecurity",
        '"Straiker" "AI agent security" official',
        '"Straiker" funding valuation acquisition Series C',
    ]
    assert result["summary"]["accepted"] == 1
    assert result["summary"]["verification_queries_run"] == 1
    lead = result["accepted_leads"][0]
    assert lead["name"] == "Straiker"
    assert lead["domain"] == "straiker.ai"
    assert lead["source_type"] == "publisher_article"
    assert lead["extracted_company_name"] == "Straiker"
    assert lead["supporting_evidence_urls"] == ["https://techcrunch.com/2026/05/01/straiker-raises-ai-agent-security/"]
    assert "publisher_article_company_extracted" in lead["verification_basis"]
    assert "official_domain_verified" in lead["verification_basis"]


def test_collect_company_discovery_uses_article_detail_before_exact_verification():
    from radar_company_discovery import collect_company_discovery

    calls = []
    fetched = []

    def fake_query(topic, **kwargs):
        calls.append(topic)
        if topic == '"Straiker" "AI agent security" official':
            assert topic == '"Straiker" "AI agent security" official'
            return {
                "items": [
                    {
                        "source": "grounding",
                        "title": "Straiker | AI Security Platform",
                        "url": "https://www.straiker.ai/",
                        "snippet": "Straiker secures AI agents and runtime permissions for enterprises.",
                    }
                ],
                "warnings": [],
            }
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "Meet the $250M startup challenging Salesforce with AI agents - Forbes",
                    "url": "https://www.forbes.com/sites/example/straiker-ai-agents/",
                    "snippet": "The company is building in AI workflow automation.",
                }
            ],
            "warnings": [],
        }

    def fake_article_fetcher(url):
        fetched.append(url)
        return """
        <html><body>
          <p>Straiker, a startup building runtime security for AI agents, raised seed funding this week.</p>
        </body></html>
        """

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        article_fetcher=fake_article_fetcher,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
    )

    assert fetched == ["https://www.forbes.com/sites/example/straiker-ai-agents/"]
    assert calls == [
        "AI agent security startup company platform official Cybersecurity",
        '"Straiker" "AI agent security" official',
        '"Straiker" funding valuation acquisition Series C',
    ]
    assert result["summary"]["article_fetches_attempted"] == 1
    assert result["summary"]["verification_queries_run"] == 1
    lead = result["accepted_leads"][0]
    assert lead["name"] == "Straiker"
    assert lead["domain"] == "straiker.ai"
    assert lead["supporting_evidence_urls"] == ["https://www.forbes.com/sites/example/straiker-ai-agents/"]


def test_article_detail_company_without_verified_domain_is_rejected():
    from radar_company_discovery import collect_company_discovery

    def fake_query(topic, **kwargs):
        if topic == '"Straiker" "AI agent security" official':
            return {
                "items": [
                    {
                        "source": "grounding",
                        "title": "Straiker coverage - TechCrunch",
                        "url": "https://techcrunch.com/straiker",
                        "snippet": "Straiker discusses AI agent security.",
                    }
                ],
                "warnings": [],
            }
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "Meet the startup challenging Salesforce with AI agents - Forbes",
                    "url": "https://www.forbes.com/sites/example/straiker-ai-agents/",
                    "snippet": "The company is building in AI workflow automation.",
                }
            ],
            "warnings": [],
        }

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        article_fetcher=lambda url: "<p>Straiker, a startup building runtime security for AI agents, raised seed funding.</p>",
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
    )

    assert result["summary"]["accepted"] == 0
    rejected = result["rejected_leads"][0]
    assert rejected["name"] == "Straiker"
    assert "official_company_domain_not_verified" in rejected["missing_evidence"]


def test_article_company_verification_rejects_unknown_article_url_as_official_domain():
    from radar_company_discovery import collect_company_discovery

    def fake_query(topic, **kwargs):
        if topic == '"Capsule Security" "AI agent security" official':
            return {
                "items": [
                    {
                        "source": "grounding",
                        "title": "Capsule Security Raises $7 Million Seed for AI Agent Security",
                        "url": "https://ittech-pulse.com/news/capsule-security-raises-7-million-seed-for-ai-agent-security/",
                        "snippet": "Capsule Security exited stealth with seed funding for AI agent security.",
                    }
                ],
                "warnings": [],
            }
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "Capsule Security emerges from stealth with $7M seed - Calcalist",
                    "url": "https://www.calcalistech.com/ctechnews/article/rk900cethzg",
                    "snippet": "Capsule Security, a cybersecurity startup focused on AI agents, raised seed funding.",
                }
            ],
            "warnings": [],
        }

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
    )

    assert result["summary"]["accepted"] == 0
    assert result["summary"]["rejected"] == 1
    rejected = result["rejected_leads"][0]
    assert rejected["name"] == "Capsule Security"
    assert "official_company_domain_not_verified" in rejected["missing_evidence"]


def test_publisher_article_without_verified_domain_is_rejected_cleanly():
    from radar_company_discovery import collect_company_discovery

    def fake_query(topic, **kwargs):
        if topic == '"Straiker" "AI agent security" official':
            return {
                "items": [
                    {
                        "source": "grounding",
                        "title": "Straiker raises seed - PR Newswire",
                        "url": "https://www.prnewswire.com/news/straiker",
                        "snippet": "Straiker discusses AI agent security.",
                    }
                ],
                "warnings": [],
            }
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "Straiker raises $21M to secure AI agents - TechCrunch",
                    "url": "https://techcrunch.com/2026/05/01/straiker-raises-ai-agent-security/",
                    "snippet": "Straiker, a startup building runtime security for AI agents, raised seed funding.",
                }
            ],
            "warnings": [],
        }

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
    )

    assert result["summary"]["accepted"] == 0
    assert result["summary"]["rejected"] == 1
    rejected = result["rejected_leads"][0]
    assert rejected["name"] == "Straiker"
    assert rejected["source_type"] == "publisher_article"
    assert "official_company_domain_not_verified" in rejected["missing_evidence"]


def test_acquisition_article_is_marked_likely_too_late():
    from radar_company_discovery import collect_company_discovery

    def fake_query(topic, **kwargs):
        if topic == '"AgentSecure" "AI agent security" official':
            return {
                "items": [
                    {
                        "source": "grounding",
                        "title": "AgentSecure | AI Agent Security",
                        "url": "https://agentsecure.ai/",
                        "snippet": "AgentSecure protects AI agent permissions and runtime security.",
                    }
                ],
                "warnings": [],
            }
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "Cisco acquires AgentSecure to protect AI agents - TechCrunch",
                    "url": "https://techcrunch.com/2026/05/01/cisco-acquires-agentsecure/",
                    "snippet": "Cisco acquires AgentSecure, a startup building AI agent security.",
                }
            ],
            "warnings": [],
        }

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
    )

    assert result["summary"]["accepted"] == 1
    lead = result["accepted_leads"][0]
    item = result["items"][0]
    assert lead["name"] == "AgentSecure"
    assert lead["likely_too_late"] is True
    assert lead["maturity_status"] == "acquired"
    assert lead["lead_route"] == "monitor_only"
    assert item["likely_too_late"] is True
    assert item["action"] == "monitor only"


def test_collect_company_discovery_routes_n8n_series_c_as_category_context():
    from radar_company_discovery import collect_company_discovery
    from radar_models import ThemeSignal

    calls = []

    def fake_query(topic, **kwargs):
        calls.append(topic)
        if "funding valuation acquisition Series C" in topic:
            assert topic == '"n8n" funding valuation acquisition Series C'
            return {
                "items": [
                    {
                        "source": "grounding",
                        "title": "n8n raises $180m to get AI closer to value with orchestration",
                        "url": "https://blog.n8n.io/series-c/",
                        "snippet": "n8n raised $180 million in Series C funding at a $2.5 billion valuation.",
                    }
                ],
                "warnings": [],
            }
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "n8n.io - AI workflow automation platform",
                    "url": "https://n8n.io/",
                    "snippet": "AI workflow automation for technical teams.",
                }
            ],
            "warnings": [],
        }

    result = collect_company_discovery(
        [
            ThemeSignal(
                market_sector="Devtools",
                theme="Devtools workflow automation",
                evidence_count=3,
                suggested_search="Devtools workflow automation startup company founder launch Devtools",
                confidence="Medium",
            )
        ],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
    )

    assert calls == [
        "Devtools workflow automation startup company platform official Devtools",
        '"n8n" funding valuation acquisition Series C',
    ]
    lead = result["accepted_leads"][0]
    item = result["items"][0]
    assert lead["maturity_status"] == "likely_too_late"
    assert "series_c_or_later" in lead["maturity_basis"]
    assert "large_round_or_valuation" in lead["maturity_basis"]
    assert lead["maturity_evidence_urls"] == ["https://blog.n8n.io/series-c/"]
    assert lead["category_anchor"] is True
    assert lead["lead_route"] == "category_context"
    assert item["lead_route"] == "category_context"
    assert item["action"] == "monitor only"


def test_maturity_lookup_uses_clean_company_name_not_page_title():
    from radar_company_discovery import _maturity_lookup_name, _maturity_query_for_lead
    from radar_models import VerifiedCompanyDiscoveryLead

    n8n = VerifiedCompanyDiscoveryLead(
        name="n8n.io - AI workflow automation platform",
        movement="Devtools workflow automation",
        market_sector="Devtools",
        source_url="https://n8n.io/",
        domain="n8n.io",
    )
    owasp = VerifiedCompanyDiscoveryLead(
        name="Home - OWASP Gen AI Security Project",
        movement="AI agent security",
        market_sector="Cybersecurity",
        source_url="https://genai.owasp.org/",
        domain="genai.owasp.org",
    )
    entro = VerifiedCompanyDiscoveryLead(
        name="Agentic AI & Non-Human Identity Security Platform | Entro Security",
        movement="AI agent security",
        market_sector="Cybersecurity",
        source_url="https://entro.security/",
        domain="entro.security",
    )
    seven_ai = VerifiedCompanyDiscoveryLead(
        name="AI SOC Agents & Agentic Security Platform | 7AI",
        movement="AI agent security",
        market_sector="Cybersecurity",
        source_url="https://7ai.com/",
        domain="7ai.com",
    )

    assert _maturity_lookup_name(n8n) == "n8n"
    assert _maturity_query_for_lead(n8n) == '"n8n" funding valuation acquisition Series C'
    assert _maturity_lookup_name(owasp) == "OWASP Gen AI Security Project"
    assert _maturity_query_for_lead(owasp) == '"OWASP Gen AI Security Project" funding valuation acquisition Series C'
    assert _maturity_lookup_name(entro) == "Entro Security"
    assert _maturity_query_for_lead(entro) == '"Entro Security" funding valuation acquisition Series C'
    assert _maturity_lookup_name(seven_ai) == "7AI"
    assert _maturity_query_for_lead(seven_ai) == '"7AI" funding valuation acquisition Series C'


def test_collect_company_discovery_keeps_seed_company_as_sourcing_candidate():
    from radar_company_discovery import collect_company_discovery

    def fake_query(topic, **kwargs):
        if "funding valuation acquisition Series C" in topic:
            return {
                "items": [
                    {
                        "source": "grounding",
                        "title": "AgentFence raises $7M seed round for AI agent security",
                        "url": "https://agentfence.dev/blog/seed",
                        "snippet": "AgentFence raised seed funding to secure AI agent permissions.",
                    }
                ],
                "warnings": [],
            }
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "AgentFence launches AI agent permission firewall",
                    "url": "https://agentfence.dev/",
                    "snippet": "AgentFence helps security teams control AI agent tool permissions.",
                    "company_name": "AgentFence",
                    "domain": "agentfence.dev",
                }
            ],
            "warnings": [],
        }

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
    )

    lead = result["accepted_leads"][0]
    assert lead["maturity_status"] == "seed_to_series_b"
    assert lead["lead_route"] == "sourcing_candidate"
    assert lead["category_anchor"] is False


def test_maturity_classification_ignores_unrelated_large_round_in_listicle():
    from radar_company_discovery import _classify_maturity_from_items

    maturity = _classify_maturity_from_items(
        [
            {
                "title": "Copperhelm Emerges from Stealth with $7M Seed Funding",
                "url": "https://www.prnewswire.com/news-releases/copperhelm-emerges-from-stealth.html",
                "snippet": "Copperhelm announced $7 million in seed funding for agentic cloud security.",
            },
            {
                "title": "Full list of Israeli high-tech funding rounds in 2026",
                "url": "https://www.calcalistech.com/ctechnews/article/rq8lzbs4c",
                "snippet": "Food delivery startup Haat raises $20 million at $100 million valuation.",
            },
        ],
        company_name="Copperhelm",
        domain="copperhelm.com",
    )

    assert maturity["maturity_status"] == "seed_to_series_b"
    assert maturity["lead_route"] == "sourcing_candidate"
    assert "large_round_or_valuation" not in maturity["maturity_basis"]


def test_collect_company_discovery_unknown_maturity_routes_research_deeper():
    from radar_company_discovery import collect_company_discovery

    def fake_query(topic, **kwargs):
        if "funding valuation acquisition Series C" in topic:
            return {"items": [], "warnings": []}
        return {
            "items": [
                {
                    "source": "grounding",
                    "title": "AgentFence launches AI agent permission firewall",
                    "url": "https://agentfence.dev/",
                    "snippet": "AgentFence helps security teams control AI agent tool permissions.",
                    "company_name": "AgentFence",
                    "domain": "agentfence.dev",
                }
            ],
            "warnings": [],
        }

    result = collect_company_discovery(
        [_theme_signal()],
        query_runner=fake_query,
        grounded_available=True,
        social_available=False,
        max_queries_per_theme=1,
    )

    lead = result["accepted_leads"][0]
    assert lead["maturity_status"] == "unknown"
    assert lead["lead_route"] == "research_deeper"
    assert lead["category_anchor"] is False


def test_discovery_yield_trial_generates_only_selected_families():
    from radar_company_discovery import DiscoveryYieldTrialConfig, build_company_discovery_queries
    from radar_models import ThemeSignal

    queries = build_company_discovery_queries(
        [
            ThemeSignal(
                market_sector="AI Infra",
                theme="Agent reliability and evals",
                evidence_count=4,
                confidence="Medium",
            )
        ],
        grounded_available=True,
        social_available=False,
        trial_config=DiscoveryYieldTrialConfig(enabled=True),
    )

    families = {query["query_family"] for query in queries}
    assert families <= {"official_company_page", "founder_company_pages", "movement_platform"}
    assert {"official_company_page", "founder_company_pages", "movement_platform"} <= families
    assert all(query["discovery_lane"] == "discovery_yield_trial" for query in queries)
    assert all(query["candidate_eligible"] is True for query in queries)


def test_discovery_yield_trial_excludes_unproven_families():
    from radar_company_discovery import DiscoveryYieldTrialConfig, build_company_discovery_queries
    from radar_models import ThemeSignal

    queries = build_company_discovery_queries(
        [
            ThemeSignal(
                market_sector="AI Infra",
                theme="Agent reliability and evals",
                evidence_count=4,
                confidence="Medium",
            )
        ],
        grounded_available=True,
        social_available=False,
        trial_config=DiscoveryYieldTrialConfig(enabled=True),
    )

    families = {query["query_family"] for query in queries}
    assert "seed_funding" not in families
    assert "launch_stealth" not in families
    assert "yc_company_pages" not in families
    assert "movement_startup" not in families
    assert "company_context" not in families


def test_discovery_yield_trial_generates_from_focus_movements_without_theme_signals():
    from radar_company_discovery import DiscoveryYieldTrialConfig, build_company_discovery_queries
    from radar_models import FocusItem

    focus = FocusItem(
        id="agent-evals-row",
        name="Agent evals row",
        market_movement="Agent reliability and evals",
        market_sector="AI Infra",
        missing_evidence=["no verified domain", "no founder or maintainer identity"],
        evidence_urls=["https://example.com/agent-evals"],
        recommended_action="Research deeper",
        noise_risk_score=30,
        why_focus_this_week="Agent reliability teams are searching for eval tooling.",
    )

    queries = build_company_discovery_queries(
        [],
        focus_items=[focus],
        grounded_available=True,
        social_available=False,
        trial_config=DiscoveryYieldTrialConfig(enabled=True),
    )

    trial_queries = [query for query in queries if query.get("discovery_lane") == "discovery_yield_trial"]
    assert trial_queries
    assert {query["query_family"] for query in trial_queries} == {
        "official_company_page",
        "founder_company_pages",
        "movement_platform",
    }
    assert all(query["origin_row_ids"] == ["agent-evals-row"] for query in trial_queries)


def test_discovery_yield_trial_caps_movement_platform_per_movement():
    from radar_company_discovery import DiscoveryYieldTrialConfig, build_company_discovery_queries
    from radar_models import ThemeSignal

    queries = build_company_discovery_queries(
        [
            ThemeSignal(market_sector="AI Infra", theme="Agent reliability and evals"),
            ThemeSignal(market_sector="AI Infra", theme="AI agent reliability"),
        ],
        grounded_available=True,
        social_available=False,
        trial_config=DiscoveryYieldTrialConfig(enabled=True, movement_platform_cap_per_movement=1),
    )

    movement_platform_queries = [query for query in queries if query["query_family"] == "movement_platform"]
    counts = {}
    for query in movement_platform_queries:
        counts[query["movement"]] = counts.get(query["movement"], 0) + 1
    assert all(count == 1 for count in counts.values())


def test_collect_company_discovery_records_discovery_yield_trial_metrics():
    from radar_company_discovery import DiscoveryRunBudget, DiscoveryYieldTrialConfig, collect_company_discovery
    from radar_models import ThemeSignal

    def fake_query_runner(topic, **kwargs):
        if "platform company official" in topic:
            return {
                "items": [
                    {
                        "source": "grounding",
                        "title": "LangWatch - AI evals platform",
                        "url": "https://langwatch.ai/",
                        "snippet": "LangWatch helps AI teams evaluate agents and monitor LLM apps.",
                        "company_name": "LangWatch",
                        "domain": "langwatch.ai",
                    }
                ],
                "warnings": [],
            }
        return {"items": [], "warnings": []}

    result = collect_company_discovery(
        [ThemeSignal(market_sector="AI Infra", theme="Agent reliability and evals", evidence_count=4)],
        query_runner=fake_query_runner,
        grounded_available=True,
        social_available=False,
        run_budget=DiscoveryRunBudget.for_mode(
            "smoke",
            max_company_discovery_queries=3,
            max_maturity_queries=0,
            per_movement_query_cap=3,
        ),
        trial_config=DiscoveryYieldTrialConfig(enabled=True),
    )

    trial = result["discovery_yield_trial"]
    assert trial["enabled"] is True
    assert trial["families_run"]["movement_platform"]["queries_run"] >= 1
    assert trial["verified_domains"] >= 1
    assert "langwatch.ai" in trial["verified_domain_list"]
    assert result["accepted_leads"][0]["discovery_lane"] == "discovery_yield_trial"
