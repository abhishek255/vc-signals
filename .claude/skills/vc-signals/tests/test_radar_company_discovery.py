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
    assert "official_homepage_domain" in lead.verification_basis
    assert any("movement_terms_present" in item for item in lead.movement_assignment_basis)


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


def test_collect_company_discovery_verifies_article_company_with_exact_query():
    from radar_company_discovery import collect_company_discovery

    calls = []

    def fake_query(topic, **kwargs):
        calls.append(topic)
        if "official" in topic:
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
        "AI agent security startups Seed Series A founder launch",
        '"Straiker" "AI agent security" official',
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


def test_publisher_article_without_verified_domain_is_rejected_cleanly():
    from radar_company_discovery import collect_company_discovery

    def fake_query(topic, **kwargs):
        if "official" in topic:
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
        if "official" in topic:
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
    assert item["likely_too_late"] is True
    assert item["action"] == "likely too late"
