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
