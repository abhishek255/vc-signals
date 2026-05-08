from __future__ import annotations


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
        max_queries_per_theme=3,
    )

    assert [query["kind"] for query in queries] == [
        "theme_company_search",
        "theme_founder_search",
        "theme_funding_search",
    ]
    assert queries[0]["market_sector"] == "Cybersecurity"
    assert queries[0]["theme"] == "AI agent security"
    assert queries[0]["movement"] == "AI agent security"
    assert queries[0]["source_reason"] == "theme_signal"
    assert queries[0]["candidate_eligible"] is True
    assert queries[0]["sources"] == "grounding"
    assert "AI agent security startups Seed Series A founder launch" in queries[0]["topic"]
    assert "founder" in queries[1]["topic"].lower()
    assert "raises" in queries[2]["topic"].lower()


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

    assert len(seen_topics) == 1
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
    assert "source_backed_domain" in lead.verification_basis
    assert any("movement_terms_present" in item for item in lead.movement_assignment_basis)


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
